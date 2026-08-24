"""Persistence for the SelfReview aggregate.

Queries and loading only: the verdict rule, the severity vocabulary and the "a fix never edits the
finding" invariant all live on the aggregate. Flush only — the service owns the commit."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...platform.models import User
from ..code_links import normalize_repo_url
from ..errors import InvalidSelfReview, NotReviewAuthor, SelfReviewPolicyNotSet, UnknownReviewSkill
from ..models import (
    LANE_DEFAULT,
    SELF_REVIEW_LANES,
    TaskReview,
    SelfReview,
    SelfReviewFix,
    SelfReviewPolicy,
    derive_verdict,
    validate_findings,
)
from ..schemas import SelfReviewFixIn, SelfReviewOut, SelfReviewSubmitIn, SelfReviewSummary
from ..serializers import self_review as serializer

class SqlSelfReviewRepository:
    """``SelfReviewRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- loading ---------------------------------------------------------------------------------

    def _loaded(self, self_review_id: int) -> SelfReview | None:
        return self._session.scalars(
            select(SelfReview)
            .where(SelfReview.id == self_review_id)
            .options(
                selectinload(SelfReview.author),
                selectinload(SelfReview.fixes).selectinload(SelfReviewFix.author),
            )
        ).first()

    def _catalog_skill(self, name: str):
        """Resolve a catalog skill by name. Imported lazily: the reviewing skill is a pointer into
        the Skills context, and this layer is the only place the two contexts touch."""
        from ...skills.models import Skill

        return self._session.scalars(select(Skill).where(Skill.name == name)).first()

    def _skill_name(self, skill_id: int | None) -> str:
        if skill_id is None:
            return ""
        from ...skills.models import Skill

        return self._session.scalars(select(Skill.name).where(Skill.id == skill_id)).first() or ""


    # --- writes ----------------------------------------------------------------------------------

    def submit(self, author: User, data: SelfReviewSubmitIn) -> SelfReviewOut:
        lane = data.lane or LANE_DEFAULT
        if lane not in SELF_REVIEW_LANES:
            raise InvalidSelfReview(
                f"unknown lane '{lane}' (expected one of {', '.join(SELF_REVIEW_LANES)})"
            )
        findings = list(data.findings or [])
        validate_findings(findings)
        skill_id, skill_name = self._resolve_skill(lane, data.skill)
        task_review = self._task_review_for(data)

        self_review = SelfReview(
            task_ref=data.task_ref,
            branch=data.branch,
            commit_shas=list(data.commit_shas or []),
            repo=normalize_repo_url(data.repo),
            lane=lane,
            skill_id=skill_id,
            skill_name=skill_name,
            model=data.model or "",
            verdict=derive_verdict(findings, data.verdict),
            summary=data.summary or "",
            findings=[f.model_dump() for f in findings],
            author_user_id=author.id,
        )
        self._session.add(self_review)
        self._session.flush()
        task_review.record_run(self_review)
        self._session.flush()
        return serializer.to_detail(self_review)

    def _task_review_for(self, data: SelfReviewSubmitIn) -> TaskReview:
        """The board row for this task, created on its first run.

        A task reaches the board by being reviewed — there is no separate "submit" step any more,
        so the first run is what puts it in front of the lead."""
        row = self._session.scalars(
            select(TaskReview).where(TaskReview.task_ref == data.task_ref)
        ).first()
        if row is None:
            row = TaskReview(task_ref=data.task_ref, title=data.title or "")
            self._session.add(row)
            self._session.flush()
        elif data.title and not row.title:
            row.title = data.title
        return row

    def _resolve_skill(self, lane: str, requested: str | None) -> tuple[int | None, str]:
        """The lane's configured skill decides who reviews — the client may only override it by
        naming a skill that actually exists, so the record stays truthful either way."""
        if requested:
            found = self._catalog_skill(requested)
            if found is None:
                raise UnknownReviewSkill(f"skill '{requested}' is not in the catalog")
            return found.id, found.name
        policy = self._session.get(SelfReviewPolicy, lane)
        if policy is None or policy.skill_id is None:
            raise SelfReviewPolicyNotSet(
                f"no self-review skill is configured for lane '{lane}' — an admin sets it via "
                "PUT /api/self-reviews/policy"
            )
        return policy.skill_id, self._skill_name(policy.skill_id)


    def record_fixes(
        self, self_review_id: int, user: User, fixes: list[SelfReviewFixIn]
    ) -> SelfReviewOut | None:
        self_review = self._loaded(self_review_id)
        if self_review is None:
            return None
        if self_review.author_user_id != user.id and not user.is_admin:
            raise NotReviewAuthor("only the author of a self-review may record fixes on it")
        for fix in fixes:
            self_review.record_fix(fix.finding_index, fix.commit_sha, fix.note, user.id)
        self._session.flush()
        return serializer.to_detail(self_review)

    def delete(self, self_review_id: int, user: User) -> bool:
        """Delete a self-review and its fixes. False if it does not exist; raises when this user may
        not. The task keeps its remaining runs and re-derives its status; a task left with no runs
        at all leaves the board, since a run is the only thing that puts it there.
        """
        self_review = self._loaded(self_review_id)
        if self_review is None:
            return False
        self_review.assert_deletable_by(user)
        task_review = self_review.task_review
        self._session.delete(self_review)
        self._session.flush()
        if task_review is not None:
            if not task_review.self_reviews:
                self._session.delete(task_review)
            else:
                task_review.resync()
            self._session.flush()
        return True

    # --- reads -----------------------------------------------------------------------------------

    def list(
        self, *, author_id: int | None, task_ref: str | None, task_review_id: int | None
    ) -> list[SelfReviewSummary]:
        stmt = select(SelfReview).options(
            selectinload(SelfReview.author), selectinload(SelfReview.fixes)
        )
        if author_id is not None:
            stmt = stmt.where(SelfReview.author_user_id == author_id)
        if task_ref:
            stmt = stmt.where(SelfReview.task_ref == task_ref)
        if task_review_id is not None:
            stmt = stmt.where(SelfReview.task_review_id == task_review_id)
        rows = self._session.scalars(stmt.order_by(SelfReview.id.desc())).all()
        return [serializer.to_summary(r) for r in rows]

    def get(self, self_review_id: int) -> SelfReviewOut | None:
        row = self._loaded(self_review_id)
        return serializer.to_detail(row) if row is not None else None


    def commit(self) -> None:
        self._session.commit()
