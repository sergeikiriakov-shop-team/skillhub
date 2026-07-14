"""LLM chain: assess the quality of a Claude Code skill against a fixed rubric."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from ..schemas import EvaluationResult, ParsedSkill
from .client import get_chat_model

# Bump when the rubric or prompt changes so stored evaluations can be re-run and compared.
RUBRIC_VERSION = "1"

_SYSTEM = """You are a senior reviewer of Claude Code "skills" (SKILL.md files) for a software \
team. A great skill has a crisp trigger (states exactly WHEN it should activate), a complete \
and correct workflow, is reusable across tasks (not a one-off), warns about destructive or \
risky steps, and is well structured (clear headings, examples, references for depth).

Score each dimension 0-10 (10 = excellent). Be strict and consistent; reserve 9-10 for \
genuinely exemplary skills. Give concrete, actionable strengths and weaknesses. Compute \
`overall` as your holistic 0-10 quality judgement, weighting trigger_quality and completeness \
most heavily."""

_HUMAN = """Evaluate this skill.

Name: {name}
Source format: {source_format}
Description / trigger:
{description}

Section headings: {headings}

Body:
{body}

Reference files (may be truncated):
{references}"""

_prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


def _render_references(skill: ParsedSkill, limit: int = 6000) -> str:
    if not skill.references:
        return "(none)"
    chunks = []
    budget = limit
    for ref in skill.references:
        snippet = ref.content[: max(0, budget)]
        chunks.append(f"--- {ref.path} ---\n{snippet}")
        budget -= len(snippet)
        if budget <= 0:
            break
    return "\n\n".join(chunks)


def evaluate_skill(skill: ParsedSkill, model: str | None = None) -> EvaluationResult:
    """Run the evaluation chain and return the structured result. Requires an API key."""
    llm = get_chat_model(model).with_structured_output(EvaluationResult)
    chain = _prompt | llm
    return chain.invoke(
        {
            "name": skill.name,
            "source_format": skill.source_format,
            "description": skill.description or "(none)",
            "headings": ", ".join(skill.section_headings) or "(none)",
            "body": skill.body_md[:12000] or "(empty)",
            "references": _render_references(skill),
        }
    )
