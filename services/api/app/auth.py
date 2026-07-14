"""FastAPI auth dependencies. Reads are open; writes require a bearer token + role."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from skillhub_core import auth as core_auth
from skillhub_core.db import get_session
from skillhub_core.models import User


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()  # tolerate a bare token


def current_user_optional(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User | None:
    return core_auth.get_user_by_token(session, _extract_token(authorization) or "")


def require_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required (bearer token)")
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
