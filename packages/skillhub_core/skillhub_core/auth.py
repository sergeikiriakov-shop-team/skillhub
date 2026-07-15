"""Auth helpers: opaque access tokens, OAuth identity upsert and the device-flow state machine.

Tokens are high-entropy random strings; we store only their SHA-256 (in ``auth_tokens``). Reads
are open. Uploads require ``can_upload``; submitting evaluations requires ``can_evaluate``; user
management requires ``admin``. The OAuth provider (browser login) only provides identity; roles
are assigned inside SkillHub. The device grant (RFC 8628) lets the headless MCP obtain a token."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    DEVICE_APPROVED,
    DEVICE_CONSUMED,
    DEVICE_DENIED,
    DEVICE_PENDING,
    ROLE_ADMIN,
    ROLE_CONTRIBUTOR,
    ROLE_VIEWER,
    ROLES,
    TOKEN_DEVICE,
    AuthToken,
    DeviceCode,
    User,
)

# Human-typed device code: unambiguous alphabet (no 0/O/1/I/L), grouped XXXX-XXXX.
_USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_DEVICE_CODE_TTL = 600  # seconds a device/user code stays valid
_DEVICE_POLL_INTERVAL = 5  # seconds the client must wait between polls


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


# --- access tokens -----------------------------------------------------------------------------


def create_auth_token(
    session: Session,
    user: User,
    kind: str = TOKEN_DEVICE,
    label: str | None = None,
    ttl_seconds: int | None = None,
) -> tuple[AuthToken, str]:
    """Mint a token for ``user`` and return ``(row, plaintext)``. The plaintext is shown once."""
    token = generate_token()
    expires_at = _now() + timedelta(seconds=ttl_seconds) if ttl_seconds else None
    row = AuthToken(
        user_id=user.id, token_hash=hash_token(token), kind=kind, label=label, expires_at=expires_at
    )
    session.add(row)
    session.flush()
    return row, token


def get_user_by_token(session: Session, token: str) -> User | None:
    """Resolve a bearer/cookie token to its user, honouring expiry. Best-effort last_used bump."""
    if not token:
        return None
    row = session.scalars(select(AuthToken).where(AuthToken.token_hash == hash_token(token))).first()
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at < _now():
        return None
    row.last_used_at = _now()  # persisted only if the request commits (writes); harmless on reads
    return row.user


def list_tokens_for_user(session: Session, user: User) -> list[AuthToken]:
    return list(
        session.scalars(
            select(AuthToken).where(AuthToken.user_id == user.id).order_by(AuthToken.id.desc())
        ).all()
    )


def revoke_token(session: Session, token: str) -> bool:
    row = session.scalars(select(AuthToken).where(AuthToken.token_hash == hash_token(token))).first()
    if row is None:
        return False
    session.delete(row)
    return True


def revoke_token_by_id(session: Session, user: User, token_id: int) -> bool:
    """Revoke one of ``user``'s own tokens (self-service). Scoped to the owner."""
    row = session.get(AuthToken, token_id)
    if row is None or row.user_id != user.id:
        return False
    session.delete(row)
    return True


# --- identity ----------------------------------------------------------------------------------


def _default_role() -> str:
    role = get_settings().skillhub_default_role
    return role if role in ROLES else ROLE_VIEWER


def upsert_oauth_user(
    session: Session,
    provider: str,
    sub: str,
    email: str | None,
    name: str | None,
    email_verified: bool,
) -> User:
    """Find-or-create the user behind an OAuth identity. Keyed on the stable
    ``(provider, sub)`` pair; ``email`` is used only (when verified) to link a pre-existing row
    and to match the bootstrap-admin list."""
    settings = get_settings()
    email_l = (email or "").strip().lower() or None

    user = session.scalars(
        select(User).where(User.auth_provider == provider, User.provider_sub == sub)
    ).first()
    if user is None and email_verified and email_l:
        user = session.scalars(select(User).where(User.email == email_l)).first()
        if user is not None:
            user.auth_provider = provider
            user.provider_sub = sub
    if user is None:
        user = User(
            name=name or email_l or "user",
            role=_default_role(),
            email=email_l,
            auth_provider=provider,
            provider_sub=sub,
        )
        session.add(user)

    if name:
        user.name = name
    if email_l:
        user.email = email_l
    if email_verified and email_l and email_l in settings.bootstrap_admin_emails:
        user.role = ROLE_ADMIN

    session.flush()
    return user


# --- admin-created users / bootstrap -----------------------------------------------------------


def create_user(
    session: Session, name: str, role: str = ROLE_CONTRIBUTOR, token: str | None = None
) -> tuple[User, str]:
    """Create a user and an initial (device) token. Returns ``(user, plaintext_token)``."""
    user = User(name=name, role=role)
    session.add(user)
    session.flush()
    token = token or generate_token()
    session.add(
        AuthToken(user_id=user.id, token_hash=hash_token(token), kind=TOKEN_DEVICE, label="admin-created")
    )
    session.flush()
    return user, token


def ensure_bootstrap_admin(session: Session, admin_token: str) -> None:
    """On first boot (no users) with a break-glass token set, create the admin + its token.
    Idempotent: does nothing once any user exists."""
    if not admin_token:
        return
    if session.scalars(select(User).limit(1)).first() is not None:
        return
    user = User(name="admin", role=ROLE_ADMIN)
    session.add(user)
    session.flush()
    session.add(
        AuthToken(
            user_id=user.id, token_hash=hash_token(admin_token), kind=TOKEN_DEVICE, label="bootstrap-admin"
        )
    )
    session.commit()


# --- device authorization grant (RFC 8628) -----------------------------------------------------


def _generate_user_code() -> str:
    raw = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def create_device_code(
    session: Session, client_label: str | None = None, ttl_seconds: int = _DEVICE_CODE_TTL
) -> tuple[DeviceCode, str]:
    """Start a device flow. Returns ``(row, device_code_plaintext)``; ``row.user_code`` is shown
    to the human. Only the SHA-256 of the device_code is stored."""
    device_code = generate_token()
    # Retry user_code on the (rare) collision with another active code.
    for _ in range(5):
        user_code = _generate_user_code()
        if session.scalars(select(DeviceCode).where(DeviceCode.user_code == user_code)).first() is None:
            break
    row = DeviceCode(
        device_code_hash=hash_token(device_code),
        user_code=user_code,
        status=DEVICE_PENDING,
        client_label=client_label,
        interval=_DEVICE_POLL_INTERVAL,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
    )
    session.add(row)
    session.flush()
    return row, device_code


def get_device_by_user_code(session: Session, user_code: str) -> DeviceCode | None:
    if not user_code:
        return None
    return session.scalars(
        select(DeviceCode).where(DeviceCode.user_code == user_code.strip().upper())
    ).first()


def approve_device_code(session: Session, user_code: str, user: User) -> DeviceCode | None:
    """Bind a pending device code to the approving user. Returns the row, or None if invalid/expired."""
    row = get_device_by_user_code(session, user_code)
    if row is None or row.expires_at < _now() or row.status != DEVICE_PENDING:
        return None
    row.status = DEVICE_APPROVED
    row.user_id = user.id
    session.flush()
    return row


def poll_device_token(session: Session, device_code: str) -> tuple[str, str | None]:
    """Poll for the device flow's result. Returns ``(status, access_token | None)`` where status is
    one of: ``authorization_pending``, ``slow_down``, ``expired_token``, ``access_denied``,
    ``success``. On ``success`` the token is minted once and the code is consumed."""
    if not device_code:
        return ("access_denied", None)
    row = session.scalars(
        select(DeviceCode).where(DeviceCode.device_code_hash == hash_token(device_code))
    ).first()
    if row is None or row.status in (DEVICE_DENIED, DEVICE_CONSUMED):
        return ("access_denied", None)
    if row.expires_at < _now():
        return ("expired_token", None)

    now = _now()
    if row.last_polled_at is not None and (now - row.last_polled_at).total_seconds() < row.interval:
        return ("slow_down", None)  # too fast; do not advance last_polled_at
    row.last_polled_at = now

    if row.status == DEVICE_PENDING:
        session.flush()
        return ("authorization_pending", None)
    if row.status == DEVICE_APPROVED:
        user = session.get(User, row.user_id)
        _, plaintext = create_auth_token(session, user, TOKEN_DEVICE, label=row.client_label)
        row.status = DEVICE_CONSUMED
        session.flush()
        return ("success", plaintext)
    return ("access_denied", None)
