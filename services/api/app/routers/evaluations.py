"""Evaluation history and submission of assessments produced by Claude Code.

Thin HTTP layer over ``EvaluationService`` (injected via the DI container); the service owns the
validation-and-commit boundary and the read/write against the repository."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from skillhub_core.platform.models import User
from skillhub_core.skills.errors import SkillNotFound
from skillhub_core.skills.rubric import RUBRIC_VERSION
from skillhub_core.skills.schemas import AssessmentIn, EvaluationOut, SkillDetail
from skillhub_core.skills.services import EvaluationService

from ..auth import require_evaluate
from ..deps import get_evaluation_service

router = APIRouter(tags=["evaluations"])


@router.get("/skills/{skill_id}/evaluations", response_model=list[EvaluationOut])
def list_evaluations(
    skill_id: int, service: EvaluationService = Depends(get_evaluation_service)
) -> list[EvaluationOut]:
    try:
        return service.list_for_skill(skill_id)
    except SkillNotFound as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc


@router.post("/skills/{skill_id}/assessment", response_model=SkillDetail)
def submit_assessment(
    skill_id: int,
    payload: AssessmentIn,
    service: EvaluationService = Depends(get_evaluation_service),
    _: User = Depends(require_evaluate),
) -> SkillDetail:
    """Store an evaluation (and optional categorization) produced by the evaluator.
    The payload is validated against the rubric schema on the way in."""
    try:
        return service.submit(
            skill_id,
            evaluation=payload.evaluation,
            model=payload.model,
            rubric_version=payload.rubric_version or RUBRIC_VERSION,
            categorization=payload.categorization,
        )
    except SkillNotFound as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
