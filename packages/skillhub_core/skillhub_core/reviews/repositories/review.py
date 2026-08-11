"""Persistence for the Review aggregate.

Queries and loading only. The workflow rules — which transitions are legal, what a verdict does to
the status, what lands in the thread — live on the ``Review`` aggregate; this layer just hands it
the arguments and saves the result. Flush only: the service owns the commit."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...platform.models import User
from ..errors import NotReviewAuthor
from ..models import REVIEW_SUBMITTED, Review, ReviewEvent, SelfReview
from ..schemas import ReviewOut, ReviewSubmitIn, ReviewSummary
from ..serializers import review as serializer


class SqlReviewRepository:
    """``ReviewRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- loading ---------------------------------------------------------------------------------

    def _loaded(self, review_id: int) -> Review | None:
        return self._session.scalars(
            select(Review)
            .where(Review.id == review_id)
            .options(
                selectinload(Review.author),
                selectinload(Review.reviewer),
                selectinload(Review.events).selectinload(ReviewEvent.author),
                selectinload(Review.self_reviews).selectinload(SelfReview.author),
            )
        ).first()

    def _detail(self, review_id: int) -> ReviewOut | None:
        review = self._loaded(review_id)
        return serializer.to_detail(review) if review is not None else None

    def _default_reviewer(self) -> User | None:
        """The single lead: the first user flagged ``is_reviewer``. None if none is designated."""
        return self._session.scalars(
            select(User).where(User.is_reviewer.is_(True)).order_by(User.id)
        ).first()

    @staticmethod
    def _require_author(review: Review, user: User) -> None:
        if review.author_user_id != user.id and not user.is_admin:
            raise NotReviewAuthor("only the review's author may do this")

    # --- writes ----------------------------------------------------------------------------------

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        reviewer = self._default_reviewer()
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
        self._session.add(review)
        self._session.flush()
        review.open_for_review(author.id, data.summary or "")
        self._attach_self_reviews(review, author)
        self._session.flush()
        return self._detail(review.id)

    def _attach_self_reviews(self, review: Review, author: User) -> int:
        """Pick up the author's unattached self-reviews of this task. Cross-aggregate by nature —
        finding them is a query, linking them is the Review's own business."""
        orphans = list(
            self._session.scalars(
                select(SelfReview)
                .where(
                    SelfReview.author_user_id == author.id,
                    SelfReview.task_ref == review.task_ref,
                    SelfReview.review_id.is_(None),
                )
                .order_by(SelfReview.id)
            ).all()
        )
        for self_review in orphans:
            review.attach_self_review(self_review, author.id)
        return len(orphans)

    def submit_result(self, review_id: int, reviewer: User, verdict: str, comments: str) -> ReviewOut | None:
        review = self._loaded(review_id)
        if review is None:
            return None
        review.decide(reviewer.id, verdict, comments)
        self._session.flush()
        return self._detail(review_id)

    def resubmit(self, review_id: int, user: User, commit_shas: list[str], note: str) -> ReviewOut | None:
        review = self._loaded(review_id)
        if review is None:
            return None
        self._require_author(review, user)
        review.resubmit(user.id, commit_shas, note)
        self._session.flush()
        return self._detail(review_id)

    def acknowledge(self, review_id: int, user: User) -> ReviewOut | None:
        review = self._loaded(review_id)
        if review is None:
            return None
        self._require_author(review, user)
        review.acknowledge(user.id)
        self._session.flush()
        return self._detail(review_id)

    # --- reads -----------------------------------------------------------------------------------

    def list(
        self, *, status: str | None, author_id: int | None, reviewer_id: int | None
    ) -> list[ReviewSummary]:
        stmt = select(Review).options(selectinload(Review.author), selectinload(Review.reviewer))
        if status:
            stmt = stmt.where(Review.status == status)
        if author_id is not None:
            stmt = stmt.where(Review.author_user_id == author_id)
        if reviewer_id is not None:
            stmt = stmt.where(Review.reviewer_user_id == reviewer_id)
        rows = self._session.scalars(stmt.order_by(Review.updated_at.desc())).all()
        return [serializer.to_summary(r) for r in rows]

    def get(self, review_id: int) -> ReviewOut | None:
        return self._detail(review_id)

    def commit(self) -> None:
        self._session.commit()
