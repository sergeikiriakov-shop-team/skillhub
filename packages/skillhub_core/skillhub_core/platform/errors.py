"""Domain errors for the Platform context (user administration).

Raised by the platform services and mapped to HTTP status in the API layer, so the services stay
framework-agnostic and unit-testable. (The OAuth / device-grant / session flows in ``auth`` are
protocol infrastructure and keep their own handling — this is only the admin user-management slice.)"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for Platform-context domain errors."""


class UserNotFound(PlatformError):
    """A user id did not resolve (the API maps it to 404)."""


class InvalidRole(PlatformError):
    """A role value is not one of the allowed roles (the API maps it to 400)."""
