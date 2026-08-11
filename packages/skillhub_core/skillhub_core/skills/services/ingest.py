"""Application service for ingest: parse → embed → persist, plus the dedup rules around it."""

from __future__ import annotations

from ...platform.models import User
from ..errors import DuplicateSkill
from ..interfaces import SkillRepository
from ..models import SOURCE_TYPE_UPLOAD
from ..parsing import compute_hash, parse
from ..schemas import ParsedSkill, Reference, SkillDetail


class IngestService:
    """Ingest an uploaded/imported skill: parse → embed → dedupe gate → upsert. Owns the flow and
    (for the API path) the commit; the granular data operations live on the repository. Raises
    :class:`DuplicateSkill` when an upload under a NEW name is essentially identical to an existing
    skill. (Folds the former ``pipeline.py`` module, which is now a thin shim over this service.)"""

    def __init__(self, skills: SkillRepository) -> None:
        self._skills = skills

    def ingest_parsed(
        self,
        parsed: ParsedSkill,
        *,
        author: str | None,
        source_type: str,
        origin: str | None = None,
        user: User | None = None,
    ) -> dict:
        """Run the ingest algorithm for an already-parsed skill (flush only; the caller owns the
        commit). Returns {skill_id, version_id, is_new_version, embedded, similar_warning, notes}."""
        vector = self._skills.embed(parsed.searchable_text())
        # Same-name re-uploads always add a version; only a NEW name is dedupe-gated.
        if not self._skills.name_exists(parsed.name):
            content_hash = compute_hash(parsed.raw_content, parsed.references)
            dup = self._skills.duplicate_for_new_name(parsed.name, content_hash, parsed.body_md, vector)
            if dup is not None:
                raise DuplicateSkill(dup[0], dup[1])
        return self._skills.save_parsed(
            parsed, author=author, source_type=source_type, origin=origin, user=user, vector=vector
        )

    def create(
        self,
        *,
        content: str,
        author: str | None,
        references: list[Reference],
        source_format: str,
        user: User,
    ) -> SkillDetail:
        parsed = parse(content, source_format=source_format, references=references)
        outcome = self.ingest_parsed(
            parsed, author=author, source_type=SOURCE_TYPE_UPLOAD, origin=None, user=user
        )
        self._skills.commit()
        detail = self._skills.get(outcome["skill_id"])
        detail.similar_warning = outcome["similar_warning"]
        return detail




