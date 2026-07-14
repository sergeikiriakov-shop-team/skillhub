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

  airflow (optional, own dep set) ── HTTP /api ─▶ api    # orchestrates, never imports core
```

## Key decisions

- **Claude Code is canonical.** The internal model is `name` + `description` + body + references.
  Other formats (Cursor `.mdc`, Codex, Copilot) are handled by parser dispatch in
  `parsing.py` and export functions in `adapters.py`. `SkillVersion.source_format` records origin.
- **One shared library.** `skillhub_core` holds all business logic; `api` and (future) batch
  jobs import it. No logic is duplicated.
- **Airflow orchestrates over HTTP, never imports the core.** Airflow 2.x pins SQLAlchemy 1.4
  while the core needs 2.0, so the DAGs call the API instead. This also keeps the pipeline
  callable identically from anywhere.
- **Local embeddings.** `sentence-transformers/all-MiniLM-L6-v2` (384-dim) avoids an extra API
  key and works offline after the first model download. Fail-soft: no model → no vector, the
  rest still works.
- **Fail-soft LLM.** No `ANTHROPIC_API_KEY` → import/browse/search still work; evaluation and
  categorization are simply skipped.

## Ingest pipeline (`skillhub_core/pipeline.py`)

`parse → embed → evaluate → categorize → persist`

- On upload, the API runs `parse + upsert + embed` inline (fast) and schedules
  `evaluate + categorize` as a background task (slow, needs Claude).
- `reprocess()` re-runs embed/evaluate/categorize on a skill's latest version in place — used by
  the `batch_reevaluate` Airflow DAG and the per-skill "Re-evaluate" button.

## Data model

`skills 1─* skill_versions 1─* evaluations`, `skill_versions 1─1 skill_embeddings`,
`skills *─* categories` (via `skill_categories`, with confidence + source). A new version is
created only when the content hash changes, so re-imports are idempotent.

## Quality rubric (v1)

`clarity`, `trigger_quality`, `completeness`, `reusability`, `safety`, `structure` (0-10 each)
plus a holistic `overall`, with strengths/weaknesses/rationale. Rubric version is stored so
skills can be re-scored and compared when the rubric evolves.

## Roadmap

- **Phase 2:** recommendation (retrieval + Claude rerank), duplicate/overlap clustering, move
  heavy processing into Airflow, version history UI.
- **Phase 3:** synthesize an "ideal" skill from a cluster (`llm/synthesize.py`), export to
  `SKILL.md` / per-client adapters, prepare a PR.
- **Phase 4:** auth, usage telemetry, feedback loop, leaderboards.
