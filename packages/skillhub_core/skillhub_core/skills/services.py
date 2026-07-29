"""Application services for the Skills context.

Services hold orchestration and own the transaction boundary; they depend on repository
*Protocols* (``skillhub_core.skills.interfaces``), not on SQLAlchemy or FastAPI — so they are
unit-testable with in-memory fakes and reusable outside the web layer. This is the template the
rest of the Skills context (and later Reviews/Platform) follows."""

from __future__ import annotations

from ..platform.models import User
from .constants import REC_KINDS, REC_STATUSES
from .errors import (
    InvalidNotebook,
    InvalidRecommendation,
    InvalidWeights,
    RecommendationNotFound,
    SkillNotFound,
)
from .interfaces import (
    CatalogRepository,
    EvaluationRepository,
    NotebookRepository,
    RecommendationRepository,
    RubricRepository,
    SkillRepository,
)
from .rubric import (
    CATEGORIZATION_RULES,
    RUBRIC_CALIBRATION,
    RUBRIC_DIMENSIONS,
    RUBRIC_INSTRUCTIONS,
    RUBRIC_VERSION,
    SELECTION_STRATEGY,
    SYNTHESIS_ALGORITHM,
    SYNTHESIS_PROMPT,
    SYNTHESIS_STRATEGY,
)
from .schemas import (
    CategoryInfo,
    EvaluationOut,
    EvaluationResult,
    NotebookOut,
    RecommendationOut,
    Reference,
    SearchHit,
    SkillDetail,
    SkillSummary,
    StatsOut,
    TaskGroupInfo,
)

_DIMENSION_KEYS = {d["key"] for d in RUBRIC_DIMENSIONS}


class RubricService:
    """Serves the rubric/strategy and applies admin weight changes (validate → persist →
    recompute every overall score → commit)."""

    def __init__(self, rubric: RubricRepository) -> None:
        self._rubric = rubric

    def get_rubric(self) -> RubricOut:
        return RubricOut(
            rubric_version=RUBRIC_VERSION,
            instructions=RUBRIC_INSTRUCTIONS,
            dimensions=RUBRIC_DIMENSIONS,
            evaluation_schema=EvaluationResult.model_json_schema(),
            categories=self._rubric.get_taxonomy(),
            weights=self._rubric.get_weights(),
            calibration=RUBRIC_CALIBRATION,
            categorization_rules=CATEGORIZATION_RULES,
            selection_strategy=SELECTION_STRATEGY,
            synthesis_strategy=SYNTHESIS_STRATEGY,
            synthesis_algorithm=SYNTHESIS_ALGORITHM,
            synthesis_prompt=SYNTHESIS_PROMPT,
        )

    def set_weights(self, weights: dict[str, float]) -> dict:
        """Validate against the rubric's dimensions, persist, recompute all overalls, commit.
        Raises :class:`InvalidWeights` on a bad payload (the API maps it to 400)."""
        unknown = set(weights) - _DIMENSION_KEYS
        if unknown:
            raise InvalidWeights(f"unknown dimension(s): {sorted(unknown)}")
        if any(w < 0 for w in weights.values()):
            raise InvalidWeights("weights must be >= 0")
        if sum(weights.values()) <= 0:
            raise InvalidWeights("at least one weight must be > 0")

        saved = self._rubric.set_weights(weights)
        rescored = self._rubric.recompute_overall_scores()
        self._rubric.commit()
        return {"weights": saved, "rescored": rescored}


class NotebookService:
    """Serves and stores the one sandbox-trial notebook attached to each skill. A run either reuses
    the stored notebook or regenerates it (the developer decides before running); this service just
    returns the current one or upserts a fresh one (validate → persist → commit)."""

    def __init__(self, notebooks: NotebookRepository) -> None:
        self._notebooks = notebooks

    def get_notebook(self, skill_id: int) -> NotebookOut | None:
        row = self._notebooks.get(skill_id)
        return NotebookOut(**row) if row is not None else None

    def submit_notebook(
        self,
        skill_id: int,
        *,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> NotebookOut:
        """Store (create/replace) a skill's trial notebook. Raises :class:`SkillNotFound` if the
        skill does not exist and :class:`InvalidNotebook` on a payload that is not a notebook."""
        if not isinstance(notebook, dict) or not notebook.get("cells"):
            raise InvalidNotebook("notebook must be an nbformat object with a non-empty `cells` list")
        row = self._notebooks.upsert(
            skill_id=skill_id,
            scenario=scenario,
            task_group=task_group,
            notebook=notebook,
            summary=summary if isinstance(summary, dict) else {},
            created_by_user_id=created_by_user_id,
        )
        if row is None:
            raise SkillNotFound(f"skill {skill_id} does not exist")
        self._notebooks.commit()
        return NotebookOut(**row)


class SkillService:
    """Read/list/delete for the skill catalog. Owns the transaction boundary for deletes; raises
    :class:`SkillNotFound` (mapped to 404 in the API)."""

    def __init__(self, skills: SkillRepository) -> None:
        self._skills = skills

    def list_skills(
        self, *, search: str | None = None, category: str | None = None, evaluated: bool | None = None
    ) -> list[SkillSummary]:
        return self._skills.list(search=search, category=category, evaluated=evaluated)

    def get_skill(self, skill_id: int) -> SkillDetail:
        detail = self._skills.get(skill_id)
        if detail is None:
            raise SkillNotFound(f"skill {skill_id} not found")
        return detail

    def delete_skill(self, skill_id: int) -> None:
        if not self._skills.delete(skill_id):
            raise SkillNotFound(f"skill {skill_id} not found")
        self._skills.commit()


class IngestService:
    """Ingest an uploaded/imported skill (parse → dedupe gate → upsert → embed). The pipeline owns
    its own commit; this service maps the infra duplicate error to the domain
    :class:`DuplicateSkill` (raised by the repository) and returns the created skill."""

    def __init__(self, skills: SkillRepository) -> None:
        self._skills = skills

    def create(
        self,
        *,
        content: str,
        author: str | None,
        references: list[Reference],
        source_format: str,
        user: User,
    ) -> SkillDetail:
        return self._skills.create(
            content=content,
            author=author,
            references=references,
            source_format=source_format,
            user=user,
        )


class EvaluationService:
    """Evaluation history + assessment submission. Owns the commit on submit; raises
    :class:`SkillNotFound` when the skill (or its version) is absent."""

    def __init__(self, evaluations: EvaluationRepository) -> None:
        self._evaluations = evaluations

    def list_for_skill(self, skill_id: int) -> list[EvaluationOut]:
        rows = self._evaluations.list_for_skill(skill_id)
        if rows is None:
            raise SkillNotFound(f"skill {skill_id} not found")
        return rows

    def submit(
        self,
        skill_id: int,
        *,
        evaluation,
        model: str,
        rubric_version: str,
        categorization,
    ) -> SkillDetail:
        detail = self._evaluations.save_assessment(
            skill_id=skill_id,
            evaluation=evaluation,
            model=model,
            rubric_version=rubric_version,
            categorization=categorization,
        )
        if detail is None:
            raise SkillNotFound(f"skill {skill_id} not found or has no version")
        self._evaluations.commit()
        return detail


class RecommendationService:
    """Curator recommendations. Validates kind/status (→ :class:`InvalidRecommendation`), owns the
    commit on writes, and raises :class:`RecommendationNotFound` on a missing id."""

    def __init__(self, recommendations: RecommendationRepository) -> None:
        self._recs = recommendations

    def list(self, status: str | None = None) -> list[RecommendationOut]:
        return self._recs.list(status)

    def create(self, payload: dict, *, created_by: str | None) -> RecommendationOut:
        if payload.get("kind") not in REC_KINDS:
            raise InvalidRecommendation(f"kind must be one of {REC_KINDS}")
        rec = self._recs.create(payload, created_by)
        self._recs.commit()
        return rec

    def set_status(self, rec_id: int, status: str) -> RecommendationOut:
        if status not in REC_STATUSES:
            raise InvalidRecommendation(f"status must be one of {REC_STATUSES}")
        rec = self._recs.set_status(rec_id, status)
        if rec is None:
            raise RecommendationNotFound(f"recommendation {rec_id} not found")
        self._recs.commit()
        return rec


class CatalogService:
    """Read-only catalog queries (search / stats / task-groups / categories). No transaction
    boundary — a thin seam over the repository so routers stay free of the session and query module."""

    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        return self._catalog.search(query, limit)

    def stats(self) -> StatsOut:
        return self._catalog.stats()

    def task_groups(self) -> list[TaskGroupInfo]:
        return self._catalog.task_groups()

    def categories(self) -> list[CategoryInfo]:
        return self._catalog.categories()
