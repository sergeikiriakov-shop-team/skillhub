"""Task Review context — application/data-access layer: the review workflow + serialization.

State machine: submit -> (reviewer) approve|changes_requested -> (author) resubmit -> submit ...,
and approve -> (author) ack -> done. The lead is the single ``is_reviewer`` user, auto-assigned at
submit time; the code itself lives in git (a Review only carries a pointer + summary).

Self-review lives here too: the author runs the policy's catalog skill over their own change and
posts the report back, which attaches to the peer review for the same task."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..platform.config import get_settings
from ..platform.models import User
from .code_links import commit_url, finding_url, normalize_repo_url
from .errors import (
    InvalidSelfReview,
    NotReviewAuthor,
    SelfReviewPolicyNotSet,
    SelfReviewRequired,
    UnknownReviewSkill,
)
from .models import (
    BLOCKING_SEVERITIES,
    EVENT_ACK,
    EVENT_RESUBMIT,
    EVENT_SELF_REVIEW,
    EVENT_SUBMIT,
    EVENT_VERDICT,
    LANE_DEFAULT,
    REVIEW_APPROVED,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_DONE,
    REVIEW_SUBMITTED,
    SELF_REVIEW_CHANGES,
    SELF_REVIEW_LANES,
    SELF_REVIEW_PASS,
    SELF_REVIEW_VERDICTS,
    SEVERITIES,
    VERDICT_APPROVE,
    VERDICT_CHANGES,
    Review,
    ReviewEvent,
    SelfReview,
    SelfReviewFix,
    SelfReviewPolicy,
)
from .schemas import (
    ReviewEventOut,
    ReviewOut,
    SelfReviewFinding,
    SelfReviewFindingOut,
    SelfReviewFixOut,
    SelfReviewOut,
    SelfReviewPolicyLane,
    SelfReviewPolicyOut,
    SelfReviewSummary,
)
from .schemas import ReviewSummary as ReviewSummaryOut


class ReviewError(Exception):
    """Invalid review-workflow transition (e.g. approving a review that is not awaiting review)."""


def _default_reviewer(session: Session) -> User | None:
    """The single lead: the first user flagged ``is_reviewer``. None if none is designated yet."""
    return session.scalars(
        select(User).where(User.is_reviewer.is_(True)).order_by(User.id)
    ).first()


def _loaded(session: Session, review_id: int) -> Review | None:
    return session.scalars(
        select(Review)
        .where(Review.id == review_id)
        .options(
            selectinload(Review.author),
            selectinload(Review.reviewer),
            selectinload(Review.events).selectinload(ReviewEvent.author),
            selectinload(Review.self_reviews).selectinload(SelfReview.author),
        )
    ).first()


def submit_review(session: Session, author: User, data) -> Review:
    """Create a review (status ``submitted``) with a submit event; auto-assign the lead.

    When the self-review policy is mandatory, the author must have self-reviewed this task first —
    the lead's queue then only ever holds work that already passed the team's review skill."""
    if self_review_required(session) and not has_self_review(session, author.id, data.task_ref):
        raise SelfReviewRequired(
            f"self-review is required before handing {data.task_ref} to the lead — run the "
            "configured review skill and post it with submit_self_review"
        )
    reviewer = _default_reviewer(session)
    review = Review(
        task_ref=data.task_ref,
        title=data.title or "",
        branch=data.branch,
        commit_shas=list(data.commit_shas or []),
        summary=data.summary or "",
        files=list(data.files or []),
        verified_notes=data.verified_notes or "",
        status=REVIEW_SUBMITTED,
        author_user_id=author.id,
        reviewer_user_id=reviewer.id if reviewer else None,
    )
    session.add(review)
    session.flush()
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_SUBMIT, author_user_id=author.id, body=data.summary or "")
    )
    attach_self_reviews(session, review, author)
    session.flush()
    return review


def list_reviews(
    session: Session,
    *,
    status: str | None = None,
    author_id: int | None = None,
    reviewer_id: int | None = None,
) -> list[Review]:
    stmt = select(Review).options(selectinload(Review.author), selectinload(Review.reviewer))
    if status:
        stmt = stmt.where(Review.status == status)
    if author_id is not None:
        stmt = stmt.where(Review.author_user_id == author_id)
    if reviewer_id is not None:
        stmt = stmt.where(Review.reviewer_user_id == reviewer_id)
    return list(session.scalars(stmt.order_by(Review.updated_at.desc())).all())


def get_review(session: Session, review_id: int) -> Review | None:
    return _loaded(session, review_id)


def submit_result(session: Session, review: Review, reviewer: User, verdict: str, comments: str) -> Review:
    """Record the lead's verdict. ``approve`` -> approved; ``changes_requested`` -> changes_requested
    (comments required). Only a review awaiting review (submitted) can be decided."""
    if review.status != REVIEW_SUBMITTED:
        raise ReviewError(f"review {review.id} is not awaiting review (status={review.status})")
    if verdict == VERDICT_APPROVE:
        review.status = REVIEW_APPROVED
    elif verdict == VERDICT_CHANGES:
        if not comments.strip():
            raise ReviewError("changes_requested requires comments")
        review.status = REVIEW_CHANGES_REQUESTED
    else:
        raise ReviewError(f"unknown verdict '{verdict}'")
    review.reviewer_user_id = reviewer.id
    session.add(
        ReviewEvent(
            review_id=review.id, kind=EVENT_VERDICT, author_user_id=reviewer.id, verdict=verdict, body=comments
        )
    )
    session.flush()
    return review


def resubmit(session: Session, review: Review, author: User, commit_shas: list[str], note: str) -> Review:
    """Author sends the task back for another round after addressing the feedback."""
    if review.status not in (REVIEW_CHANGES_REQUESTED, REVIEW_APPROVED):
        raise ReviewError(f"review {review.id} cannot be resubmitted (status={review.status})")
    if commit_shas:
        review.commit_shas = list(commit_shas)
    review.status = REVIEW_SUBMITTED
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_RESUBMIT, author_user_id=author.id, body=note)
    )
    session.flush()
    return review


def acknowledge(session: Session, review: Review, author: User, note: str = "") -> Review:
    """Author acknowledges the outcome. An approved review closes (``done``)."""
    if review.status == REVIEW_APPROVED:
        review.status = REVIEW_DONE
    session.add(
        ReviewEvent(review_id=review.id, kind=EVENT_ACK, author_user_id=author.id, body=note)
    )
    session.flush()
    return review


# --- self-review ---------------------------------------------------------------------------------


def _catalog_skill(session: Session, name: str):
    """Resolve a catalog skill by name. Imported lazily: the reviewing skill is a *pointer into the
    Skills context*, and this data-access layer is the only place the two contexts touch."""
    from ..skills.models import Skill

    return session.scalars(select(Skill).where(Skill.name == name)).first()


def _skill_name(session: Session, skill_id: int | None) -> str | None:
    if skill_id is None:
        return None
    from ..skills.models import Skill

    return session.scalars(select(Skill.name).where(Skill.id == skill_id)).first()


def _policy_row(session: Session, lane: str) -> SelfReviewPolicy | None:
    return session.get(SelfReviewPolicy, lane)


def _policy_lane_out(session: Session, row: SelfReviewPolicy) -> SelfReviewPolicyLane:
    return SelfReviewPolicyLane(
        lane=row.lane,
        skill_id=row.skill_id,
        skill=_skill_name(session, row.skill_id),
        required=row.required,
    )


def get_policy(session: Session) -> SelfReviewPolicyOut:
    """Every lane's setting. Rows are seeded on boot, so an unconfigured lane shows up with a null
    skill rather than going missing."""
    rows = {r.lane: r for r in session.scalars(select(SelfReviewPolicy)).all()}
    lanes = [
        _policy_lane_out(session, rows[lane])
        for lane in SELF_REVIEW_LANES
        if lane in rows
    ]
    return SelfReviewPolicyOut(lanes=lanes)


def get_lane_policy(session: Session, lane: str) -> SelfReviewPolicyLane | None:
    row = _policy_row(session, lane)
    return _policy_lane_out(session, row) if row is not None else None


def set_policy(
    session: Session, lane: str, skill: str | None, required: bool, admin: User
) -> SelfReviewPolicyLane:
    """Point a lane at the catalog skill that reviews it. Flush only."""
    if lane not in SELF_REVIEW_LANES:
        raise InvalidSelfReview(f"unknown lane '{lane}' (expected one of {', '.join(SELF_REVIEW_LANES)})")
    skill_id = None
    if skill:
        found = _catalog_skill(session, skill)
        if found is None:
            raise UnknownReviewSkill(f"skill '{skill}' is not in the catalog")
        skill_id = found.id
    row = _policy_row(session, lane)
    if row is None:
        row = SelfReviewPolicy(lane=lane)
        session.add(row)
    row.skill_id = skill_id
    row.required = bool(required)
    row.updated_by_user_id = admin.id
    session.flush()
    return _policy_lane_out(session, row)


def self_review_required(session: Session) -> bool:
    """Whether a self-review gates handing a task to the lead. Any lane flagged ``required`` turns
    the gate on for everyone — one predictable team-wide rule, since the author does not declare a
    lane when submitting to the lead."""
    lane = session.scalars(
        select(SelfReviewPolicy.lane).where(SelfReviewPolicy.required.is_(True))
    ).first()
    return lane is not None


def has_self_review(session: Session, author_id: int, task_ref: str) -> bool:
    found = session.scalars(
        select(SelfReview.id)
        .where(SelfReview.author_user_id == author_id, SelfReview.task_ref == task_ref)
        .limit(1)
    ).first()
    return found is not None


def _derive_verdict(findings: list[SelfReviewFinding], stated: str | None) -> str:
    """A stated verdict wins; otherwise blocker/major findings mean the change is not ready."""
    if stated:
        if stated not in SELF_REVIEW_VERDICTS:
            raise InvalidSelfReview(
                f"unknown verdict '{stated}' (expected one of {', '.join(SELF_REVIEW_VERDICTS)})"
            )
        return stated
    blocking = any(f.severity in BLOCKING_SEVERITIES for f in findings)
    return SELF_REVIEW_CHANGES if blocking else SELF_REVIEW_PASS


def _validate_findings(findings: list[SelfReviewFinding]) -> None:
    for finding in findings:
        if finding.severity not in SEVERITIES:
            raise InvalidSelfReview(
                f"unknown severity '{finding.severity}' (expected one of {', '.join(SEVERITIES)})"
            )


def _open_review_for(session: Session, author_id: int, task_ref: str) -> Review | None:
    """The author's most recent still-open peer review of this task, if any."""
    return session.scalars(
        select(Review)
        .where(
            Review.author_user_id == author_id,
            Review.task_ref == task_ref,
            Review.status != REVIEW_DONE,
        )
        .order_by(Review.id.desc())
    ).first()


def create_self_review(session: Session, author: User, data) -> SelfReview:
    """Record one self-review run. The reviewing skill defaults to the lane's configured one, so the
    team's setting — not the client — decides who reviews. Flush only."""
    lane = data.lane or LANE_DEFAULT
    if lane not in SELF_REVIEW_LANES:
        raise InvalidSelfReview(f"unknown lane '{lane}' (expected one of {', '.join(SELF_REVIEW_LANES)})")
    findings = list(data.findings or [])
    _validate_findings(findings)

    if data.skill:
        found = _catalog_skill(session, data.skill)
        if found is None:
            raise UnknownReviewSkill(f"skill '{data.skill}' is not in the catalog")
        skill_id, skill_name = found.id, found.name
    else:
        policy = _policy_row(session, lane)
        if policy is None or policy.skill_id is None:
            raise SelfReviewPolicyNotSet(
                f"no self-review skill is configured for lane '{lane}' — an admin sets it via "
                "PUT /api/self-reviews/policy"
            )
        skill_id, skill_name = policy.skill_id, _skill_name(session, policy.skill_id) or ""

    review = None
    if data.review_id is not None:
        review = session.get(Review, data.review_id)
        if review is None:
            raise InvalidSelfReview(f"review {data.review_id} not found")
        # A self-review is the author's own account of their own change — it may only be attached to
        # a review they authored, never to someone else's.
        if review.author_user_id != author.id and not author.is_admin:
            raise NotReviewAuthor(f"review {data.review_id} was not submitted by you")
    else:
        review = _open_review_for(session, author.id, data.task_ref)

    self_review = SelfReview(
        task_ref=data.task_ref,
        branch=data.branch,
        commit_shas=list(data.commit_shas or []),
        repo=normalize_repo_url(data.repo),
        lane=lane,
        skill_id=skill_id,
        skill_name=skill_name,
        model=data.model or "",
        verdict=_derive_verdict(findings, data.verdict),
        summary=data.summary or "",
        findings=[f.model_dump() for f in findings],
        review_id=review.id if review is not None else None,
        author_user_id=author.id,
    )
    session.add(self_review)
    session.flush()
    if review is not None:
        _add_self_review_event(session, review, self_review, author)
    session.flush()
    return self_review


def _add_self_review_event(
    session: Session, review: Review, self_review: SelfReview, author: User
) -> None:
    """Put the self-review into the peer review's thread, so the lead sees it in context."""
    blocking = sum(1 for f in (self_review.findings or []) if f.get("severity") in BLOCKING_SEVERITIES)
    body = (
        f"{self_review.skill_name}: {self_review.verdict} — "
        f"{len(self_review.findings or [])} finding(s), {blocking} blocking"
    )
    if self_review.summary:
        body = f"{body}\n{self_review.summary}"
    session.add(
        ReviewEvent(
            review_id=review.id,
            kind=EVENT_SELF_REVIEW,
            author_user_id=author.id,
            self_review_id=self_review.id,
            body=body,
        )
    )


def attach_self_reviews(session: Session, review: Review, author: User) -> int:
    """Attach the author's unattached self-reviews of this task to a newly created peer review, and
    thread them. Returns how many were attached."""
    orphans = list(
        session.scalars(
            select(SelfReview)
            .where(
                SelfReview.author_user_id == author.id,
                SelfReview.task_ref == review.task_ref,
                SelfReview.review_id.is_(None),
            )
            .order_by(SelfReview.id)
        ).all()
    )
    for self_review in orphans:
        self_review.review_id = review.id
        _add_self_review_event(session, review, self_review, author)
    return len(orphans)


def list_self_reviews(
    session: Session,
    *,
    author_id: int | None = None,
    task_ref: str | None = None,
    review_id: int | None = None,
) -> list[SelfReview]:
    stmt = select(SelfReview).options(selectinload(SelfReview.author))
    if author_id is not None:
        stmt = stmt.where(SelfReview.author_user_id == author_id)
    if task_ref:
        stmt = stmt.where(SelfReview.task_ref == task_ref)
    if review_id is not None:
        stmt = stmt.where(SelfReview.review_id == review_id)
    return list(session.scalars(stmt.order_by(SelfReview.id.desc())).all())


def get_self_review(session: Session, self_review_id: int) -> SelfReview | None:
    return session.scalars(
        select(SelfReview)
        .where(SelfReview.id == self_review_id)
        .options(selectinload(SelfReview.author), selectinload(SelfReview.fixes).selectinload(SelfReviewFix.author))
    ).first()


def record_fixes(session: Session, self_review: SelfReview, user: User, fixes) -> int:
    """Record what the developer did about individual findings. Flush only.

    Deliberately additive: nothing about the review changes — not the verdict, not the severities,
    not the findings — because the point is to show the fix *against* what was originally said."""
    if self_review.author_user_id != user.id and not user.is_admin:
        raise NotReviewAuthor("only the author of a self-review may record fixes on it")
    count = len(self_review.findings or [])
    for fix in fixes:
        if not 0 <= fix.finding_index < count:
            raise InvalidSelfReview(
                f"finding_index {fix.finding_index} is out of range — this self-review has "
                f"{count} finding(s)"
            )
        session.add(
            SelfReviewFix(
                self_review_id=self_review.id,
                finding_index=fix.finding_index,
                commit_sha=(fix.commit_sha or None),
                note=fix.note or "",
                author_user_id=user.id,
            )
        )
    session.flush()
    return len(fixes)


# --- serialization -----------------------------------------------------------------------------


def _event_out(ev: ReviewEvent) -> ReviewEventOut:
    return ReviewEventOut(
        id=ev.id,
        kind=ev.kind,
        author=ev.author.name if ev.author else None,
        verdict=ev.verdict,
        body=ev.body,
        created_at=ev.created_at,
        self_review_id=ev.self_review_id,
    )


def to_self_review_summary(self_review: SelfReview) -> SelfReviewSummary:
    findings = self_review.findings or []
    # Ordered worst-first (SEVERITIES), zero-count severities omitted — the list view shows this
    # instead of the full findings, which are fetched only when a reader opens the review.
    severity_counts = {
        severity: sum(1 for f in findings if f.get("severity") == severity)
        for severity in SEVERITIES
    }
    return SelfReviewSummary(
        id=self_review.id,
        fixed_count=len({f.finding_index for f in self_review.fixes}),
        task_ref=self_review.task_ref,
        branch=self_review.branch,
        lane=self_review.lane,
        skill=self_review.skill_name,
        model=self_review.model,
        verdict=self_review.verdict,
        finding_count=len(findings),
        blocking_count=sum(1 for f in findings if f.get("severity") in BLOCKING_SEVERITIES),
        severity_counts={k: v for k, v in severity_counts.items() if v},
        author=self_review.author.name if self_review.author else None,
        review_id=self_review.review_id,
        created_at=self_review.created_at,
    )


def to_self_review_detail(self_review: SelfReview) -> SelfReviewOut:
    summary = to_self_review_summary(self_review)
    commit_shas = list(self_review.commit_shas or [])
    # Pin links to the commit the review actually read; line numbers drift on a branch. Falls back
    # to the branch when the run recorded no SHAs.
    ref = commit_shas[-1] if commit_shas else self_review.branch
    template = get_settings().code_link_template if not self_review.repo else ""
    fixes_by_finding: dict[int, list[SelfReviewFixOut]] = {}
    for fix in self_review.fixes:
        fixes_by_finding.setdefault(fix.finding_index, []).append(
            SelfReviewFixOut(
                id=fix.id,
                finding_index=fix.finding_index,
                commit_sha=fix.commit_sha,
                note=fix.note,
                author=fix.author.name if fix.author else None,
                created_at=fix.created_at,
                commit_url=commit_url(self_review.repo, fix.commit_sha),
            )
        )
    findings = []
    for index, raw in enumerate(self_review.findings or []):
        finding = SelfReviewFindingOut(**raw)
        finding.url = finding_url(
            repo=self_review.repo,
            ref=ref,
            path=finding.file,
            line=finding.line,
            template=template,
        )
        finding.fixes = fixes_by_finding.get(index, [])
        findings.append(finding)
    return SelfReviewOut(
        **summary.model_dump(),
        commit_shas=commit_shas,
        repo=self_review.repo,
        summary=self_review.summary,
        findings=findings,
    )


def to_summary(review: Review) -> ReviewSummaryOut:
    return ReviewSummaryOut(
        id=review.id,
        task_ref=review.task_ref,
        title=review.title,
        branch=review.branch,
        status=review.status,
        author=review.author.name if review.author else None,
        reviewer=review.reviewer.name if review.reviewer else None,
        updated_at=review.updated_at,
    )


def to_detail(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        task_ref=review.task_ref,
        title=review.title,
        branch=review.branch,
        status=review.status,
        author=review.author.name if review.author else None,
        reviewer=review.reviewer.name if review.reviewer else None,
        updated_at=review.updated_at,
        created_at=review.created_at,
        commit_shas=list(review.commit_shas or []),
        summary=review.summary,
        files=list(review.files or []),
        verified_notes=review.verified_notes,
        events=[_event_out(e) for e in review.events],
        self_reviews=[to_self_review_summary(sr) for sr in review.self_reviews],
    )
