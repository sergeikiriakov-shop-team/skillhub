"""Application services for the Skills context.

Services hold orchestration and own the transaction boundary; they depend on repository
*Protocols* (``skillhub_core.skills.interfaces``), not on SQLAlchemy or FastAPI — so they are
unit-testable with in-memory fakes and reusable outside the web layer. This is the template the
rest of the Skills context (and later Reviews/Platform) follows."""

from __future__ import annotations

from .errors import InvalidNotebook, InvalidWeights, SkillNotFound
from .interfaces import NotebookRepository, RubricRepository
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
from .schemas import EvaluationResult, NotebookOut, RubricOut

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
