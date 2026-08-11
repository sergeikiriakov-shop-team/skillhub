"""Repository Protocol for the SkillNotebook aggregate — the seam its service depends on."""

from __future__ import annotations

from typing import Protocol

from ..schemas import NotebookModelSummary

class NotebookRepository(Protocol):
    """Persistence for the sandbox-trial notebooks attached to a skill, one per executing model."""

    def get(self, skill_id: int, model: str) -> dict | None:
        """The (skill, model) notebook as plain data (with a computed ``stale`` flag), or None."""
        ...

    def list_for_skill(self, skill_id: int) -> list[dict]:
        """Every model's trial for the skill (the effectiveness matrix), best-model first."""
        ...

    def upsert(
        self,
        *,
        skill_id: int,
        model: str,
        scenario: str,
        task_group: str | None,
        notebook: dict,
        summary: dict,
        created_by_user_id: int | None,
    ) -> dict | None:
        """Create/replace the (skill, model) notebook; None if the skill does not exist."""
        ...

    def commit(self) -> None: ...




