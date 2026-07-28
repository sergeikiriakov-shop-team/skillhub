"""Admin-managed weight of a rubric dimension in the server-computed overall score."""

from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ...platform.models import Base


class RubricWeight(Base):
    """Weight of one rubric dimension in the ``overall`` score. Admin-editable and seeded from the
    rubric defaults on first boot. ``overall`` is computed server-side as the weighted mean of the
    per-dimension scores, so changing a weight instantly re-ranks the whole catalog."""

    __tablename__ = "rubric_weights"

    dimension: Mapped[str] = mapped_column(String(40), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
