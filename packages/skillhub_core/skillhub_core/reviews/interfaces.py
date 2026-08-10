"""Repository Protocol for the Task Review context — the seam the ``ReviewService`` depends on.

Returns API DTOs (not ORM) so the service stays DB- and framework-free and is unit-testable with an
in-memory fake. The SQLAlchemy implementation lives in ``skillhub_core.reviews.repositories``."""

from __future__ import annotations

from typing import Protocol

from ..platform.models import User
from .schemas import (
    ReviewOut,
    ReviewSubmitIn,
    ReviewSummary,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)


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


class SelfReviewRepository(Protocol):
    """Persistence for skill-driven self-reviews and the admin-managed policy that says WHICH skill
    does the reviewing. Validation that depends on the catalog (does this skill exist?) and on
    stored policy lives here; the service owns the transaction boundary."""

    def policy(self) -> SelfReviewPolicyOut:
        """Every lane's setting, including the unconfigured ones."""
        ...

    def lane_policy(self, lane: str) -> SelfReviewPolicyLane | None:
        """One lane's setting, or None if ``lane`` is not a known lane."""
        ...

    def set_policy(self, lane: str, skill: str | None, required: bool, admin: User) -> SelfReviewPolicyLane:
        """Point a lane at a catalog skill (flush only). Raises ``InvalidSelfReview`` for an unknown
        lane and ``UnknownReviewSkill`` when the skill name is not in the catalog."""
        ...

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        """Record a self-review run and attach it to a peer review when one is identified (flush
        only). Raises ``InvalidSelfReview`` / ``UnknownReviewSkill`` / ``SelfReviewPolicyNotSet``."""
        ...

    def list(
        self, *, author_id: int | None, task_ref: str | None, review_id: int | None
    ) -> list[SelfReviewSummary]: ...

    def get(self, self_review_id: int) -> SelfReviewOut | None: ...

    def has_self_review(self, author_id: int, task_ref: str) -> bool:
        """Whether this author already self-reviewed this task (the ``required`` gate)."""
        ...

    def commit(self) -> None: ...
