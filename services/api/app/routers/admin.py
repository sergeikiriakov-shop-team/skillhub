"""Admin: manage users and roles. Admin-only. This is where an admin marks who may evaluate.

Thin HTTP layer over ``UserAdminService`` (injected via the DI container); the service owns role
validation + the commit and raises domain errors mapped to HTTP status here."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from skillhub_core.platform.errors import InvalidRole, UserNotFound
from skillhub_core.platform.models import User
from skillhub_core.platform.schemas import (
    ReviewerUpdate,
    RoleUpdate,
    UserCreate,
    UserCreated,
    UserOut,
)
from skillhub_core.platform.services import UserAdminService

from ..auth import require_admin
from ..deps import get_user_admin_service

router = APIRouter(tags=["admin"], prefix="/admin")


@router.get("/users", response_model=list[UserOut])
def list_users(
    service: UserAdminService = Depends(get_user_admin_service),
    _: User = Depends(require_admin),
) -> list[UserOut]:
    return service.list_users()


@router.post("/users", response_model=UserCreated, status_code=201)
def create_user(
    payload: UserCreate,
    service: UserAdminService = Depends(get_user_admin_service),
    _: User = Depends(require_admin),
) -> UserCreated:
    try:
        return service.create_user(name=payload.name, role=payload.role)
    except InvalidRole as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/users/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int,
    payload: RoleUpdate,
    service: UserAdminService = Depends(get_user_admin_service),
    _: User = Depends(require_admin),
) -> UserOut:
    """Change a user's role — e.g. promote to 'evaluator' so they may submit assessments."""
    try:
        return service.set_role(user_id, payload.role)
    except InvalidRole as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserNotFound as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.post("/users/{user_id}/reviewer", response_model=UserOut)
def set_reviewer(
    user_id: int,
    payload: ReviewerUpdate,
    service: UserAdminService = Depends(get_user_admin_service),
    _: User = Depends(require_admin),
) -> UserOut:
    """Grant/revoke the reviewer (lead) capability for the Task Review context."""
    try:
        return service.set_reviewer(user_id, payload.is_reviewer)
    except UserNotFound as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
