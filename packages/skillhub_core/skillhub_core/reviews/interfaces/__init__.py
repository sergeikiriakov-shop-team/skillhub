"""Repository Protocols for the Task Review context — the seams the services depend on."""

from __future__ import annotations

from .self_review import SelfReviewPolicyRepository, SelfReviewRepository
from .task_review import TaskReviewRepository

__all__ = ["TaskReviewRepository", "SelfReviewRepository", "SelfReviewPolicyRepository"]
