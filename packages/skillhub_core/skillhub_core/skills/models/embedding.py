"""The per-version embedding vector (pgvector) for semantic search / duplicate detection."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.config import get_settings
from ...platform.models import Base

EMBEDDING_DIM = get_settings().embedding_dim


class SkillEmbedding(Base):
    __tablename__ = "skill_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_version_id: Mapped[int] = mapped_column(
        ForeignKey("skill_versions.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill_version: Mapped["SkillVersion"] = relationship(back_populates="embedding")  # noqa: F821
