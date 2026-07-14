# SkillHub — session handoff / resume notes

Read this first to resume cold. SkillHub is a **standalone** service (independent of the
`prologistics` repo) at `C:\Users\Sergei Kiriakov\Documents\skillhub` (git branch `main`).

## Architecture (current)

- **Service = system of record + retrieval + read-only display.** It parses/embeds/stores
  skills, serves them + their evaluations + stats. **It does NOT call an LLM.**
- **Claude Code = the evaluator.** Each developer, from their own Claude Code, imports skills
  and (if allowed) evaluates them, submitting results back over the REST API. The `skillhub`
  Claude Code skill (`skills/skillhub/SKILL.md`) drives this.
- **Multi-user auth.** Reads are **open**; writes need a bearer token. Roles (ascending):
  `viewer` → `contributor` (may upload) → `evaluator` (may submit evaluations — marked by an
  admin) → `admin` (manages users). Tokens are random; only their SHA-256 is stored.
  Bootstrap admin: on first boot with an empty users table, `SKILLHUB_ADMIN_TOKEN` becomes the
  admin. Local dev token in `.env`: `dev-admin-token-change-me`.
- **Frontend = read-only dashboard** (catalog + semantic search + per-skill detail + a stats
  strip). No upload/evaluate/delete UI — those happen via Claude Code / the API.
- **No LangChain.** Embeddings are local (`sentence-transformers`, pgvector) for search /
  duplicate detection. Airflow is deferred to a later phase (automation = headless `claude -p`
  on a scheduler; the DAG file under `services/airflow/dags` is a stale Phase-2 placeholder).

## Key API endpoints
- Open reads: `GET /api/health`, `/api/stats`, `/api/skills`, `/api/skills?evaluated=false`
  (work queue), `/api/skills/{id}`, `/api/search?q=`, `/api/categories`, `/api/rubric`,
  `/api/skills/{id}/evaluations`.
- Token writes: `POST /api/skills` (contributor+), `POST /api/skills/{id}/assessment`
  (evaluator), `DELETE /api/skills/{id}` (admin).
- Admin: `GET/POST /api/admin/users`, `POST /api/admin/users/{id}/role` (mark evaluator).
- Auth header: `Authorization: Bearer <token>`.

## Run it (behind the VPN)
Build must use the legacy builder (BuildKit ignores the daemon MTU); see README →
Troubleshooting. Images `skillhub-api`, `skillhub-web`, and `pgvector/pgvector:pg16` are built
locally.
```
docker compose up -d db api web            # base stack (uses built images)
# seed the 8 real prologistics skills (already copied into the api container at /tmp/skills):
docker exec skillhub-api-1 python -m skillhub_core.seed --path /tmp/skills   # --no-llm not needed
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

## Next
- **MCP server** wrapping the (now authed) REST API, so each dev's Claude Code connects with
  their token — tools: `upload_skill`, `list_unevaluated`, `get_rubric`, `submit_assessment`,
  `search`, `get_skill`. Thin FastMCP/httpx layer; add as a compose service.
- Then: "optimal skills" (synthesis of an ideal skill from a cluster) display + richer stats.
- Later/optional: Airflow to orchestrate scheduled headless `claude -p` re-evaluation.

## Notes / loose ends
- `services/web/src/pages/Upload.tsx` is now orphaned (no route) — kept, not wired.
- `packages/skillhub_core/skillhub_core/llm/` is dormant/legacy (nothing imports it; LangChain
  removed from deps). Safe to delete later.
- LLM auth options (if the service ever needs Claude directly) discussed earlier: api_key /
  oauth / claude_agent_sdk. Not relevant while Claude Code is the evaluator.
