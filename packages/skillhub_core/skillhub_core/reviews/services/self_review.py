"""Application services for self-review and its policy.

Two services because they are two aggregates with different lifecycles and different callers: the
policy is a rarely-changed team setting an admin edits, a self-review is a per-run record every
developer writes. Both own their transaction boundary and map "not found" to a domain error; the
catalog- and rule-coupled failures surface from the repository and the aggregate untouched."""

from __future__ import annotations

from ...platform.models import User
from ..errors import SelfReviewNotFound
from ..interfaces import SelfReviewPolicyRepository, SelfReviewRepository
from ..schemas import (
    SelfReviewFixIn,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSubmitIn,
    SelfReviewSummary,
)


class SelfReviewService:
    def __init__(self, self_reviews: SelfReviewRepository) -> None:
        self._self_reviews = self_reviews

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        self_review = self._self_reviews.submit(author, data)
        self._self_reviews.commit()
        return self_review

    def list(
        self,
        *,
        author_id: int | None = None,
        task_ref: str | None = None,
        review_id: int | None = None,
    ) -> list[SelfReviewSummary]:
        return self._self_reviews.list(author_id=author_id, task_ref=task_ref, review_id=review_id)

    def get(self, self_review_id: int) -> SelfReviewOut:
        self_review = self._self_reviews.get(self_review_id)
        if self_review is None:
            raise SelfReviewNotFound(f"self-review {self_review_id} not found")
        return self_review

    def record_fixes(
        self, self_review_id: int, user: User, fixes: list[SelfReviewFixIn]
    ) -> SelfReviewOut:
        self_review = self._self_reviews.record_fixes(self_review_id, user, fixes)
        if self_review is None:
            raise SelfReviewNotFound(f"self-review {self_review_id} not found")
        self._self_reviews.commit()
        return self_review


class SelfReviewPolicyService:
    """Which catalog skill self-reviews each lane — the team-wide setting, read by every developer's
    Claude Code and written only by an admin."""

    def __init__(self, policies: SelfReviewPolicyRepository) -> None:
        self._policies = policies

    def get_policy(self) -> SelfReviewPolicyOut:
        return self._policies.all_lanes()

    def get_lane_policy(self, lane: str) -> SelfReviewPolicyLane | None:
        return self._policies.lane(lane)

    def set_policy(
        self, admin: User, *, lane: str, skill: str | None, required: bool
    ) -> SelfReviewPolicyLane:
        updated = self._policies.set_lane(lane, skill, required, admin)
        self._policies.commit()
        return updated
