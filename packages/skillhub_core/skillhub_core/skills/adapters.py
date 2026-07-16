"""Export adapters: render the canonical (Claude-shaped) representation into per-client formats.

Claude Code is the hub; these functions are the spokes — mirroring the "one canonical skill,
many client adapters" model used by ``ai.tools/setup-ai-client.php`` in Prologistics. Import
adapters live in :mod:`skillhub_core.parsing`. Fuller export (Codex/Copilot, PR generation)
arrives in Phase 3; these two cover the common cases today.
"""

from __future__ import annotations

import yaml

from .schemas import ParsedSkill


def to_claude_skill(skill: ParsedSkill) -> str:
    """Render a canonical Claude Code ``SKILL.md`` (name + description frontmatter + body)."""
    frontmatter = {"name": skill.name, "description": skill.description}
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm}---\n\n{skill.body_md}\n"


def to_cursor_mdc(skill: ParsedSkill, globs: list[str] | None = None) -> str:
    """Render a Cursor ``.mdc`` rule (description + globs + alwaysApply frontmatter)."""
    frontmatter = {
        "description": skill.description,
        "globs": globs or skill.frontmatter.get("globs", []),
        "alwaysApply": bool(skill.frontmatter.get("alwaysApply", True)),
    }
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm}---\n\n{skill.body_md}\n"
