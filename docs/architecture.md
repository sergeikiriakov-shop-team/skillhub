# SkillHub architecture

## Purpose

Collect Claude Code skills (`SKILL.md`) from the team into one registry, score their quality
with Claude, categorize them, find overlaps, and later recommend the right skill for a task and
synthesize an "ideal" merged skill.

## Components

```
┌─────────────────────┐     HTTP /api      ┌──────────────────────────────┐
│ web (React/Mantine) │ ─────────────────▶ │ api (FastAPI)                │
│  nginx + SPA        │                    │  routers: skills, evaluations│
└─────────────────────┘                    │           categories, search │
                                           │  BackgroundTasks → pipeline  │
                                           └───────────────┬──────────────┘
                                                           │ imports
                                                           ▼
                                           ┌──────────────────────────────┐
                                           │ skillhub_core (shared lib)   │
                                           │  parsing · embeddings · llm  │
                                           │  repository · pipeline       │
                                           └───────────────┬──────────────┘
                                                           │ SQLAlchemy 2.0
                                                           ▼
                                           ┌──────────────────────────────┐
                                           │ db: Postgres 16 + pgvector   │
                                           └──────────────────────────────┘

  Claude Code (each dev)  ── HTTP /api ─▶ api    # evaluates skills, submits results back
```

## Key decisions

- **Claude Code is canonical.** The internal model is `name` + `description` + body + references.
  Other formats (Cursor `.mdc`, Codex, Copilot) are handled by parser dispatch in
  `parsing.py` and export functions in `adapters.py`. `SkillVersion.source_format` records origin.
- **One shared library.** `skillhub_core` holds all business logic; `api` and (future) batch
  jobs import it. No logic is duplicated.
- **Claude Code is the evaluator, not the service.** The service stores skills + the shared
  rubric (`/api/rubric`) and never calls an LLM. Each developer's Claude Code fetches the rubric,
  scores skills, and POSTs results back (`/api/skills/{id}/assessment`), so everyone runs the one
  identical algorithm. (No LangChain / Anthropic API key in the service.)
- **Local embeddings.** `sentence-transformers/all-MiniLM-L6-v2` (384-dim) avoids an extra API
  key and works offline after the first model download. Fail-soft: no model → no vector, the
  rest still works.
- **SkillHub is its own authorization server; the OAuth provider is only identity.** Reads are
  public by default, or gated behind login via `SKILLHUB_PUBLIC_READS=false` (a `require_read_access`
  dependency on the data routers; `/api/health` + `/api/auth/*` + `/api/oauth/*` + the well-known
  metadata stay open). Humans log in with **GitHub** (auth-code flow → opaque `skillhub_session`
  cookie). The MCP is a **remote HTTP server** (the `mcp` service, behind nginx at `/mcp`) and uses
  standard **MCP OAuth**: SkillHub is a full OAuth 2.1 **authorization server** (`routers/oauth.py`:
  Dynamic Client Registration + authorization-code/PKCE + refresh, reusing the GitHub browser login
  for identity) and the MCP endpoint is the **resource server** (validates the bearer, serves
  protected-resource metadata). A legacy stdio MCP + RFC 8628 device grant remains as a fallback.
  All surfaces share one `auth_tokens` table and `get_user_by_token` (which accepts only
  access-capable kinds, never a refresh token); `current_user_optional` accepts bearer or cookie.
  Roles (`viewer→contributor→evaluator→admin`) are a SkillHub concept the provider never carries.
  The provider is deliberately isolated to `/login` + `/callback` and the `(auth_provider,
  provider_sub)` identity columns, so swapping it (GitHub↔Google↔…) is a localized change.

## Bounded contexts (`skillhub_core`)

`platform` (users, auth, tokens, DB bootstrap) · `skills` (the catalog, rubric, evaluations,
recommendations, sandbox trials) · `reviews` (task review + self-review) · `mcp` (catalogued MCP
servers). The API composes them through a `dependency-injector` container
(`services/api/app/container.py`) and thin routers that only map domain errors to HTTP.

**Every context has the same shape — a package per layer, a module per aggregate:**

```
<context>/
  models/        aggregates + their rules (transitions, invariants, derived values)
  schemas/       Pydantic DTOs (the API/MCP surface)
  serializers/   ORM aggregate → DTO
  repositories/  SQLAlchemy persistence — queries and writes, nothing else
  interfaces/    repository Protocols (the seam services depend on)
  services/      application services: orchestration, transaction boundary, cross-aggregate rules
  errors.py      domain errors, mapped to HTTP in the routers
```

Two rules keep this honest rather than decorative:

- **Rules live on the aggregate, not in the repository.** `Review.decide()` refuses an illegal
  transition and appends to the thread; `SelfReview.record_fix()` enforces that a fix never edits
  the finding; `derive_verdict()` decides what a set of findings means. A repository that also
  decided these things is how two callers end up with two different answers.
- **A rule spanning two aggregates belongs to an application service.** "No handover to the lead
  without a self-review when the policy demands one" lives in `ReviewService`, which reads the
  policy repository — not in a repository reaching sideways into another aggregate.

Dependencies inside a context point one way. In `skills`, `catalog` (the read-model over
taxonomy/stats/task-groups) may use the per-aggregate modules; none of them uses `catalog`.

## Review (`skillhub_core/reviews`)

**One flow, two aggregates.** The developer reviews their own change with the skill the team
configured; that run is what puts the task on the board; the lead signs it off. There is no separate
hand-over step and no second reviewer re-running the diff — a review nobody performs twice is the
whole point. Both aggregates carry a **pointer** to the work; the code stays in git.

- **Self-review run (`self_reviews`) — the reviewing.** *Which* skill reviews a developer's own diff
  is a server setting, exactly like the rubric weights: `self_review_policies` maps a lane
  (`default | backend | frontend`) to a catalog skill, plus a `required` flag. Claude Code reads it
  (`GET /api/self-reviews/policy` / MCP `get_self_review_policy`), fetches that SKILL.md with
  `get_skill`, applies it to the diff, and posts findings back (`POST /api/self-reviews`): verdict +
  `findings[]` with severity/file/line/detail/suggestion, plus the fixes recorded afterwards.

  The verdict is derived server-side when the client omits it: any `blocker`/`major` finding →
  `changes_needed`, otherwise `pass`. Same split as everywhere else in SkillHub — the *strategy*
  lives in the service, the *reviewing* happens in the developer's own Claude Code.

- **Task (`task_reviews`) — the board row.** One row per `task_ref`, created by the first run and
  updated by every later one. Its `status` is *derived*, never posted: a run that came back clean
  leaves the task `passed` (the lead's queue), a run with blockers/majors leaves it `changes_needed`
  (back with the author). The lead ends it — `approved` — or returns it with a mandatory
  `lead_comment`, which puts it back to `changes_needed` until the author's next run clears it.
  Status is a fact about the latest run rather than a field anyone sets, so the board cannot claim a
  task is fine while its own review says otherwise.

  Approving is guarded by the same `required` flag: with the lane marked required, a task whose
  latest run is not clean cannot be signed off (409). Requires `is_reviewer` or admin.

  **Deletion.** Who may remove what is a domain rule on the aggregates. A *run* is the author's own
  account of their own change, so its author (or an admin) may delete it at any time; its fixes go
  with it, and the task re-derives its status from what is left (an approval already given stands —
  it was a judgement about the task, not about the row). Deleting the last run leaves nothing to
  show, so the empty task row goes too. A *task* may be withdrawn by its author while it is still
  unapproved; once approved, only an admin may remove it, because an author who could delete a
  returned task could erase the lead's objection and start over as if it never happened.

  **Deep links.** A finding carries `file`/`line`, and the service turns that into a link to the
  line. The repository is recorded **per self-review** (`self_reviews.repo`, normalized from the
  agent's `git remote get-url origin` by `reviews/code_links.py`), not configured per instance —
  the team works in several repos, so a global setting would only ever be right for one of them.
  URLs are built at **read time**, never stored, so re-pointing the shape fixes every existing
  finding at once; they pin to the last reviewed commit rather than the branch, because line
  numbers drift. `SKILLHUB_CODE_LINK_TEMPLATE` overrides the host-derived shape
  (`{repo}`/`{ref}`/`{path}`/`{line}`); with no recorded repo the service falls back to
  `SKILLHUB_ALLOWED_REPO`, which keeps pre-existing runs linkable.

## Ingest pipeline (`skillhub_core/pipeline.py`)

`parse → embed → persist`

- On upload (and on seed import) the API parses the skill, upserts a version (a new version is
  created only when the content hash changes), and embeds it. The service does **not** evaluate
  or categorize — those never touch an LLM here.
- Evaluation, categorization and synthesis are produced by Claude Code and submitted back via
  `POST /api/skills/{id}/assessment`.

## Data model

`skills 1─* skill_versions 1─* evaluations`, `skill_versions 1─1 skill_embeddings`,
`skills *─* categories` (via `skill_categories`, with confidence + source). A new version is
created only when the content hash changes, so re-imports are idempotent.

`task_reviews 1─* self_reviews` (one board row per `task_ref`, one row per run, cascading — a run
without its task has nothing to be a run *of*), `self_reviews 1─* self_review_fixes`,
`self_reviews *─1 skills` (the reviewing skill, with `skill_name` kept as a snapshot so the record
survives a rename/delete), `self_review_policies` keyed by lane.

**Identity + authorship (team registry).** A skill is keyed by **name** (unique `uq_skills_name`);
re-uploading a name adds a version rather than a duplicate row. Verified authorship: `skills` and
`skill_versions` each carry `created_by_user_id → users.id` (the OAuth uploader); `Skill.author` is
a display string only. On ingest (`pipeline.ingest`), an upload under a *new* name that is
content-identical (exact or whitespace-normalized) to an existing skill is rejected
(`DuplicateSkillError` → HTTP 409); a merely-similar one (cosine ≥ 0.90) is allowed with a
`similar_warning`. Genuine variants therefore live under distinct names within a `task_group`.

## Quality rubric (v1)

`clarity`, `trigger_quality`, `completeness`, `reusability`, `safety`, `structure` (0-10 each)
plus a holistic `overall`, with strengths/weaknesses/rationale. Rubric version is stored so
skills can be re-scored and compared when the rubric evolves.

## Roadmap

- **Phase 2:** recommendation (retrieval + Claude rerank), duplicate/overlap clustering,
  version history UI.
- **Phase 3:** synthesize an "ideal" skill from a cluster (`llm/synthesize.py`), export to
  `SKILL.md` / per-client adapters, prepare a PR.
- **Phase 4:** auth, usage telemetry, feedback loop, leaderboards.
