"""Repository Protocol for the Skill aggregate — the seam its service depends on."""

from __future__ import annotations

from typing import Protocol

from ...platform.models import User
from ..schemas import ParsedSkill, SkillDetail, SkillSummary

class SkillRepository(Protocol):
    """Read/list/delete + the ingest primitives for the skill catalog. Read methods return API DTOs
    (not ORM) so services stay DB-free and fakeable; the ingest primitives are the granular data
    operations the ``IngestService`` orchestrates."""

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]: ...

    def get(self, skill_id: int, *, include_references: bool = True) -> SkillDetail | None:
        """The skill's full detail. ``include_references=False`` omits the reference FILES (the
        heaviest part of the payload) while keeping ``references_count`` accurate."""
        ...

    def delete(self, skill_id: int) -> bool:
        """Delete a skill (flush only; caller commits). False if it does not exist."""
        ...

    # --- ingest primitives (orchestrated by IngestService) ---
    def embed(self, text: str) -> list[float] | None:
        """Embed searchable text (None when the embedding model is unavailable)."""
        ...

    def name_exists(self, name: str) -> bool: ...

    def duplicate_for_new_name(
        self, name: str, content_hash: str, body_md: str, vector: list[float] | None
    ) -> tuple[int, str] | None:
        """(id, name) of an essentially-identical existing skill under a DIFFERENT name, else None."""
        ...

    def save_parsed(
        self,
        parsed: ParsedSkill,
        *,
        author: str | None,
        source_type: str,
        origin: str | None,
        user: User | None,
        vector: list[float] | None,
    ) -> dict:
        """Upsert the skill version + embedding (flush only; caller commits). Returns
        {skill_id, version_id, is_new_version, embedded, similar_warning, notes}."""
        ...

    def commit(self) -> None: ...




