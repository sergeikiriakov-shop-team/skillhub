"""Skill upload / import, listing and retrieval. Evaluation is submitted separately
(see routers/evaluations.py) by Claude Code — the service does not call an LLM."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from skillhub_core import pipeline, repository, serializers
from skillhub_core.db import get_session
from skillhub_core.schemas import Reference, SkillCreate, SkillDetail, SkillSummary

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillSummary])
def list_skills(
    search: str | None = None,
    category: str | None = None,
    evaluated: bool | None = None,
    session: Session = Depends(get_session),
) -> list[SkillSummary]:
    """List skills. ``evaluated=false`` returns the work queue for the evaluator."""
    skills = repository.list_skills(session, search=search, category=category, evaluated=evaluated)
    return [serializers.skill_to_summary(s) for s in skills]


@router.post("/skills", response_model=SkillDetail, status_code=201)
def create_skill(payload: SkillCreate, session: Session = Depends(get_session)) -> SkillDetail:
    references = [Reference(path=r.path, content=r.content) for r in payload.references]
    result = pipeline.ingest_raw(
        session,
        content=payload.content,
        author=payload.author,
        references=references,
        source_format=payload.source_format,
    )
    skill = repository.get_skill(session, result.skill_id)
    if skill is None:  # pragma: no cover - just created
        raise HTTPException(status_code=500, detail="Skill was not persisted")
    similar = repository.find_similar(session, skill)
    return serializers.skill_to_detail(skill, similar)


@router.get("/skills/{skill_id}", response_model=SkillDetail)
def get_skill(skill_id: int, session: Session = Depends(get_session)) -> SkillDetail:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    similar = repository.find_similar(session, skill)
    return serializers.skill_to_detail(skill, similar)


@router.delete("/skills/{skill_id}", status_code=204, response_class=Response)
def delete_skill(skill_id: int, session: Session = Depends(get_session)) -> Response:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    session.delete(skill)
    session.commit()
    return Response(status_code=204)
