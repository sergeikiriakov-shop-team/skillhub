"""Persistence for the Recommendation aggregate — curator findings about skills and MCP servers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Recommendation, Skill
from ..schemas import RecommendationOut


def open_improve_count_by_skill(session: Session, skill_names: list[str]) -> dict[str, int]:
    """Count of OPEN (proposed/accepted) `improve`-kind curator recommendations naming each skill
    in `targets` — surfaced on the catalog card so an outstanding suggestion isn't buried on the
    separate Recommendations page. Keyed by skill NAME (targets store names, not ids)."""
    if not skill_names:
        return {}
    names = set(skill_names)
    rows = list(
        session.scalars(
            select(Recommendation).where(
                Recommendation.target_kind == "skill",
                Recommendation.status.in_(["proposed", "accepted"]),
                Recommendation.kind == "improve",
            )
        ).all()
    )
    counts: dict[str, int] = {}
    for rec in rows:
        for target in rec.targets or []:
            if target in names:
                counts[target] = counts.get(target, 0) + 1
    return counts


def open_recommendations_for_skill(session: Session, skill: Skill) -> list[Recommendation]:
    """Every OPEN (proposed/accepted) recommendation applying to THIS skill: it is a named target,
    or the scope matches the skill's name / task_group / one of its categories. Mirrors the
    matching the skill-detail page used to do client-side against a second /recommendations
    fetch — computed here so it rides along with the single skill fetch instead."""
    cat_keys = {sc.category.key for sc in skill.categories if sc.category is not None}
    rows = list(
        session.scalars(
            select(Recommendation).where(
                Recommendation.target_kind == "skill",
                Recommendation.status.in_(["proposed", "accepted"]),
            )
        ).all()
    )
    matches = []
    for rec in rows:
        targets = rec.targets or []
        if (
            skill.name in targets
            or rec.scope == skill.name
            or (skill.task_group is not None and rec.scope == skill.task_group)
            or (rec.scope is not None and rec.scope in cat_keys)
        ):
            matches.append(rec)
    return matches




def list_recommendations(
    session: Session, status: str | None = None, target_kind: str | None = None
) -> list[Recommendation]:
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc())
    if status:
        stmt = stmt.where(Recommendation.status == status)
    if target_kind:
        stmt = stmt.where(Recommendation.target_kind == target_kind)
    return list(session.scalars(stmt).all())


def create_recommendation(session: Session, data: dict, created_by: str | None = None) -> Recommendation:
    # Flush (not commit): the service owns the transaction.
    rec = Recommendation(**data, created_by=created_by)
    session.add(rec)
    session.flush()
    return rec


def set_recommendation_status(session: Session, rec_id: int, status: str) -> Recommendation | None:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        return None
    rec.status = status
    session.flush()
    return rec




class SqlRecommendationRepository:
    """``RecommendationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, status: str | None, target_kind: str | None = None
    ) -> list[RecommendationOut]:
        return [
            RecommendationOut.model_validate(r, from_attributes=True)
            for r in list_recommendations(self._session, status=status, target_kind=target_kind)
        ]

    def create(self, payload: dict, created_by: str | None) -> RecommendationOut:
        rec = create_recommendation(self._session, payload, created_by=created_by)
        self._session.flush()
        self._session.refresh(rec)  # populate server-side defaults (created_at, status) for the DTO
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def set_status(self, rec_id: int, status: str) -> RecommendationOut | None:
        rec = set_recommendation_status(self._session, rec_id, status)
        if rec is None:
            return None
        self._session.flush()
        self._session.refresh(rec)
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def commit(self) -> None:
        self._session.commit()




