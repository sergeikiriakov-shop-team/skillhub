"""The evaluation strategy — the single source of truth, served to Claude Code AND the UI.

The service does NOT run the LLM. Every developer's Claude Code fetches this strategy
(GET /api/rubric), scores/categorizes a skill against it, and submits the result back
(POST /api/skills/{id}/assessment) — so the algorithm is identical for everyone. The
read-only dashboard renders the same content on its Methodology page.

Bump ``RUBRIC_VERSION`` whenever any part of the strategy changes so prior evaluations can be
treated as stale and re-scored under the new version.
"""

from __future__ import annotations

RUBRIC_VERSION = "2"

RUBRIC_INSTRUCTIONS = (
    "You are a senior reviewer of Claude Code \"skills\" (SKILL.md files). A great skill has a "
    "crisp trigger (states exactly WHEN it should activate), a complete and correct workflow, is "
    "reusable across tasks (not a one-off), warns about destructive or risky steps, and is well "
    "structured (clear headings, examples, references for depth). Score each dimension 0-10 using "
    "the calibration anchors below; be strict and consistent, reserving 9-10 for genuinely "
    "exemplary skills. Give concrete, actionable strengths and weaknesses. Compute `overall` as a "
    "holistic 0-10 judgement using the dimension weights (trigger_quality and completeness count "
    "most). Then categorize the skill and, when several skills do the same job, apply the "
    "selection strategy to pick the best one."
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

# Relative weight of each dimension when computing `overall`. Trigger and completeness dominate.
RUBRIC_WEIGHTS: dict[str, float] = {
    "trigger_quality": 2.0,
    "completeness": 2.0,
    "clarity": 1.0,
    "reusability": 1.0,
    "safety": 1.0,
    "structure": 1.0,
}

# 0-10 calibration anchors — the same meaning for every reviewer, so scores are comparable.
RUBRIC_CALIBRATION: list[dict] = [
    {
        "band": "9-10",
        "label": "Exemplary",
        "meaning": "Best-in-class: precise trigger, complete and correct workflow, explicit "
        "safety rails, examples and progressive disclosure. Nothing important is missing.",
    },
    {
        "band": "7-8",
        "label": "Strong",
        "meaning": "Solid and usable as-is with minor gaps (e.g. thin on examples, slightly "
        "broad trigger, or environment-coupled).",
    },
    {
        "band": "5-6",
        "label": "Serviceable",
        "meaning": "Works but noticeably incomplete or generic — missing a report format, edge "
        "cases, or the high-value specifics are buried in filler.",
    },
    {
        "band": "3-4",
        "label": "Weak",
        "meaning": "Vague trigger, important steps missing, or no safety guidance; needs real "
        "work before it can be relied on.",
    },
    {
        "band": "0-2",
        "label": "Poor / absent",
        "meaning": "Not actually a usable skill: no clear trigger or workflow, or a placeholder.",
    },
]

# How to place a skill in the TWO-LEVEL taxonomy: broad category + narrow task_group.
CATEGORIZATION_RULES = (
    "Categorize on two levels. (1) Broad `primary_category` — the single best-fit key from the "
    "taxonomy served with this rubric; add other applicable categories to `categories` with a 0-1 "
    "confidence; use `other` only when nothing fits. (2) Narrow `task_group` — a short slug naming "
    "the skill's SPECIFIC job (e.g. `single-task-driver`, `sql-data-read`, `react-authoring`), "
    "finer than the category. Skills that do the SAME job MUST share the same task_group slug so "
    "competing variants cluster together; different sub-jobs get different slugs even within one "
    "category. Before inventing a slug, fetch the existing ones (GET /api/task-groups) and REUSE a "
    "matching slug — consistency is what lets similar skills from different developers converge. "
    "Judge by what the skill DOES, not by the words it contains. Also add lowercase `tags` and a "
    "one-sentence `summary`."
)

# How to decide the best skill when several overlap (grouped by the narrow task_group).
SELECTION_STRATEGY = (
    "The selection group is the set of skills sharing a `task_group` — that is the precise 'same "
    "job' signal, finer than the broad category (a category like data-access holds several "
    "different task_groups that are COMPLEMENTARY — a toolkit, not competitors — so never rank "
    "across task_groups). Within one task_group the skills genuinely compete: the best = highest "
    "`overall`; break ties by safety, then completeness, then trigger_quality. A task_group with a "
    "single skill has a trivial winner. Record, for every non-winner, the unique strength it still "
    "has — that list is the input to synthesis."
)

# How to build the "ideal" skill for a competing group (the phase after selection).
SYNTHESIS_STRATEGY = (
    "To synthesize the ideal skill for a competing group: start from the winner's structure and "
    "trigger; graft in each runner-up's unique strengths (name the source of each grafted part); "
    "keep the strongest single trigger, the most complete workflow, and the strictest safety "
    "rails found anywhere in the group; drop duplication and one-off specifics. The result must be "
    "attributable (which source each part came from) and score at least as high as the group "
    "winner on every dimension."
)
