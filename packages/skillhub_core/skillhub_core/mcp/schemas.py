"""MCP context — Pydantic DTOs (API + MCP surface)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..skills.schemas import RecommendationOut


class McpToolIn(BaseModel):
    """One tool as the introspecting client actually sees it on the live server."""

    name: str = Field(description="The tool's exact callable name.")
    description: str = Field(default="", description="The tool's own description, verbatim.")
    input_schema: dict = Field(
        default_factory=dict,
        description="The tool's parameter JSON Schema, verbatim — do not summarize or retype it.",
    )


class McpServerIn(BaseModel):
    """An introspected tool manifest. Submitting an existing ``name`` adds a new version; an
    unchanged manifest is a no-op."""

    name: str = Field(description="The MCP server entry's name, e.g. 'beliani-db-schema-prod'.")
    description: str = Field(default="", description="What this server is for.")
    label: str | None = Field(default=None, description="Optional human-friendly display name.")
    transport: str = Field(default="stdio", description="stdio | http.")
    family: str | None = Field(
        default=None,
        description="Groups sibling entries exposing the same surface against different "
        "environments (e.g. 'beliani-db-schema' for the prod/dev/heap trio).",
    )
    tools: list[McpToolIn] = Field(default_factory=list, description="The full tool surface.")


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


class McpToolOut(McpToolIn):
    """A tool as served back, plus the derived facts the UI renders per tool."""

    required: list[str] = Field(
        default_factory=list, description="Required parameter names, lifted from input_schema."
    )
    param_count: int = 0


class McpVersionInfo(BaseModel):
    version_no: int
    tool_count: int
    author: str | None
    created_at: datetime


class McpServerSummary(BaseModel):
    id: int
    name: str
    label: str | None = None
    description: str
    transport: str
    family: str | None = None
    source_type: str
    tool_count: int = 0
    overall_score: float | None = None
    rubric_version: str | None = None  # version of the latest evaluation; None if unscored
    open_improve_count: int = 0
    # Rough context-token cost of the tool surface itself (names + descriptions + schemas), via the
    # standard ~4-chars-per-token heuristic — what an agent pays just to have these tools available.
    estimated_tokens: int | None = None
    updated_at: datetime


class McpServerDetail(McpServerSummary):
    tools: list[McpToolOut] = Field(default_factory=list)
    version_no: int = 0
    versions: list[McpVersionInfo] = Field(default_factory=list)
    contributors: list[str] = Field(default_factory=list)
    latest_evaluation: McpEvaluationOut | None = None
    # Every OPEN (proposed/accepted) recommendation with target_kind="mcp" applying to this server —
    # computed server-side in the SAME request, so the page needs no second /recommendations fetch.
    # An `improve` one whose `anchor` matches a tool name renders inline under that tool.
    open_recommendations: list[RecommendationOut] = Field(default_factory=list)


class McpRubricOut(BaseModel):
    rubric_version: str
    instructions: str
    dimensions: list[dict]
    weights: dict = Field(default_factory=dict)
    calibration: list[dict] = Field(default_factory=list)
    evaluation_schema: dict = Field(default_factory=dict)
    recommendation_strategy: str = ""
    introspection_protocol: str = ""
