"""McpEvaluation → DTOs: one tool-surface score against one introspected version."""

from __future__ import annotations

from ..models import McpEvaluation, McpServer
from ..schemas import McpEvaluationOut


def _evaluation_out(evaluation: McpEvaluation | None) -> McpEvaluationOut | None:
    if evaluation is None:
        return None
    return McpEvaluationOut(
        model=evaluation.model,
        rubric_version=evaluation.rubric_version,
        scores=evaluation.scores or {},
        overall_score=evaluation.overall_score,
        strengths=evaluation.strengths or [],
        weaknesses=evaluation.weaknesses or [],
        rationale=evaluation.rationale or "",
        created_at=evaluation.created_at,
    )


def _latest_evaluation(server: McpServer) -> McpEvaluation | None:
    version = server.latest_version
    return version.latest_evaluation if version else None




