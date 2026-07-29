"""Repository Protocols for the Skills context.

These are the seams the application services depend on, so a service can be backed by the
SQLAlchemy repositories in production and by in-memory fakes in tests — no DB, no container.
The concrete SQLAlchemy implementations live in ``skillhub_core.skills.repositories``."""

from __future__ import annotations

from typing import Protocol


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
