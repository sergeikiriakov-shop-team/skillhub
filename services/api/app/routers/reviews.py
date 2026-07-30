"""Task Review context — HTTP surface.

Thin layer over ``ReviewService`` (injected via the DI container): a developer submits a
deploy-ready task for review; the lead (``is_reviewer``) picks it off the queue and posts a verdict;
the developer resubmits after fixes or acknowledges an approval. Reviewer role is gated here
(``require_reviewer``); author-only and transition rules are enforced in the service/repository and
mapped to HTTP status.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from skillhub_core.platform.models import User
from skillhub_core.reviews.errors import (
    InvalidReviewTransition,
    NotReviewAuthor,
    ReviewNotFound,
)
from skillhub_core.reviews.schemas import (
    ReviewOut,
    ReviewResubmitIn,
    ReviewResultIn,
    ReviewSubmitIn,
    ReviewSummary,
)
from skillhub_core.reviews.services import ReviewService

from ..auth import require_reviewer, require_user
from ..deps import get_review_service

router = APIRouter(tags=["reviews"], prefix="/reviews")


@router.post("", response_model=ReviewOut, status_code=201)
def submit_review(
    payload: ReviewSubmitIn,
    user: User = Depends(require_user),
    service: ReviewService = Depends(get_review_service),
) -> ReviewOut:
    """Submit a deploy-ready task for review (author = the authenticated user)."""
    return service.submit(user, payload)


@router.get("", response_model=list[ReviewSummary])
def list_reviews(
    status: str | None = Query(default=None),
    mine: bool = Query(default=False),
    queue: bool = Query(default=False),
    user: User = Depends(require_user),
    service: ReviewService = Depends(get_review_service),
) -> list[ReviewSummary]:
    """List reviews. ``mine=true`` = ones you authored; ``queue=true`` = ones assigned to you as
    reviewer awaiting review; ``status`` filters by state."""
    return service.list(
        status=status,
        author_id=user.id if mine else None,
        reviewer_id=user.id if queue else None,
    )


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: int, service: ReviewService = Depends(get_review_service)) -> ReviewOut:
    try:
        return service.get(review_id)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc


@router.post("/{review_id}/result", response_model=ReviewOut)
def submit_result(
    review_id: int,
    payload: ReviewResultIn,
    user: User = Depends(require_reviewer),
    service: ReviewService = Depends(get_review_service),
) -> ReviewOut:
    """Reviewer (lead) posts a verdict: approve | changes_requested (+ comments)."""
    try:
        return service.submit_result(review_id, user, verdict=payload.verdict, comments=payload.comments)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc
    except InvalidReviewTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{review_id}/resubmit", response_model=ReviewOut)
def resubmit(
    review_id: int,
    payload: ReviewResubmitIn,
    user: User = Depends(require_user),
    service: ReviewService = Depends(get_review_service),
) -> ReviewOut:
    """Author resubmits after addressing the feedback (moves the review back into the queue)."""
    try:
        return service.resubmit(review_id, user, commit_shas=payload.commit_shas, note=payload.note)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc
    except NotReviewAuthor as exc:
        raise HTTPException(status_code=403, detail="Only the author may resubmit") from exc
    except InvalidReviewTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{review_id}/ack", response_model=ReviewOut)
def acknowledge(
    review_id: int,
    user: User = Depends(require_user),
    service: ReviewService = Depends(get_review_service),
) -> ReviewOut:
    """Author acknowledges the outcome; an approved review closes (done)."""
    try:
        return service.acknowledge(review_id, user)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc
    except NotReviewAuthor as exc:
        raise HTTPException(status_code=403, detail="Only the author may acknowledge") from exc
