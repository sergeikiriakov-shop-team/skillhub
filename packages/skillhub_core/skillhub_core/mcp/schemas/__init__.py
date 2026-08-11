"""MCP context — Pydantic DTOs (API + MCP surface), one module per aggregate."""

from __future__ import annotations

from .evaluation import McpAssessmentIn, McpEvaluationOut, McpEvaluationResult
from .rubric import McpRubricOut
from .server import (
    McpServerDetail,
    McpServerIn,
    McpServerSummary,
    McpToolIn,
    McpToolOut,
    McpVersionInfo,
)

__all__ = [
    "McpToolIn",
    "McpToolOut",
    "McpServerIn",
    "McpServerSummary",
    "McpServerDetail",
    "McpVersionInfo",
    "McpEvaluationResult",
    "McpAssessmentIn",
    "McpEvaluationOut",
    "McpRubricOut",
]
