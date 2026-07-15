---
name: skillhub
description: >
  ALWAYS use to work with the SkillHub registry (the team's shared Claude Code skills catalog):
  look up/search skills, import a skill, evaluate/score unevaluated skills (re-score after a rubric
  change), or install a skill from the registry into this Claude Code. Prefer the `skillhub` MCP
  tools. SkillHub does NOT call an LLM — YOU (Claude Code) are the evaluator: the reasoning is done
  here and submitted back. Trigger whenever the user mentions SkillHub, evaluating/importing skills,
  or pulling a skill from the registry.
---

# SkillHub

SkillHub is a standalone service (FastAPI + Postgres + web portal) that stores Claude Code skills,
their local embeddings (search / duplicate detection) and their quality evaluations. It performs
**no LLM calls** — this skill lets Claude Code act as the evaluator/curator.

## Interface: the `skillhub` MCP (preferred)

Use the **`skillhub` MCP tools** — no curl, no manual URLs. If the MCP isn't connected, run the
`connect-skillhub` skill first (it registers the MCP against the server URL). Auth is automatic:
reads may be public or require sign-in, and writes always do — on the first call that needs it the
MCP prints a verification link + code (approve at `<server>/device` via GitHub; cached per machine).
Writes also need a role: a fresh account is `viewer`; an admin grants `contributor`/`evaluator`.

Tools: `list_skills`, `search`, `get_skill`, `get_stats`, `list_task_groups`, `list_recommendations`,
`list_unevaluated`, `get_rubric`, `submit_assessment`, `upload_skill`, `add_recommendation`,
`set_recommendation_status`, `authenticate`.

## Workflow: look things up
- By meaning: `search(query)`. By name/author/category: `list_skills(search=…, category=…)`.
- One skill (content + latest evaluation + similar): `get_skill(id)`.
- Overview: `get_stats`; narrow task-groups: `list_task_groups`; proposals: `list_recommendations`.

## Workflow: evaluate the pending skills (YOU are the evaluator)
1. `list_unevaluated()` — the work queue.
2. `get_rubric()` — `instructions`, `dimensions`, `weights`, `calibration`, the `evaluation_schema`
   (exact JSON shape to submit), the `categories` taxonomy and `categorization_rules`. Follow it.
3. For each skill: `get_skill(id)` → read `description`, `trigger_text`, `body_md`,
   `section_headings`, `references[]`.
4. Score it yourself against the rubric. Every dimension is an **integer 0-10**; be strict and
   consistent (reserve 9-10 for exemplary skills). Write concrete strengths/weaknesses and a 2-4
   sentence rationale. Choose categories from the taxonomy; set a narrow `task_group` slug, and
   **reuse an existing slug** (`list_task_groups`) when a skill does the same job.
5. `submit_assessment(skill_id, evaluation={…rubric schema…}, categorization={primary_category,
   categories:[{key,confidence}], task_group, tags, summary}, model="claude-code (<your model>)")`.

Then tell the user how many were scored; results appear on the portal.

## Workflow: import a skill
`upload_skill(content=<raw SKILL.md text>, source_format="claude_skill", references=[{path,content}])`.
`source_format`: `claude_skill | cursor_mdc | codex_skill | generic_md`. De-dup: skills are keyed by
**name** — re-uploading a name adds a new **version** (not a copy); content identical to an existing
skill under a **different** name is rejected (409, `existing_name`); a merely-similar one is accepted
with a `similar_warning`. Authorship is the authenticated uploader (a client-supplied author is
ignored when signed in).

## Workflow: install a skill from SkillHub into this Claude Code
When asked to install/add a skill from SkillHub: `get_skill(id)` (find it first via `search`/
`list_skills`), then with your **own Write tool** write:
- `skill_md` → `<dir>/SKILL.md` (byte-for-byte),
- each `references[i]` → `<dir>/<path>`,
where `<dir>` is `.claude/skills/<name>/` (project) or `~/.claude/skills/<name>/` (personal). The
service/MCP run in a container and cannot touch the user's disk — you write the files.

## Fallback: no MCP (raw REST)
Only if the MCP is unavailable. Set `SKILLHUB_URL` and use `curl` via Bash with a bearer token
(reads may be gated too): `curl -H "Authorization: Bearer $SKILLHUB_TOKEN" "$SKILLHUB_URL/api/skills?evaluated=false"`,
`…/api/rubric`, `…/api/skills/<id>`, and `POST …/api/skills/<id>/assessment`. Prefer the MCP.

## Notes
- Re-scoring: when the rubric version changes, treat existing evaluations as stale and re-submit.
- The rubric/strategy lives server-side (`get_rubric`), so every developer scores by one algorithm.
