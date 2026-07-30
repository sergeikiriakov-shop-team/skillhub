"""Schemas for the skill sandbox-trial notebooks (one per (skill, executing model))."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotebookSubmit(BaseModel):
    """Payload the sandbox (``evals/``) sends to store a trial. The notebook + summary are exactly
    what ``evals/harness.py`` emits (``trial.ipynb`` cells and the ``trial.json`` scorecard). The
    tested skill-version snapshot is taken server-side. ``model`` is the executing model that
    produced the trial (self-reported), so effectiveness is recorded per model."""

    model: str = Field(default="", max_length=60, description="Executing model id, e.g. claude-opus-5")
    scenario: str = Field(default="", max_length=120)
    task_group: str | None = Field(default=None, max_length=80)
    notebook: dict = Field(description="nbformat 4.5 notebook (cells)")
    summary: dict = Field(default_factory=dict, description="compact scorecard (trial.json)")


class NotebookOut(BaseModel):
    """A stored (skill, model) trial notebook. ``effectiveness`` (0..1) is the combined headline:
    the judge panel's ``result_grade``/10 capped by the objective scorecard (``objective_rate``);
    for older ungraded trials it is just ``objective_rate``. ``dimensions`` = the panel-median
    per-criterion grades; ``panel`` = the individual judge votes. ``stale`` = the skill changed
    since the run."""

    skill_id: int
    model: str = ""
    scenario: str
    task_group: str | None = None
    notebook: dict
    summary: dict
    effectiveness: float | None = None
    result_grade: float | None = None
    objective_rate: float | None = None
    dimensions: dict | None = None
    panel: list[dict] | None = None
    tested_version_no: int | None = None
    stale: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotebookModelSummary(BaseModel):
    """One model's trial in the effectiveness matrix (without the heavy notebook payload). Carries
    the combined ``effectiveness`` plus its two components — the judge ``result_grade`` (0..10) and
    the objective ``objective_rate`` (0..1) gate — and the panel-median ``dimensions`` breakdown."""

    model: str
    scenario: str
    effectiveness: float | None = None
    result_grade: float | None = None
    objective_rate: float | None = None
    dimensions: dict | None = None
    stale: bool = False
    created_by: str | None = None
    created_at: datetime | None = None


class SkillFitOut(BaseModel):
    """A skill's effectiveness-by-model matrix: which models it was trialed under, how well it did,
    and the ``best_model`` (highest effectiveness). Models with no trial are simply absent (= gaps)."""

    skill_id: int
    best_model: str | None = None
    entries: list[NotebookModelSummary] = Field(default_factory=list)
