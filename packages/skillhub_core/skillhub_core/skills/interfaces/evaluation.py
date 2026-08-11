"""Repository Protocol for the Evaluation aggregate — the seam its service depends on."""

from __future__ import annotations

from typing import Protocol

from ..schemas import EvaluationOut, SkillDetail

class EvaluationRepository(Protocol):
    """Evaluation history + assessment submission for a skill."""

    def list_for_skill(self, skill_id: int) -> list[EvaluationOut] | None:
        """The skill's evaluations, or None if the skill does not exist."""
        ...

    def save_assessment(
        self,
        *,
        skill_id: int,
        evaluation: dict,
        model: str,
        rubric_version: str,
        categorization: dict | None,
    ) -> SkillDetail | None:
        """Persist an evaluation (+ optional categorization) and return the refreshed detail
        (flush only; caller commits). None if the skill does not exist / has no version."""
        ...

    def commit(self) -> None: ...




