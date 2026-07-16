"""Task Review context — HTTP surface.

A developer submits a deploy-ready task for review; the lead (``is_reviewer``) picks it off the
queue, reviews the branch, and posts a verdict; the developer resubmits after fixes or acknowledges
an approval. Reads follow the platform read-gate; writes have their own role checks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from skillhub_core.platform.db import get_session
from skillhub_core.platform.models import User
from skillhub_core.reviews import repository as reviews
from skillhub_core.reviews.schemas import (
    ReviewOut,
    ReviewResubmitIn,
    ReviewResultIn,
    ReviewSubmitIn,
    ReviewSummary,
)

from ..auth import require_reviewer, require_user

router = APIRouter(tags=["reviews"], prefix="/reviews")


def _get_or_404(session: Session, review_id: int) -> "reviews.Review":
    review = reviews.get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("", response_model=ReviewOut, status_code=201)
def submit_review(
    payload: ReviewSubmitIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReviewOut:
    """Submit a deploy-ready task for review (author = the authenticated user)."""
    review = reviews.submit_review(session, user, payload)
    session.commit()
    return reviews.to_detail(_get_or_404(session, review.id))


@router.get("", response_model=list[ReviewSummary])
def list_reviews(
    status: str | None = Query(default=None),
    mine: bool = Query(default=False),
    queue: bool = Query(default=False),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[ReviewSummary]:
    """List reviews. ``mine=true`` = ones you authored; ``queue=true`` = ones assigned to you as
    reviewer (or unassigned) awaiting review; ``status`` filters by state."""
    author_id = user.id if mine else None
    reviewer_id = user.id if queue else None
    rows = reviews.list_reviews(session, status=status, author_id=author_id, reviewer_id=reviewer_id)
    return [reviews.to_summary(r) for r in rows]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: int, session: Session = Depends(get_session)) -> ReviewOut:
    return reviews.to_detail(_get_or_404(session, review_id))


@router.post("/{review_id}/result", response_model=ReviewOut)
def submit_result(
    review_id: int,
    payload: ReviewResultIn,
    user: User = Depends(require_reviewer),
    session: Session = Depends(get_session),
) -> ReviewOut:
    """Reviewer (lead) posts a verdict: approve | changes_requested (+ comments)."""
    review = _get_or_404(session, review_id)
    try:
        reviews.submit_result(session, review, user, payload.verdict, payload.comments)
    except reviews.ReviewError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return reviews.to_detail(_get_or_404(session, review_id))


@router.post("/{review_id}/resubmit", response_model=ReviewOut)
def resubmit(
    review_id: int,
    payload: ReviewResubmitIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReviewOut:
    """Author resubmits after addressing the feedback (moves the review back into the queue)."""
    review = _get_or_404(session, review_id)
    if review.author_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only the author may resubmit")
    try:
        reviews.resubmit(session, review, user, payload.commit_shas, payload.note)
    except reviews.ReviewError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return reviews.to_detail(_get_or_404(session, review_id))


@router.post("/{review_id}/ack", response_model=ReviewOut)
def acknowledge(
    review_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReviewOut:
    """Author acknowledges the outcome; an approved review closes (done)."""
    review = _get_or_404(session, review_id)
    if review.author_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only the author may acknowledge")
    reviews.acknowledge(session, review, user)
    session.commit()
    return reviews.to_detail(_get_or_404(session, review_id))
