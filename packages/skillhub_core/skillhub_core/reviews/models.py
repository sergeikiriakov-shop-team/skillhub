"""Task Review context — ORM models.

A ``Review`` is a developer's request to have a deploy-ready Prologistics task reviewed by the lead.
It carries a *pointer* to the work (task ref + branch + commit SHAs) plus a summary — the code stays
in git; the lead fetches the branch and reviews the real diff. ``ReviewEvent`` is the append-only
thread (submit → verdict → resubmit → …). Both link to ``users`` in the shared platform kernel.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..platform.models import Base

# --- review status (state machine) ---
REVIEW_SUBMITTED = "submitted"  # in the lead's queue, awaiting review
REVIEW_CHANGES_REQUESTED = "changes_requested"  # lead asked for changes; back with the author
REVIEW_APPROVED = "approved"  # lead approved; author may acknowledge to close
REVIEW_DONE = "done"  # acknowledged/closed
REVIEW_STATUSES = (REVIEW_SUBMITTED, REVIEW_CHANGES_REQUESTED, REVIEW_APPROVED, REVIEW_DONE)

# --- verdicts a reviewer can give ---
VERDICT_APPROVE = "approve"
VERDICT_CHANGES = "changes_requested"
VERDICTS = (VERDICT_APPROVE, VERDICT_CHANGES)

# --- event kinds (the thread) ---
EVENT_SUBMIT = "submit"
EVENT_VERDICT = "verdict"
EVENT_RESUBMIT = "resubmit"
EVENT_ACK = "ack"
EVENT_KINDS = (EVENT_SUBMIT, EVENT_VERDICT, EVENT_RESUBMIT, EVENT_ACK)


class Review(Base):
    """One task handed to the lead for review. Keyed by its own id; a task may be reviewed more than
    once (each is a distinct Review). ``status`` is the queue signal; ``reviewer_user_id`` is the
    assigned lead (the single ``is_reviewer`` user at submit time)."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_ref: Mapped[str] = mapped_column(String(200))  # issue_logs id/link (a pointer, not the code)
    title: Mapped[str] = mapped_column(String(300), default="")
    branch: Mapped[str | None] = mapped_column(String(300), nullable=True)
    commit_shas: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    files: Mapped[list] = mapped_column(JSONB, default=list)  # changed files (paths)
    verified_notes: Mapped[str] = mapped_column(Text, default="")  # what the author checked / didn't
    status: Mapped[str] = mapped_column(String(20), default=REVIEW_SUBMITTED, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reviewer_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped["User"] = relationship("User", foreign_keys=[author_user_id])  # noqa: F821
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewer_user_id])  # noqa: F821
    events: Mapped[list["ReviewEvent"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", order_by="ReviewEvent.id"
    )

    @property
    def latest_verdict(self) -> "ReviewEvent | None":
        for ev in reversed(self.events):
            if ev.kind == EVENT_VERDICT:
                return ev
        return None


class ReviewEvent(Base):
    """One entry in a review's append-only thread: a submit, a reviewer verdict (+ comments), a
    resubmit after fixes, or an author acknowledgement."""

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)  # set on EVENT_VERDICT
    body: Mapped[str] = mapped_column(Text, default="")  # reviewer comments / resubmit note
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review: Mapped["Review"] = relationship(back_populates="events")
    author: Mapped["User | None"] = relationship("User", foreign_keys=[author_user_id])  # noqa: F821
