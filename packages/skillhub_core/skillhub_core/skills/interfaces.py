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
