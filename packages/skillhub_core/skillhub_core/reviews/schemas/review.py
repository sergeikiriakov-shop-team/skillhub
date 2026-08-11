"""DTOs for the Review aggregate — a task handed to the lead, as it crosses the API/MCP surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .self_review import SelfReviewSummary


class ReviewSubmitIn(BaseModel):
    """Submit a deploy-ready task for review. A POINTER to the work — the code stays in git; the
    reviewer fetches the branch and reviews the real diff."""

    task_ref: str = Field(description="issue_logs id or link identifying the task.")
    title: str = ""
    branch: str | None = None
    commit_shas: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="What changed and why (from the release note).")
    files: list[str] = Field(default_factory=list, description="Changed file paths.")
    verified_notes: str = Field(default="", description="What the author verified / did not.")


class ReviewResultIn(BaseModel):
    verdict: str = Field(description="One of: approve | changes_requested.")
    comments: str = Field(default="", description="Reviewer feedback (required for changes_requested).")


class ReviewResubmitIn(BaseModel):
    commit_shas: list[str] = Field(default_factory=list, description="New/updated commit SHAs.")
    note: str = Field(default="", description="What was changed in response to the review.")


class ReviewEventOut(BaseModel):
    id: int
    kind: str
    author: str | None
    verdict: str | None
    body: str
    created_at: datetime
    self_review_id: int | None = None


class ReviewSummary(BaseModel):
    id: int
    task_ref: str
    title: str
    branch: str | None
    status: str
    author: str | None
    reviewer: str | None
    updated_at: datetime


class ReviewOut(ReviewSummary):
    commit_shas: list[str]
    summary: str
    files: list[str]
    verified_notes: str
    created_at: datetime
    events: list[ReviewEventOut] = Field(default_factory=list)
    self_reviews: list[SelfReviewSummary] = Field(default_factory=list)
