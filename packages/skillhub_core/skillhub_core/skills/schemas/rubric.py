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
    synthesis_algorithm: list[dict] = Field(default_factory=list)
    synthesis_prompt: str = ""
