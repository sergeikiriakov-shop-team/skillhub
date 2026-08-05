"""Lightweight string constants shared across modules (no heavy imports).

Kept dependency-free so the parser and its tests can import them without pulling in
SQLAlchemy / pgvector / torch."""

# Where a skill came from.
SOURCE_TYPE_UPLOAD = "upload"
SOURCE_TYPE_IMPORT = "import"
SOURCE_TYPE_SYNTHESIZED = "synthesized"  # produced by the service's synthesis algorithm

# Author sentinel for a synthesized "ideal" skill — recognized on ingest to tag its source_type.
SYNTHESIZED_AUTHOR = "SkillHub (synthesized)"

# Curator recommendations: what kind of change is proposed, and its lifecycle state.
# - synthesize: merge a competing task_group into one ideal skill
# - split: break one skill into a short core + references/ (or into separate skills)
# - improve: upgrade/restructure ONE skill in place — move detail into references/, add examples,
#   tighten the trigger, apply progressive disclosure — without splitting it into multiple skills
# - merge: fold near-duplicate skills together   - dedup: remove/redirect duplicated content
# - delete: retire a skill   - other: anything else
REC_KINDS = ("synthesize", "split", "improve", "merge", "dedup", "delete", "other")
REC_STATUSES = ("proposed", "accepted", "done", "dismissed")
# Which catalog a recommendation is about. One table serves both, so a cross-catalog finding
# ("this skill duplicates what that MCP tool already does") stays expressible.
REC_TARGET_KINDS = ("skill", "mcp")

# The originating client format. Claude Code is canonical; the rest are adapters.
FORMAT_CLAUDE_SKILL = "claude_skill"
FORMAT_CURSOR_MDC = "cursor_mdc"
FORMAT_CODEX_SKILL = "codex_skill"
FORMAT_COPILOT = "copilot_instructions"
FORMAT_GENERIC_MD = "generic_md"
