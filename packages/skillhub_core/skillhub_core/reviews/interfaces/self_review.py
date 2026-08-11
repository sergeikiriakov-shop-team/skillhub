"""Repository Protocols for the SelfReview and SelfReviewPolicy aggregates."""

from __future__ import annotations

from typing import Protocol

from ...platform.models import User
from ..schemas import (
    SelfReviewFixIn,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)


class SelfReviewRepository(Protocol):
    """Persistence for skill-driven self-reviews. Catalog-coupled validation (does this reviewing
    skill exist?) happens here because it needs the Skills context; everything about what a review
    *means* lives on the aggregate."""

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        """Record a run and attach it to a peer review when one is identified (flush only). Raises
        ``InvalidSelfReview`` / ``UnknownReviewSkill`` / ``SelfReviewPolicyNotSet``."""
        ...

    def list(
        self, *, author_id: int | None, task_ref: str | None, review_id: int | None
    ) -> list[SelfReviewSummary]: ...

    def get(self, self_review_id: int) -> SelfReviewOut | None: ...

    def record_fixes(
        self, self_review_id: int, user: User, fixes: list[SelfReviewFixIn]
    ) -> SelfReviewOut | None:
        """Attach "this is how I addressed it" notes to findings (flush only). None if the review
        does not exist; raises ``NotReviewAuthor`` / ``InvalidSelfReview``."""
        ...

    def has_self_review(self, author_id: int, task_ref: str) -> bool:
        """Whether this author already self-reviewed this task (the ``required`` gate)."""
        ...

    def delete(self, self_review_id: int, user: User) -> bool:
        """Delete a self-review, its fixes and its thread entry (flush only). False if it does not
        exist; raises ``NotReviewAuthor`` for someone else's."""
        ...

    def commit(self) -> None: ...


class SelfReviewPolicyRepository(Protocol):
    """Persistence for the admin-managed setting that says WHICH skill reviews which lane."""

    def all_lanes(self) -> SelfReviewPolicyOut: ...

    def lane(self, lane: str) -> SelfReviewPolicyLane | None: ...

    def set_lane(
        self, lane: str, skill: str | None, required: bool, admin: User
    ) -> SelfReviewPolicyLane:
        """Point a lane at a catalog skill (flush only). Raises ``InvalidSelfReview`` for an unknown
        lane and ``UnknownReviewSkill`` when the skill name is not in the catalog."""
        ...

    def self_review_required(self) -> bool:
        """Whether any lane makes a self-review mandatory before handing work to the lead."""
        ...

    def commit(self) -> None: ...
