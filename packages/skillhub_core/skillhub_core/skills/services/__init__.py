"""Application services for the Skills context, one module per aggregate.

Each owns its transaction boundary and depends on repository Protocols (``..interfaces``), never on
SQLAlchemy or FastAPI — so they stay unit-testable with in-memory fakes."""

from __future__ import annotations

from .catalog import CatalogService
from .evaluation import EvaluationService
from .ingest import IngestService
from .notebook import NotebookService
from .recommendation import RecommendationService
from .rubric import RubricService
from .skill import SkillService

__all__ = [
    "SkillService",
    "IngestService",
    "EvaluationService",
    "RubricService",
    "NotebookService",
    "RecommendationService",
    "CatalogService",
]
