"""Lightweight string constants shared across modules (no heavy imports).

Kept dependency-free so the parser and its tests can import them without pulling in
SQLAlchemy / pgvector / torch."""

# Where a skill came from.
SOURCE_TYPE_UPLOAD = "upload"
SOURCE_TYPE_IMPORT = "import"

# The originating client format. Claude Code is canonical; the rest are adapters.
FORMAT_CLAUDE_SKILL = "claude_skill"
FORMAT_CURSOR_MDC = "cursor_mdc"
FORMAT_CODEX_SKILL = "codex_skill"
FORMAT_COPILOT = "copilot_instructions"
FORMAT_GENERIC_MD = "generic_md"
