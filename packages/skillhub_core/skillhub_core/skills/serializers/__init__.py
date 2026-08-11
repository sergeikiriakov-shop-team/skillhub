"""ORM → DTO mapping for the Skills context, one module per aggregate.

Re-exported flat: call sites say ``serializers.skill_to_detail(...)`` as they always did."""

from __future__ import annotations

from .evaluation import evaluation_to_out
from .recommendation import _recommendation_to_out
from .skill import skill_to_detail, skill_to_summary

__all__ = [
    "skill_to_summary",
    "skill_to_detail",
    "evaluation_to_out",
    "_recommendation_to_out",
]
