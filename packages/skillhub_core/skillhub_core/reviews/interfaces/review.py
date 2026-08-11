"""Repository Protocol for the Review aggregate — the seam ``ReviewService`` depends on."""

from __future__ import annotations

from typing import Protocol

from ...platform.models import User
from ..schemas import ReviewOut, ReviewSubmitIn, ReviewSummary


class ReviewRepository(Protocol):
    """Persistence for the peer-review workflow. Returns DTOs (not ORM) so the service stays DB-
    and framework-free and is unit-testable with an in-memory fake. Author-only checks and the
    aggregate's transition rules surface as domain errors; the service owns the commit."""

    def submit(self, author: User, data: ReviewSubmitIn) -> ReviewOut:
        """Create a review awaiting the lead, threading in any self-review of the same task."""
        ...

    def list(
        self, *, status: str | None, author_id: int | None, reviewer_id: int | None
    ) -> list[ReviewSummary]: ...

    def get(self, review_id: int) -> ReviewOut | None: ...

    def submit_result(self, review_id: int, reviewer: User, verdict: str, comments: str) -> ReviewOut | None:
        """Record the lead's verdict. None if the review does not exist; raises
        ``InvalidReviewTransition`` when the aggregate refuses the move."""
        ...

    def resubmit(self, review_id: int, user: User, commit_shas: list[str], note: str) -> ReviewOut | None:
        """Send the task back for another round. None if not found; raises ``NotReviewAuthor`` /
        ``InvalidReviewTransition``."""
        ...

    def acknowledge(self, review_id: int, user: User) -> ReviewOut | None:
        """Author acknowledges the outcome. None if not found; raises ``NotReviewAuthor``."""
        ...

    def delete(self, review_id: int, user: User) -> bool:
        """Withdraw a review (flush only). False if it does not exist; raises ``NotReviewAuthor``
        for someone else's, or ``InvalidReviewTransition`` once it has a verdict and the caller is
        not an admin. Attached self-reviews survive, detached."""
        ...

    def commit(self) -> None: ...
