"""Application service for evaluations — the assessments Claude Code submits back."""

from __future__ import annotations

from ..errors import SkillNotFound
from ..interfaces import EvaluationRepository
from ..schemas import EvaluationOut, SkillDetail


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




