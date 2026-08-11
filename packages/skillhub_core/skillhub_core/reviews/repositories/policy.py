"""Persistence for the SelfReviewPolicy aggregate — which catalog skill reviews which lane."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...platform.models import User
from ..errors import InvalidSelfReview, UnknownReviewSkill
from ..models import SELF_REVIEW_LANES, SelfReviewPolicy
from ..schemas import SelfReviewPolicyLane, SelfReviewPolicyOut
from ..serializers import policy as serializer


class SqlSelfReviewPolicyRepository:
    """``SelfReviewPolicyRepository`` backed by SQLAlchemy. Flush only — the service commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _skill_name(self, skill_id: int | None) -> str | None:
        if skill_id is None:
            return None
        from ...skills.models import Skill

        return self._session.scalars(select(Skill.name).where(Skill.id == skill_id)).first()

    def _lane_out(self, row: SelfReviewPolicy) -> SelfReviewPolicyLane:
        return serializer.to_lane(row, self._skill_name(row.skill_id))

    def all_lanes(self) -> SelfReviewPolicyOut:
        """Every lane's setting. Rows are seeded on boot, so an unconfigured lane shows up with a
        null skill rather than going missing."""
        rows = {r.lane: r for r in self._session.scalars(select(SelfReviewPolicy)).all()}
        return SelfReviewPolicyOut(
            lanes=[self._lane_out(rows[lane]) for lane in SELF_REVIEW_LANES if lane in rows]
        )

    def lane(self, lane: str) -> SelfReviewPolicyLane | None:
        row = self._session.get(SelfReviewPolicy, lane)
        return self._lane_out(row) if row is not None else None

    def set_lane(
        self, lane: str, skill: str | None, required: bool, admin: User
    ) -> SelfReviewPolicyLane:
        if lane not in SELF_REVIEW_LANES:
            raise InvalidSelfReview(
                f"unknown lane '{lane}' (expected one of {', '.join(SELF_REVIEW_LANES)})"
            )
        skill_id = None
        if skill:
            from ...skills.models import Skill

            found = self._session.scalars(select(Skill).where(Skill.name == skill)).first()
            if found is None:
                raise UnknownReviewSkill(f"skill '{skill}' is not in the catalog")
            skill_id = found.id
        row = self._session.get(SelfReviewPolicy, lane)
        if row is None:
            row = SelfReviewPolicy(lane=lane)
            self._session.add(row)
        row.skill_id = skill_id
        row.required = bool(required)
        row.updated_by_user_id = admin.id
        self._session.flush()
        return self._lane_out(row)

    def self_review_required(self) -> bool:
        """Whether a self-review gates handing a task to the lead. ANY lane flagged ``required``
        turns the gate on for everyone — one predictable team-wide rule, since the author does not
        declare a lane when submitting to the lead."""
        lane = self._session.scalars(
            select(SelfReviewPolicy.lane).where(SelfReviewPolicy.required.is_(True))
        ).first()
        return lane is not None

    def commit(self) -> None:
        self._session.commit()
