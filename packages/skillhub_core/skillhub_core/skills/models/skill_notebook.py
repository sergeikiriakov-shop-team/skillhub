"""The one sandbox-trial notebook attached to a skill.

Each skill has at most ONE notebook (an upsert keyed by ``skill_id``), produced by the skill
sandbox (``evals/``): the developer's live Claude Code runs the skill against a fake service and
the harness emits a Jupyter notebook (``trial.ipynb``) as the run record. A new run either reuses
this stored notebook or regenerates it, chosen by a developer-supplied flag — the service just
upserts. ``tested_content_hash`` / ``tested_version_no`` snapshot which skill revision was tested,
so the UI can flag the notebook as *stale* once the skill changes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...platform.models import Base


class SkillNotebook(Base):
    """One sandbox-trial notebook per (skill, MODEL): the run record produced by a specific
    executing model. The composite PK ``(skill_id, model)`` means a trial under Opus 4.8 and one
    under Opus 5 are separate rows — so effectiveness can be compared per model. Regenerating a
    trial for the same (skill, model) overwrites that row."""

    __tablename__ = "skill_notebooks"

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    # The executing/running model this trial was produced by (its self-reported id), e.g.
    # ``claude-opus-5``. Part of the key: effectiveness is measured per model.
    model: Mapped[str] = mapped_column(String(60), primary_key=True, default="")
    scenario: Mapped[str] = mapped_column(String(120), default="")
    task_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # The nbformat 4.5 notebook (cells) and the compact scorecard (trial.json entries), as emitted
    # by evals/harness.py. Rendered read-only on the frontend from these structured cells.
    notebook: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Which skill revision this trial exercised — for the stale check on the skill detail page.
    tested_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tested_version_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    skill: Mapped["Skill"] = relationship()  # noqa: F821
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])  # noqa: F821
