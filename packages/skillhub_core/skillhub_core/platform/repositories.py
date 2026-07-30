"""SQLAlchemy-backed repository for the Platform admin slice (user + role administration).

Injectable (holds a request-scoped :class:`Session`), satisfies ``UserAdminRepository``. Flush only
— the ``UserAdminService`` owns the commit. Delegates user+token creation to ``platform.auth``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth as core_auth
from .models import User
from .schemas import UserOut


def _out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, role=u.role, is_reviewer=u.is_reviewer, created_at=u.created_at)


class SqlUserAdminRepository:
    """``UserAdminRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_users(self) -> list[UserOut]:
        return [_out(u) for u in self._session.scalars(select(User).order_by(User.id)).all()]

    def create_user(self, *, name: str, role: str) -> dict:
        user, token = core_auth.create_user(self._session, name=name, role=role)
        return {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at,
            "token": token,
        }

    def set_role(self, user_id: int, role: str) -> UserOut | None:
        user = self._session.get(User, user_id)
        if user is None:
            return None
        user.role = role
        self._session.flush()
        return _out(user)

    def set_reviewer(self, user_id: int, is_reviewer: bool) -> UserOut | None:
        user = self._session.get(User, user_id)
        if user is None:
            return None
        user.is_reviewer = is_reviewer
        self._session.flush()
        return _out(user)

    def commit(self) -> None:
        self._session.commit()
