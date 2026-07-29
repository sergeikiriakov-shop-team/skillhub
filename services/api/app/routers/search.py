"""Semantic search over skills (falls back to text search if embeddings are unavailable).

Thin HTTP layer over ``CatalogService``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from skillhub_core.skills.schemas import SearchHit
from skillhub_core.skills.services import CatalogService

from ..deps import get_catalog_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    service: CatalogService = Depends(get_catalog_service),
) -> list[SearchHit]:
    return service.search(q, limit)
