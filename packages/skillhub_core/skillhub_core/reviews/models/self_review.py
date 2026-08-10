"""Self-review: a developer reviewing their own change with a catalog skill.

The skill that does the reviewing is chosen server-side (``SelfReviewPolicy``) so the whole team
reviews itself the same way; the developer's own Claude Code applies that SKILL.md to the diff and
posts the result back here. A self-review stands on its own (it points at a task/branch, not at a
peer review) and is attached to a ``Review`` when the task is later handed to the lead."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base

# --- verdict the reviewing skill reached on the author's own change ---
SELF_REVIEW_PASS = "pass"  # nothing blocking found
SELF_REVIEW_CHANGES = "changes_needed"  # the author should fix something before handing it over
SELF_REVIEW_VERDICTS = (SELF_REVIEW_PASS, SELF_REVIEW_CHANGES)

# --- severity of a single finding (ordered: worst first) ---
SEVERITY_BLOCKER = "blocker"
SEVERITY_MAJOR = "major"
SEVERITY_MINOR = "minor"
SEVERITY_NIT = "nit"
SEVERITIES = (SEVERITY_BLOCKER, SEVERITY_MAJOR, SEVERITY_MINOR, SEVERITY_NIT)

# Severities that make a change not ready to hand over (used to derive the verdict when the client
# does not state one, and to gate submission when the policy requires a clean self-review).
BLOCKING_SEVERITIES = (SEVERITY_BLOCKER, SEVERITY_MAJOR)


class SelfReview(Base):
    """One self-review run: which skill reviewed what, under which model, and what it found.

    ``skill_name`` is a snapshot — the catalog entry may later be renamed or deleted, and the record
    of *how* a change was reviewed must survive that. ``findings`` is the skill's report, one entry
    per issue (``severity``, ``file``, ``line``, ``title``, ``detail``, ``suggestion``)."""

    __tablename__ = "self_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_ref: Mapped[str] = mapped_column(String(200), index=True)  # issue_logs id/link
    branch: Mapped[str | None] = mapped_column(String(300), nullable=True)
    commit_shas: Mapped[list] = mapped_column(JSONB, default=list)
    # Browsable base URL of the repository reviewed, normalized from the agent's git remote. Kept
    # per review, not per instance: the team works in more than one repository, and a finding is
    # only linkable against the repo it was actually found in.
    repo: Mapped[str | None] = mapped_column(String(400), nullable=True)
    lane: Mapped[str] = mapped_column(String(20), default="default")  # which policy lane applied
    skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(200), default="")  # snapshot, survives a rename
    model: Mapped[str] = mapped_column(String(60), default="")  # model that ran the review
    verdict: Mapped[str] = mapped_column(String(20), default=SELF_REVIEW_PASS)
    summary: Mapped[str] = mapped_column(Text, default="")
    findings: Mapped[list] = mapped_column(JSONB, default=list)
    review_id: Mapped[int | None] = mapped_column(
        ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True, index=True
    )
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped["User"] = relationship("User", foreign_keys=[author_user_id])  # noqa: F821
    review: Mapped["Review | None"] = relationship(  # noqa: F821
        "Review", back_populates="self_reviews", foreign_keys=[review_id]
    )
    # Owned by the review: a fix is meaningless without the finding it answers.
    fixes: Mapped[list["SelfReviewFix"]] = relationship(  # noqa: F821
        back_populates="self_review", cascade="all, delete-orphan", order_by="SelfReviewFix.id"
    )

    @property
    def blocking_count(self) -> int:
        """Findings severe enough to hold the change back."""
        return sum(1 for f in (self.findings or []) if f.get("severity") in BLOCKING_SEVERITIES)
