"""Application service for curator recommendations."""

from __future__ import annotations

from ..constants import REC_KINDS, REC_STATUSES, REC_TARGET_KINDS
from ..errors import InvalidRecommendation, RecommendationNotFound
from ..interfaces import RecommendationRepository
from ..schemas import RecommendationOut


class RecommendationService:
    """Curator recommendations. Validates kind/status (→ :class:`InvalidRecommendation`), owns the
    commit on writes, and raises :class:`RecommendationNotFound` on a missing id."""

    def __init__(self, recommendations: RecommendationRepository) -> None:
        self._recs = recommendations

    def list(
        self, status: str | None = None, target_kind: str | None = None
    ) -> list[RecommendationOut]:
        return self._recs.list(status, target_kind)

    def create(self, payload: dict, *, created_by: str | None) -> RecommendationOut:
        if payload.get("kind") not in REC_KINDS:
            raise InvalidRecommendation(f"kind must be one of {REC_KINDS}")
        if payload.get("target_kind", "skill") not in REC_TARGET_KINDS:
            raise InvalidRecommendation(f"target_kind must be one of {REC_TARGET_KINDS}")
        rec = self._recs.create(payload, created_by)
        self._recs.commit()
        return rec

    def set_status(self, rec_id: int, status: str) -> RecommendationOut:
        if status not in REC_STATUSES:
            raise InvalidRecommendation(f"status must be one of {REC_STATUSES}")
        rec = self._recs.set_status(rec_id, status)
        if rec is None:
            raise RecommendationNotFound(f"recommendation {rec_id} not found")
        self._recs.commit()
        return rec




