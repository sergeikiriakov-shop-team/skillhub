"""Domain errors for the Skills context.

Services raise these; the API layer maps them to HTTP status codes. Keeping them here (not in the
web layer) lets the services stay framework-agnostic and unit-testable without FastAPI."""

from __future__ import annotations


class SkillsError(Exception):
    """Base class for Skills-context domain errors."""


class InvalidWeights(SkillsError):
    """A rubric-weights update failed validation (unknown dimension, negative, or all-zero)."""


class SkillNotFound(SkillsError):
    """An operation referenced a skill id that does not exist (the API maps it to 404)."""


class InvalidNotebook(SkillsError):
    """A submitted trial notebook failed validation (not a notebook / no cells)."""


class DuplicateSkill(SkillsError):
    """An upload under a NEW name is essentially identical to an existing skill (mapped to 409).
    Carries the existing skill so the API can point the uploader at it."""

    def __init__(self, existing_id: int, existing_name: str) -> None:
        self.existing_id = existing_id
        self.existing_name = existing_name
        super().__init__(f"Identical to existing skill '{existing_name}' (#{existing_id})")


class InvalidRecommendation(SkillsError):
    """A recommendation payload failed validation (unknown kind or status; mapped to 400)."""


class RecommendationNotFound(SkillsError):
    """A recommendation id did not resolve (mapped to 404)."""
