"""User/token helpers. Tokens are high-entropy random strings; we store only their SHA-256.

Reads are open. Uploads require ``can_upload``; submitting evaluations requires ``can_evaluate``
(the admin-marked ``evaluator`` role); user management requires ``admin``."""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ROLE_ADMIN, ROLE_CONTRIBUTOR, User


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_user(
    session: Session, name: str, role: str = ROLE_CONTRIBUTOR, token: str | None = None
) -> tuple[User, str]:
    """Create a user and return ``(user, plaintext_token)``. The plaintext is shown only once."""
    token = token or generate_token()
    user = User(name=name, role=role, token_hash=hash_token(token))
    session.add(user)
    session.flush()
    return user, token


def get_user_by_token(session: Session, token: str) -> User | None:
    if not token:
        return None
    return session.scalars(
        select(User).where(User.token_hash == hash_token(token))
    ).first()


def ensure_bootstrap_admin(session: Session, admin_token: str) -> None:
    """On first boot, if there are no users and an admin token is configured, create the admin.
    Idempotent: does nothing once any user exists."""
    if not admin_token:
        return
    if session.scalars(select(User).limit(1)).first() is not None:
        return
    create_user(session, name="admin", role=ROLE_ADMIN, token=admin_token)
    session.commit()
