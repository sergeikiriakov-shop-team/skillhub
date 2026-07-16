"""Auth endpoints: GitHub OAuth login (browser), the device grant (MCP/CLI), session & tokens.

SkillHub is its own authorization server; GitHub is only the browser identity provider. Reads
stay open — everything here is either public (login/callback/me/device code+token) or requires a
session/token (logout, device approve, token management)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from skillhub_core.platform import auth as core_auth
from skillhub_core.platform.config import (
    AUTH_PROVIDER,
    GITHUB_AUTHORIZE_URL,
    GITHUB_EMAILS_URL,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
    get_settings,
)
from skillhub_core.platform.db import get_session
from skillhub_core.platform.models import TOKEN_PAT, TOKEN_SESSION, User

from ..auth import SESSION_COOKIE, current_user_optional, require_user

logger = logging.getLogger("skillhub.auth")
router = APIRouter(tags=["auth"], prefix="/auth")
settings = get_settings()

STATE_COOKIE = "skillhub_oauth_state"
NEXT_COOKIE = "skillhub_oauth_next"
_STATE_TTL = 600


def _cookie_kwargs(max_age: int, path: str = "/") -> dict:
    # SameSite=Lax (never Strict): the provider's redirect back to /callback is a cross-site
    # top-level GET, and Strict would drop the state cookie. Secure is env-gated (off on localhost).
    return {
        "httponly": True,
        "secure": settings.skillhub_cookie_secure,
        "samesite": "lax",
        "path": path,
        "max_age": max_age,
    }


def _safe_next(target: str | None) -> str:
    """Only allow same-site relative paths (no scheme/host, no protocol-relative //) as a return
    destination, so ?next= can't turn login into an open redirector."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


# --- browser login (GitHub OAuth authorization-code flow) --------------------------------------


@router.get("/login")
def login(next: str = Query("/")):
    if not settings.oauth_enabled:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")
    state = core_auth.generate_token()
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.effective_redirect_uri,
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "false",
    }
    resp = RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}", status_code=302)
    resp.set_cookie(STATE_COOKIE, state, **_cookie_kwargs(_STATE_TTL, path="/api/auth"))
    resp.set_cookie(NEXT_COOKIE, _safe_next(next), **_cookie_kwargs(_STATE_TTL, path="/api/auth"))
    return resp


@router.get("/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    state_cookie: str | None = Cookie(default=None, alias=STATE_COOKIE),
    next_cookie: str | None = Cookie(default=None, alias=NEXT_COOKIE),
    session: Session = Depends(get_session),
):
    if not settings.oauth_enabled:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")
    if not state_cookie or state != state_cookie:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    ua = {"User-Agent": "SkillHub", "Accept": "application/vnd.github+json"}
    try:
        with httpx.Client(timeout=15) as client:
            token_resp = client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.effective_redirect_uri,
                },
                headers={"Accept": "application/json", "User-Agent": "SkillHub"},
            )
            token_resp.raise_for_status()
            # GitHub returns 200 with {"error": ...} on a bad code, so check the field, not status.
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=502, detail="GitHub returned no access token")
            auth_h = {**ua, "Authorization": f"Bearer {access_token}"}
            user_resp = client.get(GITHUB_USER_URL, headers=auth_h)
            user_resp.raise_for_status()
            gh = user_resp.json()
            emails_resp = client.get(GITHUB_EMAILS_URL, headers=auth_h)
            emails = emails_resp.json() if emails_resp.status_code == 200 else []
    except httpx.HTTPError as exc:
        logger.warning("GitHub OAuth exchange failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="GitHub authentication failed") from exc

    sub = gh.get("id")
    if not sub:
        raise HTTPException(status_code=502, detail="GitHub returned no user id")
    # Prefer the verified primary email (needs the user:email scope); fall back to profile email.
    email: str | None = None
    email_verified = False
    if isinstance(emails, list):
        chosen = next((e for e in emails if e.get("primary") and e.get("verified")), None) or next(
            (e for e in emails if e.get("verified")), None
        )
        if chosen:
            email, email_verified = chosen.get("email"), True
    if email is None:
        email = gh.get("email")  # unverified profile email, if any

    user = core_auth.upsert_oauth_user(
        session,
        provider=AUTH_PROVIDER,
        sub=str(sub),
        email=email,
        name=gh.get("name") or gh.get("login"),
        email_verified=email_verified,
    )
    _, token = core_auth.create_auth_token(
        session, user, kind=TOKEN_SESSION, ttl_seconds=settings.skillhub_session_ttl
    )
    session.commit()

    resp = RedirectResponse(_safe_next(next_cookie), status_code=302)
    resp.set_cookie(SESSION_COOKIE, token, **_cookie_kwargs(settings.skillhub_session_ttl, path="/"))
    resp.delete_cookie(STATE_COOKIE, path="/api/auth")
    resp.delete_cookie(NEXT_COOKIE, path="/api/auth")
    return resp


@router.get("/me")
def me(user: User | None = Depends(current_user_optional)):
    reads_require_auth = not settings.skillhub_public_reads
    if user is None:
        return {"authenticated": False, "reads_require_auth": reads_require_auth}
    return {
        "authenticated": True,
        "reads_require_auth": reads_require_auth,
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "can_upload": user.can_upload,
        "can_evaluate": user.can_evaluate,
        "is_admin": user.is_admin,
    }


@router.post("/logout")
def logout(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: Session = Depends(get_session),
):
    if session_cookie:
        core_auth.revoke_token(session, session_cookie)
        session.commit()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# --- device authorization grant (RFC 8628) — used by the MCP / CLI -----------------------------


class DeviceCodeIn(BaseModel):
    client_label: str | None = None


@router.post("/device/code")
def device_code(body: DeviceCodeIn | None = None, session: Session = Depends(get_session)):
    row, device_code_plain = core_auth.create_device_code(
        session, client_label=(body.client_label if body else None)
    )
    session.commit()
    verification_uri = f"{settings.skillhub_public_url.rstrip('/')}/device"
    expires_in = int((row.expires_at - datetime.now(timezone.utc)).total_seconds())
    return {
        "device_code": device_code_plain,
        "user_code": row.user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": f"{verification_uri}?user_code={row.user_code}",
        "expires_in": expires_in,
        "interval": row.interval,
    }


class DeviceTokenIn(BaseModel):
    device_code: str


@router.post("/device/token")
def device_token(body: DeviceTokenIn, session: Session = Depends(get_session)):
    status, token = core_auth.poll_device_token(session, body.device_code)
    session.commit()
    if status == "success":
        return {"access_token": token, "token_type": "bearer"}
    # RFC 8628: non-success is an OAuth error response (HTTP 400 + error code).
    return JSONResponse({"error": status}, status_code=400)


class ApproveIn(BaseModel):
    user_code: str


@router.post("/device/approve")
def device_approve(
    body: ApproveIn, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    row = core_auth.approve_device_code(session, body.user_code, user)
    if row is None:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    session.commit()
    return {"ok": True, "client_label": row.client_label}


# --- self-service token management -------------------------------------------------------------


class PatIn(BaseModel):
    label: str | None = None


@router.get("/tokens")
def list_my_tokens(user: User = Depends(require_user), session: Session = Depends(get_session)):
    return [
        {
            "id": t.id,
            "kind": t.kind,
            "label": t.label,
            "created_at": t.created_at,
            "last_used_at": t.last_used_at,
            "expires_at": t.expires_at,
        }
        for t in core_auth.list_tokens_for_user(session, user)
    ]


@router.post("/tokens")
def create_pat(
    body: PatIn, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    _, token = core_auth.create_auth_token(session, user, kind=TOKEN_PAT, label=(body.label or "cli"))
    session.commit()
    return {"token": token}


@router.delete("/tokens/{token_id}")
def delete_my_token(
    token_id: int, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    if not core_auth.revoke_token_by_id(session, user, token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    session.commit()
    return {"ok": True}
