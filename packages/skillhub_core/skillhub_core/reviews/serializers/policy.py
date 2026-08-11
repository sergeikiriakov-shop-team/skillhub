"""SelfReviewPolicy aggregate → DTOs.

The configured skill is stored as an id (a pointer into the Skills context) and shown by name, so
serializing a lane needs that name resolved — the repository passes it in rather than this module
reaching across contexts to fetch it."""

from __future__ import annotations

from ..models import SelfReviewPolicy
from ..schemas import SelfReviewPolicyLane


def to_lane(policy: SelfReviewPolicy, skill_name: str | None) -> SelfReviewPolicyLane:
    return SelfReviewPolicyLane(
        lane=policy.lane,
        skill_id=policy.skill_id,
        skill=skill_name,
        required=policy.required,
    )
