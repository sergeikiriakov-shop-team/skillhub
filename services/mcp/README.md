# SkillHub MCP server

Exposes the SkillHub REST API as MCP tools for Claude Code. Runs in two transports:

- **`http` (production, recommended)** — a **remote streamable-HTTP** server hosted on the SkillHub
  box (the `mcp` service in `docker-compose.prod.yml`, behind nginx at `/mcp`). Developers connect
  with a single `claude mcp add --transport http …` and sign in **in the browser via OAuth** — no
  local Docker, no image, no token. SkillHub is the OAuth authorization server (GitHub identity);
  this process is the resource server: it validates the incoming Bearer against `/api/auth/me` and
  forwards it to the REST API.
- **`stdio` (local dev / legacy)** — the thin local wrapper Claude Code spawns via `docker run -i`;
  writes authorize via the OAuth **device flow** (token cached to a volume).

Transport is chosen by `SKILLHUB_MCP_TRANSPORT` (default `stdio`).

Tools: `list_unevaluated`, `list_skills`, `get_skill`, `search`, `get_rubric`, `get_stats`,
`list_task_groups`, `list_recommendations`, `upload_skill` (contributor+),
`submit_assessment` (evaluator), `add_recommendation`/`set_recommendation_status` (contributor+),
`authenticate`.

## Connect (developer — remote HTTP, no build, no Docker)

Ask your Claude Code in plain language (with the `connect-skillhub` skill installed):

> "install the SkillHub MCP for `https://166.1.29.218.sslip.io`"

…or run it directly (substitute your server URL; the MCP endpoint is `<URL>/mcp`):

```bash
claude mcp add --transport http --scope user skillhub https://166.1.29.218.sslip.io/mcp
```

`--scope user` registers it for all your projects (use `--scope project` to commit it to a repo's
`.mcp.json`). Restart Claude Code; verify with `claude mcp list` (it may show "Needs authentication"
until first use). The **first time** a SkillHub tool runs, Claude Code opens your browser for a
one-time **OAuth sign-in with GitHub** — approve it and you're connected; the token is managed by
Claude Code. Access depends on your role: a fresh account can read and upload; `evaluator`/`admin`
are granted by an admin.

### How the OAuth flow works (remote HTTP)

Standard MCP authorization (spec 2025-06-18). Claude Code: hits `/mcp` → gets `401` with
`WWW-Authenticate` → fetches protected-resource metadata (`/.well-known/oauth-protected-resource/mcp`,
served by this service) → fetches authorization-server metadata (`/.well-known/oauth-authorization-server`,
served by the api) → **Dynamic Client Registration** → **authorization-code + PKCE** (the browser
step, where SkillHub reuses its GitHub login) → **token** → calls `/mcp` with the Bearer. Refresh
tokens are issued so re-login is rare. See `services/api/app/routers/oauth.py`.

## Local development (`stdio`)

For working on SkillHub itself, run the stdio image against a local API. Example `.mcp.json`:

```json
{
  "mcpServers": {
    "skillhub": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SKILLHUB_URL=http://host.docker.internal:8000",
        "-e", "SKILLHUB_TOKEN=${SKILLHUB_TOKEN:-}",
        "-e", "SKILLHUB_TOKEN_FILE=/data/token",
        "-v", "skillhub-mcp-token:/data",
        "skillhub-mcp"
      ]
    }
  }
}
```

- **Auth is the device flow.** On an open instance reads need nothing; on a login-only instance the
  device flow also triggers on the first read. The first **write** (or gated read) returns a
  verification URL + code — open it, sign in with GitHub, approve; the token is cached to the
  `skillhub-mcp-token` volume so you do this once per machine. Run `authenticate` to do it eagerly.
- **`SKILLHUB_TOKEN`** (optional) skips the device flow (CI / break-glass).
- Build the image locally: `DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp`.

## Publish the stdio image (optional — legacy path)

Only needed for developers still on the stdio/`docker run` connect method (the remote HTTP transport
above needs no published image):

```bash
docker build -t skillhub-mcp services/mcp
docker tag skillhub-mcp ghcr.io/sergeikiriakov-shop-team/skillhub-mcp:latest
echo "$GHCR_TOKEN" | docker login ghcr.io -u <your-github-user> --password-stdin   # PAT: write:packages
docker push ghcr.io/sergeikiriakov-shop-team/skillhub-mcp:latest
```

Make the GHCR package **public** so developers can pull without `docker login`. The image is a thin
API proxy — no secrets.

## Use
Once connected, ask Claude Code things like:
- "Import this SKILL.md into SkillHub" → `upload_skill`.
- "Evaluate the pending SkillHub skills" → `list_unevaluated` → `get_rubric` → `get_skill` →
  `submit_assessment` for each.
- "What's in SkillHub about SQL?" → `search`.
- "Install the `beliani-db-schema` skill from SkillHub into my project" → `search`/`get_skill`,
  then Claude Code writes `skill_md` + `references[]` into `.claude/skills/<name>/` with its own
  Write tool (the server can't write to your disk).
