"""Repository Protocol for the Recommendation aggregate — the seam its service depends on."""

from __future__ import annotations

from typing import Protocol

from ..schemas import RecommendationOut

class RecommendationRepository(Protocol):
    """Curator recommendations (proposed catalog changes)."""

    def list(
        self, status: str | None, target_kind: str | None = None
    ) -> list[RecommendationOut]: ...

    def create(self, payload: dict, created_by: str | None) -> RecommendationOut:
        """Create a recommendation (flush only; caller commits)."""
        ...

    def set_status(self, rec_id: int, status: str) -> RecommendationOut | None:
        """Update a recommendation's status (flush only; caller commits). None if not found."""
        ...

    def commit(self) -> None: ...




