# SkillHub — deployment (single host)

The instance runs on one small VPS via Docker Compose. No Kubernetes, no CI — deploys are a
`git push` to the server. This doc is the operator's memo.

## Where it runs
- **Host:** `166.1.29.218` (Ubuntu 24.04, 1 vCPU / 1 GB RAM + 2 GB swap, Docker). SSH: `ssh skillhub`
  (alias in `~/.ssh/config`, key auth). Code lives in `/opt/skillhub`.
- **Public URLs:**
  - `https://166.1.29.218.sslip.io` — primary (TLS via Caddy + Let's Encrypt; `sslip.io` resolves
    the name to the IP, so no domain purchase).
  - `http://166.1.29.218:8080` — plain-http fallback.
- **Exposure:** only Caddy (80/443) and web (8080) are published; `api` + `db` stay on the internal
  docker network (nginx proxies `/api` → `api:8000`). SSH on 22.

## Compose
- `docker-compose.prod.yml` (committed): built images, no bind-mounts / no `--reload`,
  `restart: unless-stopped`. Services: `db` (pgvector), `api`, `web` (nginx SPA + `/api` proxy),
  `caddy` (TLS). Volumes: `pgdata`, `hf_cache` (embedding model), `caddy_data`/`caddy_config`.
- Config comes from `/opt/skillhub/.env` (**not** in git — holds secrets). Key vars:
  `SKILLHUB_DOMAIN` (Caddy host), `SKILLHUB_PUBLIC_URL` (https), `SKILLHUB_COOKIE_SECURE=true`,
  `GITHUB_CLIENT_ID/SECRET`, `SKILLHUB_BOOTSTRAP_ADMINS`, generated `POSTGRES_PASSWORD` +
  `SKILLHUB_ADMIN_TOKEN` (break-glass). See `.env.example` for the full list.

## Deploy (push-to-deploy)
From a local clone, after committing:
```
git push vps skillhub/rubric-v2-two-level-taxonomy
```
`vps` = `skillhub:/opt/skillhub.git` (a bare repo). Its `post-receive` hook checks the branch out
into `/opt/skillhub` (leaving `.env` untouched) and runs `docker compose -f docker-compose.prod.yml
up -d --build`, then waits for `/api/health`. A failed build leaves the running containers up.

Manual equivalent on the host:
```
ssh skillhub 'cd /opt/skillhub && docker compose -f docker-compose.prod.yml up -d --build'
```

## Auth (GitHub OAuth)
- A GitHub **OAuth App** (Settings → Developer settings → OAuth Apps). Homepage + callback must use
  the public URL: callback = `https://166.1.29.218.sslip.io/api/auth/callback`. Put
  `GITHUB_CLIENT_ID/SECRET` in the server `.env`.
- First login by an email in `SKILLHUB_BOOTSTRAP_ADMINS` becomes `admin`; that admin promotes others
  (`viewer → contributor → evaluator`). Reads are public.

## MCP for developers
- Publish the MCP image once (maintainer): `docker build -t skillhub-mcp services/mcp`, tag/push to
  `ghcr.io/sergeikiriakov-shop-team/skillhub-mcp:latest` (PAT with `write:packages`), make the
  package **public**. See `services/mcp/README.md`.
- Each developer: ask Claude Code (with the `connect-skillhub` skill) "install the SkillHub MCP for
  `https://166.1.29.218.sslip.io`", or run the `claude mcp add …` command from the portal's **Guide**
  page. No build; the published image is pulled. Writes authorize via the device flow.

## Ops
- Logs: `ssh skillhub 'cd /opt/skillhub && docker compose -f docker-compose.prod.yml logs -f <svc>'`.
- Status/health: `docker compose … ps`; `curl -s https://166.1.29.218.sslip.io/api/health`.
- **1 GB RAM is tight** — a 2 GB swapfile is enabled (`/swapfile`, in `/etc/fstab`). Builds and the
  torch/embedding model rely on it; consider more RAM if it gets busy.
- DB is Postgres+pgvector in the `pgdata` volume. Back it up with `pg_dump` before risky changes.
