"""The team member (identity)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import ROLE_ADMIN, ROLE_CONTRIBUTOR, ROLE_EVALUATOR, Base


class User(Base):
    """A team member. Identity comes from an OAuth provider (``auth_provider`` + ``provider_sub``,
    e.g. github + the numeric user id) plus ``email``; access to the API is carried by rows in
    ``auth_tokens``. Reads are open; uploads/evaluations require a role.

    ``token_hash`` is the legacy single-token column, kept nullable for back-compat; new code
    issues tokens via :class:`AuthToken`. Uniqueness of ``email`` and of the
    ``(auth_provider, provider_sub)`` pair is enforced by named indexes created in
    ``db._apply_column_migrations`` (not by ``unique=`` here) so fresh and migrated databases
    converge on the same schema."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_CONTRIBUTOR)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Reviewer/lead capability for the Task Review context — orthogonal to the ascending role
    # ladder (a lead may review regardless of role). Set by an admin. See the reviews module.
    is_reviewer: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tokens: Mapped[list["AuthToken"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def can_upload(self) -> bool:
        return self.role in (ROLE_CONTRIBUTOR, ROLE_EVALUATOR, ROLE_ADMIN)

    @property
    def can_evaluate(self) -> bool:
        return self.role in (ROLE_EVALUATOR, ROLE_ADMIN)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN
