# SkillHub

A registry, quality-evaluation and (later) synthesis service for **Claude Code skills**
used across the Prologistics developer team.

Developers today each write their own near-duplicate `SKILL.md` files. SkillHub collects
them in one place, scores their quality with Claude, categorizes them, finds overlaps, and
— in later phases — recommends the right skill for a task and synthesizes an "ideal" merged
skill from a group of similar ones.

> **Standalone service.** This repository is completely independent of the `prologistics`
> repository. It only *reads* skill files from it (or from uploads) as input data.

## Design stance

- **Claude Code is the first-class, canonical format** (`SKILL.md`: `name` + `description`
  frontmatter, body, optional `references/`). We do **not** prematurely abstract to a
  universal format.
- Other agent tools (Cursor `.mdc`, Codex skills, GitHub Copilot instructions) are supported
  as **import sources and export adapters** around the Claude-Code core — the same "hub +
  per-client adapters" model that `ai.tools/setup-ai-client.php` already uses in Prologistics.
  See `source_format` on skill versions and `skillhub_core/adapters.py`.

## Stack

| Layer          | Choice                                                        |
| -------------- | ------------------------------------------------------------- |
| API            | Python 3.12 + FastAPI                                         |
| LLM            | Claude via LangChain (`langchain-anthropic`)                  |
| Embeddings     | `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim)     |
| Database       | PostgreSQL 16 + pgvector                                      |
| Orchestration  | Apache Airflow (LocalExecutor, optional compose profile)      |
| Frontend       | React + Vite + TypeScript + Mantine + TanStack Query          |

Shared business logic lives in the installable package `packages/skillhub_core` and is used
by both the API and the Airflow DAGs.

## Quick start

```bash
cp .env.example .env
# (optional) put your ANTHROPIC_API_KEY in .env to enable evaluation/categorization

# Base stack: database + API + web portal
docker compose up -d --build db api web
```

- Portal:  http://localhost:8080
- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/api/health

### Seed with the real Prologistics skills

```bash
# Offline (no LLM), just import + parse the 8 real skills:
docker compose exec api python -m skillhub_core.seed --path /seed/skills --no-llm

# Full run (needs ANTHROPIC_API_KEY): import + evaluate + categorize
docker compose exec api python -m skillhub_core.seed --path /seed/skills
```

The `prologistics/ai.readme/skills` directory is mounted into the API container at `/seed/skills`
(see `docker-compose.override.example.yml` for how to point it at your local checkout), or pass
any accessible path.

### Orchestration (optional)

```bash
docker compose --profile airflow up -d --build
```

Airflow UI: http://localhost:8081 (default login `airflow` / `airflow`). Trigger the
`batch_reevaluate` DAG to re-run evaluation/categorization over all skills.

## Local development

- **API:** `pip install -e packages/skillhub_core -e services/api` then
  `uvicorn app.main:app --reload` (needs a reachable Postgres+pgvector).
- **Web:** `cd services/web && npm install && npm run dev` (Vite dev server on :5173, proxies
  `/api` to `http://localhost:8000`).
- **Tests:** `pip install -e packages/skillhub_core[dev]` then `pytest` (parser tests need no
  API key or database).

## Troubleshooting

### Builds hang on `npm install` / `pip install` (MTU black hole)

Symptom: image builds freeze mid-download (e.g. `npm install` stalls after fetching metadata,
CPU idle) while small requests work fine. This is an **MTU black hole** — common behind a VPN:
small packets pass, large transfers stall because oversized packets are silently dropped.

Pick an MTU at or below your VPN's path MTU. `1280` is the safe minimum; if builds are slow,
try a higher value that still works (e.g. `1350`). Check your VM's own MTU for a hint:
`wsl -d docker-desktop -e sh -c "cat /sys/class/net/eth0/mtu"`.

- **Runtime fix:** set `DOCKER_MTU=1280` in `.env` (the compose network uses it).
- **Daemon fix:** lower the Docker **daemon** MTU (fixes the default bridge — runtime *and* the
  legacy builder). Docker Desktop → Settings → Docker Engine, add `{ "mtu": 1280 }`, apply & restart.
- **Build fix (important):** BuildKit uses its **own** build network and ignores the daemon MTU,
  so `docker compose build` can still hang behind a VPN. Build with the legacy builder, which runs
  RUN steps on the (fixed) default bridge:

  ```bash
  DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build
  # or per image:  DOCKER_BUILDKIT=0 docker build -f services/web/Dockerfile -t skillhub-web .
  ```

  (Alternatively `docker build --network=host ...`, which runs RUN steps on the VM's own network.)
  Note: large downloads — the `api` image pulls PyTorch (hundreds of MB) — can still be slow over a
  VPN even with the MTU fixed; allow time or build on a non-VPN network.

Quick diagnosis — small request works, large one hangs:

```bash
docker run --rm node:20-slim npm view react version         # small: fast
docker run --rm node:20-slim npm pack react-dom              # larger: hangs on a bad MTU
```

## Roadmap

- **Phase 1 (this):** registry + LLM evaluation + categorization + web portal.
- **Phase 2:** recommendation ("which skill when"), duplicate/overlap detection via clustering,
  move heavy processing into Airflow, skill versioning history.
- **Phase 3:** synthesize an "ideal" skill from a cluster, export back to `SKILL.md` / per-client
  adapters, prepare a PR.
- **Phase 4:** auth, usage telemetry, feedback loop, leaderboards.

See `docs/` and the approved plan for details.
