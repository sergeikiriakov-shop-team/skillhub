"""Skills Registry context models.

One module per entity; this package re-exports every name (including the format/source-type
constants it historically surfaced) so callers keep importing from ``skillhub_core.skills.models``
unchanged. Importing this package registers all skills models on the shared :class:`Base`.
"""

from __future__ import annotations

# Re-export the constants this module has always surfaced (defined in skills/constants.py).
from ..constants import (  # noqa: F401
    FORMAT_CLAUDE_SKILL,
    FORMAT_CODEX_SKILL,
    FORMAT_COPILOT,
    FORMAT_CURSOR_MDC,
    FORMAT_GENERIC_MD,
    SOURCE_TYPE_IMPORT,
    SOURCE_TYPE_SYNTHESIZED,
    SOURCE_TYPE_UPLOAD,
    SYNTHESIZED_AUTHOR,
)
from .category import Category, SkillCategory
from .embedding import EMBEDDING_DIM, SkillEmbedding
from .evaluation import Evaluation
from .recommendation import Recommendation
from .skill import Skill, SkillVersion

__all__ = [
    "Skill",
    "SkillVersion",
    "Evaluation",
    "Category",
    "SkillCategory",
    "Recommendation",
    "SkillEmbedding",
    "EMBEDDING_DIM",
    "FORMAT_CLAUDE_SKILL",
    "FORMAT_CODEX_SKILL",
    "FORMAT_COPILOT",
    "FORMAT_CURSOR_MDC",
    "FORMAT_GENERIC_MD",
    "SOURCE_TYPE_IMPORT",
    "SOURCE_TYPE_SYNTHESIZED",
    "SOURCE_TYPE_UPLOAD",
    "SYNTHESIZED_AUTHOR",
]
