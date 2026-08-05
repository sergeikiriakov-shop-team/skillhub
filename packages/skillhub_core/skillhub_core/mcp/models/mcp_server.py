"""The McpServer aggregate root and its introspected tool-manifest versions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base

TRANSPORT_STDIO = "stdio"
TRANSPORT_HTTP = "http"
TRANSPORTS = (TRANSPORT_STDIO, TRANSPORT_HTTP)

SOURCE_INTROSPECTED = "introspected"
SOURCE_MANUAL = "manual"
MCP_SOURCE_TYPES = (SOURCE_INTROSPECTED, SOURCE_MANUAL)


class McpServer(Base):
    """One catalogued MCP server — one canonical record per ``name`` (e.g. ``beliani-db-schema-prod``),
    uniqueness enforced by the ``uq_mcp_servers_name`` index. Re-introspecting the same name adds a
    new :class:`McpServerVersion` rather than a duplicate row, so schema drift is visible in the
    history. ``family`` groups sibling entries that expose the same tool surface against different
    environments (the prod/dev/heap trio) — the analogue of ``Skill.task_group``."""

    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    transport: Mapped[str] = mapped_column(String(20), default=TRANSPORT_STDIO)
    family: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), default=SOURCE_INTROSPECTED)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["McpServerVersion"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
        order_by="McpServerVersion.version_no",
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])  # noqa: F821

    @property
    def latest_version(self) -> "McpServerVersion | None":
        return self.versions[-1] if self.versions else None


class McpServerVersion(Base):
    """One introspection snapshot of a server's tool surface.

    ``tools`` holds the whole manifest as submitted — ``[{name, description, input_schema}, ...]``.
    Tools deliberately live in this JSONB rather than their own table: recommendation anchors match
    a tool by NAME (a string, exactly like a SKILL.md heading), so a separate table would buy
    nothing in Phase 1."""

    __tablename__ = "mcp_server_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("mcp_servers.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    tool_count: Mapped[int] = mapped_column(Integer, default=0)
    # Hash of the normalized manifest: makes a no-op re-introspection a no-op instead of a version.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    server: Mapped["McpServer"] = relationship(back_populates="versions")
    evaluations: Mapped[list["McpEvaluation"]] = relationship(  # noqa: F821
        back_populates="server_version", cascade="all, delete-orphan", order_by="McpEvaluation.id"
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])  # noqa: F821

    @property
    def latest_evaluation(self) -> "McpEvaluation | None":  # noqa: F821
        return self.evaluations[-1] if self.evaluations else None
