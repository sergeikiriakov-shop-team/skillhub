"""Application service for sandbox-trial notebooks — one per (skill, executing model)."""

from __future__ import annotations

from ..errors import InvalidNotebook, SkillNotFound
from ..interfaces import NotebookRepository
from ..schemas import NotebookModelSummary, NotebookOut, SkillFitOut


class NotebookService:
    """Serves and stores sandbox-trial notebooks, one per (skill, executing model). A run either
    reuses the stored notebook or regenerates it (the developer decides before running); this
    service returns one, the effectiveness-by-model matrix, or upserts a fresh one (validate →
    persist → commit)."""

    def __init__(self, notebooks: NotebookRepository) -> None:
        self._notebooks = notebooks

    def get_notebook(
        self, skill_id: int, model: str | None = None, *, include_cells: bool = True
    ) -> NotebookOut | None:
        """The trial for a specific model, or — when ``model`` is omitted — the skill's best-scoring
        model's trial (back-compat for callers that don't specify a model).

        ``include_cells=False`` drops the raw nbformat ``notebook`` (by far the largest field) and
        keeps the scorecard: effectiveness, result_grade, objective_rate, dimensions, panel,
        summary, staleness. That is what a caller deciding "reuse or regenerate?" actually needs;
        the cells are only for reading the transcript."""
        if not model:
            model = self.get_matrix(skill_id).best_model
            if not model:
                return None
        row = self._notebooks.get(skill_id, model)
        if row is None:
            return None
        if not include_cells:
            row = {**row, "notebook": {}}
        return NotebookOut(**row)

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




