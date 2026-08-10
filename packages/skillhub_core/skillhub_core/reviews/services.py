"""Application service for the Task Review context.

Owns the transaction boundary (commit on every write) and maps missing reviews to the domain
``ReviewNotFound``; the data-coupled rules (author-only, legal transitions) are enforced by the
repository and surface as ``NotReviewAuthor`` / ``InvalidReviewTransition``. Depends only on the
``ReviewRepository`` Protocol, so it is unit-testable with an in-memory fake."""

from __future__ import annotations

from ..platform.models import User
from .errors import ReviewNotFound, SelfReviewNotFound
from .interfaces import ReviewRepository, SelfReviewRepository
from .schemas import (
    ReviewOut,
    ReviewSubmitIn,
    ReviewSummary,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)


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


class SelfReviewService:
    """Application service for skill-driven self-review.

    Same shape as ``ReviewService``: owns the transaction boundary and maps a missing self-review to
    ``SelfReviewNotFound``; the catalog- and policy-coupled rules (which skill reviews a lane, is the
    skill real, is the finding severity known) are enforced by the repository and surface as
    ``UnknownReviewSkill`` / ``SelfReviewPolicyNotSet`` / ``InvalidSelfReview``."""

    def __init__(self, self_reviews: SelfReviewRepository) -> None:
        self._self_reviews = self_reviews

    def get_policy(self) -> SelfReviewPolicyOut:
        return self._self_reviews.policy()

    def get_lane_policy(self, lane: str) -> SelfReviewPolicyLane | None:
        return self._self_reviews.lane_policy(lane)

    def set_policy(
        self, admin: User, *, lane: str, skill: str | None, required: bool
    ) -> SelfReviewPolicyLane:
        updated = self._self_reviews.set_policy(lane, skill, required, admin)
        self._self_reviews.commit()
        return updated

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        self_review = self._self_reviews.submit(author, data)
        self._self_reviews.commit()
        return self_review

    def list(
        self,
        *,
        author_id: int | None = None,
        task_ref: str | None = None,
        review_id: int | None = None,
    ) -> list[SelfReviewSummary]:
        return self._self_reviews.list(author_id=author_id, task_ref=task_ref, review_id=review_id)

    def get(self, self_review_id: int) -> SelfReviewOut:
        self_review = self._self_reviews.get(self_review_id)
        if self_review is None:
            raise SelfReviewNotFound(f"self-review {self_review_id} not found")
        return self_review
