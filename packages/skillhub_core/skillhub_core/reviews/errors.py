"""Domain errors for the Task Review context.

Services raise these; the API layer maps them to HTTP status codes, so the services stay
framework-agnostic and unit-testable without FastAPI."""

from __future__ import annotations


class ReviewsError(Exception):
    """Base class for Task Review domain errors."""


class TaskReviewNotFound(ReviewsError):
    """A task-review id did not resolve (the API maps it to 404)."""


class NotReviewAuthor(ReviewsError):
    """A non-author (and non-admin) tried an author-only action (mapped to 403)."""


class InvalidReviewTransition(ReviewsError):
    """An illegal move on the board — approving a task with no run, approving twice, approving over
    an unclean run when the policy forbids it, or returning one without a reason (mapped to 409)."""


class SelfReviewNotFound(ReviewsError):
    """A self-review id did not resolve (mapped to 404)."""


class SelfReviewPolicyNotSet(ReviewsError):
    """No reviewing skill is configured for the lane, so a self-review cannot be run or recorded
    against it (mapped to 409). An admin sets it via ``PUT /api/self-reviews/policy``."""


class UnknownReviewSkill(ReviewsError):
    """The named reviewing skill is not in the catalog (mapped to 400)."""


class InvalidSelfReview(ReviewsError):
    """A malformed self-review: unknown lane, verdict or finding severity (mapped to 400)."""


