"""Evaluation history and on-demand re-evaluation."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from skillhub_core import repository, serializers
from skillhub_core.config import get_settings
from skillhub_core.db import get_session
from skillhub_core.schemas import EvaluationOut

from ..background import run_llm_for_skill

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


@router.post("/skills/{skill_id}/reevaluate", status_code=202)
def reevaluate(
    skill_id: int,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not get_settings().llm_enabled:
        raise HTTPException(status_code=400, detail="LLM is disabled (no ANTHROPIC_API_KEY)")
    background.add_task(run_llm_for_skill, skill_id)
    return {"status": "scheduled", "skill_id": skill_id}
