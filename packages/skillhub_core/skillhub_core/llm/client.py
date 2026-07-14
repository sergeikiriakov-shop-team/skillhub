"""Factory for the Claude chat model used by all LLM chains.

Every LLM call in SkillHub goes through here so the model id, temperature and key come from a
single place (``skillhub_core.config.Settings``)."""

from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from ..config import get_settings


class LLMNotConfigured(RuntimeError):
    """Raised when an LLM chain is invoked without ANTHROPIC_API_KEY configured."""


@lru_cache
def get_chat_model(model: str | None = None) -> ChatAnthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMNotConfigured(
            "ANTHROPIC_API_KEY is not set; LLM features (evaluation, categorization) are disabled."
        )
    return ChatAnthropic(
        model=model or settings.skillhub_llm_model,
        temperature=settings.skillhub_llm_temperature,
        max_tokens=settings.skillhub_llm_max_tokens,
        api_key=settings.anthropic_api_key,
        timeout=120,
    )
