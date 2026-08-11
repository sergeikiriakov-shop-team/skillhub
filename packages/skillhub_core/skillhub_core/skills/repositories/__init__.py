"""SQLAlchemy data-access for the Skills context, one module per aggregate.

``skill`` · ``evaluation`` · ``rubric`` · ``notebook`` · ``recommendation``, plus ``catalog`` —
the read-model over the whole catalog (taxonomy, task groups, stats, search). Dependencies point
one way: catalog may use the per-aggregate modules, none of them uses catalog, so there is no
import cycle to work around.

Each ``Sql*Repository`` holds a request-scoped :class:`Session` and satisfies the matching Protocol
in ``skillhub_core.skills.interfaces`` — the seam the application services depend on. Names are
re-exported flat so existing imports keep working."""

from __future__ import annotations

from .catalog import (
    SqlCatalogRepository,
    category_infos,
    get_taxonomy,
    stats,
    task_groups,
)
from .evaluation import SqlEvaluationRepository, save_categorization, save_evaluation
from .notebook import (
    SqlNotebookRepository,
    best_effectiveness_by_skill,
    get_skill_notebook,
    list_skill_notebooks,
    upsert_skill_notebook,
)
from .recommendation import (
    SqlRecommendationRepository,
    create_recommendation,
    list_recommendations,
    open_improve_count_by_skill,
    open_recommendations_for_skill,
    set_recommendation_status,
)
from .rubric import (
    SqlRubricRepository,
    get_weights,
    recompute_overall_scores,
    set_weights,
)
from .skill import (
    SqlSkillRepository,
    find_exact_content_duplicate,
    find_similar,
    get_skill,
    list_skills,
    nearest_other_skills,
    normalize_content,
    save_embedding,
    semantic_search,
    skill_with_name_exists,
    upsert_skill,
)

__all__ = [
    # repositories (the injectable seams)
    "SqlSkillRepository",
    "SqlEvaluationRepository",
    "SqlRubricRepository",
    "SqlNotebookRepository",
    "SqlRecommendationRepository",
    "SqlCatalogRepository",
    # skill
    "upsert_skill",
    "skill_with_name_exists",
    "find_exact_content_duplicate",
    "nearest_other_skills",
    "save_embedding",
    "list_skills",
    "get_skill",
    "find_similar",
    "semantic_search",
    "normalize_content",
    # evaluation
    "save_evaluation",
    "save_categorization",
    # rubric
    "get_weights",
    "set_weights",
    "recompute_overall_scores",
    # notebook
    "get_skill_notebook",
    "list_skill_notebooks",
    "best_effectiveness_by_skill",
    "upsert_skill_notebook",
    # recommendation
    "list_recommendations",
    "create_recommendation",
    "set_recommendation_status",
    "open_improve_count_by_skill",
    "open_recommendations_for_skill",
    # catalog
    "get_taxonomy",
    "category_infos",
    "task_groups",
    "stats",
]
