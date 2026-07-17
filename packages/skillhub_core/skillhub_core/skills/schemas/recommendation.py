"""Curator recommendation DTOs (proposed catalog changes)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecommendationIn(BaseModel):
    """A proposed catalog change, submitted by the curator (Claude Code)."""

    kind: str = Field(description="One of: synthesize | split | merge | dedup | delete | other.")
    title: str = Field(description="Short human-readable title of the recommendation.")
    rationale: str = Field(default="", description="Why this is worth doing.")
    scope: str | None = Field(
        default=None, description="What it applies to: a category key, a task_group, or a skill."
    )
    targets: list[str] = Field(
        default_factory=list, description="Skills/groups involved (names or keys)."
    )
    suggested_action: str = Field(
        default="", description="A runnable instruction a developer's Claude Code can execute."
    )


class RecommendationStatusUpdate(BaseModel):
    status: str = Field(description="One of: proposed | accepted | done | dismissed.")


class RecommendationOut(BaseModel):
    id: int
    kind: str
    title: str
    rationale: str
    scope: str | None
    targets: list[str]
    suggested_action: str
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime
