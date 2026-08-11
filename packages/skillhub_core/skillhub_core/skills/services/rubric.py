"""Application service for the rubric: the evaluation strategy served to every developer's Claude
Code, and the admin-managed weights behind the server-computed ``overall``."""

from __future__ import annotations

from ..errors import InvalidWeights
from ..interfaces import RubricRepository
from ..rubric import (
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
from ..schemas import EvaluationResult, RubricOut

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




