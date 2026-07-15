# SkillHub MCP server

A thin **stdio** MCP server that exposes the SkillHub REST API as tools for Claude Code. Each
developer runs it with their own token; authorization is enforced by the API.

Tools: `list_unevaluated`, `list_skills`, `get_skill`, `search`, `get_rubric`, `get_stats`,
`list_task_groups`, `list_recommendations`, `upload_skill` (contributor+),
`submit_assessment` (evaluator), `add_recommendation`/`set_recommendation_status` (contributor+).

## Build (once)
```bash
DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp
```

## Configure in Claude Code (`.mcp.json`)
Claude Code launches the server as a stdio subprocess via `docker run -i`. The committed
`.mcp.json` (repo root) already contains this:

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

- **Authentication is automatic (device flow).** Reads are public and need nothing. The first time
  you use a **write** tool (upload/assess/recommend), the server starts the OAuth device flow and
  returns a verification URL + short code. Open it, sign in with GitHub, approve, and the minted
  SkillHub token is cached to the `skillhub-mcp-token` docker volume (`/data/token`) so you only do
  this once per machine. You can also run the `authenticate` tool proactively. Writes still require
  a role — a fresh account is a `viewer`; ask an admin to promote you to `contributor`/`evaluator`.
- **`SKILLHUB_TOKEN` (optional override).** If set, it skips the device flow entirely (useful for
  CI or a break-glass admin token). Leave it unset for the normal flow.
- `SKILLHUB_URL` points at the server. Default `http://host.docker.internal:8000` reaches a locally
  published API; for a remote deployment set it to your public URL (e.g. `https://skillhub.example.com`).
  If you run the MCP on the compose network instead, use `--network skillhub_default` and
  `SKILLHUB_URL=http://api:8000`.

## Use
Once connected, ask Claude Code things like:
- "Import this SKILL.md into SkillHub" → `upload_skill`.
- "Evaluate the pending SkillHub skills" → `list_unevaluated` → `get_rubric` → `get_skill` →
  `submit_assessment` for each.
- "What's in SkillHub about SQL?" → `search`.
- "Install the `beliani-db-schema` skill from SkillHub into my project" → `search`/`get_skill`,
  then Claude Code writes `skill_md` + `references[]` into `.claude/skills/<name>/` with its own
  Write tool (the server can't write to your disk).
