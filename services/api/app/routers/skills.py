"""Skill upload / import, listing and retrieval.

Reads are open. Uploading requires the contributor role; deletion requires admin.
Evaluation is submitted separately (routers/evaluations.py) by users with the evaluator role."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from skillhub_core.skills import pipeline, repository, serializers
from skillhub_core.platform.db import get_session
from skillhub_core.platform.models import User
from skillhub_core.skills.errors import InvalidNotebook, SkillNotFound
from skillhub_core.skills.schemas import (
    NotebookOut,
    NotebookSubmit,
    Reference,
    SkillCreate,
    SkillDetail,
    SkillSummary,
)
from skillhub_core.skills.services import NotebookService

from ..auth import require_admin, require_read_access, require_upload
from ..deps import get_notebook_service

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillSummary])
def list_skills(
    search: str | None = None,
    category: str | None = None,
    evaluated: bool | None = None,
    session: Session = Depends(get_session),
) -> list[SkillSummary]:
    """List skills (open). ``evaluated=false`` returns the work queue for evaluators."""
    skills = repository.list_skills(session, search=search, category=category, evaluated=evaluated)
    return [serializers.skill_to_summary(s) for s in skills]


@router.post("/skills", response_model=SkillDetail, status_code=201)
def create_skill(
    payload: SkillCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_upload),
) -> SkillDetail:
    references = [Reference(path=r.path, content=r.content) for r in payload.references]
    try:
        result = pipeline.ingest_raw(
            session,
            content=payload.content,
            author=payload.author,  # ignored while authenticated; authorship comes from the user
            references=references,
            source_format=payload.source_format,
            user=user,
        )
    except repository.DuplicateSkillError as exc:
        # Identical prompt already exists under another name → don't create a duplicate.
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Identical to existing skill '{exc.existing_name}'. "
                "Update that skill (upload under its name) or change the content.",
                "existing_skill_id": exc.existing_id,
                "existing_name": exc.existing_name,
            },
        ) from exc
    skill = repository.get_skill(session, result.skill_id)
    if skill is None:  # pragma: no cover - just created
        raise HTTPException(status_code=500, detail="Skill was not persisted")
    similar = repository.find_similar(session, skill)
    detail = serializers.skill_to_detail(skill, similar)
    detail.similar_warning = result.similar_warning
    return detail


@router.get("/skills/{skill_id}", response_model=SkillDetail)
def get_skill(skill_id: int, session: Session = Depends(get_session)) -> SkillDetail:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    similar = repository.find_similar(session, skill)
    return serializers.skill_to_detail(skill, similar)


@router.get("/skills/{skill_id}/notebook", response_model=NotebookOut)
def get_skill_notebook(
    skill_id: int,
    service: NotebookService = Depends(get_notebook_service),
    _: User | None = Depends(require_read_access),
) -> NotebookOut:
    """The one sandbox-trial notebook for this skill (the run record from ``evals/``). 404 if no
    trial has been recorded yet."""
    notebook = service.get_notebook(skill_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="No sandbox trial recorded for this skill")
    return notebook


@router.put("/skills/{skill_id}/notebook", response_model=NotebookOut)
def put_skill_notebook(
    skill_id: int,
    payload: NotebookSubmit,
    service: NotebookService = Depends(get_notebook_service),
    user: User = Depends(require_upload),
) -> NotebookOut:
    """Store (create or regenerate) this skill's trial notebook. Contributor+ role. The tested
    skill-version snapshot is taken server-side."""
    try:
        return service.submit_notebook(
            skill_id,
            scenario=payload.scenario,
            task_group=payload.task_group,
            notebook=payload.notebook,
            summary=payload.summary,
            created_by_user_id=user.id,
        )
    except SkillNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidNotebook as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/skills/{skill_id}", status_code=204, response_class=Response)
def delete_skill(
    skill_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
) -> Response:
    skill = repository.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    session.delete(skill)
    session.commit()
    return Response(status_code=204)
