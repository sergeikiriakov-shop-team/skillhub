"""Data-access layer: upserts, evaluation/category/embedding persistence and similarity search."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..platform.models import User
from .models import (
    SOURCE_TYPE_SYNTHESIZED,
    SOURCE_TYPE_UPLOAD,
    SYNTHESIZED_AUTHOR,
    Category,
    Evaluation,
    Recommendation,
    Skill,
    SkillCategory,
    SkillEmbedding,
    SkillVersion,
)
from .parsing import compute_hash
from .schemas import (
    CategorizationResult,
    EvaluationResult,
    ParsedSkill,
)


class DuplicateSkillError(Exception):
    """Raised when an upload under a NEW name is essentially identical to an existing skill."""

    def __init__(self, existing_id: int, existing_name: str):
        self.existing_id = existing_id
        self.existing_name = existing_name
        super().__init__(f"Identical to existing skill '{existing_name}' (#{existing_id})")


def normalize_content(text: str) -> str:
    """Collapse all runs of whitespace so trivial reformatting counts as identical content."""
    return " ".join((text or "").split())


# ---------------------------------------------------------------------------
# Upsert / ingest
# ---------------------------------------------------------------------------


def upsert_skill(
    session: Session,
    parsed: ParsedSkill,
    author: str | None = None,
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
    user: User | None = None,
) -> tuple[Skill, SkillVersion, bool]:
    """Find-or-create the skill **by name** (one canonical record per name) and add a new version
    only when the content changed. Records verified authorship from ``user`` when present.
    Returns ``(skill, version, is_new_version)``."""
    # Verified display author: an authenticated uploader can't spoof it (a client-supplied string
    # is only honoured for unauthenticated seed/import).
    display_author = (user.name or user.email) if user is not None else author

    skill = session.scalars(select(Skill).where(Skill.name == parsed.name)).first()
    if skill is None:
        skill = Skill(
            name=parsed.name,
            author=display_author,
            created_by_user_id=user.id if user is not None else None,
            source_type=source_type,
            origin=origin,
        )
        session.add(skill)
        session.flush()

    # A skill authored by the synthesis sentinel is a service-produced "ideal" — tag it so the UI
    # and API can single it out, regardless of the caller-supplied source_type.
    if author == SYNTHESIZED_AUTHOR:
        skill.source_type = SOURCE_TYPE_SYNTHESIZED

    content_hash = compute_hash(parsed.raw_content, parsed.references)
    latest = skill.latest_version
    if latest is not None and latest.content_hash == content_hash:
        return skill, latest, False

    version = SkillVersion(
        skill_id=skill.id,
        version_no=(latest.version_no + 1) if latest else 1,
        source_format=parsed.source_format,
        frontmatter=parsed.frontmatter,
        trigger_text=parsed.trigger_text,
        body_md=parsed.body_md,
        references=[r.model_dump() for r in parsed.references],
        section_headings=parsed.section_headings,
        raw_content=parsed.raw_content,
        content_hash=content_hash,
        created_by_user_id=user.id if user is not None else None,
    )
    session.add(version)
    session.flush()
    return skill, version, True


def skill_with_name_exists(session: Session, name: str) -> bool:
    return session.scalars(select(Skill.id).where(Skill.name == name)).first() is not None


def find_exact_content_duplicate(
    session: Session, content_hash: str, exclude_name: str
) -> Skill | None:
    """A skill under a DIFFERENT name whose any version has this exact content hash."""
    return session.scalars(
        select(Skill)
        .join(SkillVersion, SkillVersion.skill_id == Skill.id)
        .where(SkillVersion.content_hash == content_hash, Skill.name != exclude_name)
        .limit(1)
    ).first()


def nearest_other_skills(
    session: Session, query_vector: list[float], exclude_name: str, limit: int = 5
) -> list[tuple[Skill, float]]:
    """Cosine-similarity neighbours excluding the skill with ``exclude_name`` (so a same-name
    update doesn't match itself). Returns ``(skill, similarity)`` best-first."""
    distance = SkillEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(Skill, distance.label("distance"))
        .join(SkillVersion, SkillVersion.skill_id == Skill.id)
        .join(SkillEmbedding, SkillEmbedding.skill_version_id == SkillVersion.id)
        .where(Skill.name != exclude_name)
        .order_by(distance)
        .limit(limit * 3)
        .options(selectinload(Skill.versions))
    )
    return _dedupe_by_skill(session.execute(stmt).all(), limit)


def save_evaluation(
    session: Session,
    version: SkillVersion,
    result: EvaluationResult,
    model: str,
    rubric_version: str,
) -> Evaluation:
    scores = {
        "clarity": result.clarity,
        "trigger_quality": result.trigger_quality,
        "completeness": result.completeness,
        "reusability": result.reusability,
        "safety": result.safety,
        "structure": result.structure,
    }
    evaluation = Evaluation(
        skill_version_id=version.id,
        model=model,
        rubric_version=rubric_version,
        scores=scores,
        overall_score=result.overall,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        rationale=result.rationale,
    )
    session.add(evaluation)
    session.flush()
    return evaluation


def save_categorization(
    session: Session, skill: Skill, result: CategorizationResult
) -> None:
    """Replace the LLM-sourced category assignments for a skill (manual ones are preserved)."""
    # Narrow "specific job" grouping key (finer than the broad category). Only overwrite when a
    # non-empty value is supplied, so a re-categorization without one (None OR "") keeps the
    # previous group rather than silently clearing it.
    task_group = (result.task_group or "").strip()
    if task_group:
        skill.task_group = task_group

    by_key = {c.key: c for c in session.scalars(select(Category)).all()}

    # Drop previous llm assignments; keep manual ones.
    for existing in list(skill.categories):
        if existing.source == "llm":
            session.delete(existing)
    session.flush()

    seen: set[int] = set()
    assignments = list(result.categories)
    if result.primary_category and result.primary_category not in {a.key for a in assignments}:
        from .schemas import CategoryAssignment

        assignments.insert(0, CategoryAssignment(key=result.primary_category, confidence=1.0))

    for assignment in assignments:
        category = by_key.get(assignment.key)
        if category is None or category.id in seen:
            continue
        seen.add(category.id)
        session.add(
            SkillCategory(
                skill_id=skill.id,
                category_id=category.id,
                confidence=assignment.confidence,
                source="llm",
            )
        )
    session.flush()


def save_embedding(
    session: Session, version: SkillVersion, vector: list[float], model: str
) -> None:
    existing = session.scalars(
        select(SkillEmbedding).where(SkillEmbedding.skill_version_id == version.id)
    ).first()
    if existing:
        existing.embedding = vector
        existing.model = model
    else:
        session.add(
            SkillEmbedding(skill_version_id=version.id, embedding=vector, model=model)
        )
    session.flush()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_taxonomy(session: Session) -> list[dict]:
    return [
        {"key": c.key, "label": c.label, "description": c.description}
        for c in session.scalars(select(Category).order_by(Category.id)).all()
    ]


def task_groups(session: Session) -> list[dict]:
    """Distinct narrow task-groups with their skill count and average score — so evaluators can
    reuse an existing group slug and the dashboard can cluster competing skills."""
    # Load only what the aggregation reads (task_group + latest evaluation score); unlike
    # list_skills(), this does NOT selectinload categories, which are never touched here.
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


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def list_recommendations(session: Session, status: str | None = None) -> list[Recommendation]:
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc())
    if status:
        stmt = stmt.where(Recommendation.status == status)
    return list(session.scalars(stmt).all())


def create_recommendation(session: Session, data: dict, created_by: str | None = None) -> Recommendation:
    # Flush (not commit) to match the rest of the layer: the router owns the transaction.
    rec = Recommendation(**data, created_by=created_by)
    session.add(rec)
    session.flush()
    return rec


def set_recommendation_status(session: Session, rec_id: int, status: str) -> Recommendation | None:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        return None
    rec.status = status
    session.flush()
    return rec


def _loaded_skill_query():
    return select(Skill).options(
        selectinload(Skill.versions).selectinload(SkillVersion.evaluations),
        selectinload(Skill.versions).selectinload(SkillVersion.creator),
        selectinload(Skill.categories).selectinload(SkillCategory.category),
    )


def list_skills(
    session: Session,
    search: str | None = None,
    category: str | None = None,
    evaluated: bool | None = None,
) -> list[Skill]:
    stmt = _loaded_skill_query()
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Skill.name).like(like), func.lower(Skill.author).like(like))
        )
    if category:
        stmt = stmt.join(Skill.categories).join(SkillCategory.category).where(Category.key == category)
    stmt = stmt.order_by(Skill.name)
    skills = list(session.scalars(stmt).unique().all())
    if evaluated is not None:
        # A skill counts as evaluated when its latest version has at least one evaluation.
        skills = [
            s
            for s in skills
            if bool(s.latest_version and s.latest_version.evaluations) == evaluated
        ]
    return skills


def get_skill(session: Session, skill_id: int) -> Skill | None:
    return session.scalars(_loaded_skill_query().where(Skill.id == skill_id)).unique().first()


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


def find_similar(session: Session, skill: Skill, limit: int = 5) -> list[tuple[Skill, float]]:
    """Cosine-similarity neighbours of a skill's latest version, excluding itself."""
    version = skill.latest_version
    if version is None or version.embedding is None:
        return []
    query_vec = version.embedding.embedding
    distance = SkillEmbedding.embedding.cosine_distance(query_vec)
    stmt = (
        select(Skill, distance.label("distance"))
        .join(SkillVersion, SkillVersion.skill_id == Skill.id)
        .join(SkillEmbedding, SkillEmbedding.skill_version_id == SkillVersion.id)
        .where(Skill.id != skill.id)
        .order_by(distance)
        .limit(limit * 3)  # over-fetch, then dedupe multiple versions of the same skill
        .options(
            selectinload(Skill.versions).selectinload(SkillVersion.evaluations),
        )
    )
    return _dedupe_by_skill(session.execute(stmt).all(), limit)


def semantic_search(
    session: Session, query_vector: list[float], limit: int = 20
) -> list[tuple[Skill, float]]:
    """Rank skills by cosine similarity to a query embedding (latest version per skill)."""
    distance = SkillEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(Skill, distance.label("distance"))
        .join(SkillVersion, SkillVersion.skill_id == Skill.id)
        .join(SkillEmbedding, SkillEmbedding.skill_version_id == SkillVersion.id)
        .order_by(distance)
        .limit(limit * 3)
        .options(
            selectinload(Skill.versions).selectinload(SkillVersion.evaluations),
            selectinload(Skill.categories).selectinload(SkillCategory.category),
        )
    )
    return _dedupe_by_skill(session.execute(stmt).all(), limit)


def _dedupe_by_skill(rows, limit: int) -> list[tuple[Skill, float]]:
    """Keep the closest match per skill (rows are pre-ordered by ascending distance)."""
    seen: set[int] = set()
    out: list[tuple[Skill, float]] = []
    for skill, dist in rows:
        if skill.id in seen:
            continue
        seen.add(skill.id)
        out.append((skill, 1.0 - float(dist)))
        if len(out) >= limit:
            break
    return out
