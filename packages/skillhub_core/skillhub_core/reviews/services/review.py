"""Application service for the Review aggregate.

Owns the transaction boundary, maps a missing review to ``ReviewNotFound``, and enforces the one
rule that spans two aggregates — "a task may not reach the lead without a self-review when the
policy demands one". That check sits here rather than in either repository because it reads the
SelfReviewPolicy to decide something about a Review: coordinating aggregates is precisely what an
application service is for."""

from __future__ import annotations

from ...platform.models import User
from ..errors import ReviewNotFound, SelfReviewRequired
from ..interfaces import ReviewRepository, SelfReviewPolicyRepository, SelfReviewRepository
from ..schemas import ReviewOut, ReviewSubmitIn, ReviewSummary


class ReviewService:
    def __init__(
        self,
        reviews: ReviewRepository,
        self_reviews: SelfReviewRepository,
        policies: SelfReviewPolicyRepository,
    ) -> None:
        self._reviews = reviews
        self._self_reviews = self_reviews
        self._policies = policies

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        if self._policies.self_review_required() and not self._self_reviews.has_self_review(
            author.id, data.task_ref
        ):
            raise SelfReviewRequired(
                f"self-review is required before handing {data.task_ref} to the lead — run the "
                "configured review skill and post it with submit_self_review"
            )
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

    def delete(self, review_id: int, user: User) -> None:
        if not self._reviews.delete(review_id, user):
            raise ReviewNotFound(f"review {review_id} not found")
        self._reviews.commit()
