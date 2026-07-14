"""The evaluation rubric — served to Claude Code (the evaluator) so scoring is consistent.

The service does NOT run the LLM. Claude Code fetches this rubric (GET /api/rubric),
scores a skill against it, and submits the result back (POST /api/skills/{id}/assessment).
Bump ``RUBRIC_VERSION`` when the rubric changes so prior evaluations can be treated as stale."""

from __future__ import annotations

RUBRIC_VERSION = "1"

RUBRIC_INSTRUCTIONS = (
    "You are a senior reviewer of Claude Code \"skills\" (SKILL.md files). A great skill has a "
    "crisp trigger (states exactly WHEN it should activate), a complete and correct workflow, is "
    "reusable across tasks (not a one-off), warns about destructive or risky steps, and is well "
    "structured (clear headings, examples, references for depth). Score each dimension 0-10 "
    "(10 = excellent); be strict and consistent, reserving 9-10 for genuinely exemplary skills. "
    "Give concrete, actionable strengths and weaknesses. Compute `overall` as your holistic 0-10 "
    "judgement, weighting trigger_quality and completeness most heavily."
)

# key -> what the dimension measures (mirrors the fields of EvaluationResult).
RUBRIC_DIMENSIONS: list[dict] = [
    {"key": "clarity", "description": "Is the writing clear and unambiguous?"},
    {"key": "trigger_quality", "description": "How precisely does it state WHEN the skill should trigger?"},
    {"key": "completeness", "description": "Does it cover the workflow with no critical gaps?"},
    {"key": "reusability", "description": "Is it generic/parameterized rather than one-off?"},
    {"key": "safety", "description": "Does it warn about destructive actions and edge cases?"},
    {"key": "structure", "description": "Good headings, examples, progressive disclosure via references?"},
]
