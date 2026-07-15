---
name: connect-skillhub
description: >
  Use to connect this Claude Code to a SkillHub server by registering its MCP, when the user says
  something like "connect me to SkillHub at <URL>", "install the SkillHub MCP for <URL>", or
  "add skillhub mcp <URL>". It runs a single `claude mcp add` command with the given server URL
  and the published MCP image — no manual .mcp.json editing and no local image build. Authentication
  happens later automatically (device flow on the first write). Trigger only for connecting/installing
  the SkillHub MCP; not for uploading/evaluating skills (that's the `skillhub` skill).
---

# Connect to SkillHub (register its MCP)

Register the SkillHub MCP server in this Claude Code so the user can browse/search/upload/evaluate
skills against their SkillHub instance. Depending on the instance, reads are either public or also
require sign-in; writes always do. Authorization happens via the device flow on the first call that needs it.

## Inputs
- **Server URL** — the SkillHub base URL the user gives you, e.g. `https://166.1.29.218.sslip.io`
  or `https://skillhub.example.com`. If the user didn't include a URL, ask for it before proceeding.
  Strip any trailing slash.

## Steps
1. **Check Docker is available** (`docker --version`). The MCP runs as a container. If Docker is
   missing, tell the user to install Docker Desktop and stop.
2. **Check for an existing entry**: `claude mcp list`. If a `skillhub` server is already registered,
   ask whether to replace it (`claude mcp remove skillhub` first) rather than duplicating.
3. **Register it** with one command (substitute `<URL>` with the server URL). Use `--scope user` so
   it's available in all of the user's projects; a persistent docker volume caches the auth token:

   ```bash
   claude mcp add --scope user skillhub -- \
     docker run --rm -i \
     -e SKILLHUB_URL=<URL> \
     -e SKILLHUB_TOKEN_FILE=/data/token \
     -v skillhub-mcp-token:/data \
     ghcr.io/sergeikiriakov-shop-team/skillhub-mcp:latest
   ```

   Notes:
   - `--` separates Claude's flags from the container command; everything after it is the MCP command.
   - `SKILLHUB_URL` MUST be a `-e` flag inside `docker run` (that's what reaches the container).
   - Use `--scope project` instead of `--scope user` only if the user explicitly wants it committed to
     this repo's `.mcp.json` for the whole team.
4. **Confirm** with `claude mcp list` (the `skillhub` entry should appear).
5. **Tell the user**:
   - The MCP connects on the **next** Claude Code session (restart Claude Code).
   - **Reads need nothing.** The first time they use a **write** tool (upload/evaluate) — or if they
     run the MCP's `authenticate` tool — it prints a verification link + code: open it, sign in with
     GitHub, approve at `<URL>/device`, and the token is cached to the `skillhub-mcp-token` volume
     (one-time per machine). Writes also require a role — a fresh account is `viewer`; an admin
     promotes to `contributor`/`evaluator`.

## Fallbacks
- If pulling `ghcr.io/sergeikiriakov-shop-team/skillhub-mcp` fails with auth (private image), the
  user must `docker login ghcr.io` first, or the image owner should make the package public.
- If the org/image path differs on your deployment, substitute the correct
  `<registry>/<owner>/skillhub-mcp:<tag>` in the command above.
