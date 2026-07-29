"""SQLAlchemy-backed repository classes for the Skills context.

Injectable (each holds a request-scoped :class:`Session`) and satisfies the Protocols in
``skillhub_core.skills.interfaces``. During the incremental DDD refactor these delegate to the
existing query helpers in ``skillhub_core.skills.repository`` (which stays as the shared query
module); over time the query bodies move here and ``repository`` becomes a thin shim."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..platform.config import get_settings
from ..platform.models import User
from . import embeddings, repository, serializers
from .schemas import (
    CategoryInfo,
    ParsedSkill,
    RecommendationOut,
    SearchHit,
    SkillDetail,
    SkillSummary,
    StatsOut,
    TaskGroupInfo,
)

# A different-named skill at/above this cosine similarity is flagged (not blocked) on upload.
_SIMILAR_WARN_THRESHOLD = 0.90


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

    # --- ingest primitives (orchestrated by IngestService; each delegates to a query helper) ---
    def embed(self, text: str) -> list[float] | None:
        return embeddings.embed(text)

    def name_exists(self, name: str) -> bool:
        return repository.skill_with_name_exists(self._session, name)

    def duplicate_for_new_name(
        self, name: str, content_hash: str, body_md: str, vector: list[float] | None
    ) -> tuple[int, str] | None:
        # Block an essentially-identical copy under a NEW name. "Identical" is judged on the skill
        # BODY (so renaming a copy doesn't slip past); the exact raw-hash is the cheap fallback.
        dup = repository.find_exact_content_duplicate(self._session, content_hash, name)
        if dup is None and vector is not None:
            norm_body = repository.normalize_content(body_md)
            for cand, _sim in repository.nearest_other_skills(self._session, vector, name, limit=3):
                latest = cand.latest_version
                if latest is not None and repository.normalize_content(latest.body_md) == norm_body:
                    dup = cand
                    break
        return (dup.id, dup.name) if dup is not None else None

    def save_parsed(
        self,
        parsed: ParsedSkill,
        *,
        author: str | None,
        source_type: str,
        origin: str | None,
        user: User | None,
        vector: list[float] | None,
    ) -> dict:
        settings = get_settings()
        skill, version, is_new_version = repository.upsert_skill(
            self._session, parsed, author=author, source_type=source_type, origin=origin, user=user
        )
        embedded = False
        notes: list[str] = []
        similar_warning = None
        if vector is not None:
            repository.save_embedding(self._session, version, vector, settings.embedding_model)
            embedded = True
            # Warn (don't block) when a different skill is highly similar — variants are welcome.
            neighbours = repository.nearest_other_skills(self._session, vector, parsed.name, limit=1)
            if neighbours and neighbours[0][1] >= _SIMILAR_WARN_THRESHOLD:
                cand, sim = neighbours[0]
                similar_warning = {"skill_id": cand.id, "name": cand.name, "similarity": round(sim, 4)}
        else:
            notes.append("embedding model unavailable")
        self._session.flush()
        return {
            "skill_id": skill.id,
            "version_id": version.id,
            "is_new_version": is_new_version,
            "embedded": embedded,
            "similar_warning": similar_warning,
            "notes": notes,
        }

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


class SqlCatalogRepository:
    """``CatalogRepository`` backed by SQLAlchemy (+ the embedding model for semantic search)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int) -> list[SearchHit]:
        vector = embeddings.embed(query)
        if vector is not None:
            hits = repository.semantic_search(self._session, vector, limit=limit)
            return [
                SearchHit(skill=serializers.skill_to_summary(s), similarity=round(sim, 4))
                for s, sim in hits
            ]
        # Fallback: plain name/author match when embeddings are unavailable.
        skills = repository.list_skills(self._session, search=query)[:limit]
        return [SearchHit(skill=serializers.skill_to_summary(s)) for s in skills]

    def stats(self) -> StatsOut:
        return StatsOut(**repository.stats(self._session))

    def task_groups(self) -> list[TaskGroupInfo]:
        return [TaskGroupInfo(**g) for g in repository.task_groups(self._session)]

    def categories(self) -> list[CategoryInfo]:
        return [CategoryInfo(**c) for c in repository.category_infos(self._session)]


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
