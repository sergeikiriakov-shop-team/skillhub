"""Ingest pipeline: parse -> embed -> persist.

The service does NOT call an LLM. Evaluation and categorization are produced by Claude Code
and submitted back via the API (POST /api/skills/{id}/assessment). Embeddings are local
(sentence-transformers) and fail-soft: no model -> no vector, the rest still works."""

from __future__ import annotations

import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import embeddings, repository
from .config import get_settings
from .models import SOURCE_TYPE_UPLOAD
from .parsing import parse
from .schemas import ParsedSkill, Reference

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    skill_id: int
    version_id: int
    is_new_version: bool
    embedded: bool = False
    notes: list[str] = []


def ingest(
    session: Session,
    parsed: ParsedSkill,
    author: str | None = None,
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
) -> IngestResult:
    """Parse-provided skill -> upsert version -> embed. Commits."""
    settings = get_settings()
    skill, version, is_new = repository.upsert_skill(session, parsed, author, source_type, origin)
    result = IngestResult(skill_id=skill.id, version_id=version.id, is_new_version=is_new)

    vector = embeddings.embed(parsed.searchable_text())
    if vector is not None:
        repository.save_embedding(session, version, vector, settings.embedding_model)
        result.embedded = True
    else:
        result.notes.append("embedding model unavailable")

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
) -> IngestResult:
    """Parse raw skill content and run the pipeline."""
    parsed = parse(content, source_format=source_format, references=references)
    return ingest(session, parsed, author, source_type, origin)
