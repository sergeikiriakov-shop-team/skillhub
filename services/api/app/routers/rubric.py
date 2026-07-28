"""Serve the evaluation rubric so Claude Code scores skills consistently, and let an admin manage
the dimension weights that drive the server-computed overall score."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from skillhub_core.platform.db import get_session
from skillhub_core.platform.models import User
from skillhub_core.skills import repository
from skillhub_core.skills.rubric import (
    CATEGORIZATION_RULES,
    RUBRIC_CALIBRATION,
    RUBRIC_DIMENSIONS,
    RUBRIC_INSTRUCTIONS,
    RUBRIC_VERSION,
    SELECTION_STRATEGY,
    SYNTHESIS_ALGORITHM,
    SYNTHESIS_PROMPT,
    SYNTHESIS_STRATEGY,
)
from skillhub_core.skills.schemas import EvaluationResult, RubricOut, WeightsUpdate

from ..auth import require_admin

router = APIRouter(tags=["rubric"])

_DIMENSION_KEYS = {d["key"] for d in RUBRIC_DIMENSIONS}


@router.get("/rubric", response_model=RubricOut)
def get_rubric(session: Session = Depends(get_session)) -> RubricOut:
    return RubricOut(
        rubric_version=RUBRIC_VERSION,
        instructions=RUBRIC_INSTRUCTIONS,
        dimensions=RUBRIC_DIMENSIONS,
        evaluation_schema=EvaluationResult.model_json_schema(),
        categories=repository.get_taxonomy(session),
        weights=repository.get_weights(session),
        calibration=RUBRIC_CALIBRATION,
        categorization_rules=CATEGORIZATION_RULES,
        selection_strategy=SELECTION_STRATEGY,
        synthesis_strategy=SYNTHESIS_STRATEGY,
        synthesis_algorithm=SYNTHESIS_ALGORITHM,
        synthesis_prompt=SYNTHESIS_PROMPT,
    )


@router.put("/rubric/weights", response_model=dict)
def update_weights(
    payload: WeightsUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict:
    """Admin-only: set the dimension weights. Validated against the rubric's dimensions; weights
    must be >= 0 with at least one > 0. Applying them recomputes every skill's overall score."""
    weights = payload.weights
    unknown = set(weights) - _DIMENSION_KEYS
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown dimension(s): {sorted(unknown)}")
    if any(w < 0 for w in weights.values()):
        raise HTTPException(status_code=400, detail="weights must be >= 0")
    if sum(weights.values()) <= 0:
        raise HTTPException(status_code=400, detail="at least one weight must be > 0")

    saved = repository.set_weights(session, weights)
    rescored = repository.recompute_overall_scores(session)
    session.commit()
    return {"weights": saved, "rescored": rescored}
