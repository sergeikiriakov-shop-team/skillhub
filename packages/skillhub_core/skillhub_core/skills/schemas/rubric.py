"""The rubric/strategy DTO served to every developer's Claude Code (GET /api/rubric)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RubricOut(BaseModel):
    """Everything the evaluator needs to score, categorize and rank a skill consistently.

    Served to every developer's Claude Code (GET /api/rubric) and rendered on the dashboard's
    Methodology page, so the strategy lives in one place instead of in each reviewer's head."""

    rubric_version: str
    instructions: str
    dimensions: list[dict]
    evaluation_schema: dict
    categories: list[dict]
    weights: dict = Field(default_factory=dict)
    calibration: list[dict] = Field(default_factory=list)
    categorization_rules: str = ""
    selection_strategy: str = ""
    synthesis_strategy: str = ""
    recommendation_strategy: str = ""
    synthesis_algorithm: list[dict] = Field(default_factory=list)
    synthesis_prompt: str = ""
    # The empirical, per-model layer: how a TRIAL RESULT (the artifact a model produced) is graded by
    # the blind judge panel — so the same criteria apply to outcomes per model, not just to SKILL.md.
    result_judge_version: str = ""
    result_judge_instructions: str = ""
    result_judge_dimensions: list[dict] = Field(default_factory=list)
    result_judge_panel: dict = Field(default_factory=dict)
    result_judge_protocol: str = ""


class WeightsUpdate(BaseModel):
    """Admin payload to set rubric dimension weights. Each weight must be >= 0 and at least one
    must be > 0 (so the weighted mean has a positive denominator)."""

    weights: dict[str, float] = Field(description="dimension -> weight (>= 0)")
