"""Parse skill files into the normalized :class:`ParsedSkill` representation.

Claude Code ``SKILL.md`` is the canonical format (YAML frontmatter with ``name`` +
``description``, a Markdown body, and optional ``references/*.md``). Other client formats are
handled by dedicated parsers behind :func:`parse` so the internal model stays Claude-shaped.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .constants import (
    FORMAT_CLAUDE_SKILL,
    FORMAT_CURSOR_MDC,
    FORMAT_GENERIC_MD,
)
from .schemas import ParsedSkill, Reference

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
# Trigger convention used across the team's skills: "ALWAYS use ..." (optionally "... Do NOT ...").
_TRIGGER_RE = re.compile(r"(ALWAYS\s+use\b.*?)(?:(?<=\.)\s|$)", re.IGNORECASE | re.DOTALL)


def split_frontmatter(raw: str) -> tuple[dict, str]:
    """Return ``(frontmatter_dict, body)``. Empty dict if there is no frontmatter block."""
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    body = raw[match.end():]
    return data, body


def extract_headings(body: str) -> list[str]:
    """Collect H2/H3 section headings (without the leading hashes), skipping the H1 title."""
    headings: list[str] = []
    for hashes, text in _HEADING_RE.findall(body):
        if len(hashes) >= 2:
            headings.append(text.strip())
    return headings


def extract_trigger(description: str, body: str) -> str | None:
    """Pull the 'when to use' trigger. Prefer the ``ALWAYS use ...`` sentence, else the first
    sentence of the description."""
    for source in (description, body):
        if not source:
            continue
        m = _TRIGGER_RE.search(source)
        if m:
            return " ".join(m.group(1).split())
    if description:
        first = description.strip().split(". ")[0].strip()
        return first + ("." if first and not first.endswith(".") else "")
    return None


def compute_hash(raw: str, references: list[Reference]) -> str:
    hasher = hashlib.sha256()
    hasher.update(raw.encode("utf-8"))
    for ref in sorted(references, key=lambda r: r.path):
        hasher.update(ref.path.encode("utf-8"))
        hasher.update(ref.content.encode("utf-8"))
    return hasher.hexdigest()


def parse_claude_skill(raw: str, references: list[Reference] | None = None) -> ParsedSkill:
    references = references or []
    frontmatter, body = split_frontmatter(raw)
    name = str(frontmatter.get("name", "")).strip()
    description = " ".join(str(frontmatter.get("description", "")).split())
    if not name:  # fall back to the first H1 title
        h1 = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
        name = h1.group(1).strip() if h1 else "untitled-skill"
    return ParsedSkill(
        name=name,
        description=description,
        trigger_text=extract_trigger(description, body),
        body_md=body.strip(),
        references=references,
        section_headings=extract_headings(body),
        frontmatter={"name": name, "description": description},
        source_format=FORMAT_CLAUDE_SKILL,
        raw_content=raw,
    )


def parse_cursor_mdc(
    raw: str, references: list[Reference] | None = None, name_hint: str | None = None
) -> ParsedSkill:
    """Cursor ``.mdc`` rules use a different frontmatter schema: ``description``, ``globs``,
    ``alwaysApply`` (and no ``name`` — the filename is the identity)."""
    references = references or []
    frontmatter, body = split_frontmatter(raw)
    description = " ".join(str(frontmatter.get("description", "")).split())
    name = (name_hint or "").strip() or "untitled-rule"
    return ParsedSkill(
        name=name,
        description=description,
        trigger_text=extract_trigger(description, body),
        body_md=body.strip(),
        references=references,
        section_headings=extract_headings(body),
        frontmatter={
            "name": name,
            "description": description,
            "globs": frontmatter.get("globs", []),
            "alwaysApply": frontmatter.get("alwaysApply"),
        },
        source_format=FORMAT_CURSOR_MDC,
        raw_content=raw,
    )


def parse_generic_md(
    raw: str, references: list[Reference] | None = None, name_hint: str | None = None
) -> ParsedSkill:
    references = references or []
    frontmatter, body = split_frontmatter(raw)
    h1 = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
    name = (name_hint or "").strip() or (h1.group(1).strip() if h1 else "untitled")
    description = " ".join(str(frontmatter.get("description", "")).split())
    return ParsedSkill(
        name=name,
        description=description,
        trigger_text=extract_trigger(description, body),
        body_md=body.strip(),
        references=references,
        section_headings=extract_headings(body),
        frontmatter={"name": name, "description": description},
        source_format=FORMAT_GENERIC_MD,
        raw_content=raw,
    )


def parse(
    raw: str,
    source_format: str = FORMAT_CLAUDE_SKILL,
    references: list[Reference] | None = None,
    name_hint: str | None = None,
) -> ParsedSkill:
    """Dispatch to the right parser for ``source_format``."""
    if source_format == FORMAT_CURSOR_MDC:
        return parse_cursor_mdc(raw, references, name_hint)
    if source_format == FORMAT_GENERIC_MD:
        return parse_generic_md(raw, references, name_hint)
    # Codex / Copilot skills are Markdown-with-frontmatter today; treat as Claude-shaped until
    # they diverge enough to need their own parser.
    return parse_claude_skill(raw, references)


def parse_skill_dir(path: str | Path) -> ParsedSkill:
    """Parse a skill folder: ``SKILL.md`` plus every file under ``references/``."""
    path = Path(path)
    skill_md = path / "SKILL.md"
    raw = skill_md.read_text(encoding="utf-8")
    references: list[Reference] = []
    ref_dir = path / "references"
    if ref_dir.is_dir():
        for ref_file in sorted(ref_dir.rglob("*")):
            if ref_file.is_file():
                rel = ref_file.relative_to(path).as_posix()
                references.append(
                    Reference(path=rel, content=ref_file.read_text(encoding="utf-8"))
                )
    parsed = parse_claude_skill(raw, references)
    # The folder name is the authoritative skill identity in the canonical layout.
    parsed.name = path.name
    parsed.frontmatter["name"] = path.name
    return parsed
