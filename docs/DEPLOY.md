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
  (`viewer → contributor → evaluator`). This instance sets `SKILLHUB_PUBLIC_READS=false`, so even
  reads require sign-in (only `/api/health` + `/api/auth/*` stay open).

## MCP for developers (remote HTTP + OAuth)
- The MCP is a **service in this compose** (`mcp`), hosted behind nginx at `/mcp`. Nothing to publish
  and no per-developer Docker. SkillHub is the OAuth authorization server; the `mcp` service is the
  resource server (validates the Bearer via the api and forwards it). See `services/mcp/README.md`.
- Each developer connects with one command (or asks Claude Code via the `connect-skillhub` skill,
  "install the SkillHub MCP for `https://166.1.29.218.sslip.io`"):
  ```
  claude mcp add --transport http --scope user skillhub https://166.1.29.218.sslip.io/mcp
  ```
  On first use Claude Code opens the browser for a one-time GitHub sign-in (OAuth); no token to copy.
- **Routing** (nginx, `services/web/nginx.conf`): `/mcp` and `/.well-known/oauth-protected-resource`
  → `mcp:9000`; `/.well-known/oauth-authorization-server` → `api:8000`; `/api/oauth/*` → `api`.
- **GitHub OAuth App:** unchanged — the MCP flow reuses the existing `/api/auth/login` + `/callback`,
  so the only registered callback stays `https://166.1.29.218.sslip.io/api/auth/callback`.
- The legacy stdio image (`ghcr.io/…/skillhub-mcp`, device flow, needs local Docker) still works for
  anyone mid-transition; prefer the HTTP form above.

## Ops
- Logs: `ssh skillhub 'cd /opt/skillhub && docker compose -f docker-compose.prod.yml logs -f <svc>'`.
- Status/health: `docker compose … ps`; `curl -s https://166.1.29.218.sslip.io/api/health`.
- **1 GB RAM is tight** — a 2 GB swapfile is enabled (`/swapfile`, in `/etc/fstab`). Builds and the
  torch/embedding model rely on it; consider more RAM if it gets busy.
- DB is Postgres+pgvector in the `pgdata` volume. Back it up with `pg_dump` before risky changes.
