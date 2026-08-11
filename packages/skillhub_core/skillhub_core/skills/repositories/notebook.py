"""Persistence for the SkillNotebook aggregate — one sandbox-trial notebook per (skill, model).

Self-contained on purpose: it reads the Skill row directly rather than through the Skill
repository, so the trial layer never depends on the catalog layer that displays its numbers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Skill, SkillNotebook


def _current_content_hash(skill: Skill | None) -> tuple[str | None, int | None]:
    version = skill.latest_version if skill else None
    if version is None:
        return None, None
    return version.content_hash, version.version_no


def _objective_rate(summary: dict | None) -> float | None:
    """The OBJECTIVE (quantitative) signal: the best keyword-scorecard pass-rate across the entries
    (0..1) — did the run actually do the required mechanics. The winning entry is the skill itself;
    baselines score lower. None if no scored entry. This is the GATE (a ceiling on effectiveness)."""
    best: float | None = None
    for entry in (summary or {}).get("entries", []):
        total = len(entry.get("passed", [])) + len(entry.get("failed", []))
        if total:
            rate = len(entry.get("passed", [])) / total
            best = rate if best is None else max(best, rate)
    return round(best, 4) if best is not None else None


def _result_grade(summary: dict | None) -> float | None:
    """The QUALITY signal: the judge PANEL's median grade of the trial artifact (0..10), applied to
    what the model actually produced — not to the SKILL.md in the abstract. ``None`` for older,
    ungraded trials. The judge strategy (dimensions, panel, protocol) lives server-side in
    ``rubric.py`` so every developer's grading uses one algorithm."""
    grade = (summary or {}).get("result_grade")
    try:
        return float(grade) if grade is not None else None
    except (TypeError, ValueError):
        return None


def _effectiveness(summary: dict | None) -> float | None:
    """Per-model effectiveness (0..1) — the combined headline. When the trial artifact has been
    graded by the judge panel, the headline is the panel-median grade / 10; but the objective
    scorecard is a CEILING — a run that only completed part of the required mechanics cannot score
    above that pass-rate however good the prose (checks = the gate). Falls back to the plain
    objective pass-rate for older, ungraded trials."""
    objective = _objective_rate(summary)
    grade = _result_grade(summary)
    if grade is not None:
        graded = grade / 10.0
        return round(min(graded, objective) if objective is not None else graded, 4)
    return objective


def _notebook_to_dict(nb: SkillNotebook, current_hash: str | None) -> dict:
    creator = nb.creator
    return {
        "skill_id": nb.skill_id,
        "model": nb.model,
        "scenario": nb.scenario,
        "task_group": nb.task_group,
        "notebook": nb.notebook or {},
        "summary": nb.summary or {},
        "effectiveness": _effectiveness(nb.summary),
        "result_grade": _result_grade(nb.summary),
        "objective_rate": _objective_rate(nb.summary),
        "dimensions": (nb.summary or {}).get("dimensions"),
        "panel": (nb.summary or {}).get("panel"),
        "tested_content_hash": nb.tested_content_hash,
        "tested_version_no": nb.tested_version_no,
        "created_by": (creator.name or creator.email) if creator else None,
        "created_at": nb.created_at,
        "updated_at": nb.updated_at,
        # Stale = the skill's content moved on since this trial was run.
        "stale": bool(
            nb.tested_content_hash and current_hash and nb.tested_content_hash != current_hash
        ),
    }


def get_skill_notebook(session: Session, skill_id: int, model: str) -> dict | None:
    """The sandbox-trial notebook for a (skill, model) pair (plain data, with a computed ``stale``
    flag), or None if no trial has been recorded for that model."""
    nb = session.get(SkillNotebook, (skill_id, model))
    if nb is None:
        return None
    current_hash, _ = _current_content_hash(session.get(Skill, skill_id))
    return _notebook_to_dict(nb, current_hash)


def list_skill_notebooks(session: Session, skill_id: int) -> list[dict]:
    """Every model's trial for a skill (the effectiveness matrix), best-model first."""
    rows = list(
        session.scalars(select(SkillNotebook).where(SkillNotebook.skill_id == skill_id)).all()
    )
    if not rows:
        return []
    current_hash, _ = _current_content_hash(session.get(Skill, skill_id))
    out = [_notebook_to_dict(nb, current_hash) for nb in rows]
    out.sort(key=lambda d: (d["effectiveness"] is not None, d["effectiveness"] or 0), reverse=True)
    return out


def best_effectiveness_by_skill(
    session: Session, skill_ids: list[int]
) -> dict[int, tuple[float, str]]:
    """Best (effectiveness, model) per skill across all its recorded sandbox trials — the
    empirical headline the catalog list surfaces instead of the static rubric score. Skills with
    no trial yet (or no graded/passing entry) are simply absent from the result."""
    if not skill_ids:
        return {}
    rows = list(
        session.scalars(select(SkillNotebook).where(SkillNotebook.skill_id.in_(skill_ids))).all()
    )
    best: dict[int, tuple[float, str]] = {}
    for nb in rows:
        eff = _effectiveness(nb.summary)
        if eff is None:
            continue
        current = best.get(nb.skill_id)
        if current is None or eff > current[0]:
            best[nb.skill_id] = (eff, nb.model)
    return best




def upsert_skill_notebook(
    session: Session,
    *,
    skill_id: int,
    model: str,
    scenario: str,
    task_group: str | None,
    notebook: dict,
    summary: dict,
    created_by_user_id: int | None,
) -> dict | None:
    """Create or replace the (skill, model) trial notebook (flush only; the caller owns the commit).
    Snapshots the skill's current content hash + version so staleness can be shown later. Returns
    None when the skill does not exist."""
    skill = session.get(Skill, skill_id)
    if skill is None:
        return None
    current_hash, version_no = _current_content_hash(skill)
    row = session.get(SkillNotebook, (skill_id, model))
    if row is None:
        row = SkillNotebook(skill_id=skill_id, model=model)
        session.add(row)
    row.scenario = scenario
    row.task_group = task_group
    row.notebook = notebook
    row.summary = summary
    row.tested_content_hash = current_hash
    row.tested_version_no = version_no
    if created_by_user_id is not None:
        row.created_by_user_id = created_by_user_id
    session.flush()
    session.refresh(row)
    return _notebook_to_dict(row, current_hash)




class SqlNotebookRepository:
    """``NotebookRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, skill_id: int, model: str) -> dict | None:
        return get_skill_notebook(self._session, skill_id, model)

    def list_for_skill(self, skill_id: int) -> list[dict]:
        return list_skill_notebooks(self._session, skill_id)

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
        return upsert_skill_notebook(
            self._session,
            skill_id=skill_id,
            model=model,
            scenario=scenario,
            task_group=task_group,
            notebook=notebook,
            summary=summary,
            created_by_user_id=created_by_user_id,
        )

    def commit(self) -> None:
        self._session.commit()


