"""What the developer did about one finding — recorded next to the review, never inside it.

A self-review is a statement about the code at a point in time; editing it later to say "fixed"
would destroy exactly the record worth keeping (what the skill caught, and how bad it looked then).
So fixes live in their own table and are layered on at read time: the verdict, the findings and
their severities stay frozen, and the page additionally shows which commit closed each point."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base


class SelfReviewFix(Base):
    """One "this is how I addressed it" note against one finding of a self-review.

    ``finding_index`` points into the review's frozen ``findings`` list. ``commit_sha`` is optional:
    not every finding is closed by code (a missing test run, a deliberate non-issue), and a note
    alone is a legitimate answer — but for the ones that are, the sha is what makes the fix
    reviewable at a glance. A finding may collect several fixes; they are shown in order."""

    __tablename__ = "self_review_fixes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    self_review_id: Mapped[int] = mapped_column(
        ForeignKey("self_reviews.id", ondelete="CASCADE"), index=True
    )
    finding_index: Mapped[int] = mapped_column(Integer)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped["User | None"] = relationship("User", foreign_keys=[author_user_id])  # noqa: F821
    self_review: Mapped["SelfReview"] = relationship(back_populates="fixes")  # noqa: F821
