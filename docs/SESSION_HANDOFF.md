# SkillHub — session handoff / resume notes

Snapshot of the state at the end of the first build session, so work can resume cold
(e.g. from a different Claude Code login).

## What SkillHub is
Standalone service (independent of the `prologistics` repo) that collects Claude Code
skills (`SKILL.md`), scores their quality with Claude, categorizes them, finds overlaps;
later: recommendation ("which skill when") and synthesis of an "ideal" skill.

## Location & git
- Path: `C:\Users\Sergei Kiriakov\Documents\skillhub`
- Branch: `main` (standalone repo, no remote configured)
- Commits:
  - `bd1449a` — Initial SkillHub MVP (58 files)
  - `797c21b` — Fix image builds behind VPN + FastAPI 204 delete route
  - (+ this handoff doc)

## Status: Phase 1 (MVP) COMPLETE and verified end-to-end
Verified live on this machine:
- `docker compose up -d db api web` → all three containers up (db healthy).
- `GET /api/health` → `{"status":"ok","llm_enabled":false,...}`.
- Web portal on :8080 (nginx serves the SPA, proxies `/api`).
- Seeded the 8 real prologistics skills offline (`seed --no-llm`): parsed, stored,
  embedded (pgvector). Semantic search ranks correctly (e.g. "run SQL on production"
  → `beliani-sql-query` first).
- Parser unit tests: 9 passing (`tests/test_parsing.py`).
- LLM evaluation/categorization NOT exercised yet — needs `ANTHROPIC_API_KEY` (fail-soft
  by design: import/browse/search work without it).

## Access (if the stack is still running)
- Portal:  http://localhost:8080
- API docs: http://localhost:8000/docs
- Health:  http://localhost:8000/api/health
Stop it with: `docker compose down` (data persists in the `pgdata` volume).

## IMPORTANT — environment fix that makes builds work here (VPN / MTU)
This machine is behind a VPN that black-holes large Docker downloads. Root cause &
fixes applied (see README → Troubleshooting for the full write-up):
1. Docker daemon MTU lowered to **1280** in `C:\Users\Sergei Kiriakov\.docker\daemon.json`
   (added `"mtu": 1280`; original `builder.gc` settings preserved). Applied via
   `docker desktop restart`. You can keep or revert this.
2. **BuildKit ignores the daemon MTU**, so images must be built with the legacy builder:
   `DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build`
   (or `DOCKER_BUILDKIT=0 docker build -f services/<svc>/Dockerfile -t skillhub-<svc> .`).
3. `services/web/Dockerfile` serializes npm downloads via `ARG NPM_MAXSOCKETS=1` — the VPN
   can't handle npm's parallel tarball fetches. On a fast network build with
   `--build-arg NPM_MAXSOCKETS=15`.
4. `services/api/Dockerfile` installs CPU-only PyTorch (the default Linux wheel is the
   ~2GB CUDA build).
Both images (`skillhub-web`, `skillhub-api`) and the db image are already built locally.

## Rebuild / run from scratch (behind the VPN)
```
cp .env.example .env            # already present; set ANTHROPIC_API_KEY to enable LLM
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build
docker compose up -d db api web
# seed the 8 real skills (skills already copied into the api container at /tmp/skills):
docker exec skillhub-api-1 python -m skillhub_core.seed --path /tmp/skills --no-llm
```

## To enable Claude evaluation/categorization
1. Put a key in `.env` → `ANTHROPIC_API_KEY=...`, then `docker compose restart api`.
2. Re-run seed without `--no-llm` (or use the "Re-evaluate" button per skill):
   `docker exec skillhub-api-1 python -m skillhub_core.seed --path /tmp/skills`

### Open decision — LLM auth (discussed, not yet implemented)
API key (Console) bills separately from a Claude Pro/Max subscription — you can't point
the LangChain client at the subscription. Three options were discussed:
- **api_key** (current): key in `.env` / secrets manager. Simplest.
- **oauth**: `ant auth login` profile / `ANTHROPIC_AUTH_TOKEN` — no key in code, still API billing.
- **claude_agent_sdk**: drive `claude` headless / Claude Agent SDK on the Claude Code
  subscription login (uses subscription quota, not API credits). Would replace the
  `langchain-anthropic` call in `skillhub_core/llm/client.py`.
Proposed next step: put the provider behind `SKILLHUB_LLM_PROVIDER = api_key|oauth|claude_agent_sdk`
so evaluation/categorization chains don't change.

## Roadmap (next phases)
- **Phase 2:** recommendation (retrieval + Claude rerank), duplicate/overlap detection
  (clustering by embedding — the core pain), move heavy processing into Airflow, version
  history UI.
- **Phase 3:** synthesize an "ideal" skill from a cluster (`llm/synthesize.py`), export to
  `SKILL.md` / per-client adapters, prepare a PR.
- **Phase 4:** auth, usage telemetry, feedback loop, leaderboards.

## Design reminders
- Claude Code `SKILL.md` is the canonical format; Cursor/Codex/Copilot are import/export
  adapters (`parsing.py` dispatch + `adapters.py`).
- Shared logic lives in `packages/skillhub_core`; API and Airflow import it. Airflow
  orchestrates over HTTP (never imports core — SQLAlchemy 1.4 vs 2.0 clash).
- Fail-soft everywhere: no API key → no scores/categories; no embedding model → no vectors;
  the rest keeps working.
