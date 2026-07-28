"""Serve the evaluation rubric and let an admin manage the dimension weights.

Thin HTTP layer: it delegates to ``RubricService`` (injected via the DI container) and maps domain
errors to HTTP status. All rubric logic — assembling the strategy, validating and applying weights,
recomputing scores, owning the commit — lives in the service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from skillhub_core.platform.models import User
from skillhub_core.skills.errors import InvalidWeights
from skillhub_core.skills.schemas import RubricOut, WeightsUpdate
from skillhub_core.skills.services import RubricService

from ..auth import require_admin
from ..deps import get_rubric_service

router = APIRouter(tags=["rubric"])


@router.get("/rubric", response_model=RubricOut)
def get_rubric(service: RubricService = Depends(get_rubric_service)) -> RubricOut:
    return service.get_rubric()


@router.put("/rubric/weights", response_model=dict)
def update_weights(
    payload: WeightsUpdate,
    service: RubricService = Depends(get_rubric_service),
    _: User = Depends(require_admin),
) -> dict:
    """Admin-only: set the dimension weights. Applying them recomputes every skill's overall."""
    try:
        return service.set_weights(payload.weights)
    except InvalidWeights as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
