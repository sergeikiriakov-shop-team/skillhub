"""Persistence for the TaskReview aggregate — the board the lead reads.

Queries and loading only: what a status means, when an approval is allowed and what a return
requires all live on the aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...platform.models import User
from ..models import SelfReview, SelfReviewFix, TaskReview
from ..schemas import TaskReviewOut, TaskReviewSummary
from ..serializers import task_review as serializer


class SqlTaskReviewRepository:
    """``TaskReviewRepository`` backed by SQLAlchemy. Flush only — the service commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _loaded(self, task_review_id: int) -> TaskReview | None:
        return self._session.scalars(
            select(TaskReview)
            .where(TaskReview.id == task_review_id)
            .options(
                selectinload(TaskReview.author),
                selectinload(TaskReview.approved_by),
                selectinload(TaskReview.self_reviews).selectinload(SelfReview.author),
                selectinload(TaskReview.self_reviews).selectinload(SelfReview.fixes).selectinload(
                    SelfReviewFix.author
                ),
            )
        ).first()

    def for_task(self, task_ref: str) -> TaskReview | None:
        """The board row for a task, if it has one. Used by the self-review path, which creates it
        on the first run — a task reaches the board by being reviewed, never by being announced."""
        row = self._session.scalars(select(TaskReview).where(TaskReview.task_ref == task_ref)).first()
        return self._loaded(row.id) if row is not None else None

    def list(self, *, status: str | None, author_id: int | None) -> list[TaskReviewSummary]:
        stmt = select(TaskReview).options(
            selectinload(TaskReview.author),
            selectinload(TaskReview.approved_by),
            selectinload(TaskReview.self_reviews).selectinload(SelfReview.fixes),
        )
        if status:
            stmt = stmt.where(TaskReview.status == status)
        if author_id is not None:
            stmt = stmt.where(TaskReview.author_user_id == author_id)
        rows = self._session.scalars(stmt.order_by(TaskReview.updated_at.desc())).unique().all()
        return [serializer.to_summary(r) for r in rows]

    def get(self, task_review_id: int) -> TaskReviewOut | None:
        row = self._loaded(task_review_id)
        return serializer.to_detail(row) if row is not None else None

    def approve(self, task_review_id: int, lead: User, *, require_clean_run: bool) -> TaskReviewOut | None:
        row = self._loaded(task_review_id)
        if row is None:
            return None
        row.approve(lead, require_clean_run=require_clean_run)
        self._session.flush()
        return self.get(task_review_id)

    def send_back(self, task_review_id: int, lead: User, comment: str) -> TaskReviewOut | None:
        row = self._loaded(task_review_id)
        if row is None:
            return None
        row.return_to_author(lead, comment)
        self._session.flush()
        return self.get(task_review_id)

    def delete(self, task_review_id: int, user: User) -> bool:
        """Remove a task from the board with its runs (they are its history, not standalone
        records). False if it does not exist; raises when this user may not."""
        row = self._loaded(task_review_id)
        if row is None:
            return False
        row.assert_deletable_by(user)
        self._session.delete(row)
        self._session.flush()
        return True

    def commit(self) -> None:
        self._session.commit()
