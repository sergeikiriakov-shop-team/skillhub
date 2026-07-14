"""Aggregate statistics for the read-only dashboard (open)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from skillhub_core import repository
from skillhub_core.db import get_session
from skillhub_core.schemas import StatsOut

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(session: Session = Depends(get_session)) -> StatsOut:
    return StatsOut(**repository.stats(session))
