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
| Evaluation     | Claude Code (each developer's agent) — the service runs no LLM |
| Embeddings     | `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim)     |
| Database       | PostgreSQL 16 + pgvector                                      |
| Frontend       | React + Vite + TypeScript + Mantine + TanStack Query          |

Shared business logic (parsing, embeddings, repository, ingest pipeline) lives in the
installable package `packages/skillhub_core` and is imported by the API.

## Quick start

```bash
cp .env.example .env
# reads are open; to enable browser login set GITHUB_CLIENT_ID/SECRET + SKILLHUB_BOOTSTRAP_ADMINS
# (see "Authentication" below). Everything else works without it.

# Base stack: database + API + web portal
docker compose up -d --build db api web
```

- Portal:  http://localhost:8080
- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/api/health

### Seed with the real Prologistics skills

```bash
# Import + parse + embed the real skills (the service never evaluates — that's Claude Code's job):
docker compose exec api python -m skillhub_core.seed --path /seed/skills
```

The `prologistics/ai.readme/skills` directory is mounted into the API container at `/seed/skills`
(see `docker-compose.override.example.yml` for how to point it at your local checkout), or pass
any accessible path. Evaluation/categorization then happen from Claude Code (see below).

### Evaluate from Claude Code

The service stores skills + the shared rubric but never calls an LLM. Evaluation,
categorization and synthesis are done by each developer's **Claude Code**, which fetches the
rubric (`GET /api/rubric`) and the unevaluated queue (`GET /api/skills?evaluated=false`), scores
each skill against it, and submits results back (`POST /api/skills/{id}/assessment`). Install
`skills/skillhub/SKILL.md` into Claude Code, or add the SkillHub MCP server (`services/mcp/`), to
drive this. Storing the strategy server-side means every developer runs the one identical algorithm.

## Authentication

Built for a shared, remotely-hosted instance. **Reads are public.** Writes require auth:

- **Humans** sign in with **GitHub** in the browser (button in the header → `/api/auth/login`).
  Any GitHub account works and starts as `viewer`; roles ascend `viewer → contributor → evaluator
  → admin`. Emails in `SKILLHUB_BOOTSTRAP_ADMINS` become admin on first login; an admin then
  promotes others. SkillHub is its own authorization server — GitHub only provides identity, so
  the provider is easy to swap (only `/login` and `/callback` are provider-specific).
- **Claude Code / MCP** authorizes via the **OAuth device flow**: on the first write it shows a
  verification URL + code; you approve it at `/device` (signed in with GitHub) and the minted
  SkillHub token is cached to a docker volume. See `services/mcp/README.md`.

Setup: register an OAuth App under your GitHub account (Settings → Developer settings → OAuth Apps;
"Authorization callback URL" = `SKILLHUB_PUBLIC_URL` + `/api/auth/callback`), then set
`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `SKILLHUB_PUBLIC_URL`, `SKILLHUB_BOOTSTRAP_ADMINS`, and
`SKILLHUB_COOKIE_SECURE=true` (prod/HTTPS) in `.env`. Without GitHub creds the stack still runs;
only browser login is disabled.

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

- **Phase 1 (this):** registry + Claude-Code evaluation/categorization + read-only web portal.
- **Phase 2:** recommendation ("which skill when"), duplicate/overlap detection via clustering,
  skill versioning history.
- **Phase 3:** synthesize an "ideal" skill from a cluster, export back to `SKILL.md` / per-client
  adapters, prepare a PR.
- **Phase 4:** auth (**done** — GitHub OAuth login + device-flow tokens for the MCP), usage
  telemetry, feedback loop, leaderboards.
- **Later/optional:** scheduled re-evaluation (headless `claude -p` on a scheduler).

See `docs/` and the approved plan for details.
