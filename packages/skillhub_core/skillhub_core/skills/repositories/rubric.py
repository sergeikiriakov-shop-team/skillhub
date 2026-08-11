"""Persistence for the admin-managed rubric weights.

``overall`` is server-authoritative — the weighted mean of the per-dimension scores — so changing a
weight rescores every stored evaluation here rather than leaving the catalog ranked by stale numbers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Evaluation, RubricWeight
from ..rubric import compute_overall
from .catalog import get_taxonomy


def get_weights(session: Session) -> dict[str, float]:
    """Current dimension weights (dimension -> weight), as stored in the DB."""
    return {r.dimension: float(r.weight) for r in session.scalars(select(RubricWeight)).all()}


def set_weights(session: Session, weights: dict[str, float]) -> dict[str, float]:
    """Upsert the given dimension weights (flush only; the caller owns the transaction)."""
    existing = {r.dimension: r for r in session.scalars(select(RubricWeight)).all()}
    for dimension, weight in weights.items():
        if dimension in existing:
            existing[dimension].weight = float(weight)
        else:
            session.add(RubricWeight(dimension=dimension, weight=float(weight)))
    session.flush()
    return get_weights(session)


def recompute_overall_scores(session: Session) -> int:
    """Recompute every evaluation's overall_score from its stored per-dimension scores and the
    current weights. Call after the weights change. Returns how many rows were updated."""
    weights = get_weights(session)
    updated = 0
    for evaluation in session.scalars(select(Evaluation)).all():
        recomputed = compute_overall(evaluation.scores or {}, weights)
        if recomputed is not None and recomputed != evaluation.overall_score:
            evaluation.overall_score = recomputed
            updated += 1
    session.flush()
    return updated




class SqlRubricRepository:
    """``RubricRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_weights(self) -> dict[str, float]:
        return get_weights(self._session)

    def set_weights(self, weights: dict[str, float]) -> dict[str, float]:
        return set_weights(self._session, weights)

    def recompute_overall_scores(self) -> int:
        return recompute_overall_scores(self._session)

    def get_taxonomy(self) -> list[dict]:
        return get_taxonomy(self._session)

    def commit(self) -> None:
        self._session.commit()




