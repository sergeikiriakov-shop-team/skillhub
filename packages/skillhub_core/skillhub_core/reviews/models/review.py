"""The Review aggregate root (a task handed to the lead for review)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base
from .event import (
    EVENT_ACK,
    EVENT_RESUBMIT,
    EVENT_SELF_REVIEW,
    EVENT_SUBMIT,
    EVENT_VERDICT,
)

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
    events: Mapped[list["ReviewEvent"]] = relationship(  # noqa: F821
        back_populates="review", cascade="all, delete-orphan", order_by="ReviewEvent.id"
    )
    # Self-reviews the author ran on this task before handing it over. Not owned by the review (they
    # exist before it and outlive it), so no delete-cascade — the FK is nulled instead.
    self_reviews: Mapped[list["SelfReview"]] = relationship(  # noqa: F821
        "SelfReview", back_populates="review", order_by="SelfReview.id"
    )

    @property
    def latest_verdict(self) -> "ReviewEvent | None":  # noqa: F821
        for ev in reversed(self.events):
            if ev.kind == EVENT_VERDICT:
                return ev
        return None

    # --- workflow (the aggregate owns its own transitions) ---------------------------------------
    #
    # Every legal move through the state machine is a method here, not a branch in the repository:
    # the rule "only a review awaiting review can be decided" belongs to the Review itself, and
    # keeping it next to ``status`` is what stops a second caller from inventing a different one.
    # Each move appends to the thread, because a transition that leaves no trace never happened.

    def _record(self, kind: str, author_id: int, body: str = "", verdict: str | None = None) -> None:
        from .event import ReviewEvent

        self.events.append(
            ReviewEvent(kind=kind, author_user_id=author_id, body=body, verdict=verdict)
        )

    def open_for_review(self, author_id: int, summary: str = "") -> None:
        """Opening entry in the thread — the review starts life already awaiting the lead."""
        self._record(EVENT_SUBMIT, author_id, summary)

    def decide(self, reviewer_id: int, verdict: str, comments: str) -> None:
        """Record the lead's verdict: ``approve`` → approved, ``changes_requested`` → back to the
        author (comments required — a change request without them is not actionable)."""
        from ..errors import InvalidReviewTransition

        if self.status != REVIEW_SUBMITTED:
            raise InvalidReviewTransition(
                f"review {self.id} is not awaiting review (status={self.status})"
            )
        if verdict == VERDICT_APPROVE:
            self.status = REVIEW_APPROVED
        elif verdict == VERDICT_CHANGES:
            if not comments.strip():
                raise InvalidReviewTransition("changes_requested requires comments")
            self.status = REVIEW_CHANGES_REQUESTED
        else:
            raise InvalidReviewTransition(f"unknown verdict '{verdict}'")
        self.reviewer_user_id = reviewer_id
        self._record(EVENT_VERDICT, reviewer_id, comments, verdict=verdict)

    def resubmit(self, author_id: int, commit_shas: list[str], note: str) -> None:
        """Author sends the task back for another round after addressing the feedback."""
        from ..errors import InvalidReviewTransition

        if self.status not in (REVIEW_CHANGES_REQUESTED, REVIEW_APPROVED):
            raise InvalidReviewTransition(
                f"review {self.id} cannot be resubmitted (status={self.status})"
            )
        if commit_shas:
            self.commit_shas = list(commit_shas)
        self.status = REVIEW_SUBMITTED
        self._record(EVENT_RESUBMIT, author_id, note)

    def acknowledge(self, author_id: int, note: str = "") -> None:
        """Author acknowledges the outcome; an approved review closes. Acknowledging anything else
        is a no-op on the status by design — the author confirming they read a change request is
        legitimate, it just does not close anything."""
        if self.status == REVIEW_APPROVED:
            self.status = REVIEW_DONE
        self._record(EVENT_ACK, author_id, note)

    def assert_deletable_by(self, user) -> None:
        """Who may withdraw this review, and when.

        The author may withdraw their own submission while it is still awaiting a verdict —
        a mistyped task or a duplicate should not need an admin. Once the lead has ruled on it, the
        thread is a record of someone else's judgement, so only an admin may remove it: an author
        who could delete a `changes_requested` review could quietly erase the request and resubmit
        as if it never happened."""
        from ..errors import InvalidReviewTransition, NotReviewAuthor

        if user.is_admin:
            return
        if self.author_user_id != user.id:
            raise NotReviewAuthor("only the review's author (or an admin) may delete it")
        if self.status != REVIEW_SUBMITTED:
            raise InvalidReviewTransition(
                f"review {self.id} already has a verdict (status={self.status}) — ask an admin to "
                "delete it; withdrawing your own review is only possible before it is decided"
            )

    def detach_self_review(self, self_review_id: int) -> None:
        """Drop the thread entry that carried a now-deleted self-review.

        The FK alone would only null the pointer, leaving an event describing findings the reader
        can no longer open — worse than no entry at all."""
        self.events[:] = [
            event for event in self.events if event.self_review_id != self_review_id
        ]

    def attach_self_review(self, self_review, author_id: int) -> None:
        """Link a self-review of the same task and thread it, so the lead sees what the author
        already caught before opening the diff."""
        self_review.review_id = self.id
        blocking, total = self_review.blocking_count, len(self_review.findings or [])
        body = f"{self_review.skill_name}: {self_review.verdict} — {total} finding(s), {blocking} blocking"
        if self_review.summary:
            body = f"{body}\n{self_review.summary}"
        self._record(EVENT_SELF_REVIEW, author_id, body)
        self.events[-1].self_review_id = self_review.id
