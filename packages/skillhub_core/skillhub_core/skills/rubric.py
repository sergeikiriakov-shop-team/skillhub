"""The evaluation strategy — the single source of truth, served to Claude Code AND the UI.

The service does NOT run the LLM. Every developer's Claude Code fetches this strategy
(GET /api/rubric), scores/categorizes a skill against it, and submits the result back
(POST /api/skills/{id}/assessment) — so the algorithm is identical for everyone. The
read-only dashboard renders the same content on its Methodology page.

Bump ``RUBRIC_VERSION`` whenever any part of the strategy changes. Each evaluation records the
version that produced it; prior evaluations keep their old version and are surfaced as **stale**
(the dashboard flags a score whose ``rubric_version`` differs from the current one). Re-scoring a
stale evaluation under the new version is a manual curator step — it is not automatic.
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

# Default weight of each dimension when computing `overall`. Trigger and completeness dominate.
# These are only the SEED values: the live weights are admin-editable and stored in the DB
# (rubric_weights table); see skillhub_core.skills.repository.get_weights / set_weights.
RUBRIC_WEIGHTS: dict[str, float] = {
    "trigger_quality": 2.0,
    "completeness": 2.0,
    "clarity": 1.0,
    "reusability": 1.0,
    "safety": 1.0,
    "structure": 1.0,
}


def compute_overall(scores: dict, weights: dict) -> float | None:
    """The server-authoritative ``overall``: the weighted mean of the per-dimension scores.

    Only dimensions that have both a score and a positive weight contribute. Returns ``None`` when
    nothing contributes (no weights configured, or an evaluation with no matching scores), so the
    caller can fall back. Rounded to 2 dp to match how scores are displayed and ranked."""
    numerator = 0.0
    denominator = 0.0
    for dimension, weight in (weights or {}).items():
        score = (scores or {}).get(dimension)
        if score is None or weight is None or float(weight) <= 0:
            continue
        numerator += float(score) * float(weight)
        denominator += float(weight)
    if denominator <= 0:
        return None
    return round(numerator / denominator, 2)

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
# The one-line summary; the full, reproducible procedure is SYNTHESIS_ALGORITHM + SYNTHESIS_PROMPT.
SYNTHESIS_STRATEGY = (
    "Synthesize the ideal skill for a competing task_group by starting from the winner's structure "
    "and grafting every runner-up's unique strength (attributed), so the result scores at least as "
    "high as the winner on every dimension. Follow the fixed algorithm and prompt below so every "
    "developer's Claude Code produces the ideal the same way."
)

# The exact, ordered synthesis procedure — stored here so it is identical for everyone.
SYNTHESIS_ALGORITHM: list[dict] = [
    {
        "step": "1. Identify the group",
        "detail": "Take the set of skills sharing one `task_group` with 2+ members (a real 'same "
        "job' competition). A single-member group has nothing to synthesize.",
    },
    {
        "step": "2. Choose the base",
        "detail": "Rank the group by `overall` (tie-break: safety → completeness → "
        "trigger_quality). The winner's SKILL.md is the structural starting point.",
    },
    {
        "step": "3. Extract graftable strengths",
        "detail": "For each non-winner, list the concrete strengths (from its evaluation) that the "
        "winner lacks. These are the graft candidates; discard one-off, environment-specific bits.",
    },
    {
        "step": "4. Draft the ideal SKILL.md",
        "detail": "Start from the base; keep the single strongest trigger, the most complete "
        "workflow and the strictest safety rails found ANYWHERE in the group; integrate each graft "
        "cleanly with no duplication.",
    },
    {
        "step": "5. Enforce the output contract",
        "detail": "The result must: be a valid SKILL.md (frontmatter name + description); carry a "
        "'Synthesis provenance' note mapping each part to its source skill; keep one crisp trigger; "
        "and be projected to score >= the base on EVERY rubric dimension.",
    },
    {
        "step": "6. Upload & self-evaluate",
        "detail": "Upload with author 'SkillHub (synthesized)' and the group's `task_group`, then "
        "score it against this rubric. If any dimension scores below the base, revise and re-score.",
    },
]

# The fill-in prompt a developer's Claude Code uses to run step 4 — one wording for everyone.
SYNTHESIS_PROMPT = (
    "You are synthesizing the single ideal Claude Code skill for the task_group `{task_group}`.\n"
    "BASE (structural starting point): `{winner_name}` — overall {winner_overall}. Its SKILL.md is "
    "provided below.\n"
    "GRAFT these unique strengths from the runners-up, attributing each to its source:\n"
    "{runner_up_strengths}\n\n"
    "Produce ONE SKILL.md that: (a) keeps the single strongest trigger in the group; (b) merges the "
    "most complete workflow; (c) adopts the strictest safety rails present anywhere in the group; "
    "(d) integrates every graft with no duplication and no one-off specifics; (e) ends with a short "
    "'Synthesis provenance' section mapping each part to its source skill. The result MUST be "
    "projected to score at least as high as the base on every rubric dimension. Then categorize it "
    "into the same `task_group` and submit it for evaluation via the standard assessment flow.\n\n"
    "BASE SKILL.md:\n{winner_body}"
)

# ── Trial-result judging: the empirical, per-model layer ──────────────────────────────────────
# The rubric above grades a SKILL.md as AUTHORED (model-agnostic). This block grades the RESULT of a
# sandbox TRIAL — the artifact a given model actually produced when it RAN the skill — so the quality
# criteria apply to the OUTCOME, per model, not to the skill in the abstract. A blind PANEL of judges
# scores each artifact; the per-(skill, model) headline is the panel MEDIAN, and the objective keyword
# scorecard is a CEILING on it (the checks are the gate). Stored per (skill × model); the highest is
# the skill's best model. Bump RESULT_JUDGE_VERSION when any part of this changes.
RESULT_JUDGE_VERSION = "1"

RESULT_JUDGE_INSTRUCTIONS = (
    "You are grading the ARTIFACT a model produced in a sandbox trial (e.g. the plan.md it wrote), "
    "NOT the skill's SKILL.md in the abstract. Judge how well THIS output executed the task against "
    "the criteria below, using the same 0-10 calibration as the skill rubric; be strict and "
    "discriminating, reserving 9-10 for genuinely exemplary results. Grade BLIND — you are not told "
    "which model produced which artifact. Score every dimension for every artifact and give a "
    "one-line reason per artifact naming a concrete strength or gap."
)

# Applied to the trial OUTPUT (mirrors EvaluationResult's dimensions, re-aimed at a result).
RESULT_JUDGE_DIMENSIONS: list[dict] = [
    {"key": "completeness", "description": "Captures every real task requirement, incl. buried/edge ones; nothing required missing."},
    {"key": "correctness", "description": "The specifics are right — ordering, edge cases, dependencies, the actual decisions."},
    {"key": "scope_discipline", "description": "Invents nothing; excludes withdrawn / out-of-scope items; no over-engineering."},
    {"key": "process_fidelity", "description": "Follows the skill's own procedure and guardrails (branching, safety, pipeline, delivery)."},
    {"key": "clarity", "description": "Clear, well-organized, actionable, appropriately concise."},
]

# The panel: several models grade each artifact blind; the score is the MEDIAN of their overalls (and,
# per dimension, the median of their dimension scores) — robust to one outlier judge, so a weak or
# self-preferring judge cannot swing the result. Aggregation is fixed here so it is identical for all.
RESULT_JUDGE_PANEL: dict = {
    "judges": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
    "aggregate": "median",
}

RESULT_JUDGE_PROTOCOL = (
    "1. The developer's live Claude Code runs the skill under a target model in the sandbox; the "
    "harness records the artifact + the objective keyword scorecard. 2. Each panel judge grades the "
    "artifact BLIND (artifacts labelled A/B/C; the judge is not told the model) on the dimensions "
    "above. 3. result_grade for (skill, model) = the MEDIAN of the panel's overalls; each dimension = "
    "the median of that dimension across judges. 4. effectiveness (0..1) = result_grade/10 CAPPED by "
    "the objective pass-rate — a run that skipped required mechanics cannot score above what it "
    "actually did (the checks are the gate). 5. Stored per (skill × model); the highest-effectiveness "
    "model is the skill's best_model, and models with no trial are gaps in the re-eval queue."
)
