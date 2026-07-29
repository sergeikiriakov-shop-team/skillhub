"""Aggregate statistics for the read-only dashboard (open). Thin HTTP layer over ``CatalogService``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from skillhub_core.skills.schemas import StatsOut
from skillhub_core.skills.services import CatalogService

from ..deps import get_catalog_service

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(service: CatalogService = Depends(get_catalog_service)) -> StatsOut:
    return service.stats()
