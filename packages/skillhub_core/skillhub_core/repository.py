"""Data-access layer: upserts, evaluation/category/embedding persistence and similarity search."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    SOURCE_TYPE_UPLOAD,
    Category,
    Evaluation,
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


# ---------------------------------------------------------------------------
# Upsert / ingest
# ---------------------------------------------------------------------------


def upsert_skill(
    session: Session,
    parsed: ParsedSkill,
    author: str | None = None,
    source_type: str = SOURCE_TYPE_UPLOAD,
    origin: str | None = None,
) -> tuple[Skill, SkillVersion, bool]:
    """Find-or-create the skill by (name, author, origin) and add a new version only when the
    content changed. Returns ``(skill, version, is_new_version)``."""
    skill = session.scalars(
        select(Skill).where(
            Skill.name == parsed.name,
            Skill.author.is_(author) if author is None else Skill.author == author,
            Skill.origin.is_(origin) if origin is None else Skill.origin == origin,
        )
    ).first()
    if skill is None:
        skill = Skill(name=parsed.name, author=author, source_type=source_type, origin=origin)
        session.add(skill)
        session.flush()

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
    )
    session.add(version)
    session.flush()
    return skill, version, True


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


def _loaded_skill_query():
    return select(Skill).options(
        selectinload(Skill.versions).selectinload(SkillVersion.evaluations),
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
