"""Application service for the review board.

Owns the transaction boundary and maps a missing task to ``TaskReviewNotFound``. It reads the
self-review policy to decide whether an approval may stand on an unclean run — a rule that spans
two aggregates, which is why it lives here rather than inside either repository."""

from __future__ import annotations

from ...platform.models import User
from ..errors import TaskReviewNotFound
from ..interfaces import SelfReviewPolicyRepository, TaskReviewRepository
from ..schemas import TaskReviewOut, TaskReviewSummary


class TaskReviewService:
    def __init__(self, tasks: TaskReviewRepository, policies: SelfReviewPolicyRepository) -> None:
        self._tasks = tasks
        self._policies = policies

    def list(self, *, status: str | None = None, author_id: int | None = None) -> list[TaskReviewSummary]:
        return self._tasks.list(status=status, author_id=author_id)

    def get(self, task_review_id: int) -> TaskReviewOut:
        task = self._tasks.get(task_review_id)
        if task is None:
            raise TaskReviewNotFound(f"task review {task_review_id} not found")
        return task

    def approve(self, task_review_id: int, lead: User) -> TaskReviewOut:
        task = self._tasks.approve(
            task_review_id, lead, require_clean_run=self._policies.self_review_required()
        )
        if task is None:
            raise TaskReviewNotFound(f"task review {task_review_id} not found")
        self._tasks.commit()
        return task

    def send_back(self, task_review_id: int, lead: User, *, comment: str) -> TaskReviewOut:
        task = self._tasks.send_back(task_review_id, lead, comment)
        if task is None:
            raise TaskReviewNotFound(f"task review {task_review_id} not found")
        self._tasks.commit()
        return task

    def delete(self, task_review_id: int, user: User) -> None:
        if not self._tasks.delete(task_review_id, user):
            raise TaskReviewNotFound(f"task review {task_review_id} not found")
        self._tasks.commit()
