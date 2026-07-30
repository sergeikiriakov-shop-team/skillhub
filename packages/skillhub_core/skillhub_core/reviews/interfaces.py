"""Repository Protocol for the Task Review context — the seam the ``ReviewService`` depends on.

Returns API DTOs (not ORM) so the service stays DB- and framework-free and is unit-testable with an
in-memory fake. The SQLAlchemy implementation lives in ``skillhub_core.reviews.repositories``."""

from __future__ import annotations

from typing import Protocol

from ..platform.models import User
from .schemas import ReviewOut, ReviewSubmitIn, ReviewSummary


class ReviewRepository(Protocol):
    """Persistence + the review workflow (submit → verdict → resubmit → ack). Data-coupled rules
    (author-only actions, legal transitions) are enforced here and surface as domain errors; the
    service owns the transaction boundary (commit)."""

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        """Create a review (status ``submitted``) with a submit event; flush only."""
        ...

    def list(
        self, *, status: str | None, author_id: int | None, reviewer_id: int | None
    ) -> list[ReviewSummary]: ...

    def get(self, review_id: int) -> ReviewOut | None: ...

    def submit_result(self, review_id: int, reviewer: User, verdict: str, comments: str) -> ReviewOut | None:
        """Record the lead's verdict (flush only). None if the review does not exist; raises
        ``InvalidReviewTransition`` for an illegal transition."""
        ...

    def resubmit(self, review_id: int, user: User, commit_shas: list[str], note: str) -> ReviewOut | None:
        """Author sends the task back for another round (flush only). None if not found; raises
        ``NotReviewAuthor`` / ``InvalidReviewTransition``."""
        ...

    def acknowledge(self, review_id: int, user: User) -> ReviewOut | None:
        """Author acknowledges the outcome (flush only). None if not found; raises
        ``NotReviewAuthor``."""
        ...

    def commit(self) -> None: ...
