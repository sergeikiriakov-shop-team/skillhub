"""Read-only catalog DTOs: search hits, task-group and category listings.

Previously defined inline in the API routers; moved here so the (thin) routers and the
``CatalogService`` share one definition and the services stay framework-agnostic."""

from __future__ import annotations

from pydantic import BaseModel

from .skill import SkillSummary


class SearchHit(BaseModel):
    skill: SkillSummary
    similarity: float | None = None


class TaskGroupInfo(BaseModel):
    key: str
    count: int
    avg_overall: float | None = None


class CategoryInfo(BaseModel):
    key: str
    label: str
    description: str
    skill_count: int
