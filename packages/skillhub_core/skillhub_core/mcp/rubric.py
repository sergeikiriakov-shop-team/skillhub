"""The MCP evaluation strategy — the single source of truth, served to Claude Code AND the UI.

Same contract as the skills rubric: the service does NOT run the LLM. Every developer's Claude Code
fetches this strategy (GET /api/mcp/rubric), scores a server's tool surface against it, and submits
the result back (POST /api/mcp/{id}/assessment) — so the algorithm is identical for everyone, and
``overall`` is recomputed server-side from the weights rather than trusted from the caller.

Why a separate rubric instead of reusing the skills one: a skill is a DOCUMENT (does it say when to
trigger? is the workflow complete?), while an MCP server is a TYPED TOOL SURFACE. The failure modes
differ, and this session's own trial evidence shows the gap concretely — 2 of 3 models invented a
``pattern`` parameter that does not exist on the real ``find_columns`` tool. No skills dimension
measures "is this schema precise enough that a model can't guess a plausible-but-wrong param",
which is exactly what ``schema_precision`` below is for.

Bump ``MCP_RUBRIC_VERSION`` whenever any part of this strategy changes; evaluations record the
version that produced them, so an older score surfaces as stale.
"""

from __future__ import annotations

MCP_RUBRIC_VERSION = "1"

MCP_RUBRIC_INSTRUCTIONS = (
    "You are a senior reviewer of MCP (Model Context Protocol) servers. You are scoring the TOOL "
    "SURFACE a server exposes to an agent — the tool names, their descriptions, and their parameter "
    "schemas — NOT any prose documentation that happens to exist elsewhere about it. A great MCP "
    "server is one an agent can drive correctly on the FIRST attempt, without guessing: every tool "
    "says what it does and when to reach for it, every parameter is explicitly typed and named so a "
    "plausible-sounding wrong argument is impossible to invent, the returned shape is predictable, "
    "mutating and destructive tools are unmistakable, and the surface does not flood the context "
    "window. Score each dimension 0-10 using the calibration anchors below; be strict and "
    "consistent, reserving 9-10 for a genuinely exemplary surface. Judge only what the manifest "
    "actually contains — if a tool's description is empty or its schema is untyped, that is a real "
    "finding, not something to fill in charitably from what you assume the tool probably does. Give "
    "concrete, actionable strengths and weaknesses, naming the specific tools they apply to."
)

# key -> what the dimension measures (mirrors the fields of McpEvaluationResult).
MCP_RUBRIC_DIMENSIONS: list[dict] = [
    {
        "key": "schema_precision",
        "description": "Are parameters explicitly typed and unambiguously named, with required vs "
        "optional clear and enums/formats/constraints stated? Could a model invent a "
        "plausible-but-nonexistent parameter, or pass the wrong shape, and not be stopped?",
    },
    {
        "key": "tool_clarity",
        "description": "Does each tool's own description say what it does AND when to reach for it, "
        "rather than restating its name?",
    },
    {
        "key": "discoverability",
        "description": "Can an agent pick the right tool first try — consistent naming, no two tools "
        "that plausibly do the same job, an obvious entry point for an unfamiliar caller?",
    },
    {
        "key": "result_shape",
        "description": "Is what comes back predictable and documented — the fields, pagination, "
        "truncation flags, and what an error or empty result looks like?",
    },
    {
        "key": "safety",
        "description": "Are read-only and mutating tools unmistakably distinguished, destructive "
        "operations flagged, and dangerous ambiguity (e.g. prod vs dev targeting) hard to get wrong?",
    },
    {
        "key": "token_economy",
        "description": "Does the surface avoid flooding the context — bounded/short results by "
        "design, limits and pagination, no tool that dumps everything by default?",
    },
]

# Default weight of each dimension when computing `overall`. Schema precision and tool clarity
# dominate: they are what decide whether an agent can use the surface correctly at all.
MCP_RUBRIC_WEIGHTS: dict[str, float] = {
    "schema_precision": 2.0,
    "tool_clarity": 2.0,
    "discoverability": 1.0,
    "result_shape": 1.0,
    "safety": 1.0,
    "token_economy": 1.0,
}

# 0-10 calibration anchors — the same meaning for every reviewer, so scores are comparable.
MCP_RUBRIC_CALIBRATION: list[dict] = [
    {
        "band": "9-10",
        "label": "Exemplary",
        "meaning": "An agent drives it correctly first try with no outside documentation: every "
        "parameter typed and constrained, every tool description states its when-to-use, results "
        "and error shapes documented, mutating tools unmistakable, results bounded by default.",
    },
    {
        "band": "7-8",
        "label": "Strong",
        "meaning": "Solid and usable as-is. Types and names are sound and the tool set is coherent, "
        "but something is thin — a few descriptions restate the name, an error/truncation shape is "
        "undocumented, or one parameter's accepted values are left implicit.",
    },
    {
        "band": "5-6",
        "label": "Workable",
        "meaning": "Usable only with trial and error or outside docs: loose or untyped parameters, "
        "descriptions that don't say when to use the tool, or overlapping tools that force a guess. "
        "A capable model gets there; a weaker one misuses it.",
    },
    {
        "band": "3-4",
        "label": "Weak",
        "meaning": "Actively invites misuse — ambiguous parameter names a model will guess wrong, no "
        "stated types, unbounded results, or no distinction between reading and mutating.",
    },
    {
        "band": "0-2",
        "label": "Unusable",
        "meaning": "Effectively undocumented: bare tool names, empty descriptions, free-form or "
        "absent schemas. An agent cannot call it correctly except by accident.",
    },
]

MCP_RECOMMENDATION_STRATEGY = (
    "Recommendations for an MCP server work like the skills ones (same kinds, same statuses, same "
    "`suggested_action` runnable-instruction contract), with one addition that matters: when a "
    "recommendation is about ONE specific tool, set `anchor` to that tool's EXACT name (e.g. "
    "`find_columns`) and `target_kind` to `mcp`. It then renders inline directly under that tool on "
    "the server's page, instead of only in a side list. Leave `anchor` unset for anything about the "
    "surface as a whole (naming consistency across tools, a missing tool, two tools that should "
    "merge). Ground every recommendation in what the MANIFEST shows or a real misuse someone "
    "observed — 'a model invented a parameter that does not exist on this tool' is evidence; 'this "
    "description could be nicer' is not. The highest-value findings are the ones where the tool's "
    "real schema and the way agents actually call it have drifted apart, since that drift is "
    "invisible until someone reads both."
)

MCP_INTROSPECTION_PROTOCOL = (
    "A server enters the catalog by CLIENT-SIDE introspection: SkillHub never connects out to a "
    "third-party MCP server and holds no credentials for one. The developer's Claude Code is already "
    "connected to the server, so it enumerates the tool surface it can actually see — for each tool "
    "the exact name, the description, and the parameter schema — and submits that manifest via "
    "`upload_mcp_server`. Read it from the live connected server, never from a skill's "
    "`references/tools.md` or from memory: the entire point of the catalog is to expose where the "
    "documentation and the real schema have drifted, and transcribing the docs would launder exactly "
    "the discrepancy you are trying to find. Re-introspecting the same server name creates a new "
    "VERSION (an unchanged manifest is a no-op), so drift shows up in the version history."
)
