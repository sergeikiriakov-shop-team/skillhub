"""A Claude-produced quality assessment of an MCP server's tool surface."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base


class McpEvaluation(Base):
    """An assessment of one :class:`McpServerVersion` against the versioned MCP rubric.

    Its own table rather than a reuse of ``evaluations``: an MCP server is scored on a different set
    of dimensions (schema precision, result shape, token economy) than a SKILL.md, so the two score
    sets are not comparable and must not share a rubric-version namespace."""

    __tablename__ = "mcp_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_version_id: Mapped[int] = mapped_column(
        ForeignKey("mcp_server_versions.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(80))
    rubric_version: Mapped[str] = mapped_column(String(20))
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    overall_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[list] = mapped_column(JSONB, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    server_version: Mapped["McpServerVersion"] = relationship(  # noqa: F821
        back_populates="evaluations"
    )
