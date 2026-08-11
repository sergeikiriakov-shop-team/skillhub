"""Repository Protocols for the Task Review context — the seams the services depend on."""

from __future__ import annotations

from .review import ReviewRepository
from .self_review import SelfReviewPolicyRepository, SelfReviewRepository

__all__ = ["ReviewRepository", "SelfReviewRepository", "SelfReviewPolicyRepository"]
