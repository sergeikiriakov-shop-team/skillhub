"""The append-only review thread entry."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base

# --- event kinds (the thread) ---
EVENT_SUBMIT = "submit"
EVENT_VERDICT = "verdict"
EVENT_RESUBMIT = "resubmit"
EVENT_ACK = "ack"
EVENT_SELF_REVIEW = "self_review"  # the author's own skill-driven review, attached to this review
EVENT_KINDS = (EVENT_SUBMIT, EVENT_VERDICT, EVENT_RESUBMIT, EVENT_ACK, EVENT_SELF_REVIEW)


class ReviewEvent(Base):
    """One entry in a review's append-only thread: a submit, a reviewer verdict (+ comments), a
    resubmit after fixes, or an author acknowledgement."""

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    self_review_id: Mapped[int | None] = mapped_column(  # set on EVENT_SELF_REVIEW
        ForeignKey("self_reviews.id", ondelete="SET NULL"), nullable=True
    )
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)  # set on EVENT_VERDICT
    body: Mapped[str] = mapped_column(Text, default="")  # reviewer comments / resubmit note
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review: Mapped["Review"] = relationship(back_populates="events")  # noqa: F821
    author: Mapped["User | None"] = relationship("User", foreign_keys=[author_user_id])  # noqa: F821
