"""Read-model over the whole catalog: taxonomy, task groups, aggregate stats and search.

Everything here answers a question about the catalog as a WHOLE, which is why it may depend on the
per-aggregate modules (skill, notebook, recommendation) while none of them depends on it."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import embeddings, serializers
from ..models import Category, Skill, SkillCategory, SkillVersion
from ..schemas import CategoryInfo, SearchHit, StatsOut, TaskGroupInfo
from .notebook import best_effectiveness_by_skill
from .recommendation import open_improve_count_by_skill
from .skill import list_skills, semantic_search


def get_taxonomy(session: Session) -> list[dict]:
    return [
        {"key": c.key, "label": c.label, "description": c.description}
        for c in session.scalars(select(Category).order_by(Category.id)).all()
    ]


def category_infos(session: Session) -> list[dict]:
    """The taxonomy with per-category distinct skill counts (for the /categories listing)."""
    counts = dict(
        session.execute(
            select(SkillCategory.category_id, func.count(func.distinct(SkillCategory.skill_id)))
            .group_by(SkillCategory.category_id)
        ).all()
    )
    categories = session.scalars(select(Category).order_by(Category.id)).all()
    return [
        {
            "key": c.key,
            "label": c.label,
            "description": c.description,
            "skill_count": int(counts.get(c.id, 0)),
        }
        for c in categories
    ]




def task_groups(session: Session) -> list[dict]:
    """Distinct narrow task-groups with their skill count and average score — so evaluators can
    reuse an existing group slug and the dashboard can cluster competing skills."""
    stmt = (
        select(Skill)
        .options(selectinload(Skill.versions).selectinload(SkillVersion.evaluations))
        .where(Skill.task_group.is_not(None))
    )
    skills = list(session.scalars(stmt).all())
    agg: dict[str, dict] = {}
    for s in skills:
        key = s.task_group
        if not key:
            continue
        version = s.latest_version
        evaluation = version.latest_evaluation if version else None
        entry = agg.setdefault(key, {"key": key, "count": 0, "_scores": []})
        entry["count"] += 1
        if evaluation is not None:
            entry["_scores"].append(float(evaluation.overall_score))
    out = []
    for entry in agg.values():
        scores = entry.pop("_scores")
        entry["avg_overall"] = round(sum(scores) / len(scores), 2) if scores else None
        out.append(entry)
    out.sort(key=lambda d: -d["count"])
    return out




def stats(session: Session) -> dict:
    """Aggregate numbers for the read-only dashboard."""
    skills = list_skills(session)
    scored: list[tuple[Skill, float]] = []
    for s in skills:
        version = s.latest_version
        evaluation = version.latest_evaluation if version else None
        if evaluation is not None:
            scored.append((s, float(evaluation.overall_score)))

    labels = {c["key"]: c["label"] for c in get_taxonomy(session)}
    cat_counts: dict[str, int] = {}
    for s in skills:
        for sc in s.categories:
            if sc.category is not None:
                cat_counts[sc.category.key] = cat_counts.get(sc.category.key, 0) + 1

    by_category = sorted(
        [{"key": k, "label": labels.get(k, k), "count": v} for k, v in cat_counts.items()],
        key=lambda d: -d["count"],
    )
    top = [
        {"id": s.id, "name": s.name, "overall": round(sc, 2)}
        for s, sc in sorted(scored, key=lambda t: -t[1])[:5]
    ]
    avg = round(sum(sc for _, sc in scored) / len(scored), 2) if scored else None
    return {
        "total": len(skills),
        "evaluated": len(scored),
        "avg_overall": avg,
        "by_category": by_category,
        "top": top,
    }




class SqlCatalogRepository:
    """``CatalogRepository`` backed by SQLAlchemy (+ the embedding model for semantic search)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int) -> list[SearchHit]:
        vector = embeddings.embed(query)
        if vector is not None:
            hits = semantic_search(self._session, vector, limit=limit)
            best_effectiveness = best_effectiveness_by_skill(self._session, [s.id for s, _ in hits])
            open_improve = open_improve_count_by_skill(self._session, [s.name for s, _ in hits])
            return [
                SearchHit(
                    skill=serializers.skill_to_summary(
                        s, best_effectiveness.get(s.id), open_improve.get(s.name, 0)
                    ),
                    similarity=round(sim, 4),
                )
                for s, sim in hits
            ]
        # Fallback: plain name/author match when embeddings are unavailable.
        skills = list_skills(self._session, search=query)[:limit]
        best_effectiveness = best_effectiveness_by_skill(self._session, [s.id for s in skills])
        open_improve = open_improve_count_by_skill(self._session, [s.name for s in skills])
        return [
            SearchHit(
                skill=serializers.skill_to_summary(
                    s, best_effectiveness.get(s.id), open_improve.get(s.name, 0)
                )
            )
            for s in skills
        ]

    def stats(self) -> StatsOut:
        return StatsOut(**stats(self._session))

    def task_groups(self) -> list[TaskGroupInfo]:
        return [TaskGroupInfo(**g) for g in task_groups(self._session)]

    def categories(self) -> list[CategoryInfo]:
        return [CategoryInfo(**c) for c in category_infos(self._session)]




