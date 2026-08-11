"""ORM aggregate → DTO, one module per aggregate.

Imported as ``from .serializers import review as review_serializer`` so call sites read as
``review_serializer.to_detail(...)`` — the aggregate stays visible at the call, which flat
``to_review_detail`` / ``to_self_review_detail`` names lost as the context grew."""

from __future__ import annotations

from . import policy, review, self_review

__all__ = ["review", "self_review", "policy"]
