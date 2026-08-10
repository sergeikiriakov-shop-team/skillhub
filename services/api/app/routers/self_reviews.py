"""Self-review — HTTP surface.

A developer reviews their OWN change with a skill the team picked once, server-side: the admin
points each lane (default/backend/frontend) at a catalog skill, and every developer's Claude Code
applies that same SKILL.md to its diff and posts the report back here. Same split as the rest of
SkillHub — the strategy (which skill, is it mandatory) lives in the service; the reviewing itself
happens in the developer's own Claude Code.

Thin layer over ``SelfReviewService`` (injected via the DI container); domain errors are mapped to
HTTP status here. Mounted at ``/self-reviews`` rather than under ``/reviews`` so nothing collides
with ``/reviews/{review_id}``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from skillhub_core.platform.models import User
from skillhub_core.reviews.errors import (
    InvalidSelfReview,
    NotReviewAuthor,
    SelfReviewNotFound,
    SelfReviewPolicyNotSet,
    UnknownReviewSkill,
)
from skillhub_core.reviews.schemas import (
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewPolicyUpdate,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)
from skillhub_core.reviews.services import SelfReviewService

from ..auth import require_admin, require_user
from ..deps import get_self_review_service

router = APIRouter(tags=["self-reviews"], prefix="/self-reviews")


# NOTE: declared before ``/{self_review_id}`` so the literal path wins the match.
@router.get("/policy", response_model=SelfReviewPolicyOut)
def get_policy(
    service: SelfReviewService = Depends(get_self_review_service),
) -> SelfReviewPolicyOut:
    """Which catalog skill self-reviews each lane, and whether it is mandatory before handing a task
    to the lead. Claude Code reads this, then fetches that skill with ``get_skill``."""
    return service.get_policy()


@router.put("/policy", response_model=SelfReviewPolicyLane)
def set_policy(
    payload: SelfReviewPolicyUpdate,
    service: SelfReviewService = Depends(get_self_review_service),
    admin: User = Depends(require_admin),
) -> SelfReviewPolicyLane:
    """Admin-only: point one lane at the skill that reviews it (``skill: null`` unsets the lane)."""
    try:
        return service.set_policy(
            admin, lane=payload.lane, skill=payload.skill, required=payload.required
        )
    except UnknownReviewSkill as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidSelfReview as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=SelfReviewOut, status_code=201)
def submit_self_review(
    payload: SelfReviewSubmitIn,
    user: User = Depends(require_user),
    service: SelfReviewService = Depends(get_self_review_service),
) -> SelfReviewOut:
    """Record the result of reviewing your own change with the lane's skill. Attaches to your open
    peer review of the same task when there is one (and to a later one when you submit it)."""
    try:
        return service.submit(user, payload)
    except UnknownReviewSkill as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidSelfReview as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotReviewAuthor as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SelfReviewPolicyNotSet as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[SelfReviewSummary])
def list_self_reviews(
    mine: bool = Query(default=False, description="Only the ones you ran."),
    task_ref: str | None = Query(default=None, description="Filter by task."),
    review_id: int | None = Query(default=None, description="Only those attached to this review."),
    user: User = Depends(require_user),
    service: SelfReviewService = Depends(get_self_review_service),
) -> list[SelfReviewSummary]:
    return service.list(
        author_id=user.id if mine else None, task_ref=task_ref, review_id=review_id
    )


@router.get("/{self_review_id}", response_model=SelfReviewOut)
def get_self_review(
    self_review_id: int,
    service: SelfReviewService = Depends(get_self_review_service),
) -> SelfReviewOut:
    """One self-review with its full findings list."""
    try:
        return service.get(self_review_id)
    except SelfReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Self-review not found") from exc
