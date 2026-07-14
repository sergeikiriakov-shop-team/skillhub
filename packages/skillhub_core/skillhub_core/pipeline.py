"""Ingest pipeline: parse -> embed -> evaluate -> categorize -> persist.

Used inline by the API (via FastAPI ``BackgroundTasks``) and, in later phases, by Airflow DAGs.
Every step degrades gracefully: missing API key skips LLM steps, missing embedding model skips
the vector."""

from __future__ import annotations

import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import embeddings, repository
from .config import get_settings
from .models import SOURCE_TYPE_UPLOAD, Skill
from .parsing import parse
from .schemas import ParsedSkill, Reference

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    skill_id: int
    version_id: int
    is_new_version: bool
    embedded: bool = False
    evaluated: bool = False
    categorized: bool = False
    notes: list[str] = []


def ingest(
    session: Session,
    parsed: ParsedSkill,
    author: str | None = None,
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
    run_llm: bool = True,
) -> IngestResult:
    """Full pipeline for an already-parsed skill."""
    settings = get_settings()
    skill, version, is_new = repository.upsert_skill(session, parsed, author, source_type, origin)
    result = IngestResult(skill_id=skill.id, version_id=version.id, is_new_version=is_new)

    # --- embedding (local, fail-soft) ---
    vector = embeddings.embed(parsed.searchable_text())
    if vector is not None:
        repository.save_embedding(session, version, vector, settings.embedding_model)
        result.embedded = True
    else:
        result.notes.append("embedding model unavailable")

    # --- LLM evaluation + categorization ---
    if run_llm and settings.llm_enabled:
        try:
            from .llm.evaluate import RUBRIC_VERSION, evaluate_skill

            evaluation = evaluate_skill(parsed)
            repository.save_evaluation(
                session, version, evaluation, settings.skillhub_llm_model, RUBRIC_VERSION
            )
            result.evaluated = True
        except Exception as exc:  # noqa: BLE001 - never fail ingest because of the LLM
            logger.exception("Evaluation failed for skill %s", parsed.name)
            result.notes.append(f"evaluation failed: {exc}")

        try:
            from .llm.categorize import categorize_skill

            taxonomy = repository.get_taxonomy(session)
            categorization = categorize_skill(parsed, taxonomy)
            repository.save_categorization(session, skill, categorization)
            result.categorized = True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Categorization failed for skill %s", parsed.name)
            result.notes.append(f"categorization failed: {exc}")
    elif run_llm:
        result.notes.append("LLM disabled (no ANTHROPIC_API_KEY)")

    session.commit()
    return result


def ingest_raw(
    session: Session,
    content: str,
    author: str | None = None,
    references: list[Reference] | None = None,
    source_format: str = "claude_skill",
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
    run_llm: bool = True,
) -> IngestResult:
    """Parse raw skill content and run the pipeline."""
    parsed = parse(content, source_format=source_format, references=references)
    return ingest(session, parsed, author, source_type, origin, run_llm)


def reprocess(session: Session, skill: Skill, run_llm: bool = True) -> IngestResult:
    """Re-embed / re-evaluate / re-categorize a skill's latest version in place (no new version).
    Used by the batch re-evaluation DAG."""
    settings = get_settings()
    version = skill.latest_version
    if version is None:
        raise ValueError(f"Skill {skill.id} has no versions")

    parsed = ParsedSkill(
        name=skill.name,
        description=version.description,
        trigger_text=version.trigger_text,
        body_md=version.body_md,
        references=[Reference(**r) for r in (version.references or [])],
        section_headings=version.section_headings or [],
        frontmatter=version.frontmatter or {},
        source_format=version.source_format,
        raw_content=version.raw_content,
    )
    result = IngestResult(skill_id=skill.id, version_id=version.id, is_new_version=False)

    vector = embeddings.embed(parsed.searchable_text())
    if vector is not None:
        repository.save_embedding(session, version, vector, settings.embedding_model)
        result.embedded = True

    if run_llm and settings.llm_enabled:
        from .llm.categorize import categorize_skill
        from .llm.evaluate import RUBRIC_VERSION, evaluate_skill

        evaluation = evaluate_skill(parsed)
        repository.save_evaluation(
            session, version, evaluation, settings.skillhub_llm_model, RUBRIC_VERSION
        )
        result.evaluated = True

        categorization = categorize_skill(parsed, repository.get_taxonomy(session))
        repository.save_categorization(session, skill, categorization)
        result.categorized = True

    session.commit()
    return result
