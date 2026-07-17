"""Shared declarative base + identity/access constants for the platform kernel.

``Base`` is the single SQLAlchemy declarative base shared by EVERY bounded context (skills,
reviews, …) so ``create_all`` and cross-context foreign keys resolve on one metadata/registry.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# --- roles (ascending capability) ---
ROLE_VIEWER = "viewer"
ROLE_CONTRIBUTOR = "contributor"  # may upload skills
ROLE_EVALUATOR = "evaluator"  # may submit evaluations (marked by an admin)
ROLE_ADMIN = "admin"  # may manage users
ROLES = (ROLE_VIEWER, ROLE_CONTRIBUTOR, ROLE_EVALUATOR, ROLE_ADMIN)

# --- auth token kinds ---
TOKEN_SESSION = "session"  # browser cookie, TTL'd
TOKEN_DEVICE = "device"  # long-lived, issued to the MCP via the device flow
TOKEN_PAT = "pat"  # long-lived personal access token, self-minted from the UI
TOKEN_OAUTH = "oauth"  # access token from the OAuth authorization-code flow (remote HTTP MCP)
TOKEN_OAUTH_REFRESH = "oauth_refresh"  # refresh token paired with a TOKEN_OAUTH access token
TOKEN_KINDS = (TOKEN_SESSION, TOKEN_DEVICE, TOKEN_PAT, TOKEN_OAUTH, TOKEN_OAUTH_REFRESH)
# Kinds usable as a bearer/cookie to *access* the API. A refresh token is deliberately excluded so
# it can never be replayed as an access token (it only mints new access tokens at /oauth/token).
ACCESS_TOKEN_KINDS = (TOKEN_SESSION, TOKEN_DEVICE, TOKEN_PAT, TOKEN_OAUTH)

# --- device-flow states ---
DEVICE_PENDING = "pending"
DEVICE_APPROVED = "approved"
DEVICE_CONSUMED = "consumed"
DEVICE_DENIED = "denied"
