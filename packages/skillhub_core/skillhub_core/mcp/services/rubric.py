"""Application service for the MCP rubric — the tool-surface scoring strategy, served as data."""

from __future__ import annotations

from ..rubric import (
    MCP_INTROSPECTION_PROTOCOL,
    MCP_RECOMMENDATION_STRATEGY,
    MCP_RUBRIC_CALIBRATION,
    MCP_RUBRIC_DIMENSIONS,
    MCP_RUBRIC_INSTRUCTIONS,
    MCP_RUBRIC_VERSION,
    MCP_RUBRIC_WEIGHTS,
)
from ..schemas import McpEvaluationResult, McpRubricOut


class McpRubricService:
    """Serves the MCP evaluation strategy. Static by design — unlike the skills rubric, the MCP
    weights are not admin-editable yet, so there is nothing to persist."""

    def get_rubric(self) -> McpRubricOut:
        return McpRubricOut(
            rubric_version=MCP_RUBRIC_VERSION,
            instructions=MCP_RUBRIC_INSTRUCTIONS,
            dimensions=MCP_RUBRIC_DIMENSIONS,
            weights=MCP_RUBRIC_WEIGHTS,
            calibration=MCP_RUBRIC_CALIBRATION,
            evaluation_schema=McpEvaluationResult.model_json_schema(),
            recommendation_strategy=MCP_RECOMMENDATION_STRATEGY,
            introspection_protocol=MCP_INTROSPECTION_PROTOCOL,
        )




