"""FastAPI auth dependencies. Reads are open; writes require auth (a role).

Two credential surfaces resolve to the same user: a ``Bearer`` token (MCP / CLI / explicit) and
the ``skillhub_session`` cookie (browser login). Bearer wins when both are present."""

from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from skillhub_core.platform import auth as core_auth
from skillhub_core.platform.config import get_settings
from skillhub_core.platform.db import get_session
from skillhub_core.platform.models import User

SESSION_COOKIE = "skillhub_session"


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()  # tolerate a bare token


def current_user_optional(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: Session = Depends(get_session),
) -> User | None:
    token = _extract_token(authorization) or session_cookie or ""
    return core_auth.get_user_by_token(session, token)


def require_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required (bearer token)")
    return user


def require_read_access(user: User | None = Depends(current_user_optional)) -> User | None:
    """Gate for read endpoints. Open when ``skillhub_public_reads`` is True; otherwise requires a
    logged-in user (session cookie or bearer token)."""
    if get_settings().skillhub_public_reads:
        return user
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_upload(user: User = Depends(require_user)) -> User:
    if not user.can_upload:
        raise HTTPException(status_code=403, detail="Upload requires the contributor role")
    return user


def require_evaluate(user: User = Depends(require_user)) -> User:
    if not user.can_evaluate:
        raise HTTPException(
            status_code=403, detail="Submitting evaluations requires the evaluator role (ask an admin)"
        )
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_reviewer(user: User = Depends(require_user)) -> User:
    """Task Review context: only the lead (``is_reviewer``) or an admin may post a verdict."""
    if not (user.is_reviewer or user.is_admin):
        raise HTTPException(status_code=403, detail="Reviewer (lead) role required")
    return user
