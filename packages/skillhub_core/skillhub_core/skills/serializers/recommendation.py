"""Recommendation aggregate → DTOs."""

from __future__ import annotations

from ..models import Recommendation
from ..schemas import RecommendationOut


def _recommendation_to_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        target_kind=rec.target_kind,
        kind=rec.kind,
        title=rec.title,
        rationale=rec.rationale,
        scope=rec.scope,
        targets=rec.targets or [],
        suggested_action=rec.suggested_action,
        anchor=rec.anchor,
        status=rec.status,
        created_by=rec.created_by,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )




