"""SQLAlchemy-backed repository classes for the Skills context.

Injectable (each holds a request-scoped :class:`Session`) and satisfies the Protocols in
``skillhub_core.skills.interfaces``. During the incremental DDD refactor these delegate to the
existing query helpers in ``skillhub_core.skills.repository`` (which stays as the shared query
module); over time the query bodies move here and ``repository`` becomes a thin shim."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..platform.models import User
from . import pipeline, repository, serializers
from .errors import DuplicateSkill
from .schemas import RecommendationOut, Reference, SkillDetail, SkillSummary


class SqlRubricRepository:
    """``RubricRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_weights(self) -> dict[str, float]:
        return repository.get_weights(self._session)

    def set_weights(self, weights: dict[str, float]) -> dict[str, float]:
        return repository.set_weights(self._session, weights)

    def recompute_overall_scores(self) -> int:
        return repository.recompute_overall_scores(self._session)

    def get_taxonomy(self) -> list[dict]:
        return repository.get_taxonomy(self._session)

    def commit(self) -> None:
        self._session.commit()


class SqlSkillRepository:
    """``SkillRepository`` backed by SQLAlchemy (serializes ORM → DTO so services stay DB-free)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]:
        skills = repository.list_skills(self._session, search=search, category=category, evaluated=evaluated)
        return [serializers.skill_to_summary(s) for s in skills]

    def get(self, skill_id: int) -> SkillDetail | None:
        skill = repository.get_skill(self._session, skill_id)
        if skill is None:
            return None
        return serializers.skill_to_detail(skill, repository.find_similar(self._session, skill))

    def create(
        self,
        *,
        content: str,
        author: str | None,
        references: list[Reference],
        source_format: str,
        user: User,
    ) -> SkillDetail:
        try:
            result = pipeline.ingest_raw(
                self._session,
                content=content,
                author=author,  # ignored while authenticated; authorship comes from the user
                references=references,
                source_format=source_format,
                user=user,
            )
        except repository.DuplicateSkillError as exc:
            raise DuplicateSkill(exc.existing_id, exc.existing_name) from exc
        skill = repository.get_skill(self._session, result.skill_id)
        detail = serializers.skill_to_detail(skill, repository.find_similar(self._session, skill))
        detail.similar_warning = result.similar_warning
        return detail

    def delete(self, skill_id: int) -> bool:
        skill = repository.get_skill(self._session, skill_id)
        if skill is None:
            return False
        self._session.delete(skill)
        self._session.flush()
        return True

    def commit(self) -> None:
        self._session.commit()


class SqlEvaluationRepository:
    """``EvaluationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_skill(self, skill_id: int) -> list | None:
        skill = repository.get_skill(self._session, skill_id)
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
        skill = repository.get_skill(self._session, skill_id)
        if skill is None or skill.latest_version is None:
            return None
        repository.save_evaluation(self._session, skill.latest_version, evaluation, model, rubric_version)
        if categorization is not None:
            repository.save_categorization(self._session, skill, categorization)
        self._session.flush()
        self._session.expire_all()  # drop stale identity-map state so the detail reflects new rows
        skill = repository.get_skill(self._session, skill_id)
        return serializers.skill_to_detail(skill, repository.find_similar(self._session, skill))

    def commit(self) -> None:
        self._session.commit()


class SqlRecommendationRepository:
    """``RecommendationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, status: str | None) -> list[RecommendationOut]:
        return [
            RecommendationOut.model_validate(r, from_attributes=True)
            for r in repository.list_recommendations(self._session, status=status)
        ]

    def create(self, payload: dict, created_by: str | None) -> RecommendationOut:
        rec = repository.create_recommendation(self._session, payload, created_by=created_by)
        self._session.flush()
        self._session.refresh(rec)  # populate server-side defaults (created_at, status) for the DTO
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def set_status(self, rec_id: int, status: str) -> RecommendationOut | None:
        rec = repository.set_recommendation_status(self._session, rec_id, status)
        if rec is None:
            return None
        self._session.flush()
        self._session.refresh(rec)
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def commit(self) -> None:
        self._session.commit()


class SqlNotebookRepository:
    """``NotebookRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, skill_id: int) -> dict | None:
        return repository.get_skill_notebook(self._session, skill_id)

    def upsert(
        self,
        *,
        skill_id: int,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> dict | None:
        return repository.upsert_skill_notebook(
            self._session,
            skill_id=skill_id,
            scenario=scenario,
            task_group=task_group,
            notebook=notebook,
            summary=summary,
            created_by_user_id=created_by_user_id,
        )

    def commit(self) -> None:
        self._session.commit()
