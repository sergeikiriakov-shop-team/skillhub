"""Domain errors for the Skills context.

Services raise these; the API layer maps them to HTTP status codes. Keeping them here (not in the
web layer) lets the services stay framework-agnostic and unit-testable without FastAPI."""

from __future__ import annotations


class SkillsError(Exception):
    """Base class for Skills-context domain errors."""


class InvalidWeights(SkillsError):
    """A rubric-weights update failed validation (unknown dimension, negative, or all-zero)."""
