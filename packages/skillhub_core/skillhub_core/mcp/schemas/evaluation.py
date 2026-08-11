"""DTOs for scoring an MCP server's tool surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class McpEvaluationResult(BaseModel):
    """Quality assessment of one MCP server's tool surface. All dimension scores are 0-10 integers."""

    schema_precision: int = Field(
        ge=0, le=10, description="Typed, unambiguous params; a wrong argument can't be invented?"
    )
    tool_clarity: int = Field(
        ge=0, le=10, description="Does each description say what it does AND when to use it?"
    )
    discoverability: int = Field(
        ge=0, le=10, description="Can an agent pick the right tool first try?"
    )
    result_shape: int = Field(
        ge=0, le=10, description="Predictable, documented return/error/truncation shape?"
    )
    safety: int = Field(
        ge=0, le=10, description="Read-only vs mutating unmistakable; destructive ops flagged?"
    )
    token_economy: int = Field(
        ge=0, le=10, description="Bounded results, limits/pagination — no context flooding?"
    )
    overall: float = Field(ge=0, le=10, description="Weighted overall quality, 0-10.")
    strengths: list[str] = Field(default_factory=list, description="Concrete strengths.")
    weaknesses: list[str] = Field(default_factory=list, description="Concrete, actionable gaps.")
    rationale: str = Field(default="", description="2-4 sentence justification of the scores.")


class McpAssessmentIn(BaseModel):
    """A completed MCP assessment submitted by the evaluator (Claude Code)."""

    evaluation: McpEvaluationResult
    model: str = Field(default="claude-code", description="What produced the assessment.")
    rubric_version: str | None = Field(
        default=None, description="Defaults to the server's current MCP rubric version."
    )




class McpEvaluationOut(BaseModel):
    model: str
    rubric_version: str
    scores: dict
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    rationale: str
    created_at: datetime




