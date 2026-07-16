---
name: connect-skillhub
description: >
  Use to connect this Claude Code to a SkillHub server by registering its MCP, when the user says
  something like "connect me to SkillHub at <URL>", "install the SkillHub MCP for <URL>", or
  "add skillhub mcp <URL>". It runs a single `claude mcp add --transport http` command pointing at
  the server's `/mcp` endpoint — no Docker, no image, no token. Sign-in happens automatically in the
  browser (OAuth via GitHub) the first time a tool needs it. Trigger only for connecting/installing
  the SkillHub MCP; not for uploading/evaluating skills (that's the `skillhub` skill).
---

# Connect to SkillHub (register its remote MCP)

Register the SkillHub MCP server in this Claude Code so the user can browse/search/upload/evaluate
skills against their SkillHub instance. SkillHub hosts the MCP itself as a **remote HTTP server**, so
there is nothing to run locally — Claude Code just connects to a URL and authenticates in the browser.

## Inputs
- **Server URL** — the SkillHub base URL the user gives you, e.g. `https://166.1.29.218.sslip.io`
  or `https://skillhub.example.com`. If the user didn't include a URL, ask for it. Strip any trailing
  slash; the MCP endpoint is `<URL>/mcp`.

## Steps
1. **Check for an existing entry**: `claude mcp list`. If a `skillhub` server is already registered,
   ask whether to replace it (`claude mcp remove skillhub` first) rather than duplicating.
2. **Register it** with one command (substitute `<URL>`). Use `--scope user` so it's available in all
   of the user's projects:

   ```bash
   claude mcp add --transport http --scope user skillhub <URL>/mcp
   ```

   - `--transport http` — it's a remote streamable-HTTP MCP (like the `beliani-*` MCPs), not a local
     process. No Docker, no image pull, no token file.
   - Use `--scope project` instead of `--scope user` only if the user explicitly wants it committed to
     this repo's `.mcp.json` for the whole team.
3. **Confirm** with `claude mcp list` (the `skillhub` entry should appear; it may show
   "Needs authentication" until the first sign-in — that's expected).
4. **Tell the user**:
   - The MCP connects on the **next** Claude Code session (restart Claude Code).
   - The **first time** a SkillHub tool runs (or when the client prompts), Claude Code opens the
     browser for a one-time **OAuth sign-in with GitHub**; approve it and the connection is authorized
     (the token is managed by Claude Code — nothing to copy or paste). If the instance gates reads,
     even browsing prompts this sign-in the first time.
   - Access depends on the account's **role**: a fresh account can read and upload skills; submitting
     evaluations (`evaluator`) or managing users (`admin`) is granted by an admin.

## Fallbacks
- **Older instances without the remote MCP** (only the legacy local image): register the stdio server
  instead — `claude mcp add --scope user skillhub -- docker run --rm -i -e SKILLHUB_URL=<URL> -e SKILLHUB_TOKEN_FILE=/data/token -v skillhub-mcp-token:/data ghcr.io/sergeikiriakov-shop-team/skillhub-mcp:latest`
  — which needs Docker locally and authorizes via the device flow. Prefer the HTTP form above.
- If `claude mcp add --transport http` isn't recognized, update Claude Code (remote HTTP MCP support).
