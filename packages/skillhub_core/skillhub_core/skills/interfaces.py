"""Repository Protocols for the Skills context.

These are the seams the application services depend on, so a service can be backed by the
SQLAlchemy repositories in production and by in-memory fakes in tests — no DB, no container.
The concrete SQLAlchemy implementations live in ``skillhub_core.skills.repositories``."""

from __future__ import annotations

from typing import Protocol

from ..platform.models import User
from .schemas import (
    CategoryInfo,
    EvaluationOut,
    ParsedSkill,
    RecommendationOut,
    SearchHit,
    SkillDetail,
    SkillSummary,
    StatsOut,
    TaskGroupInfo,
)


class RubricRepository(Protocol):
    """Persistence for the admin-managed rubric weights and the category taxonomy."""

    def get_weights(self) -> dict[str, float]: ...

    def set_weights(self, weights: dict[str, float]) -> dict[str, float]: ...

    def recompute_overall_scores(self) -> int: ...

    def get_taxonomy(self) -> list[dict]: ...

    def commit(self) -> None:
        """Commit the current unit of work (the service owns the transaction boundary)."""
        ...


class NotebookRepository(Protocol):
    """Persistence for the sandbox-trial notebooks attached to a skill, one per executing model."""

    def get(self, skill_id: int, model: str) -> dict | None:
        """The (skill, model) notebook as plain data (with a computed ``stale`` flag), or None."""
        ...

    def list_for_skill(self, skill_id: int) -> list[dict]:
        """Every model's trial for the skill (the effectiveness matrix), best-model first."""
        ...

    def upsert(
        self,
        *,
        skill_id: int,
        model: str,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> dict | None:
        """Create/replace the (skill, model) notebook; None if the skill does not exist."""
        ...

    def commit(self) -> None: ...


class SkillRepository(Protocol):
    """Read/list/delete + the ingest primitives for the skill catalog. Read methods return API DTOs
    (not ORM) so services stay DB-free and fakeable; the ingest primitives are the granular data
    operations the ``IngestService`` orchestrates."""

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]: ...

    def get(self, skill_id: int) -> SkillDetail | None: ...

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


class EvaluationRepository(Protocol):
    """Evaluation history + assessment submission for a skill."""

    def list_for_skill(self, skill_id: int) -> list[EvaluationOut] | None:
        """The skill's evaluations, or None if the skill does not exist."""
        ...

    def save_assessment(
        self,
        *,
        skill_id: int,
        evaluation: dict,
        model: str,
        rubric_version: str,
        categorization: dict | None,
    ) -> SkillDetail | None:
        """Persist an evaluation (+ optional categorization) and return the refreshed detail
        (flush only; caller commits). None if the skill does not exist / has no version."""
        ...

    def commit(self) -> None: ...


class RecommendationRepository(Protocol):
    """Curator recommendations (proposed catalog changes)."""

    def list(self, status: str | None) -> list[RecommendationOut]: ...

    def create(self, payload: dict, created_by: str | None) -> RecommendationOut:
        """Create a recommendation (flush only; caller commits)."""
        ...

    def set_status(self, rec_id: int, status: str) -> RecommendationOut | None:
        """Update a recommendation's status (flush only; caller commits). None if not found."""
        ...

    def commit(self) -> None: ...


class CatalogRepository(Protocol):
    """Read-only catalog queries: semantic/text search, dashboard stats, task-group and category
    listings. All return API DTOs."""

    def search(self, query: str, limit: int) -> list[SearchHit]: ...

    def stats(self) -> StatsOut: ...

    def task_groups(self) -> list[TaskGroupInfo]: ...

    def categories(self) -> list[CategoryInfo]: ...
