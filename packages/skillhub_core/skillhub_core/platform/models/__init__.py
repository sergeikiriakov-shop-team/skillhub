"""Platform shared-kernel models: identity & access.

Split one module per entity; this package re-exports every name so callers keep importing from
``skillhub_core.platform.models`` unchanged. Importing this package registers all identity models
on the shared :class:`Base`.
"""

from __future__ import annotations

from .auth_token import AuthToken
from .base import (
    ACCESS_TOKEN_KINDS,
    DEVICE_APPROVED,
    DEVICE_CONSUMED,
    DEVICE_DENIED,
    DEVICE_PENDING,
    ROLE_ADMIN,
    ROLE_CONTRIBUTOR,
    ROLE_EVALUATOR,
    ROLE_VIEWER,
    ROLES,
    TOKEN_DEVICE,
    TOKEN_KINDS,
    TOKEN_OAUTH,
    TOKEN_OAUTH_REFRESH,
    TOKEN_PAT,
    TOKEN_SESSION,
    Base,
)
from .device import DeviceCode
from .oauth import OAuthClient, OAuthCode
from .user import User

__all__ = [
    "Base",
    "User",
    "AuthToken",
    "DeviceCode",
    "OAuthClient",
    "OAuthCode",
    "ROLE_VIEWER",
    "ROLE_CONTRIBUTOR",
    "ROLE_EVALUATOR",
    "ROLE_ADMIN",
    "ROLES",
    "TOKEN_SESSION",
    "TOKEN_DEVICE",
    "TOKEN_PAT",
    "TOKEN_OAUTH",
    "TOKEN_OAUTH_REFRESH",
    "TOKEN_KINDS",
    "ACCESS_TOKEN_KINDS",
    "DEVICE_PENDING",
    "DEVICE_APPROVED",
    "DEVICE_CONSUMED",
    "DEVICE_DENIED",
]
