"""Which catalog skill reviews a developer's own work — an admin-managed, server-side setting.

Same principle as the rubric weights: the *strategy* lives in the service, not in each developer's
head, so every self-review across the team is done by the same skill. One row per lane, because a
backend diff and a frontend diff want different reviewers; ``default`` is the fallback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ...platform.models import Base

# --- lanes a change can fall into (the policy is keyed by these) ---
LANE_DEFAULT = "default"
LANE_BACKEND = "backend"
LANE_FRONTEND = "frontend"
SELF_REVIEW_LANES = (LANE_DEFAULT, LANE_BACKEND, LANE_FRONTEND)


class SelfReviewPolicy(Base):
    """The self-review setting for one lane: the reviewing skill and whether it is mandatory.

    ``skill_id`` NULL = the lane is not configured yet (self-review is then unavailable for it and
    ``required`` is meaningless). Rows are seeded for every lane on boot so the admin editor always
    has the full set to fill in."""

    __tablename__ = "self_review_policies"

    lane: Mapped[str] = mapped_column(String(20), primary_key=True)
    skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
