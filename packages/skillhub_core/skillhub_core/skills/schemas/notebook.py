"""Schemas for the skill sandbox-trial notebook (one per skill)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotebookSubmit(BaseModel):
    """Payload the sandbox (``evals/``) sends to store a skill's trial. The notebook + summary are
    exactly what ``evals/harness.py`` emits (``trial.ipynb`` cells and the ``trial.json`` scorecard).
    The tested skill-version snapshot is taken server-side from the skill's current content, so the
    client does not send it."""

    scenario: str = Field(default="", max_length=120)
    task_group: str | None = Field(default=None, max_length=80)
    notebook: dict = Field(description="nbformat 4.5 notebook (cells)")
    summary: dict = Field(default_factory=dict, description="compact scorecard (trial.json)")


class NotebookOut(BaseModel):
    """A skill's stored trial notebook, with a ``stale`` flag = the skill changed since the run."""

    skill_id: int
    scenario: str
    task_group: str | None = None
    notebook: dict
    summary: dict
    tested_version_no: int | None = None
    stale: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
