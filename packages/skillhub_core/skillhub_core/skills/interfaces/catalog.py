"""Repository Protocol for the catalog read-model aggregate — the seam its service depends on."""

from __future__ import annotations

from typing import Protocol

from ..schemas import CategoryInfo, SearchHit, SkillSummary, StatsOut, TaskGroupInfo

class CatalogRepository(Protocol):
    """Read-only catalog queries: semantic/text search, dashboard stats, task-group and category
    listings. All return API DTOs."""

    def search(self, query: str, limit: int) -> list[SearchHit]: ...

    def stats(self) -> StatsOut: ...

    def task_groups(self) -> list[TaskGroupInfo]: ...

    def categories(self) -> list[CategoryInfo]: ...


