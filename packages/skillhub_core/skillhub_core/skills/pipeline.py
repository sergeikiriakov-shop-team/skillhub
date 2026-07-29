"""Back-compat shim for the ingest pipeline.

The ingest algorithm now lives in :class:`skillhub_core.skills.services.IngestService`
(orchestration + dedupe gate) and ``SqlSkillRepository`` (parse-provided data ops). This module is
kept only so ``skillhub_core.skills.seed`` and any external caller keep importing ``ingest`` /
``ingest_raw`` unchanged — each delegates to the service. The former ``session.commit()`` is now
the caller's responsibility (the seed wraps this in ``session_scope``; the API in ``IngestService``)."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..platform.models import User
from .models import SOURCE_TYPE_UPLOAD
from .schemas import ParsedSkill, Reference

# Kept for back-compat; the live value is ``_SIMILAR_WARN_THRESHOLD`` in skills.repositories.
SIMILAR_WARN_THRESHOLD = 0.90


class IngestResult(BaseModel):
    skill_id: int
    version_id: int
    is_new_version: bool
    embedded: bool = False
    similar_warning: dict | None = None
    notes: list[str] = []


def ingest(
    session: Session,
    parsed: ParsedSkill,
    author: str | None = None,
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
    user: User | None = None,
) -> IngestResult:
    """Run the ingest algorithm for an already-parsed skill (flush only; the caller commits).
    Delegates to :class:`IngestService`; raises ``DuplicateSkill`` for a dup under a new name."""
    from .repositories import SqlSkillRepository
    from .services import IngestService

    outcome = IngestService(SqlSkillRepository(session)).ingest_parsed(
        parsed, author=author, source_type=source_type, origin=origin, user=user
    )
    return IngestResult(**outcome)


def ingest_raw(
    session: Session,
    content: str,
    author: str | None = None,
    references: list[Reference] | None = None,
    source_format: str = "claude_skill",
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
    user: User | None = None,
) -> IngestResult:
    """Parse raw skill content and run the pipeline."""
    from .parsing import parse

    parsed = parse(content, source_format=source_format, references=references)
    return ingest(session, parsed, author, source_type, origin, user=user)
