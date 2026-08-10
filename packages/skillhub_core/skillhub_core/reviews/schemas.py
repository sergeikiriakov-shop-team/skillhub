"""Task Review context — Pydantic DTOs (API + MCP surface)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
    self_reviews: list["SelfReviewSummary"] = Field(default_factory=list)


# --- self-review (the author reviewing their own change with the policy's skill) -----------------


class SelfReviewFinding(BaseModel):
    """One issue the reviewing skill reported. ``file``/``line`` point into the diff when the skill
    localized it; a finding without them is a change-wide remark."""

    severity: str = Field(description="One of: blocker | major | minor | nit.")
    title: str = Field(description="One-line statement of the issue.")
    file: str | None = Field(default=None, description="Repo-relative path the finding is in.")
    line: int | None = Field(default=None, description="1-indexed line the finding anchors to.")
    detail: str = Field(default="", description="Why it is wrong / what breaks.")
    suggestion: str = Field(default="", description="The concrete fix.")


class SelfReviewSubmitIn(BaseModel):
    """Result of running the policy's review skill over your own change. A POINTER plus the report —
    the code stays in git."""

    task_ref: str = Field(description="issue_logs id or link identifying the task.")
    branch: str | None = None
    commit_shas: list[str] = Field(default_factory=list)
    lane: str = Field(default="default", description="Policy lane used: default | backend | frontend.")
    skill: str | None = Field(
        default=None,
        description="Name of the skill that reviewed. Omit to record the lane's configured skill.",
    )
    model: str = Field(default="", description="Model that ran the review, e.g. claude-opus-5.")
    verdict: str | None = Field(
        default=None,
        description="pass | changes_needed. Omit to derive it from the findings' severities.",
    )
    summary: str = Field(default="", description="What the review covered and concluded.")
    findings: list[SelfReviewFinding] = Field(default_factory=list)
    review_id: int | None = Field(
        default=None, description="Attach to this peer review; omit to attach by task_ref later."
    )


class SelfReviewSummary(BaseModel):
    id: int
    task_ref: str
    branch: str | None
    lane: str
    skill: str
    model: str
    verdict: str
    finding_count: int
    blocking_count: int
    author: str | None
    review_id: int | None
    created_at: datetime


class SelfReviewOut(SelfReviewSummary):
    commit_shas: list[str]
    summary: str
    findings: list[SelfReviewFinding] = Field(default_factory=list)


class SelfReviewPolicyLane(BaseModel):
    """The self-review setting for one lane."""

    lane: str
    skill_id: int | None
    skill: str | None = Field(default=None, description="Configured skill's name; null = not set.")
    required: bool = Field(description="Block handing the task to the lead without a self-review.")


class SelfReviewPolicyOut(BaseModel):
    lanes: list[SelfReviewPolicyLane]


class SelfReviewPolicyUpdate(BaseModel):
    """Admin: set the reviewing skill for one lane. ``skill`` is the catalog name; null clears it."""

    lane: str = Field(description="default | backend | frontend.")
    skill: str | None = Field(default=None, description="Catalog skill name, or null to unset.")
    required: bool = False


# ``ReviewOut.self_reviews`` forward-references a class defined below it; resolve it now so the
# model is usable at import time (FastAPI builds response models eagerly).
ReviewOut.model_rebuild()
