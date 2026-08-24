"""DTOs for the TaskReview aggregate — one row per task on the review board."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .self_review import SelfReviewOut, SelfReviewSummary


class TaskReviewSummary(BaseModel):
    """A board row: enough to triage without loading the runs."""

    id: int
    task_ref: str
    title: str
    branch: str | None
    status: str = Field(description="changes_needed | passed | approved.")
    author: str | None
    approved_by: str | None = None
    approved_at: datetime | None = None
    lead_comment: str = Field(default="", description="Why the lead sent it back, if they did.")
    run_count: int = Field(description="Self-review runs recorded against this task.")
    latest_verdict: str | None = Field(default=None, description="Verdict of the latest run.")
    open_finding_count: int = Field(
        default=0, description="Findings of the latest run with no fix recorded against them."
    )
    updated_at: datetime
    created_at: datetime


class TaskReviewOut(TaskReviewSummary):
    """The task with its full run history, newest last."""

    repo: str | None = None
    self_reviews: list[SelfReviewSummary] = Field(default_factory=list)
    latest_run: SelfReviewOut | None = Field(
        default=None, description="The run the status reflects, with its findings and fixes."
    )


class TaskReviewReturnIn(BaseModel):
    """The lead sends a task back instead of approving it."""

    comment: str = Field(description="What must change. Required — a bare rejection costs a round trip.")
