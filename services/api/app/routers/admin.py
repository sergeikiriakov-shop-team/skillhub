"""Admin: manage users and roles. Admin-only. This is where an admin marks who may evaluate."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from skillhub_core import auth as core_auth
from skillhub_core.db import get_session
from skillhub_core.models import ROLES, User
from skillhub_core.schemas import RoleUpdate, UserCreate, UserCreated, UserOut

from ..auth import require_admin

router = APIRouter(tags=["admin"], prefix="/admin")


def _out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, role=u.role, created_at=u.created_at)


@router.get("/users", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session), _: User = Depends(require_admin)):
    return [_out(u) for u in session.scalars(select(User).order_by(User.id)).all()]


@router.post("/users", response_model=UserCreated, status_code=201)
def create_user(
    payload: UserCreate, session: Session = Depends(get_session), _: User = Depends(require_admin)
):
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {ROLES}")
    user, token = core_auth.create_user(session, name=payload.name, role=payload.role)
    session.commit()
    return UserCreated(id=user.id, name=user.name, role=user.role, created_at=user.created_at, token=token)


@router.post("/users/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int,
    payload: RoleUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Change a user's role — e.g. promote to 'evaluator' so they may submit assessments."""
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {ROLES}")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    session.commit()
    return _out(user)
