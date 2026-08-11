"""Application service for the Skill aggregate — catalog reads and the single-skill detail."""

from __future__ import annotations

from ..errors import SkillNotFound
from ..interfaces import SkillRepository
from ..schemas import SkillDetail, SkillSummary


class SkillService:
    """Read/list/delete for the skill catalog. Owns the transaction boundary for deletes; raises
    :class:`SkillNotFound` (mapped to 404 in the API)."""

    def __init__(self, skills: SkillRepository) -> None:
        self._skills = skills

    def list_skills(
        self, *, search: str | None = None, category: str | None = None, evaluated: bool | None = None
    ) -> list[SkillSummary]:
        return self._skills.list(search=search, category=category, evaluated=evaluated)

    def get_skill(self, skill_id: int, *, include_references: bool = True) -> SkillDetail:
        detail = self._skills.get(skill_id, include_references=include_references)
        if detail is None:
            raise SkillNotFound(f"skill {skill_id} not found")
        return detail

    def delete_skill(self, skill_id: int) -> None:
        if not self._skills.delete(skill_id):
            raise SkillNotFound(f"skill {skill_id} not found")
        self._skills.commit()




