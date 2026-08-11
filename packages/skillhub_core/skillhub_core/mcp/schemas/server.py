"""DTOs for the McpServer aggregate — the server, its versions and their tool surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ...skills.schemas import RecommendationOut

from .evaluation import McpEvaluationOut


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




