"""TaskReview aggregate → DTOs."""

from __future__ import annotations

from ..models import TaskReview
from ..schemas import TaskReviewOut, TaskReviewSummary
from .self_review import to_detail as run_detail
from .self_review import to_summary as run_summary


def _open_finding_count(task_review: TaskReview) -> int:
    """Findings of the latest run that nothing has answered yet.

    A fix carrying only a note counts as answered here — the developer said something about it —
    while `fixed_count` on the run itself stays stricter and counts only commits. The lead wants to
    know what is still unaddressed; the run wants to know what is actually repaired."""
    run = task_review.latest_run
    if run is None:
        return 0
    answered = {fix.finding_index for fix in run.fixes}
    return max(len(run.findings or []) - len(answered), 0)


def to_summary(task_review: TaskReview) -> TaskReviewSummary:
    run = task_review.latest_run
    return TaskReviewSummary(
        id=task_review.id,
        task_ref=task_review.task_ref,
        title=task_review.title,
        branch=task_review.branch,
        status=task_review.status,
        author=task_review.author.name if task_review.author else None,
        approved_by=task_review.approved_by.name if task_review.approved_by else None,
        approved_at=task_review.approved_at,
        lead_comment=task_review.lead_comment,
        run_count=len(task_review.self_reviews),
        latest_verdict=run.verdict if run is not None else None,
        open_finding_count=_open_finding_count(task_review),
        updated_at=task_review.updated_at,
        created_at=task_review.created_at,
    )


def to_detail(task_review: TaskReview) -> TaskReviewOut:
    run = task_review.latest_run
    return TaskReviewOut(
        **to_summary(task_review).model_dump(),
        repo=task_review.repo,
        self_reviews=[run_summary(r) for r in task_review.self_reviews],
        latest_run=run_detail(run) if run is not None else None,
    )
