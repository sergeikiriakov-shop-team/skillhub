"""DTO for the MCP rubric — the strategy served to every developer's Claude Code."""

from __future__ import annotations

from pydantic import BaseModel, Field


class McpRubricOut(BaseModel):
    rubric_version: str
    instructions: str
    dimensions: list[dict]
    weights: dict = Field(default_factory=dict)
    calibration: list[dict] = Field(default_factory=list)
    evaluation_schema: dict = Field(default_factory=dict)
    recommendation_strategy: str = ""
    introspection_protocol: str = ""


