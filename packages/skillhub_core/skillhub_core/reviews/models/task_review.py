"""A task on the review board — the unit the lead actually looks at.

One row per task (`task_ref`), not per run: a developer re-runs the self-review skill as they fix
things, and a board that grew a line per attempt would bury the current state under its own
history. So the status is derived from the LATEST run, the runs stay attached as the history, and
the lead's Approved is recorded once, on the task.

Lifecycle:

    (first run) ──► changes_needed ──(a clean run)──► passed ──(lead)──► approved
                          ▲                                              │
                          └──────────── lead returns it ─────────────────┘

A new run always re-derives the status — including on an approved task, because the code changed
under the approval and the lead's judgement no longer describes what is there."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base

# --- board statuses ---
TASK_REVIEW_CHANGES_NEEDED = "changes_needed"  # the last run found something, or the lead sent it back
TASK_REVIEW_PASSED = "passed"  # the last run was clean; waiting for the lead
TASK_REVIEW_APPROVED = "approved"  # the lead signed it off
TASK_REVIEW_STATUSES = (TASK_REVIEW_CHANGES_NEEDED, TASK_REVIEW_PASSED, TASK_REVIEW_APPROVED)


class TaskReview(Base):
    """One task's review state, with its self-review runs as history."""

    __tablename__ = "task_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_ref: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    branch: Mapped[str | None] = mapped_column(String(300), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(400), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TASK_REVIEW_CHANGES_NEEDED, index=True)
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The lead's sign-off, kept even after a later run re-opens the task — "who approved what, and
    # when" is the question an audit asks, and clearing it on the next run would erase the answer.
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Why the lead sent it back, and when. Set on a return, cleared by the next run that answers it.
    lead_comment: Mapped[str] = mapped_column(Text, default="")
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[author_user_id]
    )
    approved_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[approved_by_user_id]
    )
    self_reviews: Mapped[list["SelfReview"]] = relationship(  # noqa: F821
        "SelfReview", back_populates="task_review", order_by="SelfReview.id"
    )

    # --- the aggregate's own rules ---------------------------------------------------------------

    @property
    def latest_run(self):
        """The run the status reflects. None before the first one (which cannot happen in practice:
        a task reaches the board by being self-reviewed)."""
        return self.self_reviews[-1] if self.self_reviews else None

    def record_run(self, self_review) -> None:
        """Attach a run and re-derive the status from it.

        Deliberately overrides an existing `approved`: the run means the code moved, so the lead's
        sign-off no longer describes what is on the branch. ``approved_by``/``approved_at`` stay as
        the record of what was approved and when."""
        from .self_review import SELF_REVIEW_PASS

        self_review.task_review = self
        self.status = (
            TASK_REVIEW_PASSED if self_review.verdict == SELF_REVIEW_PASS else TASK_REVIEW_CHANGES_NEEDED
        )
        # A fresh run is the author's answer to whatever the lead objected to.
        self.lead_comment = ""
        self.returned_at = None
        if self_review.branch:
            self.branch = self_review.branch
        if self_review.repo:
            self.repo = self_review.repo
        if self.author_user_id is None:
            self.author_user_id = self_review.author_user_id

    def resync(self) -> None:
        """Re-derive the status after a run was deleted.

        An approval is left alone: the lead signed off on what they saw, and removing a later run
        does not retract that."""
        from .self_review import SELF_REVIEW_PASS

        run = self.latest_run
        if run is None or self.status == TASK_REVIEW_APPROVED:
            return
        self.status = (
            TASK_REVIEW_PASSED if run.verdict == SELF_REVIEW_PASS else TASK_REVIEW_CHANGES_NEEDED
        )

    def approve(self, lead, *, require_clean_run: bool) -> None:
        """The lead signs the task off.

        ``require_clean_run`` comes from the self-review policy: when set, a task whose latest run
        still reports blocking findings cannot be approved at all. When it is off the lead may
        approve over an unclean run — a judgement call they are allowed to make — but never over no
        run at all, since there would be nothing to have looked at."""
        from ..errors import InvalidReviewTransition

        if self.latest_run is None:
            raise InvalidReviewTransition(
                f"task {self.task_ref} has no self-review to approve — the developer runs the "
                "self-review skill first"
            )
        if self.status == TASK_REVIEW_APPROVED:
            raise InvalidReviewTransition(f"task {self.task_ref} is already approved")
        if require_clean_run and self.status != TASK_REVIEW_PASSED:
            raise InvalidReviewTransition(
                f"task {self.task_ref} has not passed its self-review (status={self.status}) and "
                "the policy requires a clean run before approval"
            )
        self.status = TASK_REVIEW_APPROVED
        self.approved_by_user_id = lead.id
        self.approved_at = func.now()

    def return_to_author(self, lead, comment: str) -> None:
        """The lead disagrees with a clean run, or wants something changed anyway.

        The comment is mandatory: a task pushed back without a reason costs the developer a whole
        round trip just to ask what was wrong."""
        from ..errors import InvalidReviewTransition

        if not comment.strip():
            raise InvalidReviewTransition("returning a task requires a comment saying what to fix")
        self.status = TASK_REVIEW_CHANGES_NEEDED
        self.lead_comment = comment
        self.returned_at = func.now()

    def assert_deletable_by(self, user) -> None:
        """The author may remove their own task from the board while the lead has not signed it
        off; after an approval only an admin may, so a sign-off cannot be quietly erased."""
        from ..errors import InvalidReviewTransition, NotReviewAuthor

        if user.is_admin:
            return
        if self.author_user_id != user.id:
            raise NotReviewAuthor("only the task's author (or an admin) may delete it")
        if self.status == TASK_REVIEW_APPROVED:
            raise InvalidReviewTransition(
                f"task {self.task_ref} is approved — ask an admin to delete it"
            )
