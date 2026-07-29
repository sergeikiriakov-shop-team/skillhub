"""Skills context Pydantic schemas, one module per concern; re-exported so callers keep importing
from ``skillhub_core.skills.schemas`` unchanged."""

from __future__ import annotations

from .assessment import AssessmentIn
from .catalog import CategoryInfo, SearchHit, TaskGroupInfo
from .evaluation import CategorizationResult, CategoryAssignment, EvaluationResult
from .notebook import NotebookOut, NotebookSubmit
from .parsed import ParsedSkill, Reference
from .recommendation import RecommendationIn, RecommendationOut, RecommendationStatusUpdate
from .rubric import RubricOut, WeightsUpdate
from .skill import (
    CategoryOut,
    EvaluationOut,
    ReferenceIn,
    SimilarSkill,
    SkillCreate,
    SkillDetail,
    SkillSummary,
    SkillVersionInfo,
    StatsOut,
)

__all__ = [
    "Reference",
    "ParsedSkill",
    "EvaluationResult",
    "CategoryAssignment",
    "CategorizationResult",
    "AssessmentIn",
    "RubricOut",
    "WeightsUpdate",
    "NotebookOut",
    "NotebookSubmit",
    "ReferenceIn",
    "SkillCreate",
    "StatsOut",
    "CategoryOut",
    "EvaluationOut",
    "SkillSummary",
    "SkillVersionInfo",
    "SkillDetail",
    "SimilarSkill",
    "RecommendationIn",
    "RecommendationStatusUpdate",
    "RecommendationOut",
    "SearchHit",
    "TaskGroupInfo",
    "CategoryInfo",
]
