"""Structured evaluation + categorization results (produced by Claude Code, submitted back)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """Quality assessment of a single skill. All dimension scores are 0-10 integers."""

    clarity: int = Field(ge=0, le=10, description="Is the writing clear and unambiguous?")
    trigger_quality: int = Field(
        ge=0, le=10, description="How precisely does it state WHEN the skill should trigger?"
    )
    completeness: int = Field(
        ge=0, le=10, description="Does it cover the workflow with no critical gaps?"
    )
    reusability: int = Field(
        ge=0, le=10, description="Is it generic/parameterized rather than one-off?"
    )
    safety: int = Field(
        ge=0, le=10, description="Does it warn about destructive actions and edge cases?"
    )
    structure: int = Field(
        ge=0, le=10, description="Good headings, examples, progressive disclosure via references?"
    )
    overall: float = Field(ge=0, le=10, description="Weighted overall quality, 0-10.")
    strengths: list[str] = Field(default_factory=list, description="Concrete strengths.")
    weaknesses: list[str] = Field(default_factory=list, description="Concrete, actionable gaps.")
    rationale: str = Field(default="", description="2-4 sentence justification of the scores.")


class CategoryAssignment(BaseModel):
    key: str = Field(description="Category key from the provided taxonomy.")
    confidence: float = Field(ge=0, le=1, description="Confidence 0-1.")


class CategorizationResult(BaseModel):
    primary_category: str = Field(description="Single best-fit category key from the taxonomy.")
    categories: list[CategoryAssignment] = Field(
        default_factory=list, description="All applicable categories with confidences."
    )
    task_group: str | None = Field(
        default=None,
        description="Narrow slug for the skill's SPECIFIC job (e.g. 'single-task-driver', "
        "'sql-data-read'), finer than the broad category. Skills doing the same job MUST share "
        "the same slug so competing variants cluster together. Reuse an existing slug when one "
        "fits (see GET /api/task-groups); only invent a new one for a genuinely new job.",
    )
    tags: list[str] = Field(default_factory=list, description="Free-form lowercase tags.")
    summary: str = Field(default="", description="One-sentence summary of what the skill does.")
