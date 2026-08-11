"""Review aggregate → DTOs."""

from __future__ import annotations

from ..models import Review, ReviewEvent
from ..schemas import ReviewEventOut, ReviewOut, ReviewSummary
from .self_review import to_summary as self_review_summary


def _event_out(ev: ReviewEvent) -> ReviewEventOut:
    return ReviewEventOut(
        id=ev.id,
        kind=ev.kind,
        author=ev.author.name if ev.author else None,
        verdict=ev.verdict,
        body=ev.body,
        created_at=ev.created_at,
        self_review_id=ev.self_review_id,
    )


def to_summary(review: Review) -> ReviewSummary:
    return ReviewSummary(
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
        **to_summary(review).model_dump(),
        created_at=review.created_at,
        commit_shas=list(review.commit_shas or []),
        summary=review.summary,
        files=list(review.files or []),
        verified_notes=review.verified_notes,
        events=[_event_out(e) for e in review.events],
        self_reviews=[self_review_summary(sr) for sr in review.self_reviews],
    )
