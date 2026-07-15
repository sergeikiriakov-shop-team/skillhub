"""Narrow task-groups (the specific-job layer below the broad categories).

Lets the evaluator reuse an existing group slug when uploading a similar skill, and lets the
dashboard cluster competing skills so a best-of-group can be chosen."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from skillhub_core import repository
from skillhub_core.db import get_session

router = APIRouter(tags=["task-groups"])


class TaskGroupInfo(BaseModel):
    key: str
    count: int
    avg_overall: float | None = None


@router.get("/task-groups", response_model=list[TaskGroupInfo])
def list_task_groups(session: Session = Depends(get_session)) -> list[TaskGroupInfo]:
    return [TaskGroupInfo(**g) for g in repository.task_groups(session)]
