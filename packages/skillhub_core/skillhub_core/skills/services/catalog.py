"""Application service for the catalog read-model: search, stats, task groups, categories."""

from __future__ import annotations

from ..interfaces import CatalogRepository
from ..schemas import CategoryInfo, SearchHit, StatsOut, TaskGroupInfo


class CatalogService:
    """Read-only catalog queries (search / stats / task-groups / categories). No transaction
    boundary — a thin seam over the repository so routers stay free of the session and query module."""

    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        return self._catalog.search(query, limit)

    def stats(self) -> StatsOut:
        return self._catalog.stats()

    def task_groups(self) -> list[TaskGroupInfo]:
        return self._catalog.task_groups()

    def categories(self) -> list[CategoryInfo]:
        return self._catalog.categories()


