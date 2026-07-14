"""Serve the evaluation rubric so Claude Code scores skills consistently."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from skillhub_core import repository
from skillhub_core.db import get_session
from skillhub_core.rubric import RUBRIC_DIMENSIONS, RUBRIC_INSTRUCTIONS, RUBRIC_VERSION
from skillhub_core.schemas import EvaluationResult, RubricOut

router = APIRouter(tags=["rubric"])


@router.get("/rubric", response_model=RubricOut)
def get_rubric(session: Session = Depends(get_session)) -> RubricOut:
    return RubricOut(
        rubric_version=RUBRIC_VERSION,
        instructions=RUBRIC_INSTRUCTIONS,
        dimensions=RUBRIC_DIMENSIONS,
        evaluation_schema=EvaluationResult.model_json_schema(),
        categories=repository.get_taxonomy(session),
    )
