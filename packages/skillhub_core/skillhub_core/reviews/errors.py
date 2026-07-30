"""Domain errors for the Task Review context.

Services raise these; the API layer maps them to HTTP status codes, so the services stay
framework-agnostic and unit-testable without FastAPI."""

from __future__ import annotations


class ReviewsError(Exception):
    """Base class for Task Review domain errors."""


class ReviewNotFound(ReviewsError):
    """A review id did not resolve (the API maps it to 404)."""


class NotReviewAuthor(ReviewsError):
    """A non-author (and non-admin) tried an author-only action — resubmit/ack (mapped to 403)."""


class InvalidReviewTransition(ReviewsError):
    """An illegal workflow transition (e.g. approving a review not awaiting review; mapped to 409)."""
