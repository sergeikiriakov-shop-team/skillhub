# SkillHub architecture

## Purpose

Collect Claude Code skills (`SKILL.md`) from the team into one registry, score their quality
with Claude, categorize them, find overlaps, and later recommend the right skill for a task and
synthesize an "ideal" merged skill.

## Components

```
┌─────────────────────┐     HTTP /api      ┌──────────────────────────────┐
│ web (React/Mantine) │ ─────────────────▶ │ api (FastAPI)                │
│  nginx + SPA        │                    │  routers: skills, evaluations│
└─────────────────────┘                    │           categories, search │
                                           │  BackgroundTasks → pipeline  │
                                           └───────────────┬──────────────┘
                                                           │ imports
                                                           ▼
                                           ┌──────────────────────────────┐
                                           │ skillhub_core (shared lib)   │
                                           │  parsing · embeddings · llm  │
                                           │  repository · pipeline       │
                                           └───────────────┬──────────────┘
                                                           │ SQLAlchemy 2.0
                                                           ▼
                                           ┌──────────────────────────────┐
                                           │ db: Postgres 16 + pgvector   │
                                           └──────────────────────────────┘

  Claude Code (each dev)  ── HTTP /api ─▶ api    # evaluates skills, submits results back
```

## Key decisions

- **Claude Code is canonical.** The internal model is `name` + `description` + body + references.
  Other formats (Cursor `.mdc`, Codex, Copilot) are handled by parser dispatch in
  `parsing.py` and export functions in `adapters.py`. `SkillVersion.source_format` records origin.
- **One shared library.** `skillhub_core` holds all business logic; `api` and (future) batch
  jobs import it. No logic is duplicated.
- **Claude Code is the evaluator, not the service.** The service stores skills + the shared
  rubric (`/api/rubric`) and never calls an LLM. Each developer's Claude Code fetches the rubric,
  scores skills, and POSTs results back (`/api/skills/{id}/assessment`), so everyone runs the one
  identical algorithm. (No LangChain / Anthropic API key in the service.)
- **Local embeddings.** `sentence-transformers/all-MiniLM-L6-v2` (384-dim) avoids an extra API
  key and works offline after the first model download. Fail-soft: no model → no vector, the
  rest still works.

## Ingest pipeline (`skillhub_core/pipeline.py`)

`parse → embed → persist`

- On upload (and on seed import) the API parses the skill, upserts a version (a new version is
  created only when the content hash changes), and embeds it. The service does **not** evaluate
  or categorize — those never touch an LLM here.
- Evaluation, categorization and synthesis are produced by Claude Code and submitted back via
  `POST /api/skills/{id}/assessment`.

## Data model

`skills 1─* skill_versions 1─* evaluations`, `skill_versions 1─1 skill_embeddings`,
`skills *─* categories` (via `skill_categories`, with confidence + source). A new version is
created only when the content hash changes, so re-imports are idempotent.

## Quality rubric (v1)

`clarity`, `trigger_quality`, `completeness`, `reusability`, `safety`, `structure` (0-10 each)
plus a holistic `overall`, with strengths/weaknesses/rationale. Rubric version is stored so
skills can be re-scored and compared when the rubric evolves.

## Roadmap

- **Phase 2:** recommendation (retrieval + Claude rerank), duplicate/overlap clustering,
  version history UI.
- **Phase 3:** synthesize an "ideal" skill from a cluster (`llm/synthesize.py`), export to
  `SKILL.md` / per-client adapters, prepare a PR.
- **Phase 4:** auth, usage telemetry, feedback loop, leaderboards.
