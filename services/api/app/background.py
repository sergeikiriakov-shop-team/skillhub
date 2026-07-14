"""Background jobs run via FastAPI BackgroundTasks (each opens its own DB session)."""

from __future__ import annotations

import logging

from skillhub_core import pipeline, repository
from skillhub_core.db import session_scope

logger = logging.getLogger("skillhub.api.background")


def run_llm_for_skill(skill_id: int) -> None:
    """Evaluate + categorize a skill's latest version out of band."""
    try:
        with session_scope() as session:
            skill = repository.get_skill(session, skill_id)
            if skill is None:
                logger.warning("Skill %s vanished before LLM processing", skill_id)
                return
            pipeline.reprocess(session, skill, run_llm=True)
        logger.info("LLM processing done for skill %s", skill_id)
    except Exception:  # noqa: BLE001
        logger.exception("Background LLM processing failed for skill %s", skill_id)
