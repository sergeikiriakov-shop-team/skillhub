"""Application service for the Task Review context.

Owns the transaction boundary (commit on every write) and maps missing reviews to the domain
``ReviewNotFound``; the data-coupled rules (author-only, legal transitions) are enforced by the
repository and surface as ``NotReviewAuthor`` / ``InvalidReviewTransition``. Depends only on the
``ReviewRepository`` Protocol, so it is unit-testable with an in-memory fake."""

from __future__ import annotations

from ..platform.models import User
from .errors import ReviewNotFound
from .interfaces import ReviewRepository
from .schemas import ReviewOut, ReviewSubmitIn, ReviewSummary


class ReviewService:
    def __init__(self, reviews: ReviewRepository) -> None:
        self._reviews = reviews

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        review = self._reviews.submit(author, data)
        self._reviews.commit()
        return review

    def list(
        self, *, status: str | None = None, author_id: int | None = None, reviewer_id: int | None = None
    ) -> list[ReviewSummary]:
        return self._reviews.list(status=status, author_id=author_id, reviewer_id=reviewer_id)

    def get(self, review_id: int) -> ReviewOut:
        review = self._reviews.get(review_id)
        if review is None:
            raise ReviewNotFound(f"review {review_id} not found")
        return review

    def submit_result(self, review_id: int, reviewer: User, *, verdict: str, comments: str) -> ReviewOut:
        review = self._reviews.submit_result(review_id, reviewer, verdict, comments)
        if review is None:
            raise ReviewNotFound(f"review {review_id} not found")
        self._reviews.commit()
        return review

    def resubmit(self, review_id: int, user: User, *, commit_shas: list[str], note: str) -> ReviewOut:
        review = self._reviews.resubmit(review_id, user, commit_shas, note)
        if review is None:
            raise ReviewNotFound(f"review {review_id} not found")
        self._reviews.commit()
        return review

    def acknowledge(self, review_id: int, user: User) -> ReviewOut:
        review = self._reviews.acknowledge(review_id, user)
        if review is None:
            raise ReviewNotFound(f"review {review_id} not found")
        self._reviews.commit()
        return review
