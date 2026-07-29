"""Narrow task-groups (the specific-job layer below the broad categories).

Lets the evaluator reuse an existing group slug when uploading a similar skill, and lets the
dashboard cluster competing skills so a best-of-group can be chosen. Thin HTTP layer over
``CatalogService``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from skillhub_core.skills.schemas import TaskGroupInfo
from skillhub_core.skills.services import CatalogService

from ..deps import get_catalog_service

router = APIRouter(tags=["task-groups"])


@router.get("/task-groups", response_model=list[TaskGroupInfo])
def list_task_groups(service: CatalogService = Depends(get_catalog_service)) -> list[TaskGroupInfo]:
    return service.task_groups()
