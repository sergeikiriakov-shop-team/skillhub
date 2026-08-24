"""The review board — HTTP surface.

One flow: the developer runs the self-review skill, each run lands on its task here, and the lead
either approves the task or sends it back with a reason. There is no separate hand-over step —
a task reaches the board by being reviewed.

Thin layer over ``TaskReviewService``; domain errors are mapped to HTTP status here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from skillhub_core.platform.models import User
from skillhub_core.reviews.errors import (
    InvalidReviewTransition,
    NotReviewAuthor,
    TaskReviewNotFound,
)
from skillhub_core.reviews.schemas import TaskReviewOut, TaskReviewReturnIn, TaskReviewSummary
from skillhub_core.reviews.services import TaskReviewService

from ..auth import require_reviewer, require_user
from ..deps import get_task_review_service

router = APIRouter(tags=["task-reviews"], prefix="/task-reviews")


@router.get("", response_model=list[TaskReviewSummary])
def list_task_reviews(
    status: str | None = Query(default=None, description="changes_needed | passed | approved."),
    mine: bool = Query(default=False, description="Only tasks you self-reviewed."),
    user: User = Depends(require_user),
    service: TaskReviewService = Depends(get_task_review_service),
) -> list[TaskReviewSummary]:
    """The board. `status=passed` is the lead's queue: self-review clean, waiting for a sign-off."""
    return service.list(status=status, author_id=user.id if mine else None)


@router.get("/{task_review_id}", response_model=TaskReviewOut)
def get_task_review(
    task_review_id: int,
    service: TaskReviewService = Depends(get_task_review_service),
) -> TaskReviewOut:
    """One task with its run history and the latest run's findings."""
    try:
        return service.get(task_review_id)
    except TaskReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Task review not found") from exc


@router.post("/{task_review_id}/approve", response_model=TaskReviewOut)
def approve_task_review(
    task_review_id: int,
    lead: User = Depends(require_reviewer),
    service: TaskReviewService = Depends(get_task_review_service),
) -> TaskReviewOut:
    """The lead signs the task off. Rejected with 409 when there is no run to approve, when it is
    already approved, or when the policy requires a clean run this task has not had."""
    try:
        return service.approve(task_review_id, lead)
    except TaskReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Task review not found") from exc
    except InvalidReviewTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_review_id}/return", response_model=TaskReviewOut)
def return_task_review(
    task_review_id: int,
    payload: TaskReviewReturnIn,
    lead: User = Depends(require_reviewer),
    service: TaskReviewService = Depends(get_task_review_service),
) -> TaskReviewOut:
    """The lead sends the task back to its author. The comment is required."""
    try:
        return service.send_back(task_review_id, lead, comment=payload.comment)
    except TaskReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Task review not found") from exc
    except InvalidReviewTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{task_review_id}", status_code=204, response_class=Response)
def delete_task_review(
    task_review_id: int,
    user: User = Depends(require_user),
    service: TaskReviewService = Depends(get_task_review_service),
) -> Response:
    """Remove a task and its runs from the board. The author may while it is unapproved; after a
    sign-off only an admin may, so an approval cannot be quietly erased."""
    try:
        service.delete(task_review_id, user)
    except TaskReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Task review not found") from exc
    except NotReviewAuthor as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidReviewTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
