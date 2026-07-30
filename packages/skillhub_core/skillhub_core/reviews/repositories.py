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
from .schemas import ReviewOut, ReviewSubmitIn, ReviewSummary


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
