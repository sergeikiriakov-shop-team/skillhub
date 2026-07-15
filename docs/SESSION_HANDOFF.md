# SkillHub — session handoff / resume notes

Read this first to resume cold. SkillHub is a **standalone** service (independent of the
`prologistics` repo) at `C:\Users\Sergei Kiriakov\Documents\skillhub` (git branch `main`).

## Architecture (current)

- **Service = system of record + retrieval + read-only display.** It parses/embeds/stores
  skills, serves them + their evaluations + stats. **It does NOT call an LLM.**
- **Claude Code = the evaluator.** Each developer, from their own Claude Code, imports skills
  and (if allowed) evaluates them, submitting results back over the REST API. The `skillhub`
  Claude Code skill (`skills/skillhub/SKILL.md`) drives this.
- **Auth = Google OAuth (humans) + device flow (MCP); SkillHub is its own auth server.** Reads are
  **open**. Humans sign in with Google in the browser (`GET /api/auth/login` → callback → opaque
  session cookie `skillhub_session`). The MCP authorizes via the RFC 8628 device grant and caches a
  SkillHub-minted token. All credentials live in `auth_tokens` (kind `session|device|pat`, SHA-256
  only) and resolve through one `get_user_by_token`; `current_user_optional` reads **bearer OR
  cookie**. Roles (ascending) `viewer → contributor → evaluator → admin`; any Google account starts
  `viewer`; emails in `SKILLHUB_BOOTSTRAP_ADMINS` become admin on first login. `SKILLHUB_ADMIN_TOKEN`
  is a deprecated break-glass. Google keys via `GOOGLE_CLIENT_ID/SECRET` + `SKILLHUB_PUBLIC_URL`;
  without them the stack runs but browser login is disabled.
- **Frontend = read-only dashboard** (catalog + semantic search + per-skill detail + a stats
  strip). No upload/evaluate/delete UI — those happen via Claude Code / the API. It is fully
  **bilingual (RU/EN)** via a lightweight home-grown i18n (`services/web/src/i18n.tsx`, toggle in
  the header, choice persisted to localStorage), and has a **Guide** page (`/guide`) with
  developer instructions. Only static UI chrome is translated; API data stays as stored.
- **Install a skill into your Claude Code.** `GET /api/skills/{id}` returns `skill_md` (the ready
  canonical SKILL.md); each skill page shows an "Install into Claude Code" phrase to paste. The
  actual install is done by the user's own Claude Code (via the `skillhub` skill / MCP `get_skill`):
  it writes `skill_md` + `references[]` into `.claude/skills/<name>/` with its own Write tool.
- **No LLM in the service, no LangChain.** Embeddings are local (`sentence-transformers`,
  pgvector) for search / duplicate detection. The dormant `skillhub_core/llm/` package and the
  stale `services/airflow/` DAG have been **removed**. Orchestration (scheduled headless
  `claude -p` re-evaluation) is deferred to a later phase.

## Key API endpoints
- Open reads: `GET /api/health`, `/api/stats`, `/api/skills`, `/api/skills?evaluated=false`
  (work queue), `/api/skills/{id}`, `/api/search?q=`, `/api/categories`, `/api/rubric`,
  `/api/skills/{id}/evaluations`.
- Token/cookie writes: `POST /api/skills` (contributor+), `POST /api/skills/{id}/assessment`
  (evaluator), `DELETE /api/skills/{id}` (admin).
- Auth: `GET /api/auth/login|callback`, `GET /api/auth/me`, `POST /api/auth/logout`,
  `POST /api/auth/device/{code,token,approve}`, `GET/POST/DELETE /api/auth/tokens` (self-service).
- Admin: `GET/POST /api/admin/users`, `POST /api/admin/users/{id}/role` (mark evaluator).
- Auth: `Authorization: Bearer <token>` (MCP/CLI) or the `skillhub_session` cookie (browser).

## Run it (behind the VPN)
Build must use the legacy builder (BuildKit ignores the daemon MTU); see README →
Troubleshooting. Images `skillhub-api`, `skillhub-web`, and `pgvector/pgvector:pg16` are built
locally.
```
docker compose up -d db api web            # base stack (uses built images)
# seed the 8 real prologistics skills (already copied into the api container at /tmp/skills):
docker exec skillhub-api-1 python -m skillhub_core.seed --path /tmp/skills
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
`services/mcp/` — a thin stdio FastMCP+httpx wrapper over the authed REST API. Image
`skillhub-mcp` (build: `DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp`). Tools:
`list_unevaluated`, `list_skills`, `get_skill`, `search`, `get_rubric`, `get_stats`,
`upload_skill` (contributor+), `submit_assessment` (evaluator). Each dev adds it to `.mcp.json`
(`docker run -i ... -e SKILLHUB_TOKEN=<theirs> skillhub-mcp`) — see `services/mcp/README.md`.
Verified from a container against the running API.

## Next
- **Trial upload via Claude Code** using the MCP (connect it, then upload a real SKILL.md and
  evaluate it). A trial `evaluator` user `dev-trial` was created for this.
- Then: "optimal skills" (synthesis of an ideal skill from a cluster) display + richer stats.
- Later/optional: a scheduler running headless `claude -p` re-evaluation.

## Notes / loose ends
- `services/web/src/pages/Upload.tsx` is now orphaned (no route) — kept, not wired.
- The dormant `skillhub_core/llm/` package and the `services/airflow/` DAG were removed (the
  service does not call an LLM; Claude Code is the evaluator).
