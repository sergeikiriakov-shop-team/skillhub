"""Ingest pipeline: parse -> dedupe-gate -> upsert (by name) -> embed -> persist.

The service does NOT call an LLM. Evaluation and categorization are produced by Claude Code
and submitted back via the API (POST /api/skills/{id}/assessment). Embeddings are local
(sentence-transformers) and fail-soft: no model -> no vector, the rest still works.

Skills are keyed by name (one canonical record per name); re-uploading a name adds a version.
An upload under a NEW name that is essentially identical to an existing skill is rejected
(`DuplicateSkillError`); a merely-similar one is accepted with a `similar_warning`."""

from __future__ import annotations

import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import embeddings, repository
from ..platform.config import get_settings
from ..platform.models import User
from .models import SOURCE_TYPE_UPLOAD
from .parsing import compute_hash, parse
from .schemas import ParsedSkill, Reference

logger = logging.getLogger(__name__)

# A different-named skill at/above this cosine similarity is flagged (not blocked) on upload.
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
    """Parse-provided skill -> dedupe gate -> upsert version -> embed. Commits.

    Raises ``repository.DuplicateSkillError`` if an upload under a new name is identical to an
    existing skill."""
    settings = get_settings()

    content_hash = compute_hash(parsed.raw_content, parsed.references)
    is_new_name = not repository.skill_with_name_exists(session, parsed.name)
    vector = embeddings.embed(parsed.searchable_text())

    # Block an essentially-identical copy under a NEW name (same-name re-uploads are always allowed
    # — they just add a version to the one canonical skill). "Identical" is judged on the skill
    # BODY (the prompt), so merely renaming a copy doesn't slip past; the exact raw-hash check is a
    # cheap fallback. Similar-but-different bodies are allowed (that's the point of the registry).
    if is_new_name:
        dup = repository.find_exact_content_duplicate(session, content_hash, parsed.name)
        if dup is None and vector is not None:
            norm_body = repository.normalize_content(parsed.body_md)
            for cand, _sim in repository.nearest_other_skills(session, vector, parsed.name, limit=3):
                latest = cand.latest_version
                if latest is not None and repository.normalize_content(latest.body_md) == norm_body:
                    dup = cand
                    break
        if dup is not None:
            raise repository.DuplicateSkillError(dup.id, dup.name)

    skill, version, is_new_version = repository.upsert_skill(
        session, parsed, author=author, source_type=source_type, origin=origin, user=user
    )
    result = IngestResult(skill_id=skill.id, version_id=version.id, is_new_version=is_new_version)

    if vector is not None:
        repository.save_embedding(session, version, vector, settings.embedding_model)
        result.embedded = True
        # Warn (don't block) when a different skill is highly similar — variants are welcome.
        neighbours = repository.nearest_other_skills(session, vector, parsed.name, limit=1)
        if neighbours and neighbours[0][1] >= SIMILAR_WARN_THRESHOLD:
            cand, sim = neighbours[0]
            result.similar_warning = {"skill_id": cand.id, "name": cand.name, "similarity": round(sim, 4)}
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
    user: User | None = None,
) -> IngestResult:
    """Parse raw skill content and run the pipeline."""
    parsed = parse(content, source_format=source_format, references=references)
    return ingest(session, parsed, author, source_type, origin, user=user)
