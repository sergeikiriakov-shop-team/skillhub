"""SQLAlchemy-backed repositories for the Task Review context, one module per aggregate.

Each satisfies the matching Protocol in ``..interfaces`` and returns DTOs, so services stay DB-free
and fakeable. Persistence only: the workflow rules live on the aggregates in ``..models``."""

from __future__ import annotations

from .policy import SqlSelfReviewPolicyRepository
from .review import SqlReviewRepository
from .self_review import SqlSelfReviewRepository

__all__ = [
    "SqlReviewRepository",
    "SqlSelfReviewRepository",
    "SqlSelfReviewPolicyRepository",
]
