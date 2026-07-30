"""Application service for the Platform admin slice (user + role administration).

Owns validation (role must be allowed → ``InvalidRole``) and the commit; maps a missing user to
``UserNotFound``. Depends only on the ``UserAdminRepository`` Protocol, so it is unit-testable with
an in-memory fake."""

from __future__ import annotations

from .errors import InvalidRole, UserNotFound
from .interfaces import UserAdminRepository
from .models import ROLES
from .schemas import UserCreated, UserOut


class UserAdminService:
    def __init__(self, users: UserAdminRepository) -> None:
        self._users = users

    def list_users(self) -> list[UserOut]:
        return self._users.list_users()

    def create_user(self, *, name: str, role: str) -> UserCreated:
        if role not in ROLES:
            raise InvalidRole(f"role must be one of {ROLES}")
        created = self._users.create_user(name=name, role=role)
        self._users.commit()
        return UserCreated(**created)

    def set_role(self, user_id: int, role: str) -> UserOut:
        if role not in ROLES:
            raise InvalidRole(f"role must be one of {ROLES}")
        user = self._users.set_role(user_id, role)
        if user is None:
            raise UserNotFound(f"user {user_id} not found")
        self._users.commit()
        return user

    def set_reviewer(self, user_id: int, is_reviewer: bool) -> UserOut:
        user = self._users.set_reviewer(user_id, is_reviewer)
        if user is None:
            raise UserNotFound(f"user {user_id} not found")
        self._users.commit()
        return user
