# AI agent instructions (SkillHub)

This is a **standalone** service, independent of the `prologistics` repository. Do not add
Prologistics-specific business logic here; SkillHub only consumes skill files as data.

## Conventions

- Write all `.md` files, code comments and docstrings in **English**.
- Python: FastAPI + SQLAlchemy + Pydantic v2. Format with `ruff`. Type hints everywhere.
- Business logic lives in `packages/skillhub_core` and is imported by `services/api` — never
  duplicate logic elsewhere.
- **The service never calls an LLM.** Evaluation/categorization/synthesis are done by each
  developer's Claude Code, which fetches the shared rubric (`GET /api/rubric`) and submits
  results back (`POST /api/skills/{id}/assessment`). Keep the strategy server-side (see
  `skillhub_core/rubric.py`), not in code that calls a model.
- **Claude Code `SKILL.md` is the canonical format.** Support for other clients (Cursor,
  Codex, Copilot) is added only through the parser dispatch in `parsing.py` and the export
  functions in `adapters.py` — keep the internal model Claude-shaped.

## Do not

- Do not commit `.env` or any secret.
- Do not add a server-side LLM call. The rubric is served to Claude Code, which does the scoring.
