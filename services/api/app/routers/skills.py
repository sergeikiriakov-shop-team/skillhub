"""Skill upload / import, listing, retrieval and the per-skill sandbox notebook.

Thin HTTP layer: it delegates to the Skills services (injected via the DI container) and maps
domain errors to HTTP status. Reads are open; uploading requires the contributor role; deletion
requires admin. Evaluation is submitted separately (routers/evaluations.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from skillhub_core.platform.models import User
from skillhub_core.skills.errors import DuplicateSkill, InvalidNotebook, SkillNotFound
from skillhub_core.skills.schemas import (
    NotebookOut,
    NotebookSubmit,
    Reference,
    SkillCreate,
    SkillDetail,
    SkillFitOut,
    SkillSummary,
)
from skillhub_core.skills.services import IngestService, NotebookService, SkillService

from ..auth import require_admin, require_read_access, require_upload
from ..deps import get_ingest_service, get_notebook_service, get_skill_service

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillSummary])
def list_skills(
    search: str | None = None,
    category: str | None = None,
    evaluated: bool | None = None,
    service: SkillService = Depends(get_skill_service),
) -> list[SkillSummary]:
    """List skills (open). ``evaluated=false`` returns the work queue for evaluators."""
    return service.list_skills(search=search, category=category, evaluated=evaluated)


@router.post("/skills", response_model=SkillDetail, status_code=201)
def create_skill(
    payload: SkillCreate,
    service: IngestService = Depends(get_ingest_service),
    user: User = Depends(require_upload),
) -> SkillDetail:
    references = [Reference(path=r.path, content=r.content) for r in payload.references]
    try:
        return service.create(
            content=payload.content,
            author=payload.author,  # ignored while authenticated; authorship comes from the user
            references=references,
            source_format=payload.source_format,
            user=user,
        )
    except DuplicateSkill as exc:
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


@router.get("/skills/{skill_id}", response_model=SkillDetail)
def get_skill(
    skill_id: int,
    include_references: bool = True,
    service: SkillService = Depends(get_skill_service),
) -> SkillDetail:
    """One skill in full. ``include_references=false`` omits the reference FILES — the heaviest
    part of the payload — while `references_count` still reports how many exist. Defaults to true
    so existing callers (the web UI, which renders them) are unaffected."""
    try:
        return service.get_skill(skill_id, include_references=include_references)
    except SkillNotFound as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc


@router.get("/skills/{skill_id}/notebook", response_model=NotebookOut)
def get_skill_notebook(
    skill_id: int,
    model: str | None = None,
    include_cells: bool = True,
    service: NotebookService = Depends(get_notebook_service),
    _: User | None = Depends(require_read_access),
) -> NotebookOut:
    """A sandbox-trial notebook for this skill (the run record from ``evals/``). ``model`` selects
    the executing model's trial; omitted, returns the best-scoring model's. 404 if none recorded.
    ``include_cells=false`` drops the raw nbformat cells and keeps only the scorecard — enough to
    decide reuse-vs-regenerate without pulling the whole transcript."""
    notebook = service.get_notebook(skill_id, model, include_cells=include_cells)
    if notebook is None:
        raise HTTPException(status_code=404, detail="No sandbox trial recorded for this skill")
    return notebook


@router.get("/skills/{skill_id}/notebooks", response_model=SkillFitOut)
def get_skill_fit(
    skill_id: int,
    service: NotebookService = Depends(get_notebook_service),
    _: User | None = Depends(require_read_access),
) -> SkillFitOut:
    """The skill's effectiveness-by-model matrix (which models it was trialed under, the score per
    model, and the best model). Models with no trial are absent — the gaps to fill."""
    return service.get_matrix(skill_id)


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
            model=payload.model,
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
    service: SkillService = Depends(get_skill_service),
    _: User = Depends(require_admin),
) -> Response:
    try:
        service.delete_skill(skill_id)
    except SkillNotFound as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
    return Response(status_code=204)
