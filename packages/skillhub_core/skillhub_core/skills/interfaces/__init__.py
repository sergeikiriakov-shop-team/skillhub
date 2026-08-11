"""Repository Protocols for the Skills context — the seams the services depend on.

One module per aggregate; the SQLAlchemy implementations live in ``..repositories``."""

from __future__ import annotations

from .catalog import CatalogRepository
from .evaluation import EvaluationRepository
from .notebook import NotebookRepository
from .recommendation import RecommendationRepository
from .rubric import RubricRepository
from .skill import SkillRepository

__all__ = [
    "SkillRepository",
    "EvaluationRepository",
    "RubricRepository",
    "NotebookRepository",
    "RecommendationRepository",
    "CatalogRepository",
]
