"""The completed assessment payload submitted by the evaluator (Claude Code)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .evaluation import CategorizationResult, EvaluationResult


class AssessmentIn(BaseModel):
    """A completed assessment submitted by the evaluator (Claude Code)."""

    evaluation: EvaluationResult
    categorization: CategorizationResult | None = None
    model: str = Field(default="claude-code", description="What produced the assessment.")
    rubric_version: str | None = Field(
        default=None, description="Defaults to the server's current rubric version."
    )
