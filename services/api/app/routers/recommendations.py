"""Curator recommendations — proposed catalog changes (split / merge / dedup / delete /
synthesize), stored so the dashboard can show them and a developer can pick one up and run it.

Thin HTTP layer over ``RecommendationService``: reads are open; creating or restatusing one
requires a contributor+ token, and the service validates kind/status + owns the commit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from skillhub_core.platform.models import User
from skillhub_core.skills.errors import InvalidRecommendation, RecommendationNotFound
from skillhub_core.skills.schemas import RecommendationIn, RecommendationOut, RecommendationStatusUpdate
from skillhub_core.skills.services import RecommendationService

from ..auth import require_upload
from ..deps import get_recommendation_service

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    status: str | None = None,
    target_kind: str | None = None,
    service: RecommendationService = Depends(get_recommendation_service),
) -> list[RecommendationOut]:
    return service.list(status, target_kind)


@router.post("/recommendations", response_model=RecommendationOut, status_code=201)
def create_recommendation(
    payload: RecommendationIn,
    service: RecommendationService = Depends(get_recommendation_service),
    user: User = Depends(require_upload),
) -> RecommendationOut:
    try:
        return service.create(payload.model_dump(), created_by=user.name)
    except InvalidRecommendation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommendations/{rec_id}/status", response_model=RecommendationOut)
def set_status(
    rec_id: int,
    payload: RecommendationStatusUpdate,
    service: RecommendationService = Depends(get_recommendation_service),
    _: User = Depends(require_upload),
) -> RecommendationOut:
    try:
        return service.set_status(rec_id, payload.status)
    except InvalidRecommendation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecommendationNotFound as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found") from exc
