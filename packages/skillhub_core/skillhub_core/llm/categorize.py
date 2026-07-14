"""LLM chain: categorize a skill against the SkillHub taxonomy and suggest tags."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from ..schemas import CategorizationResult, ParsedSkill
from .client import get_chat_model

_SYSTEM = """You classify Claude Code skills into a fixed taxonomy. Choose the single best-fit \
`primary_category`, then list every applicable category with a confidence 0-1. Add a few \
short, lowercase free-form tags (e.g. "sql", "react", "pull-request"). Only use category keys \
from the taxonomy provided; never invent keys."""

_HUMAN = """Taxonomy (key: description):
{taxonomy}

Skill name: {name}
Description: {description}
Section headings: {headings}
Body (excerpt):
{body}"""

_prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


def categorize_skill(
    skill: ParsedSkill, taxonomy: list[dict], model: str | None = None
) -> CategorizationResult:
    """Run the categorization chain. ``taxonomy`` is a list of ``{"key","label","description"}``."""
    llm = get_chat_model(model).with_structured_output(CategorizationResult)
    chain = _prompt | llm
    taxonomy_str = "\n".join(f"- {c['key']}: {c.get('description', c.get('label', ''))}" for c in taxonomy)
    return chain.invoke(
        {
            "taxonomy": taxonomy_str,
            "name": skill.name,
            "description": skill.description or "(none)",
            "headings": ", ".join(skill.section_headings) or "(none)",
            "body": skill.body_md[:8000] or "(empty)",
        }
    )
