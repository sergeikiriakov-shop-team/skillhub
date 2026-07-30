"""Repository Protocol for the Platform admin slice (user + role administration).

The seam ``UserAdminService`` depends on; returns API DTOs so the service is DB-free and testable
with an in-memory fake. The SQLAlchemy implementation lives in ``skillhub_core.platform.repositories``.
(OAuth / session flows are infrastructure and are not modelled here.)"""

from __future__ import annotations

from typing import Protocol

from .schemas import UserOut


class UserAdminRepository(Protocol):
    def list_users(self) -> list[UserOut]: ...

    def create_user(self, *, name: str, role: str) -> dict:
        """Create a user + initial device token (flush only; caller commits). Returns the
        ``UserCreated`` fields including the one-time plaintext ``token``."""
        ...

    def set_role(self, user_id: int, role: str) -> UserOut | None:
        """Set a user's role (flush only). None if the user does not exist."""
        ...

    def set_reviewer(self, user_id: int, is_reviewer: bool) -> UserOut | None:
        """Grant/revoke the reviewer capability (flush only). None if the user does not exist."""
        ...

    def commit(self) -> None: ...
