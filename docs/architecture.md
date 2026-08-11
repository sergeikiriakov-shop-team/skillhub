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

## Task Review + self-review (`skillhub_core/reviews`)

Two halves of one context, both carrying a **pointer** to the work — the code stays in git.

- **Task review (peer).** A developer submits a deploy-ready task (`task_ref`, branch, commit SHAs,
  changed files, summary, verification notes); the lead fetches the branch, reviews the real diff and
  posts a verdict. State machine: `submitted → approved | changes_requested → (resubmit) submitted
  … → done` (author `ack`). Every transition appends to an immutable thread (`review_events`). The
  lead is the single `is_reviewer` user, auto-assigned at submit; in **open-review** mode (default)
  any authenticated user may post a verdict.
- **Self-review (own change, team's skill).** *Which* skill reviews a developer's own diff is a
  server setting, exactly like the rubric weights: `self_review_policies` maps a lane
  (`default | backend | frontend`) to a catalog skill, plus a `required` flag. Claude Code reads it
  (`GET /api/self-reviews/policy` / MCP `get_self_review_policy`), fetches that SKILL.md with
  `get_skill`, applies it to the diff, and posts findings back (`POST /api/self-reviews`). The result
  (`self_reviews`: verdict + `findings[]` with severity/file/line/detail/suggestion) attaches to the
  author's peer review of the same task — on submit, any unattached self-review for that `task_ref`
  is picked up — and appears in its thread as a `self_review` event. With any lane marked `required`,
  submitting a task to the lead without a self-review is rejected (409).

  The verdict is derived server-side when the client omits it: any `blocker`/`major` finding →
  `changes_needed`, otherwise `pass`. Same split as everywhere else in SkillHub — the *strategy*
  lives in the service, the *reviewing* happens in the developer's own Claude Code.

  **Deletion.** Who may remove what is a domain rule on the aggregates. A *self-review* is the
  author's own account of their own change, so its author (or an admin) may delete it at any time;
  its fixes go with it and so does its entry in a peer review's thread — a line pointing at findings
  nobody can open is worse than no line, which the FK's `SET NULL` alone would have left. A *peer
  review* is different: the author may withdraw it only while it is still awaiting a verdict, after
  which only an admin may, because an author who could delete a `changes_requested` review could
  erase the request and resubmit as if it never happened. Withdrawing a review keeps the
  self-reviews attached to it — they existed before the handover, so they detach and return to the
  standalone list.

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

`reviews 1─* review_events`, `reviews 1─* self_reviews` (nullable FK: a self-review exists before,
and outlives, the peer review), `self_reviews *─1 skills` (the reviewing skill, with `skill_name`
kept as a snapshot so the record survives a rename/delete), `self_review_policies` keyed by lane.

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
