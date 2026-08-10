"""SQLAlchemy-backed repository for the Task Review context.

Injectable (holds a request-scoped :class:`Session`) and satisfies ``ReviewRepository``. Delegates
the workflow + serialization to the query helpers in ``skillhub_core.reviews.repository``; enforces
the author-only rule and translates the infra ``ReviewError`` into the domain
``InvalidReviewTransition``. Flush only — the ``ReviewService`` owns the commit."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..platform.models import User
from . import repository
from .errors import InvalidReviewTransition, NotReviewAuthor
from .schemas import (
    ReviewOut,
    ReviewSubmitIn,
    ReviewSummary,
    SelfReviewFixIn,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)


class SqlReviewRepository:
    """``ReviewRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _detail(self, review_id: int) -> ReviewOut | None:
        review = repository.get_review(self._session, review_id)
        return repository.to_detail(review) if review is not None else None

    @staticmethod
    def _require_author(review, user: User) -> None:
        if review.author_user_id != user.id and not user.is_admin:
            raise NotReviewAuthor("only the review's author may do this")

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        review = repository.submit_review(self._session, author, data)
        return repository.to_detail(repository.get_review(self._session, review.id))

    def list(
        self, *, status: str | None, author_id: int | None, reviewer_id: int | None
    ) -> list[ReviewSummary]:
        rows = repository.list_reviews(
            self._session, status=status, author_id=author_id, reviewer_id=reviewer_id
        )
        return [repository.to_summary(r) for r in rows]

    def get(self, review_id: int) -> ReviewOut | None:
        return self._detail(review_id)

    def submit_result(self, review_id: int, reviewer: User, verdict: str, comments: str) -> ReviewOut | None:
        review = repository.get_review(self._session, review_id)
        if review is None:
            return None
        try:
            repository.submit_result(self._session, review, reviewer, verdict, comments)
        except repository.ReviewError as exc:
            raise InvalidReviewTransition(str(exc)) from exc
        return self._detail(review_id)

    def resubmit(self, review_id: int, user: User, commit_shas: list[str], note: str) -> ReviewOut | None:
        review = repository.get_review(self._session, review_id)
        if review is None:
            return None
        self._require_author(review, user)
        try:
            repository.resubmit(self._session, review, user, commit_shas, note)
        except repository.ReviewError as exc:
            raise InvalidReviewTransition(str(exc)) from exc
        return self._detail(review_id)

    def acknowledge(self, review_id: int, user: User) -> ReviewOut | None:
        review = repository.get_review(self._session, review_id)
        if review is None:
            return None
        self._require_author(review, user)
        repository.acknowledge(self._session, review, user)
        return self._detail(review_id)

    def commit(self) -> None:
        self._session.commit()


class SqlSelfReviewRepository:
    """``SelfReviewRepository`` backed by SQLAlchemy.

    Delegates to the query helpers in ``skillhub_core.reviews.repository``, which own the catalog
    lookups (which skill reviews this lane) and the attach-to-peer-review rule. Flush only — the
    ``SelfReviewService`` owns the commit."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def policy(self) -> SelfReviewPolicyOut:
        return repository.get_policy(self._session)

    def lane_policy(self, lane: str) -> SelfReviewPolicyLane | None:
        return repository.get_lane_policy(self._session, lane)

    def set_policy(
        self, lane: str, skill: str | None, required: bool, admin: User
    ) -> SelfReviewPolicyLane:
        return repository.set_policy(self._session, lane, skill, required, admin)

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        self_review = repository.create_self_review(self._session, author, data)
        return repository.to_self_review_detail(self_review)

    def list(
        self, *, author_id: int | None, task_ref: str | None, review_id: int | None
    ) -> list[SelfReviewSummary]:
        rows = repository.list_self_reviews(
            self._session, author_id=author_id, task_ref=task_ref, review_id=review_id
        )
        return [repository.to_self_review_summary(r) for r in rows]

    def get(self, self_review_id: int) -> SelfReviewOut | None:
        row = repository.get_self_review(self._session, self_review_id)
        return repository.to_self_review_detail(row) if row is not None else None

    def record_fixes(
        self, self_review_id: int, user: User, fixes: list[SelfReviewFixIn]
    ) -> SelfReviewOut | None:
        row = repository.get_self_review(self._session, self_review_id)
        if row is None:
            return None
        repository.record_fixes(self._session, row, user, fixes)
        self._session.refresh(row)
        return repository.to_self_review_detail(row)

    def has_self_review(self, author_id: int, task_ref: str) -> bool:
        return repository.has_self_review(self._session, author_id, task_ref)

    def commit(self) -> None:
        self._session.commit()
