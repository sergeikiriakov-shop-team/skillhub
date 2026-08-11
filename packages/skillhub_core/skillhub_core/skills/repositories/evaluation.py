"""Persistence for the Evaluation aggregate — a rubric score against one skill version.

Categorization lands here too: it is written by the same assessment submission and, like the score,
is Claude Code's judgement about a version rather than anything the catalog computes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers
from ..models import Category, Evaluation, Skill, SkillCategory, SkillVersion
from ..rubric import compute_overall
from ..schemas import CategorizationResult, EvaluationResult, SkillDetail
from .rubric import get_weights
from .skill import find_similar, get_skill


def save_evaluation(
    session: Session,
    version: SkillVersion,
    result: EvaluationResult,
    model: str,
    rubric_version: str,
) -> Evaluation:
    scores = {
        "clarity": result.clarity,
        "trigger_quality": result.trigger_quality,
        "completeness": result.completeness,
        "reusability": result.reusability,
        "safety": result.safety,
        "structure": result.structure,
    }
    # `overall` is server-authoritative: the weighted mean of the dimension scores under the
    # admin-managed weights, not the model's holistic figure (kept deterministic and re-rankable).
    overall = compute_overall(scores, get_weights(session))
    if overall is None:  # no weights configured yet (shouldn't happen post-seed) — fall back
        overall = float(result.overall)
    evaluation = Evaluation(
        skill_version_id=version.id,
        model=model,
        rubric_version=rubric_version,
        scores=scores,
        overall_score=overall,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        rationale=result.rationale,
    )
    session.add(evaluation)
    session.flush()
    return evaluation


def save_categorization(session: Session, skill: Skill, result: CategorizationResult) -> None:
    """Replace the LLM-sourced category assignments for a skill (manual ones are preserved)."""
    # Only overwrite the task_group when a non-empty value is supplied, so a re-categorization
    # without one keeps the previous group rather than silently clearing it.
    task_group = (result.task_group or "").strip()
    if task_group:
        skill.task_group = task_group

    by_key = {c.key: c for c in session.scalars(select(Category)).all()}

    # Drop previous llm assignments; keep manual ones.
    for existing in list(skill.categories):
        if existing.source == "llm":
            session.delete(existing)
    session.flush()

    seen: set[int] = set()
    assignments = list(result.categories)
    if result.primary_category and result.primary_category not in {a.key for a in assignments}:
        from .schemas import CategoryAssignment

        assignments.insert(0, CategoryAssignment(key=result.primary_category, confidence=1.0))

    for assignment in assignments:
        category = by_key.get(assignment.key)
        if category is None or category.id in seen:
            continue
        seen.add(category.id)
        session.add(
            SkillCategory(
                skill_id=skill.id,
                category_id=category.id,
                confidence=assignment.confidence,
                source="llm",
            )
        )
    session.flush()




class SqlEvaluationRepository:
    """``EvaluationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_skill(self, skill_id: int) -> list | None:
        skill = get_skill(self._session, skill_id)
        if skill is None:
            return None
        version = skill.latest_version
        if version is None:
            return []
        return [serializers.evaluation_to_out(e) for e in version.evaluations]

    def save_assessment(
        self,
        *,
        skill_id: int,
        evaluation,
        model: str,
        rubric_version: str,
        categorization,
    ) -> SkillDetail | None:
        skill = get_skill(self._session, skill_id)
        if skill is None or skill.latest_version is None:
            return None
        save_evaluation(self._session, skill.latest_version, evaluation, model, rubric_version)
        if categorization is not None:
            save_categorization(self._session, skill, categorization)
        self._session.flush()
        self._session.expire_all()  # drop stale identity-map state so the detail reflects new rows
        skill = get_skill(self._session, skill_id)
        return serializers.skill_to_detail(skill, find_similar(self._session, skill))

    def commit(self) -> None:
        self._session.commit()




