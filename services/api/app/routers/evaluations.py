"""Evaluation history and submission of assessments produced by Claude Code."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from skillhub_core import repository, serializers
from skillhub_core.db import get_session
from skillhub_core.models import User
from skillhub_core.rubric import RUBRIC_VERSION
from skillhub_core.schemas import AssessmentIn, EvaluationOut, SkillDetail

from ..auth import require_evaluate

router = APIRouter(tags=["evaluations"])


@router.get("/skills/{skill_id}/evaluations", response_model=list[EvaluationOut])
def list_evaluations(skill_id: int, session: Session = Depends(get_session)) -> list[EvaluationOut]:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    version = skill.latest_version
    if version is None:
        return []
    return [serializers.evaluation_to_out(e) for e in version.evaluations]


@router.post("/skills/{skill_id}/assessment", response_model=SkillDetail)
def submit_assessment(
    skill_id: int,
    payload: AssessmentIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_evaluate),
) -> SkillDetail:
    """Store an evaluation (and optional categorization) produced by the evaluator.
    The payload is validated against the rubric schema on the way in."""
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    version = skill.latest_version
    if version is None:
        raise HTTPException(status_code=400, detail="Skill has no versions")

    repository.save_evaluation(
        session, version, payload.evaluation, payload.model, payload.rubric_version or RUBRIC_VERSION
    )
    if payload.categorization is not None:
        repository.save_categorization(session, skill, payload.categorization)
    session.commit()
    session.expire_all()  # drop stale identity-map state so the response reflects the new rows

    skill = repository.get_skill(session, skill_id)
    similar = repository.find_similar(session, skill)
    return serializers.skill_to_detail(skill, similar)
