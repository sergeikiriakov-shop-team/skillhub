"""Task Review context — application/data-access layer: the review workflow + serialization.

State machine: submit -> (reviewer) approve|changes_requested -> (author) resubmit -> submit ...,
and approve -> (author) ack -> done. The lead is the single ``is_reviewer`` user, auto-assigned at
submit time; the code itself lives in git (a Review only carries a pointer + summary)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..platform.models import User
from .models import (
    EVENT_ACK,
    EVENT_RESUBMIT,
    EVENT_SUBMIT,
    EVENT_VERDICT,
    REVIEW_APPROVED,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_DONE,
    REVIEW_SUBMITTED,
    VERDICT_APPROVE,
    VERDICT_CHANGES,
    Review,
    ReviewEvent,
)
from .schemas import ReviewEventOut, ReviewOut
from .schemas import ReviewSummary as ReviewSummaryOut


class ReviewError(Exception):
    """Invalid review-workflow transition (e.g. approving a review that is not awaiting review)."""


def _default_reviewer(session: Session) -> User | None:
    """The single lead: the first user flagged ``is_reviewer``. None if none is designated yet."""
    return session.scalars(
        select(User).where(User.is_reviewer.is_(True)).order_by(User.id)
    ).first()


def _loaded(session: Session, review_id: int) -> Review | None:
    return session.scalars(
        select(Review)
        .where(Review.id == review_id)
        .options(
            selectinload(Review.author),
            selectinload(Review.reviewer),
            selectinload(Review.events).selectinload(ReviewEvent.author),
        )
    ).first()


def submit_review(session: Session, author: User, data) -> Review:
    """Create a review (status ``submitted``) with a submit event; auto-assign the lead."""
    reviewer = _default_reviewer(session)
    review = Review(
        task_ref=data.task_ref,
        title=data.title or "",
        branch=data.branch,
        commit_shas=list(data.commit_shas or []),
        summary=data.summary or "",
        files=list(data.files or []),
        verified_notes=data.verified_notes or "",
        status=REVIEW_SUBMITTED,
        author_user_id=author.id,
        reviewer_user_id=reviewer.id if reviewer else None,
    )
    session.add(review)
    session.flush()
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_SUBMIT, author_user_id=author.id, body=data.summary or "")
    )
    session.flush()
    return review


def list_reviews(
    session: Session,
    *,
    status: str | None = None,
    author_id: int | None = None,
    reviewer_id: int | None = None,
) -> list[Review]:
    stmt = select(Review).options(selectinload(Review.author), selectinload(Review.reviewer))
    if status:
        stmt = stmt.where(Review.status == status)
    if author_id is not None:
        stmt = stmt.where(Review.author_user_id == author_id)
    if reviewer_id is not None:
        stmt = stmt.where(Review.reviewer_user_id == reviewer_id)
    return list(session.scalars(stmt.order_by(Review.updated_at.desc())).all())


def get_review(session: Session, review_id: int) -> Review | None:
    return _loaded(session, review_id)


def submit_result(session: Session, review: Review, reviewer: User, verdict: str, comments: str) -> Review:
    """Record the lead's verdict. ``approve`` -> approved; ``changes_requested`` -> changes_requested
    (comments required). Only a review awaiting review (submitted) can be decided."""
    if review.status != REVIEW_SUBMITTED:
        raise ReviewError(f"review {review.id} is not awaiting review (status={review.status})")
    if verdict == VERDICT_APPROVE:
        review.status = REVIEW_APPROVED
    elif verdict == VERDICT_CHANGES:
        if not comments.strip():
            raise ReviewError("changes_requested requires comments")
        review.status = REVIEW_CHANGES_REQUESTED
    else:
        raise ReviewError(f"unknown verdict '{verdict}'")
    review.reviewer_user_id = reviewer.id
    session.add(
        ReviewEvent(
            review_id=review.id, kind=EVENT_VERDICT, author_user_id=reviewer.id, verdict=verdict, body=comments
        )
    )
    session.flush()
    return review


def resubmit(session: Session, review: Review, author: User, commit_shas: list[str], note: str) -> Review:
    """Author sends the task back for another round after addressing the feedback."""
    if review.status not in (REVIEW_CHANGES_REQUESTED, REVIEW_APPROVED):
        raise ReviewError(f"review {review.id} cannot be resubmitted (status={review.status})")
    if commit_shas:
        review.commit_shas = list(commit_shas)
    review.status = REVIEW_SUBMITTED
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_RESUBMIT, author_user_id=author.id, body=note)
    )
    session.flush()
    return review


def acknowledge(session: Session, review: Review, author: User, note: str = "") -> Review:
    """Author acknowledges the outcome. An approved review closes (``done``)."""
    if review.status == REVIEW_APPROVED:
        review.status = REVIEW_DONE
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_ACK, author_user_id=author.id, body=note)
    )
    session.flush()
    return review


# --- serialization -----------------------------------------------------------------------------


def _event_out(ev: ReviewEvent) -> ReviewEventOut:
    return ReviewEventOut(
        id=ev.id,
        kind=ev.kind,
        author=ev.author.name if ev.author else None,
        verdict=ev.verdict,
        body=ev.body,
        created_at=ev.created_at,
    )


def to_summary(review: Review) -> ReviewSummaryOut:
    return ReviewSummaryOut(
        id=review.id,
        task_ref=review.task_ref,
        title=review.title,
        branch=review.branch,
        status=review.status,
        author=review.author.name if review.author else None,
        reviewer=review.reviewer.name if review.reviewer else None,
        updated_at=review.updated_at,
    )


def to_detail(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        task_ref=review.task_ref,
        title=review.title,
        branch=review.branch,
        status=review.status,
        author=review.author.name if review.author else None,
        reviewer=review.reviewer.name if review.reviewer else None,
        updated_at=review.updated_at,
        created_at=review.created_at,
        commit_shas=list(review.commit_shas or []),
        summary=review.summary,
        files=list(review.files or []),
        verified_notes=review.verified_notes,
        events=[_event_out(e) for e in review.events],
    )
