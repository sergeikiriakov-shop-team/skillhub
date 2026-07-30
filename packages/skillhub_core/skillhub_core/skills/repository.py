"""Back-compat shim — the Skills data-access layer now lives in ``skillhub_core.skills.repositories``.

The query/persistence bodies moved into ``repositories`` alongside the injectable ``Sql*Repository``
classes (the seam the application services depend on). This module re-exports them so existing
callers — ``skillhub_core.platform.db`` seeding, the ``seed`` importer, scripts and tests — keep
importing ``skillhub_core.skills.repository`` unchanged. New code should depend on the repository
classes via the DI container, not on this module."""

from __future__ import annotations

from .repositories import (  # noqa: F401
    DuplicateSkillError,
    category_infos,
    create_recommendation,
    find_exact_content_duplicate,
    find_similar,
    get_skill,
    get_skill_notebook,
    get_taxonomy,
    get_weights,
    list_recommendations,
    list_skills,
    nearest_other_skills,
    normalize_content,
    recompute_overall_scores,
    save_categorization,
    save_embedding,
    save_evaluation,
    semantic_search,
    set_recommendation_status,
    set_weights,
    skill_with_name_exists,
    stats,
    task_groups,
    upsert_skill,
    upsert_skill_notebook,
)

__all__ = [
    "DuplicateSkillError",
    "normalize_content",
    "upsert_skill",
    "skill_with_name_exists",
    "find_exact_content_duplicate",
    "nearest_other_skills",
    "save_evaluation",
    "save_categorization",
    "save_embedding",
    "get_taxonomy",
    "category_infos",
    "get_weights",
    "set_weights",
    "recompute_overall_scores",
    "get_skill_notebook",
    "upsert_skill_notebook",
    "task_groups",
    "list_recommendations",
    "create_recommendation",
    "set_recommendation_status",
    "list_skills",
    "get_skill",
    "stats",
    "find_similar",
    "semantic_search",
]
