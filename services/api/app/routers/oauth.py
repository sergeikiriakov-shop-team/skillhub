"""OAuth 2.1 Authorization Server for the remote HTTP MCP.

SkillHub is the authorization server; the MCP endpoint (served by the ``mcp`` service) is the
protected resource. This implements:

- Dynamic Client Registration (RFC 7591) — Claude Code registers itself.
- The authorization-code grant with PKCE/S256 (RFC 6749 + 7636).
- Refresh tokens.

The user is authenticated by **reusing the existing GitHub browser login**: ``/authorize`` checks
the ``skillhub_session`` cookie and, if absent, bounces through ``/api/auth/login`` (stashing the
request in a short-lived cookie) and resumes after the callback. Authorization-server metadata is
served at the root well-known path by ``main.py`` via :func:`authorization_server_metadata`.
"""

from __future__ import annotations

import base64
import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from skillhub_core import auth as core_auth
from skillhub_core.config import get_settings
from skillhub_core.db import get_session
from skillhub_core.models import TOKEN_OAUTH, TOKEN_OAUTH_REFRESH, User

from ..auth import current_user_optional

logger = logging.getLogger("skillhub.oauth")
router = APIRouter(tags=["oauth"], prefix="/oauth")
settings = get_settings()

# Cookie holding the pending authorization request across the GitHub-login bounce. Scoped to the
# authorize path; the redirect_uri inside is re-validated against the registered client on resume,
# so a tampered cookie cannot cause an open redirect.
AUTHZ_COOKIE = "skillhub_authz"


def _issuer() -> str:
    return settings.skillhub_public_url.rstrip("/")


def authorization_server_metadata() -> dict:
    """RFC 8414 metadata for this authorization server (served at the root well-known path).

    ``issuer`` carries a trailing slash to match exactly what the resource server advertises in its
    protected-resource metadata (the MCP SDK normalizes the issuer URL via pydantic's AnyHttpUrl,
    which appends "/"); a strict client compares the two for equality."""
    base = _issuer()
    return {
        "issuer": f"{base}/",
        "authorization_endpoint": f"{base}/api/oauth/authorize",
        "token_endpoint": f"{base}/api/oauth/token",
        "registration_endpoint": f"{base}/api/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["skillhub"],
    }


def _oauth_error(error: str, status: int = 400, description: str | None = None) -> JSONResponse:
    body = {"error": error}
    if description:
        body["error_description"] = description
    return JSONResponse(body, status_code=status)


def _encode_authz(params: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(params).encode("utf-8")).decode("ascii")


def _decode_authz(raw: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))


# --- Dynamic Client Registration (RFC 7591) ----------------------------------------------------


class RegisterIn(BaseModel):
    redirect_uris: list[str] = []
    client_name: str | None = None
    # Clients send extra metadata (grant_types, token_endpoint_auth_method, …); ignore it.


@router.post("/register")
def register(body: RegisterIn, session: Session = Depends(get_session)) -> JSONResponse:
    if not body.redirect_uris:
        return _oauth_error("invalid_client_metadata", description="redirect_uris is required")
    client = core_auth.register_oauth_client(session, body.client_name, body.redirect_uris)
    session.commit()
    return JSONResponse(
        {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
        status_code=201,
    )


# --- Authorization endpoint (code flow + PKCE, identity via the GitHub session) -----------------


@router.get("/authorize")
def authorize(
    request: Request,
    response_type: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    redirect_uri: str | None = Query(default=None),
    code_challenge: str | None = Query(default=None),
    code_challenge_method: str = Query(default="S256"),
    state: str | None = Query(default=None),
    scope: str | None = Query(default=None),
    resource: str | None = Query(default=None),
    authz_cookie: str | None = Cookie(default=None, alias=AUTHZ_COOKIE),
    user: User | None = Depends(current_user_optional),
    session: Session = Depends(get_session),
):
    # On the post-login return the browser lands here with no query but the stashed cookie.
    if client_id is None and authz_cookie:
        try:
            p = _decode_authz(authz_cookie)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid authorization request")
        response_type = p.get("response_type")
        client_id = p.get("client_id")
        redirect_uri = p.get("redirect_uri")
        code_challenge = p.get("code_challenge")
        code_challenge_method = p.get("code_challenge_method", "S256")
        state = p.get("state")
        scope = p.get("scope")
        resource = p.get("resource")

    if response_type != "code":
        raise HTTPException(status_code=400, detail="unsupported response_type (only 'code')")
    if not client_id or not redirect_uri or not code_challenge:
        raise HTTPException(
            status_code=400, detail="client_id, redirect_uri and code_challenge (PKCE) are required"
        )
    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="only the S256 PKCE method is supported")

    client = core_auth.get_oauth_client(session, client_id)
    if client is None or redirect_uri not in (client.redirect_uris or []):
        raise HTTPException(status_code=400, detail="unknown client_id or unregistered redirect_uri")

    if user is None:
        # Not logged in — stash the request and bounce through the existing GitHub login, returning
        # to a bare /authorize (which then reads the cookie). next= is a fixed same-site path.
        params = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
            "scope": scope,
            "resource": resource,
        }
        login_url = "/api/auth/login?" + urlencode({"next": "/api/oauth/authorize"})
        resp = RedirectResponse(login_url, status_code=302)
        resp.set_cookie(
            AUTHZ_COOKIE,
            _encode_authz(params),
            httponly=True,
            secure=settings.skillhub_cookie_secure,
            samesite="lax",
            path="/api/oauth",
            max_age=600,
        )
        return resp

    # Authenticated — issue a single-use code bound to (client, redirect_uri, PKCE, user, resource).
    _, code = core_auth.create_oauth_code(
        session,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        user=user,
        scope=scope,
        resource=resource,
    )
    session.commit()
    q: dict[str, str] = {"code": code}
    if state is not None:
        q["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    resp = RedirectResponse(f"{redirect_uri}{sep}{urlencode(q)}", status_code=302)
    resp.delete_cookie(AUTHZ_COOKIE, path="/api/oauth")
    return resp


# --- Token endpoint (authorization_code + refresh_token grants) --------------------------------


def _issue_tokens(
    session: Session, user: User, scope: str | None, keep_refresh: str | None = None
) -> JSONResponse:
    _, access = core_auth.create_auth_token(
        session, user, kind=TOKEN_OAUTH, ttl_seconds=settings.skillhub_oauth_access_ttl, label="mcp-oauth"
    )
    refresh = keep_refresh
    if refresh is None:
        _, refresh = core_auth.create_auth_token(
            session, user, kind=TOKEN_OAUTH_REFRESH, label="mcp-oauth-refresh"
        )
    session.commit()
    body = {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.skillhub_oauth_access_ttl,
        "refresh_token": refresh,
        "scope": scope or "skillhub",
    }
    return JSONResponse(body)


@router.post("/token")
def token(
    grant_type: str = Form(...),
    code: str | None = Form(default=None),
    redirect_uri: str | None = Form(default=None),
    client_id: str | None = Form(default=None),
    code_verifier: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> JSONResponse:
    if grant_type == "authorization_code":
        if not (code and redirect_uri and client_id and code_verifier):
            return _oauth_error("invalid_request", description="missing code/redirect_uri/client_id/code_verifier")
        result = core_auth.consume_oauth_code(
            session, code=code, client_id=client_id, redirect_uri=redirect_uri, code_verifier=code_verifier
        )
        if result is None:
            session.rollback()
            return _oauth_error("invalid_grant", description="code invalid, expired, reused, or PKCE mismatch")
        user, _resource, scope = result
        return _issue_tokens(session, user, scope)

    if grant_type == "refresh_token":
        if not refresh_token:
            return _oauth_error("invalid_request", description="refresh_token is required")
        row = core_auth.load_refresh_token(session, refresh_token)
        if row is None:
            return _oauth_error("invalid_grant", description="unknown or expired refresh_token")
        return _issue_tokens(session, row.user, None, keep_refresh=refresh_token)

    return _oauth_error("unsupported_grant_type")
