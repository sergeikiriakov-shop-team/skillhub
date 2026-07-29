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
    RecommendationOut,
    Reference,
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
    """Persistence for the one sandbox-trial notebook attached to each skill."""

    def get(self, skill_id: int) -> dict | None:
        """The skill's notebook as plain data (with a computed ``stale`` flag), or None."""
        ...

    def upsert(
        self,
        *,
        skill_id: int,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> dict | None:
        """Create/replace the skill's notebook; None if the skill does not exist."""
        ...

    def commit(self) -> None: ...


class SkillRepository(Protocol):
    """Read/list/ingest/delete for the skill catalog. Returns API DTOs (not ORM) so services stay
    DB-free and fakeable."""

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]: ...

    def get(self, skill_id: int) -> SkillDetail | None: ...

    def create(
        self,
        *,
        content: str,
        author: str | None,
        references: list[Reference],
        source_format: str,
        user: User,
    ) -> SkillDetail:
        """Ingest raw skill content (parse → dedupe gate → upsert → embed) and return the detail.
        Raises ``repository.DuplicateSkillError`` for an identical upload under a new name."""
        ...

    def delete(self, skill_id: int) -> bool:
        """Delete a skill (flush only; caller commits). False if it does not exist."""
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
