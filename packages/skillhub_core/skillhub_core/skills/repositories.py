"""SQLAlchemy data-access for the Skills context: the injectable ``Sql*Repository`` classes that
satisfy the Protocols in ``skillhub_core.skills.interfaces``, plus the query/persistence functions
they are built on.

The query bodies live here (previously in ``skillhub_core.skills.repository``, now a thin
back-compat shim that re-exports these). Each ``Sql*Repository`` holds a request-scoped
:class:`Session` and is the seam the application services depend on."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..platform.config import get_settings
from ..platform.models import User
from . import embeddings, serializers
from .models import (
    SOURCE_TYPE_SYNTHESIZED,
    SOURCE_TYPE_UPLOAD,
    SYNTHESIZED_AUTHOR,
    Category,
    Evaluation,
    Recommendation,
    RubricWeight,
    Skill,
    SkillCategory,
    SkillEmbedding,
    SkillNotebook,
    SkillVersion,
)
from .parsing import compute_hash
from .rubric import compute_overall
from .schemas import (
    CategorizationResult,
    CategoryInfo,
    EvaluationResult,
    ParsedSkill,
    RecommendationOut,
    SearchHit,
    SkillDetail,
    SkillSummary,
    StatsOut,
    TaskGroupInfo,
)

# A different-named skill at/above this cosine similarity is flagged (not blocked) on upload.
_SIMILAR_WARN_THRESHOLD = 0.90


class DuplicateSkillError(Exception):
    """Raised when an upload under a NEW name is essentially identical to an existing skill.
    Kept for back-compat; the ingest flow now raises the domain ``errors.DuplicateSkill``."""

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

    # A skill authored by the synthesis sentinel is a service-produced "ideal" — tag it.
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
    # `overall` is server-authoritative: the weighted mean of the dimension scores under the
    # admin-managed weights, not the model's holistic figure (kept deterministic and re-rankable).
    overall = compute_overall(scores, get_weights(session))
    if overall is None:  # no weights configured yet (shouldn't happen post-seed) — fall back
        overall = float(result.overall)
    evaluation = Evaluation(
        skill_version_id=version.id,
        model=model,
        rubric_version=rubric_version,
        scores=scores,
        overall_score=overall,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        rationale=result.rationale,
    )
    session.add(evaluation)
    session.flush()
    return evaluation


def save_categorization(session: Session, skill: Skill, result: CategorizationResult) -> None:
    """Replace the LLM-sourced category assignments for a skill (manual ones are preserved)."""
    # Only overwrite the task_group when a non-empty value is supplied, so a re-categorization
    # without one keeps the previous group rather than silently clearing it.
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


def save_embedding(session: Session, version: SkillVersion, vector: list[float], model: str) -> None:
    existing = session.scalars(
        select(SkillEmbedding).where(SkillEmbedding.skill_version_id == version.id)
    ).first()
    if existing:
        existing.embedding = vector
        existing.model = model
    else:
        session.add(SkillEmbedding(skill_version_id=version.id, embedding=vector, model=model))
    session.flush()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Rubric weights (admin-managed; drive the server-computed overall score)
# ---------------------------------------------------------------------------


def get_weights(session: Session) -> dict[str, float]:
    """Current dimension weights (dimension -> weight), as stored in the DB."""
    return {r.dimension: float(r.weight) for r in session.scalars(select(RubricWeight)).all()}


def set_weights(session: Session, weights: dict[str, float]) -> dict[str, float]:
    """Upsert the given dimension weights (flush only; the caller owns the transaction)."""
    existing = {r.dimension: r for r in session.scalars(select(RubricWeight)).all()}
    for dimension, weight in weights.items():
        if dimension in existing:
            existing[dimension].weight = float(weight)
        else:
            session.add(RubricWeight(dimension=dimension, weight=float(weight)))
    session.flush()
    return get_weights(session)


def recompute_overall_scores(session: Session) -> int:
    """Recompute every evaluation's overall_score from its stored per-dimension scores and the
    current weights. Call after the weights change. Returns how many rows were updated."""
    weights = get_weights(session)
    updated = 0
    for evaluation in session.scalars(select(Evaluation)).all():
        recomputed = compute_overall(evaluation.scores or {}, weights)
        if recomputed is not None and recomputed != evaluation.overall_score:
            evaluation.overall_score = recomputed
            updated += 1
    session.flush()
    return updated


# ---------------------------------------------------------------------------
# Skill sandbox notebooks (one per skill; the run record from evals/)
# ---------------------------------------------------------------------------


def _current_content_hash(skill: Skill | None) -> tuple[str | None, int | None]:
    version = skill.latest_version if skill else None
    if version is None:
        return None, None
    return version.content_hash, version.version_no


def _effectiveness(summary: dict | None) -> float | None:
    """The skill's effectiveness for this trial = the best pass-rate across the scorecard entries
    (0..1). The winning entry is the skill itself; baselines score lower. None if no scored entry."""
    best: float | None = None
    for entry in (summary or {}).get("entries", []):
        total = len(entry.get("passed", [])) + len(entry.get("failed", []))
        if total:
            rate = len(entry.get("passed", [])) / total
            best = rate if best is None else max(best, rate)
    return round(best, 4) if best is not None else None


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
    current_hash, _ = _current_content_hash(get_skill(session, skill_id))
    return _notebook_to_dict(nb, current_hash)


def list_skill_notebooks(session: Session, skill_id: int) -> list[dict]:
    """Every model's trial for a skill (the effectiveness matrix), best-model first."""
    rows = list(
        session.scalars(select(SkillNotebook).where(SkillNotebook.skill_id == skill_id)).all()
    )
    if not rows:
        return []
    current_hash, _ = _current_content_hash(get_skill(session, skill_id))
    out = [_notebook_to_dict(nb, current_hash) for nb in rows]
    out.sort(key=lambda d: (d["effectiveness"] is not None, d["effectiveness"] or 0), reverse=True)
    return out


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
    skill = get_skill(session, skill_id)
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


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def list_recommendations(session: Session, status: str | None = None) -> list[Recommendation]:
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc())
    if status:
        stmt = stmt.where(Recommendation.status == status)
    return list(session.scalars(stmt).all())


def create_recommendation(session: Session, data: dict, created_by: str | None = None) -> Recommendation:
    # Flush (not commit): the service owns the transaction.
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


# ---------------------------------------------------------------------------
# Skill listing / retrieval / similarity
# ---------------------------------------------------------------------------


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
        .options(selectinload(Skill.versions).selectinload(SkillVersion.evaluations))
    )
    return _dedupe_by_skill(session.execute(stmt).all(), limit)


def semantic_search(session: Session, query_vector: list[float], limit: int = 20) -> list[tuple[Skill, float]]:
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


# ---------------------------------------------------------------------------
# Injectable repositories (the seam the application services depend on)
# ---------------------------------------------------------------------------


class SqlRubricRepository:
    """``RubricRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_weights(self) -> dict[str, float]:
        return get_weights(self._session)

    def set_weights(self, weights: dict[str, float]) -> dict[str, float]:
        return set_weights(self._session, weights)

    def recompute_overall_scores(self) -> int:
        return recompute_overall_scores(self._session)

    def get_taxonomy(self) -> list[dict]:
        return get_taxonomy(self._session)

    def commit(self) -> None:
        self._session.commit()


class SqlSkillRepository:
    """``SkillRepository`` backed by SQLAlchemy (serializes ORM → DTO so services stay DB-free)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]:
        skills = list_skills(self._session, search=search, category=category, evaluated=evaluated)
        return [serializers.skill_to_summary(s) for s in skills]

    def get(self, skill_id: int) -> SkillDetail | None:
        skill = get_skill(self._session, skill_id)
        if skill is None:
            return None
        return serializers.skill_to_detail(skill, find_similar(self._session, skill))

    # --- ingest primitives (orchestrated by IngestService) ---
    def embed(self, text: str) -> list[float] | None:
        return embeddings.embed(text)

    def name_exists(self, name: str) -> bool:
        return skill_with_name_exists(self._session, name)

    def duplicate_for_new_name(
        self, name: str, content_hash: str, body_md: str, vector: list[float] | None
    ) -> tuple[int, str] | None:
        # Block an essentially-identical copy under a NEW name. "Identical" is judged on the skill
        # BODY (so renaming a copy doesn't slip past); the exact raw-hash is the cheap fallback.
        dup = find_exact_content_duplicate(self._session, content_hash, name)
        if dup is None and vector is not None:
            norm_body = normalize_content(body_md)
            for cand, _sim in nearest_other_skills(self._session, vector, name, limit=3):
                latest = cand.latest_version
                if latest is not None and normalize_content(latest.body_md) == norm_body:
                    dup = cand
                    break
        return (dup.id, dup.name) if dup is not None else None

    def save_parsed(
        self,
        parsed: ParsedSkill,
        *,
        author: str | None,
        source_type: str,
        origin: str | None,
        user: User | None,
        vector: list[float] | None,
    ) -> dict:
        settings = get_settings()
        skill, version, is_new_version = upsert_skill(
            self._session, parsed, author=author, source_type=source_type, origin=origin, user=user
        )
        embedded = False
        notes: list[str] = []
        similar_warning = None
        if vector is not None:
            save_embedding(self._session, version, vector, settings.embedding_model)
            embedded = True
            # Warn (don't block) when a different skill is highly similar — variants are welcome.
            neighbours = nearest_other_skills(self._session, vector, parsed.name, limit=1)
            if neighbours and neighbours[0][1] >= _SIMILAR_WARN_THRESHOLD:
                cand, sim = neighbours[0]
                similar_warning = {"skill_id": cand.id, "name": cand.name, "similarity": round(sim, 4)}
        else:
            notes.append("embedding model unavailable")
        self._session.flush()
        return {
            "skill_id": skill.id,
            "version_id": version.id,
            "is_new_version": is_new_version,
            "embedded": embedded,
            "similar_warning": similar_warning,
            "notes": notes,
        }

    def delete(self, skill_id: int) -> bool:
        skill = get_skill(self._session, skill_id)
        if skill is None:
            return False
        self._session.delete(skill)
        self._session.flush()
        return True

    def commit(self) -> None:
        self._session.commit()


class SqlEvaluationRepository:
    """``EvaluationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_skill(self, skill_id: int) -> list | None:
        skill = get_skill(self._session, skill_id)
        if skill is None:
            return None
        version = skill.latest_version
        if version is None:
            return []
        return [serializers.evaluation_to_out(e) for e in version.evaluations]

    def save_assessment(
        self,
        *,
        skill_id: int,
        evaluation,
        model: str,
        rubric_version: str,
        categorization,
    ) -> SkillDetail | None:
        skill = get_skill(self._session, skill_id)
        if skill is None or skill.latest_version is None:
            return None
        save_evaluation(self._session, skill.latest_version, evaluation, model, rubric_version)
        if categorization is not None:
            save_categorization(self._session, skill, categorization)
        self._session.flush()
        self._session.expire_all()  # drop stale identity-map state so the detail reflects new rows
        skill = get_skill(self._session, skill_id)
        return serializers.skill_to_detail(skill, find_similar(self._session, skill))

    def commit(self) -> None:
        self._session.commit()


class SqlRecommendationRepository:
    """``RecommendationRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, status: str | None) -> list[RecommendationOut]:
        return [
            RecommendationOut.model_validate(r, from_attributes=True)
            for r in list_recommendations(self._session, status=status)
        ]

    def create(self, payload: dict, created_by: str | None) -> RecommendationOut:
        rec = create_recommendation(self._session, payload, created_by=created_by)
        self._session.flush()
        self._session.refresh(rec)  # populate server-side defaults (created_at, status) for the DTO
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def set_status(self, rec_id: int, status: str) -> RecommendationOut | None:
        rec = set_recommendation_status(self._session, rec_id, status)
        if rec is None:
            return None
        self._session.flush()
        self._session.refresh(rec)
        return RecommendationOut.model_validate(rec, from_attributes=True)

    def commit(self) -> None:
        self._session.commit()


class SqlCatalogRepository:
    """``CatalogRepository`` backed by SQLAlchemy (+ the embedding model for semantic search)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int) -> list[SearchHit]:
        vector = embeddings.embed(query)
        if vector is not None:
            hits = semantic_search(self._session, vector, limit=limit)
            return [
                SearchHit(skill=serializers.skill_to_summary(s), similarity=round(sim, 4))
                for s, sim in hits
            ]
        # Fallback: plain name/author match when embeddings are unavailable.
        skills = list_skills(self._session, search=query)[:limit]
        return [SearchHit(skill=serializers.skill_to_summary(s)) for s in skills]

    def stats(self) -> StatsOut:
        return StatsOut(**stats(self._session))

    def task_groups(self) -> list[TaskGroupInfo]:
        return [TaskGroupInfo(**g) for g in task_groups(self._session)]

    def categories(self) -> list[CategoryInfo]:
        return [CategoryInfo(**c) for c in category_infos(self._session)]


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
