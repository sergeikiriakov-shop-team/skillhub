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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_settings

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

# --- roles (ascending capability) ---
ROLE_VIEWER = "viewer"
ROLE_CONTRIBUTOR = "contributor"  # may upload skills
ROLE_EVALUATOR = "evaluator"  # may submit evaluations (marked by an admin)
ROLE_ADMIN = "admin"  # may manage users
ROLES = (ROLE_VIEWER, ROLE_CONTRIBUTOR, ROLE_EVALUATOR, ROLE_ADMIN)

# --- auth token kinds ---
TOKEN_SESSION = "session"  # browser cookie, TTL'd
TOKEN_DEVICE = "device"  # long-lived, issued to the MCP via the device flow
TOKEN_PAT = "pat"  # long-lived personal access token, self-minted from the UI
TOKEN_KINDS = (TOKEN_SESSION, TOKEN_DEVICE, TOKEN_PAT)

# --- device-flow states ---
DEVICE_PENDING = "pending"
DEVICE_APPROVED = "approved"
DEVICE_CONSUMED = "consumed"
DEVICE_DENIED = "denied"


class Base(DeclarativeBase):
    pass


class Skill(Base):
    """A logical skill. Multiple authors may register their own variant of the same name —
    that overlap is a first-class signal, not an error (see duplicate detection, Phase 2)."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
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

    __table_args__ = (UniqueConstraint("name", "author", "origin", name="uq_skill_identity"),)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["Skill"] = relationship(back_populates="versions")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="skill_version", cascade="all, delete-orphan", order_by="Evaluation.id"
    )
    embedding: Mapped["SkillEmbedding | None"] = relationship(
        back_populates="skill_version", cascade="all, delete-orphan", uselist=False
    )

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


class User(Base):
    """A team member. Identity comes from an OAuth provider (``auth_provider`` + ``provider_sub``,
    e.g. github + the numeric user id) plus ``email``; access to the API is carried by rows in
    ``auth_tokens``. Reads are open; uploads/evaluations require a role.

    ``token_hash`` is the legacy single-token column, kept nullable for back-compat; new code
    issues tokens via :class:`AuthToken`. Uniqueness of ``email`` and of the
    ``(auth_provider, provider_sub)`` pair is enforced by named indexes created in
    ``db._apply_column_migrations`` (not by ``unique=`` here) so fresh and migrated databases
    converge on the same schema."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_CONTRIBUTOR)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tokens: Mapped[list["AuthToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def can_upload(self) -> bool:
        return self.role in (ROLE_CONTRIBUTOR, ROLE_EVALUATOR, ROLE_ADMIN)

    @property
    def can_evaluate(self) -> bool:
        return self.role in (ROLE_EVALUATOR, ROLE_ADMIN)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


class AuthToken(Base):
    """An access credential for one user. The plaintext is shown once; only its SHA-256 is stored.

    ``kind`` is one of ``TOKEN_KINDS``. ``expires_at`` NULL means non-expiring (device tokens/PATs);
    sessions get a TTL."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default=TOKEN_DEVICE)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="tokens")


class DeviceCode(Base):
    """One in-flight OAuth 2.0 Device Authorization Grant (RFC 8628). We store only the SHA-256 of
    the ``device_code``; ``user_code`` is the short human-typed code (worthless without the
    device_code, so kept plaintext)."""

    __tablename__ = "device_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default=DEVICE_PENDING)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    client_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interval: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
