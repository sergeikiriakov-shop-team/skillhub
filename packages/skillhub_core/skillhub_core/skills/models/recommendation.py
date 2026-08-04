"""A curator-proposed catalog change (synthesize / split / merge / dedup / delete)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ...platform.models import Base


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
    # For kind="improve": the exact SKILL.md heading text this suggestion attaches to, so the skill
    # detail page can render it inline right after that section instead of only in a side list.
    anchor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_action: Mapped[str] = mapped_column(Text, default="")  # a runnable instruction for Claude Code
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)  # see REC_STATUSES
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
