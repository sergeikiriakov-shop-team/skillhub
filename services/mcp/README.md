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
`.mcp.json` (repo root) already contains this — the token is read from your **environment**, so no
secret is committed and no `.env` file is required to start:

```json
{
  "mcpServers": {
    "skillhub": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SKILLHUB_URL=http://host.docker.internal:8000",
        "-e", "SKILLHUB_TOKEN=${SKILLHUB_TOKEN:-}",
        "skillhub-mcp"
      ]
    }
  }
}
```

- **Your token.** `${SKILLHUB_TOKEN:-}` expands from the environment Claude Code was started with.
  Set `SKILLHUB_TOKEN` (from an admin) as a user/OS environment variable — e.g. on Windows
  `setx SKILLHUB_TOKEN <your-token>` (reopen the terminal), on macOS/Linux export it in your shell
  profile. Leave it unset to run read-only. Only `SKILLHUB_URL` and `SKILLHUB_TOKEN` are passed to
  the container — no DB password or admin token is injected (unlike a blanket `--env-file .env`).
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
- "Install the `beliani-db-schema` skill from SkillHub into my project" → `search`/`get_skill`,
  then Claude Code writes `skill_md` + `references[]` into `.claude/skills/<name>/` with its own
  Write tool (the server can't write to your disk).
