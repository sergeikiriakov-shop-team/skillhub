"""SQLAlchemy ORM models for the SkillHub registry.

The internal representation is Claude-Code-shaped (name + description + body + references).
Other client formats (Cursor, Codex, Copilot) are recorded via ``SkillVersion.source_format``
and converted through ``skillhub_core.adapters`` on import/export.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..platform.config import get_settings
from ..platform.models import Base

# Re-exported so callers can keep importing them from skillhub_core.models.
from .constants import (  # noqa: F401
    FORMAT_CLAUDE_SKILL,
    FORMAT_CODEX_SKILL,
    FORMAT_COPILOT,
    FORMAT_CURSOR_MDC,
    FORMAT_GENERIC_MD,
    SOURCE_TYPE_IMPORT,
    SOURCE_TYPE_SYNTHESIZED,
    SOURCE_TYPE_UPLOAD,
    SYNTHESIZED_AUTHOR,
)

EMBEDDING_DIM = get_settings().embedding_dim


class Skill(Base):
    """A logical skill — one canonical record per ``name`` (uniqueness enforced by the
    ``uq_skills_name`` index, created in ``db._apply_column_migrations``). Re-uploading the same
    name adds a new :class:`SkillVersion` rather than a duplicate row; genuinely different variants
    live under different names within a shared ``task_group``. ``author`` is a display string;
    ``created_by_user_id`` is the verified original uploader (from OAuth)."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(20), default=SOURCE_TYPE_UPLOAD)
    origin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Narrow "what specific job it does" grouping key (a slug), finer than the broad category.
    # Skills that do the SAME job share a task_group, so competing variants cluster together.
    task_group: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["SkillVersion"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", order_by="SkillVersion.version_no"
    )
    categories: Mapped[list["SkillCategory"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def latest_version(self) -> "SkillVersion | None":
        return self.versions[-1] if self.versions else None


class SkillVersion(Base):
    """One parsed revision of a skill's content."""

    __tablename__ = "skill_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    source_format: Mapped[str] = mapped_column(String(30), default=FORMAT_CLAUDE_SKILL)
    frontmatter: Mapped[dict] = mapped_column(JSONB, default=dict)
    trigger_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_md: Mapped[str] = mapped_column(Text, default="")
    references: Mapped[list] = mapped_column(JSONB, default=list)
    section_headings: Mapped[list] = mapped_column(JSONB, default=list)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["Skill"] = relationship(back_populates="versions")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="skill_version", cascade="all, delete-orphan", order_by="Evaluation.id"
    )
    embedding: Mapped["SkillEmbedding | None"] = relationship(
        back_populates="skill_version", cascade="all, delete-orphan", uselist=False
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", "")) if self.frontmatter else ""

    @property
    def latest_evaluation(self) -> "Evaluation | None":
        return self.evaluations[-1] if self.evaluations else None


class Evaluation(Base):
    """A Claude-produced quality assessment against a versioned rubric."""

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_version_id: Mapped[int] = mapped_column(
        ForeignKey("skill_versions.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(80))
    rubric_version: Mapped[str] = mapped_column(String(20))
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    overall_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[list] = mapped_column(JSONB, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill_version: Mapped["SkillVersion"] = relationship(back_populates="evaluations")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")

    skills: Mapped[list["SkillCategory"]] = relationship(back_populates="category")


class SkillCategory(Base):
    __tablename__ = "skill_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(20), default="llm")

    skill: Mapped["Skill"] = relationship(back_populates="categories")
    category: Mapped["Category"] = relationship(back_populates="skills")

    __table_args__ = (UniqueConstraint("skill_id", "category_id", name="uq_skill_category"),)


class Recommendation(Base):
    """A curator-proposed change to the catalog (split / merge / dedup / delete / synthesize),
    stored so it can be shown on the dashboard and picked up and run by a developer later."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # see REC_KINDS
    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str | None] = mapped_column(String(120), nullable=True)  # category / task_group / skill
    targets: Mapped[list] = mapped_column(JSONB, default=list)  # skill names/ids or group keys involved
    suggested_action: Mapped[str] = mapped_column(Text, default="")  # a runnable instruction for Claude Code
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)  # see REC_STATUSES
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SkillEmbedding(Base):
    __tablename__ = "skill_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_version_id: Mapped[int] = mapped_column(
        ForeignKey("skill_versions.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill_version: Mapped["SkillVersion"] = relationship(back_populates="embedding")
