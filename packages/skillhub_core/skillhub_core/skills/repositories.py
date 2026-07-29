"""SQLAlchemy-backed repository classes for the Skills context.

Injectable (each holds a request-scoped :class:`Session`) and satisfies the Protocols in
``skillhub_core.skills.interfaces``. During the incremental DDD refactor these delegate to the
existing query helpers in ``skillhub_core.skills.repository`` (which stays as the shared query
module); over time the query bodies move here and ``repository`` becomes a thin shim."""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import repository


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
