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

    @property
    def fixed_count(self) -> int:
        """Findings closed by a commit. A fix carrying only a note is an ANSWER — usually "not
        addressed, because…" — and counting those as fixed would make the progress badge lie."""
        return len({f.finding_index for f in self.fixes if f.commit_sha})

    @property
    def severity_counts(self) -> dict[str, int]:
        """Findings per severity, worst-first, zero counts omitted — enough for a list to show the
        shape of a review without loading every finding."""
        counts = {
            severity: sum(1 for f in (self.findings or []) if f.get("severity") == severity)
            for severity in SEVERITIES
        }
        return {severity: n for severity, n in counts.items() if n}

    def assert_deletable_by(self, user) -> None:
        """A self-review is the author's own account of their own change, so the author may delete
        it at any point in its life — unlike a peer review, no one else's judgement is recorded in
        it. Admins may delete any. Its fixes go with it (they answer findings that no longer
        exist); the peer review it was attached to survives, minus the thread entry."""
        from ..errors import NotReviewAuthor

        if user.is_admin or self.author_user_id == user.id:
            return
        raise NotReviewAuthor("only the author of a self-review (or an admin) may delete it")

    def record_fix(self, finding_index: int, commit_sha: str | None, note: str, author_id: int):
        """Attach "this is how I addressed it" to one finding.

        Deliberately additive: the verdict, the severities and the findings never change, because
        the record is only worth keeping if it still shows what the skill originally said."""
        from ..errors import InvalidSelfReview
        from .self_review_fix import SelfReviewFix

        count = len(self.findings or [])
        if not 0 <= finding_index < count:
            raise InvalidSelfReview(
                f"finding_index {finding_index} is out of range — this self-review has "
                f"{count} finding(s)"
            )
        fix = SelfReviewFix(
            finding_index=finding_index,
            commit_sha=commit_sha or None,
            note=note or "",
            author_user_id=author_id,
        )
        self.fixes.append(fix)
        return fix


def derive_verdict(findings, stated: str | None) -> str:
    """The verdict a set of findings implies. A stated one wins; otherwise any blocker/major means
    the change is not ready to hand over.

    A domain rule, not a formatting detail: it decides whether work reaches the lead, so it lives
    with the model rather than wherever the payload happens to be unpacked."""
    from ..errors import InvalidSelfReview

    if stated:
        if stated not in SELF_REVIEW_VERDICTS:
            raise InvalidSelfReview(
                f"unknown verdict '{stated}' (expected one of {', '.join(SELF_REVIEW_VERDICTS)})"
            )
        return stated
    blocking = any(getattr(f, "severity", None) in BLOCKING_SEVERITIES for f in findings)
    return SELF_REVIEW_CHANGES if blocking else SELF_REVIEW_PASS


def validate_findings(findings) -> None:
    """Reject a severity outside the vocabulary rather than storing a finding nothing can rank."""
    from ..errors import InvalidSelfReview

    for finding in findings:
        if finding.severity not in SEVERITIES:
            raise InvalidSelfReview(
                f"unknown severity '{finding.severity}' (expected one of {', '.join(SEVERITIES)})"
            )
