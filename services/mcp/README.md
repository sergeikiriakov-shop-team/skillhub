# SkillHub MCP server

A thin **stdio** MCP server that exposes the SkillHub REST API as tools for Claude Code. Each
developer runs it with their own token; authorization is enforced by the API.

Tools: `list_unevaluated`, `list_skills`, `get_skill`, `search`, `get_rubric`, `get_stats`,
`upload_skill` (contributor+), `submit_assessment` (evaluator).

## Build (once)
```bash
DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp
```

## Configure in Claude Code (`.mcp.json`)
Claude Code launches the server as a stdio subprocess via `docker run -i`. Put this in your
project (or user) `.mcp.json` — replace the token with yours (from an admin):

```json
{
  "mcpServers": {
    "skillhub": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SKILLHUB_URL=http://host.docker.internal:8000",
        "-e", "SKILLHUB_TOKEN=<your-token>",
        "skillhub-mcp"
      ]
    }
  }
}
```

- `SKILLHUB_URL` defaults to `http://host.docker.internal:8000` (Docker Desktop reaches the
  host-published API port). If you run the MCP on the compose network instead, use
  `--network skillhub_default` and `SKILLHUB_URL=http://api:8000`.
- Reads work without a token; `upload_skill` needs a contributor+ token; `submit_assessment`
  needs an evaluator token. Ask an admin to create your user
  (`POST /api/admin/users`) and, for evaluation, set your role to `evaluator`.

## Use
Once connected, ask Claude Code things like:
- "Import this SKILL.md into SkillHub" → `upload_skill`.
- "Evaluate the pending SkillHub skills" → `list_unevaluated` → `get_rubric` → `get_skill` →
  `submit_assessment` for each.
- "What's in SkillHub about SQL?" → `search`.
