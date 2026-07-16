"""SQLAlchemy ORM models for the SkillHub registry.

The internal representation is Claude-Code-shaped (name + description + body + references).
Other client formats (Cursor, Codex, Copilot) are recorded via ``SkillVersion.source_format``
and converted through ``skillhub_core.adapters`` on import/export.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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


class Base(DeclarativeBase):
    pass


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tokens: Mapped[list["AuthToken"]] = relationship(
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


class AuthToken(Base):
    """An access credential for one user. The plaintext is shown once; only its SHA-256 is stored.

    ``kind`` is one of ``TOKEN_KINDS``. ``expires_at`` NULL means non-expiring (device tokens/PATs);
    sessions get a TTL."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default=TOKEN_DEVICE)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="tokens")


class DeviceCode(Base):
    """One in-flight OAuth 2.0 Device Authorization Grant (RFC 8628). We store only the SHA-256 of
    the ``device_code``; ``user_code`` is the short human-typed code (worthless without the
    device_code, so kept plaintext)."""

    __tablename__ = "device_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default=DEVICE_PENDING)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    client_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interval: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthClient(Base):
    """A dynamically-registered OAuth client (RFC 7591) — e.g. a developer's Claude Code connecting
    the remote HTTP MCP. Public client (no secret); PKCE is required at the authorize/token steps."""

    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    redirect_uris: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OAuthCode(Base):
    """A short-lived, single-use OAuth authorization code (code flow + PKCE). Stored hashed; bound to
    the client, redirect_uri, PKCE challenge and the authenticated user."""

    __tablename__ = "oauth_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    redirect_uri: Mapped[str] = mapped_column(String(500))
    code_challenge: Mapped[str] = mapped_column(String(128))
    code_challenge_method: Mapped[str] = mapped_column(String(10), default="S256")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    used: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
