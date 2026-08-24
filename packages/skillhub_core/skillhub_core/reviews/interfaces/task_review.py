"""Repository Protocol for the TaskReview aggregate — the seam ``TaskReviewService`` depends on."""

from __future__ import annotations

from typing import Protocol

from ...platform.models import User
from ..schemas import TaskReviewOut, TaskReviewSummary


class TaskReviewRepository(Protocol):
    """Persistence for the review board. Returns DTOs, so the service stays DB-free and fakeable;
    the transition rules live on the aggregate and surface as domain errors."""

    def list(self, *, status: str | None, author_id: int | None) -> list[TaskReviewSummary]: ...

    def get(self, task_review_id: int) -> TaskReviewOut | None: ...

    def approve(
        self, task_review_id: int, lead: User, *, require_clean_run: bool
    ) -> TaskReviewOut | None:
        """Sign a task off (flush only). None if it does not exist; raises
        ``InvalidReviewTransition`` when the aggregate refuses — no run to approve, already
        approved, or the policy demands a clean run this task has not had."""
        ...

    def send_back(self, task_review_id: int, lead: User, comment: str) -> TaskReviewOut | None:
        """Return a task to its author with a reason (flush only). None if it does not exist;
        raises ``InvalidReviewTransition`` when the comment is empty."""
        ...

    def delete(self, task_review_id: int, user: User) -> bool:
        """Remove a task and its runs (flush only). False if it does not exist; raises
        ``NotReviewAuthor`` / ``InvalidReviewTransition``."""
        ...

    def commit(self) -> None: ...
