"""Curator recommendations — proposed catalog changes (split / merge / dedup / delete /
synthesize), stored so the dashboard can show them and a developer can pick one up and run it.

Reads are open; creating or restatusing one requires a contributor+ token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from skillhub_core import repository
from skillhub_core.constants import REC_KINDS, REC_STATUSES
from skillhub_core.db import get_session
from skillhub_core.models import User
from skillhub_core.schemas import RecommendationIn, RecommendationOut, RecommendationStatusUpdate

from ..auth import require_upload

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    status: str | None = None, session: Session = Depends(get_session)
) -> list[RecommendationOut]:
    return [RecommendationOut.model_validate(r, from_attributes=True) for r in repository.list_recommendations(session, status=status)]


@router.post("/recommendations", response_model=RecommendationOut, status_code=201)
def create_recommendation(
    payload: RecommendationIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_upload),
) -> RecommendationOut:
    if payload.kind not in REC_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {REC_KINDS}")
    rec = repository.create_recommendation(session, payload.model_dump(), created_by=user.name)
    session.commit()
    return RecommendationOut.model_validate(rec, from_attributes=True)


@router.post("/recommendations/{rec_id}/status", response_model=RecommendationOut)
def set_status(
    rec_id: int,
    payload: RecommendationStatusUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_upload),
) -> RecommendationOut:
    if payload.status not in REC_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {REC_STATUSES}")
    rec = repository.set_recommendation_status(session, rec_id, payload.status)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    session.commit()
    return RecommendationOut.model_validate(rec, from_attributes=True)
