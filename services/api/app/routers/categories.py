"""Taxonomy listing with per-category skill counts. Thin HTTP layer over ``CatalogService``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from skillhub_core.skills.schemas import CategoryInfo
from skillhub_core.skills.services import CatalogService

from ..deps import get_catalog_service

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryInfo])
def list_categories(service: CatalogService = Depends(get_catalog_service)) -> list[CategoryInfo]:
    return service.categories()
