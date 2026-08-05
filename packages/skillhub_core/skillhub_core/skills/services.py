"""Application services for the Skills context.

Services hold orchestration and own the transaction boundary; they depend on repository
*Protocols* (``skillhub_core.skills.interfaces``), not on SQLAlchemy or FastAPI — so they are
unit-testable with in-memory fakes and reusable outside the web layer. This is the template the
rest of the Skills context (and later Reviews/Platform) follows."""

from __future__ import annotations

from ..platform.models import User
from .constants import REC_KINDS, REC_STATUSES, REC_TARGET_KINDS
from .errors import (
    DuplicateSkill,
    InvalidNotebook,
    InvalidRecommendation,
    InvalidWeights,
    RecommendationNotFound,
    SkillNotFound,
)
from .models import SOURCE_TYPE_UPLOAD
from .parsing import compute_hash, parse
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
    RECOMMENDATION_STRATEGY,
    RESULT_JUDGE_DIMENSIONS,
    RESULT_JUDGE_INSTRUCTIONS,
    RESULT_JUDGE_PANEL,
    RESULT_JUDGE_PROTOCOL,
    RESULT_JUDGE_VERSION,
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
    NotebookModelSummary,
    NotebookOut,
    ParsedSkill,
    RecommendationOut,
    Reference,
    RubricOut,
    SearchHit,
    SkillDetail,
    SkillFitOut,
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
            recommendation_strategy=RECOMMENDATION_STRATEGY,
            synthesis_algorithm=SYNTHESIS_ALGORITHM,
            synthesis_prompt=SYNTHESIS_PROMPT,
            result_judge_version=RESULT_JUDGE_VERSION,
            result_judge_instructions=RESULT_JUDGE_INSTRUCTIONS,
            result_judge_dimensions=RESULT_JUDGE_DIMENSIONS,
            result_judge_panel=RESULT_JUDGE_PANEL,
            result_judge_protocol=RESULT_JUDGE_PROTOCOL,
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
    """Serves and stores sandbox-trial notebooks, one per (skill, executing model). A run either
    reuses the stored notebook or regenerates it (the developer decides before running); this
    service returns one, the effectiveness-by-model matrix, or upserts a fresh one (validate →
    persist → commit)."""

    def __init__(self, notebooks: NotebookRepository) -> None:
        self._notebooks = notebooks

    def get_notebook(self, skill_id: int, model: str | None = None) -> NotebookOut | None:
        """The trial for a specific model, or — when ``model`` is omitted — the skill's best-scoring
        model's trial (back-compat for callers that don't specify a model)."""
        if not model:
            model = self.get_matrix(skill_id).best_model
            if not model:
                return None
        row = self._notebooks.get(skill_id, model)
        return NotebookOut(**row) if row is not None else None

    def get_matrix(self, skill_id: int) -> SkillFitOut:
        """The skill's effectiveness-by-model matrix (best model first)."""
        rows = self._notebooks.list_for_skill(skill_id)
        entries = [
            NotebookModelSummary(
                model=r["model"],
                scenario=r["scenario"],
                effectiveness=r["effectiveness"],
                result_grade=r.get("result_grade"),
                objective_rate=r.get("objective_rate"),
                dimensions=r.get("dimensions"),
                stale=r["stale"],
                created_by=r["created_by"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
        best = next((e.model for e in entries if e.effectiveness is not None), None)
        return SkillFitOut(skill_id=skill_id, best_model=best, entries=entries)

    def submit_notebook(
        self,
        skill_id: int,
        *,
        model: str,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> NotebookOut:
        """Store (create/replace) the (skill, model) trial notebook. Raises :class:`InvalidNotebook`
        on a payload that is not a notebook or a missing model, and :class:`SkillNotFound` if the
        skill does not exist."""
        if not (model or "").strip():
            raise InvalidNotebook("a model id is required (the executing model that produced the trial)")
        if not isinstance(notebook, dict) or not notebook.get("cells"):
            raise InvalidNotebook("notebook must be an nbformat object with a non-empty `cells` list")
        row = self._notebooks.upsert(
            skill_id=skill_id,
            model=model.strip(),
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
    """Ingest an uploaded/imported skill: parse → embed → dedupe gate → upsert. Owns the flow and
    (for the API path) the commit; the granular data operations live on the repository. Raises
    :class:`DuplicateSkill` when an upload under a NEW name is essentially identical to an existing
    skill. (Folds the former ``pipeline.py`` module, which is now a thin shim over this service.)"""

    def __init__(self, skills: SkillRepository) -> None:
        self._skills = skills

    def ingest_parsed(
        self,
        parsed: ParsedSkill,
        *,
        author: str | None,
        source_type: str,
        origin: str | None = None,
        user: User | None = None,
    ) -> dict:
        """Run the ingest algorithm for an already-parsed skill (flush only; the caller owns the
        commit). Returns {skill_id, version_id, is_new_version, embedded, similar_warning, notes}."""
        vector = self._skills.embed(parsed.searchable_text())
        # Same-name re-uploads always add a version; only a NEW name is dedupe-gated.
        if not self._skills.name_exists(parsed.name):
            content_hash = compute_hash(parsed.raw_content, parsed.references)
            dup = self._skills.duplicate_for_new_name(parsed.name, content_hash, parsed.body_md, vector)
            if dup is not None:
                raise DuplicateSkill(dup[0], dup[1])
        return self._skills.save_parsed(
            parsed, author=author, source_type=source_type, origin=origin, user=user, vector=vector
        )

    def create(
        self,
        *,
        content: str,
        author: str | None,
        references: list[Reference],
        source_format: str,
        user: User,
    ) -> SkillDetail:
        parsed = parse(content, source_format=source_format, references=references)
        outcome = self.ingest_parsed(
            parsed, author=author, source_type=SOURCE_TYPE_UPLOAD, origin=None, user=user
        )
        self._skills.commit()
        detail = self._skills.get(outcome["skill_id"])
        detail.similar_warning = outcome["similar_warning"]
        return detail


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

    def list(
        self, status: str | None = None, target_kind: str | None = None
    ) -> list[RecommendationOut]:
        return self._recs.list(status, target_kind)

    def create(self, payload: dict, *, created_by: str | None) -> RecommendationOut:
        if payload.get("kind") not in REC_KINDS:
            raise InvalidRecommendation(f"kind must be one of {REC_KINDS}")
        if payload.get("target_kind", "skill") not in REC_TARGET_KINDS:
            raise InvalidRecommendation(f"target_kind must be one of {REC_TARGET_KINDS}")
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
