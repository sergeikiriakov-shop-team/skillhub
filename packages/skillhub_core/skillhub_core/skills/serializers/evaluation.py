"""Evaluation aggregate → DTOs."""

from __future__ import annotations

from ..models import Evaluation
from ..schemas import EvaluationOut


def evaluation_to_out(evaluation: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        model=evaluation.model,
        rubric_version=evaluation.rubric_version,
        scores=evaluation.scores,
        overall_score=evaluation.overall_score,
        strengths=evaluation.strengths or [],
        weaknesses=evaluation.weaknesses or [],
        rationale=evaluation.rationale or "",
        created_at=evaluation.created_at,
    )






