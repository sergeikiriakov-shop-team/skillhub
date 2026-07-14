# AI agent instructions (SkillHub)

This is a **standalone** service, independent of the `prologistics` repository. Do not add
Prologistics-specific business logic here; SkillHub only consumes skill files as data.

## Conventions

- Write all `.md` files, code comments and docstrings in **English**.
- Python: FastAPI + SQLAlchemy + Pydantic v2. Format with `ruff`. Type hints everywhere.
- Business logic lives in `packages/skillhub_core` and is imported by both `services/api`
  and `services/airflow` — never duplicate logic between them.
- LLM access goes through `skillhub_core/llm/client.py` (LangChain `ChatAnthropic`). Do not
  call the Anthropic SDK directly elsewhere.
- **Claude Code `SKILL.md` is the canonical format.** Support for other clients (Cursor,
  Codex, Copilot) is added only through the parser dispatch in `parsing.py` and the export
  functions in `adapters.py` — keep the internal model Claude-shaped.

## Latest Claude models (for reference)

`claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`, `claude-fable-5`.
Default LLM is configured via `SKILLHUB_LLM_MODEL` (see `.env.example`).

## Do not

- Do not commit `.env` or any secret.
- Do not hardcode model ids in code — read them from `skillhub_core.config.Settings`.
