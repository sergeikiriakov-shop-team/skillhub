"""Persistence for the Skill aggregate: the catalog entry, its versions and their embeddings.

Also owns finding skills BY skill — similarity and semantic search — because those are questions
about a Skill, not about the catalog as a whole."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ...platform.config import get_settings
from ...platform.models import User
from .. import embeddings, serializers
from ..models import (
    SOURCE_TYPE_SYNTHESIZED,
    SOURCE_TYPE_UPLOAD,
    SYNTHESIZED_AUTHOR,
    Category,
    Skill,
    SkillCategory,
    SkillEmbedding,
    SkillVersion,
)
from ..parsing import compute_hash
from ..schemas import ParsedSkill, SkillDetail, SkillSummary
from .notebook import best_effectiveness_by_skill
from .recommendation import open_improve_count_by_skill, open_recommendations_for_skill

# A different-named skill at/above this cosine similarity is flagged (not blocked) on upload.
_SIMILAR_WARN_THRESHOLD = 0.90


def normalize_content(text: str) -> str:
    """Collapse all runs of whitespace so trivial reformatting counts as identical content."""
    return " ".join((text or "").split())



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




class SqlSkillRepository:
    """``SkillRepository`` backed by SQLAlchemy (serializes ORM → DTO so services stay DB-free)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, search: str | None, category: str | None, evaluated: bool | None) -> list[SkillSummary]:
        skills = list_skills(self._session, search=search, category=category, evaluated=evaluated)
        best_effectiveness = best_effectiveness_by_skill(self._session, [s.id for s in skills])
        open_improve = open_improve_count_by_skill(self._session, [s.name for s in skills])
        return [
            serializers.skill_to_summary(
                s, best_effectiveness.get(s.id), open_improve.get(s.name, 0)
            )
            for s in skills
        ]

    def get(self, skill_id: int, *, include_references: bool = True) -> SkillDetail | None:
        skill = get_skill(self._session, skill_id)
        if skill is None:
            return None
        open_recs = open_recommendations_for_skill(self._session, skill)
        return serializers.skill_to_detail(
            skill,
            find_similar(self._session, skill),
            open_recs,
            include_references=include_references,
        )

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




