---
name: skillhub
description: >
  ALWAYS use to work with the SkillHub registry: import Claude Code skills into it, and —
  since SkillHub does NOT call an LLM itself — YOU (Claude Code) are the evaluator. Use it
  whenever asked to add/import a skill, to evaluate/score unevaluated skills, to re-score
  after a rubric change, or to look up existing skills and their evaluations. SkillHub only
  stores, serves and displays; the reasoning is done here and submitted back over its REST API.
---

# SkillHub

SkillHub is a standalone service (FastAPI + Postgres + a web portal) that stores Claude Code
skills, their local embeddings (for search / duplicate detection) and their quality
evaluations. It performs no LLM calls. This skill lets Claude Code act as the evaluator.

- Base URL (local dev): `http://localhost:8000` (env `SKILLHUB_URL` overrides).
- All calls are plain JSON over the REST API. Use `curl` via the Bash tool.

## Workflow: evaluate the pending skills

1. **Fetch the work queue** — skills with no evaluation yet:
   ```bash
   curl -s "$SKILLHUB_URL/api/skills?evaluated=false"
   ```
2. **Fetch the rubric** (instructions + the exact JSON shape to submit + the category taxonomy):
   ```bash
   curl -s "$SKILLHUB_URL/api/rubric"
   ```
   It returns `rubric_version`, `instructions`, `dimensions`, `evaluation_schema`
   (JSON Schema for the `evaluation` object) and `categories` (allowed category keys).
3. **For each pending skill**, fetch its full content:
   ```bash
   curl -s "$SKILLHUB_URL/api/skills/<id>"
   ```
   Read `description`, `trigger_text`, `body_md`, `section_headings` and `references[]`.
4. **Score it yourself** against the rubric. Every dimension is an integer 0-10; be strict and
   consistent (reserve 9-10 for exemplary skills). Also choose categories from the taxonomy.
5. **Submit the assessment** (validated server-side against the rubric schema):
   ```bash
   curl -s -X POST "$SKILLHUB_URL/api/skills/<id>/assessment" \
     -H "Content-Type: application/json" -d '{
       "model": "claude-code (opus-4.8)",
       "evaluation": {
         "clarity": 8, "trigger_quality": 7, "completeness": 8,
         "reusability": 6, "safety": 7, "structure": 8, "overall": 7.4,
         "strengths": ["..."], "weaknesses": ["..."],
         "rationale": "2-4 sentences."
       },
       "categorization": {
         "primary_category": "data-access",
         "categories": [{"key": "data-access", "confidence": 0.9}],
         "tags": ["sql", "postgres"], "summary": "One sentence."
       }
     }'
   ```
   `rubric_version` is optional (defaults to the server's current version).

Then tell the user how many skills were scored; results are visible on the portal (`:8080`).

## Workflow: import skills from somewhere the user points to
For each `SKILL.md` folder (dir with `SKILL.md`, optional `references/`):
```bash
curl -s -X POST "$SKILLHUB_URL/api/skills" -H "Content-Type: application/json" -d '{
  "content": "<raw SKILL.md text>",
  "author": "<team/person>",
  "source_format": "claude_skill",
  "references": [{"path": "references/tools.md", "content": "<file text>"}]
}'
```
`source_format` may be `claude_skill` | `cursor_mdc` | `codex_skill` | `generic_md`.
Bulk import of a directory can also be done from the API container:
`docker exec skillhub-api-1 python -m skillhub_core.seed --path /tmp/skills`.

## Look things up
- Search by meaning: `curl -s "$SKILLHUB_URL/api/search?q=<query>"`.
- One skill (incl. its evaluation + similar skills): `curl -s "$SKILLHUB_URL/api/skills/<id>"`.
- Categories with counts: `curl -s "$SKILLHUB_URL/api/categories"`.
- Evaluation history for a skill: `curl -s "$SKILLHUB_URL/api/skills/<id>/evaluations"`.

## Notes
- Re-scoring: when the rubric version changes, treat existing evaluations as stale and
  re-submit; `?evaluated=false` will (in a later phase) also surface stale ones.
- Set `SKILLHUB_URL` if the service is not on localhost:8000.
