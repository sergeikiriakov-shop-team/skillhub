"""DTOs for the SelfReviewPolicy aggregate — which catalog skill reviews which lane."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
