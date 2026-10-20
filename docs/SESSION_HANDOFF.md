# SkillHub — session handoff / resume notes

Read this first to resume cold. SkillHub is a **standalone** service (independent of the
`prologistics` repo) at `C:\Users\Sergei Kiriakov\Documents\skillhub` (git branch `main`).

## Architecture (current)

- **Service = system of record + retrieval + read-only display.** It parses/embeds/stores
  skills, serves them + their evaluations + stats. **It does NOT call an LLM.**
- **Claude Code = the evaluator.** Each developer, from their own Claude Code, imports skills
  and (if allowed) evaluates them, submitting results back over the REST API. The `skillhub`
  Claude Code skill (`skills/skillhub/SKILL.md`) drives this.
- **Auth = GitHub OAuth (humans) + device flow (MCP); SkillHub is its own auth server.** Reads are
  **open by default** but can be closed with `SKILLHUB_PUBLIC_READS=false` (prod is closed — then
  only `/api/health` + `/api/auth/*` stay open, everything else needs a logged-in user via
  `require_read_access`; the SPA shows a login gate and the MCP auto-runs the device flow on the
  first gated read). Humans sign in with GitHub in the browser (`GET /api/auth/login` → callback → opaque
  session cookie `skillhub_session`). The MCP authorizes via the RFC 8628 device grant and caches a
  SkillHub-minted token. All credentials live in `auth_tokens` (kind `session|device|pat`, SHA-256
  only) and resolve through one `get_user_by_token`; `current_user_optional` reads **bearer OR
  cookie**. Roles (ascending) `viewer → contributor → evaluator → admin`; any GitHub account starts
  `viewer`; emails in `SKILLHUB_BOOTSTRAP_ADMINS` become admin on first login. Identity is stored
  provider-agnostically (`users.auth_provider` + `provider_sub`), so the provider is easy to swap —
  only `routers/auth.py` `/login`+`/callback` and `config.py` are provider-specific.
  `SKILLHUB_ADMIN_TOKEN` is a deprecated break-glass. GitHub keys via `GITHUB_CLIENT_ID/SECRET` +
  `SKILLHUB_PUBLIC_URL`; without them the stack runs but browser login is disabled.
- **Frontend = read-only dashboard** (catalog + semantic search + per-skill detail + a stats
  strip + the review board at `/reviews`, where the only editable thing is the admin's self-review
  policy). No upload/evaluate/delete UI — those happen via Claude Code / the API. It is fully
  **bilingual (RU/EN)** via a lightweight home-grown i18n (`services/web/src/i18n.tsx`, toggle in
  the header, choice persisted to localStorage), and has a **Guide** page (`/guide`) with
  developer instructions. Only static UI chrome is translated; API data stays as stored.
- **Install a skill into your Claude Code.** `GET /api/skills/{id}` returns `skill_md` (the ready
  canonical SKILL.md); each skill page shows an "Install into Claude Code" phrase to paste. The
  actual install is done by the user's own Claude Code (via the `skillhub` skill / MCP `get_skill`):
  it writes `skill_md` + `references[]` into `.claude/skills/<name>/` with its own Write tool.
- **One canonical skill per name + verified authorship (team registry).** Skills are keyed by
  `name` (unique index `uq_skills_name`; old `(name,author,origin)` identity dropped). Re-uploading
  a name adds a **version**, not a copy; each version records `created_by_user_id` (the verified
  OAuth uploader), and `Skill.author`/`created_by_user_id` is the original author. An upload under a
  **new** name that is content-identical (exact or whitespace-normalized) to an existing skill is
  **rejected 409**; a merely-similar one (cosine ≥ 0.90) is accepted with a `similar_warning`. The
  client-supplied `author` is ignored while authenticated. Detail API exposes `uploaded_by`,
  `contributors`, `versions`. Dedup logic: `pipeline.ingest` + `repository` (`upsert_skill` by name,
  `find_exact_content_duplicate`, `nearest_other_skills`, `normalize_content`).
- **No LLM in the service, no LangChain.** Embeddings are local (`sentence-transformers`,
  pgvector) for search / duplicate detection. The dormant `skillhub_core/llm/` package and the
  stale `services/airflow/` DAG have been **removed**. Orchestration (scheduled headless
  `claude -p` re-evaluation) is deferred to a later phase.

- **Task review + self-review are their own bounded context** (`skillhub_core/reviews`), and the
  service is DDD-shaped throughout: contexts `platform` / `skills` / `reviews` / `mcp`, each laid
  out the same way — **a package per layer, a module per aggregate**: `models/ · schemas/ ·
  serializers/ · repositories/ · interfaces/ · services/ · errors.py` — wired by a
  `dependency-injector` container (`services/api/app/container.py` + `deps.py`). Routers are thin:
  they only map domain errors to HTTP. Rules live on the aggregates (`TaskReview.approve()`,
  `TaskReview.record_run()`, `SelfReview.record_fix()`, `derive_verdict()`), not in the repositories;
  a rule spanning two aggregates lives in an application service (the required-clean-run gate in
  `TaskReviewService`). Flat facades in each `__init__.py` mean
  `from skillhub_core.<context>.<layer> import X` still works regardless of which module X ended up in.
  - **One flow.** The developer runs the review on their own change; that run puts the task on the
    board; the lead signs it off. No hand-over step, no second reviewer re-running the diff.
  - **Self-review run.** WHICH skill reviews a developer's own diff is an admin-managed server
    setting (`self_review_policies`: lane `default|backend|frontend` → catalog skill, + `required`),
    the same pattern as the rubric weights. Claude Code reads the policy, fetches that SKILL.md via
    `get_skill`, applies it to the diff, and POSTs the findings back. Verdict is server-derived when
    omitted: any `blocker`/`major` → `changes_needed`, else `pass`. Findings deep-link to their line:
    the agent passes `repo` (its `git remote get-url origin`), stored per run because the team spans
    repositories; URLs are derived at read time in `reviews/code_links.py` and pinned to the last
    reviewed commit. Afterwards the author records what each fix closed (a commit = closed, a
    note-only fix = an answer, counted separately) — additive, never editing the original findings.
  - **Task board.** One `task_reviews` row per `task_ref`, created by the first run. Its status is
    DERIVED from the latest run — `changes_needed` (with the author) or `passed` (the lead's queue) —
    never posted. The lead ends it: `approved`, or returned with a mandatory `lead_comment` that puts
    it back to `changes_needed` until the next run clears it. A lane marked `required` makes
    approving an unclean task 409.

## Key API endpoints
- Reads (open when `SKILLHUB_PUBLIC_READS=true`, else require a logged-in user): `GET /api/stats`,
  `/api/skills`, `/api/skills?evaluated=false` (work queue), `/api/skills/{id}`, `/api/search?q=`,
  `/api/categories`, `/api/rubric`, `/api/skills/{id}/evaluations`. `GET /api/health` is always open.
- Review board: `GET /api/task-reviews?status=|mine=`, `GET /api/task-reviews/{id}`,
  `POST /api/task-reviews/{id}/approve` (reviewer), `POST /api/task-reviews/{id}/return` (reviewer,
  comment required), `DELETE /api/task-reviews/{id}` (author while unapproved, admin any).
- Self-review runs: `GET /api/self-reviews/policy`, `PUT /api/self-reviews/policy` (admin),
  `POST /api/self-reviews` (this is what creates/updates the board row),
  `GET /api/self-reviews?mine=|task_ref=|task_review_id=`, `GET /api/self-reviews/{id}`,
  `POST /api/self-reviews/{id}/fixes` (author), `DELETE /api/self-reviews/{id}` (author or admin;
  takes its fixes with it and re-derives the task's status).
- Token/cookie writes: `POST /api/skills` (contributor+), `POST /api/skills/{id}/assessment`
  (evaluator), `DELETE /api/skills/{id}` (admin).
- Auth: `GET /api/auth/login|callback`, `GET /api/auth/me`, `POST /api/auth/logout`,
  `POST /api/auth/device/{code,token,approve}`, `GET/POST/DELETE /api/auth/tokens` (self-service).
- Admin: `GET/POST /api/admin/users`, `POST /api/admin/users/{id}/role` (mark evaluator; 409 on
  your own role), `POST /api/admin/users/{id}/reviewer` (the lead flag). Portal page `/users`
  (admin only, linked from the account menu).
- Auth: `Authorization: Bearer <token>` (MCP/CLI) or the `skillhub_session` cookie (browser).

## Run it (behind the VPN)
Build must use the legacy builder (BuildKit ignores the daemon MTU); see README →
Troubleshooting. Images `skillhub-api`, `skillhub-web`, and `pgvector/pgvector:pg16` are built
locally.
```
docker compose up -d db api web            # base stack (uses built images)
# seed the 8 real prologistics skills (already copied into the api container at /tmp/skills):
docker exec skillhub-api-1 python -m skillhub_core.skills.seed --path /tmp/skills
# rebuild after code changes:
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build
```
- Portal: http://localhost:8080  ·  API docs: http://localhost:8000/docs

## Evaluate via Claude Code (the flow that replaces the LLM-in-service)
Install `skills/skillhub/SKILL.md` into Claude Code (or point it at the repo). Set
`SKILLHUB_URL=http://localhost:8000` and a bearer token for an `evaluator` user. It: fetches
`?evaluated=false`, fetches `/api/rubric`, scores each skill, POSTs `/api/skills/{id}/assessment`.

## Status (verified live)
- Backend: auth (401/403/201 gating), admin user create + role change, assessment submit
  round-trip, `evaluated=false` queue, `/api/stats` — all verified with curl/PowerShell.
- Seeded 8 real skills; embeddings + semantic search work.
- Frontend read-only rebuild: web image rebuilt with the read-only dashboard + stats strip.
- git: `bd1449a` MVP · `797c21b` VPN/MTU build fixes + 204 fix · `76ab4d3` handoff ·
  `<pivot>` store+display + Claude-Code evaluator · `<auth>` multi-user auth + read-only frontend.

## MCP server (done)
`services/mcp/` — a FastMCP+httpx wrapper over the authed REST API, two transports (env
`SKILLHUB_MCP_TRANSPORT`):
- **`http` (prod, default on the server)** — remote streamable-HTTP resource server (compose service
  `mcp`, nginx `/mcp`). Devs connect with `claude mcp add --transport http skillhub <url>/mcp` and
  sign in in the browser via **MCP OAuth** — no Docker/token. SkillHub is the OAuth AS
  (`services/api/app/routers/oauth.py`: DCR + code/PKCE + refresh, reusing the GitHub login); this
  service validates the bearer via `/api/auth/me` and forwards it. **Deployed + verified on prod**
  (metadata, PRM, 401/WWW-Authenticate, register→authorize→token→gated-read, single-use codes,
  refresh≠access).
- **`stdio` (local dev / legacy)** — the old `docker run -i` wrapper; device flow, token cached to a
  volume. Image still publishable to GHCR for anyone mid-transition.

Tools: `list_unevaluated`, `list_skills`, `get_skill`, `search`, `get_rubric`, `get_stats`,
`list_task_groups`, `list_recommendations`, `upload_skill` (contributor+), `submit_assessment`
(evaluator), `add_recommendation`/`set_recommendation_status` (contributor+), `authenticate`;
review board (lead) — `list_review_board`, `get_task_review`, `approve_task_review`,
`return_task_review`, `delete_task_review`; self-review — `get_self_review_policy`,
`submit_self_review`, `list_self_reviews`, `get_self_review`, `record_self_review_fixes`,
`delete_self_review`; users (admin) — `list_users`, `set_user_role`, `set_reviewer`. See
`services/mcp/README.md`.

## Skills shipped with the service (`skills/`)
`skillhub` (evaluate the catalog) · `connect-skillhub` (one-line MCP setup) · `sandbox-eval` ·
`self-review` (developer) · `review-board` (lead, under `/loop`) · `review-status` (developer).

## Next
- **End-to-end trial of the one-flow board on prod**: `self-review` (with the lane pointed at a
  review skill) → the task appears `changes_needed`/`passed` → `record_self_review_fixes` → re-run →
  the lead approves or returns it.
- **Wire `green-loop` to the board**: re-run the self-review once a task is deploy-ready, and again
  after the lead returns it.
- Then: "optimal skills" (synthesis of an ideal skill from a cluster) display + richer stats.
- Later/optional: a scheduler running headless `claude -p` re-evaluation.

## Notes / loose ends
- `services/web/src/pages/Upload.tsx` is now orphaned (no route) — kept, not wired.
- The dormant `skillhub_core/llm/` package and the `services/airflow/` DAG were removed (the
  service does not call an LLM; Claude Code is the evaluator).
