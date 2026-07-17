"""The Skill aggregate root and its versions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base
from ..constants import FORMAT_CLAUDE_SKILL, SOURCE_TYPE_UPLOAD


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
    categories: Mapped[list["SkillCategory"]] = relationship(  # noqa: F821
        back_populates="skill", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])  # noqa: F821

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
    evaluations: Mapped[list["Evaluation"]] = relationship(  # noqa: F821
        back_populates="skill_version", cascade="all, delete-orphan", order_by="Evaluation.id"
    )
    embedding: Mapped["SkillEmbedding | None"] = relationship(  # noqa: F821
        back_populates="skill_version", cascade="all, delete-orphan", uselist=False
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])  # noqa: F821

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", "")) if self.frontmatter else ""

    @property
    def latest_evaluation(self) -> "Evaluation | None":  # noqa: F821
        return self.evaluations[-1] if self.evaluations else None
