"""Unit tests for the skill parser. No API key or database required."""

from __future__ import annotations

from pathlib import Path

from skillhub_core.constants import FORMAT_CLAUDE_SKILL, FORMAT_CURSOR_MDC
from skillhub_core.parsing import (
    compute_hash,
    extract_headings,
    extract_trigger,
    parse,
    parse_claude_skill,
    parse_skill_dir,
    split_frontmatter,
)
from skillhub_core.schemas import Reference

FIXTURES = Path(__file__).parent / "fixtures"


def test_split_frontmatter_extracts_yaml_and_body():
    raw = "---\nname: x\ndescription: hello\n---\n# Title\n\nBody\n"
    fm, body = split_frontmatter(raw)
    assert fm == {"name": "x", "description": "hello"}
    assert body.startswith("# Title")


def test_split_frontmatter_without_block():
    raw = "# No frontmatter\n\ntext"
    fm, body = split_frontmatter(raw)
    assert fm == {}
    assert body == raw


def test_folded_description_collapses_newlines():
    parsed = parse_claude_skill(
        "---\nname: s\ndescription: >\n  line one\n  line two\n---\n# S\n"
    )
    assert parsed.description == "line one line two"


def test_extract_trigger_prefers_always_use():
    desc = "ALWAYS use before writing SQL. Do NOT guess."
    assert extract_trigger(desc, "").lower().startswith("always use")


def test_extract_headings_skips_h1():
    body = "# Title\n\n## Workflow\n\ntext\n\n### Sub\n\n## Reference\n"
    assert extract_headings(body) == ["Workflow", "Sub", "Reference"]


def test_parse_skill_dir_claude_skill_with_references():
    parsed = parse_skill_dir(FIXTURES / "beliani-db-schema")
    assert parsed.name == "beliani-db-schema"
    assert parsed.source_format == FORMAT_CLAUDE_SKILL
    assert parsed.description.startswith("ALWAYS use")
    assert parsed.trigger_text and parsed.trigger_text.lower().startswith("always use")
    assert "Workflow" in parsed.section_headings
    assert len(parsed.references) == 1
    assert parsed.references[0].path == "references/tools.md"
    assert "get_table_schema" in parsed.references[0].content


def test_parse_skill_dir_without_references():
    parsed = parse_skill_dir(FIXTURES / "check-task")
    assert parsed.name == "check-task"
    assert parsed.references == []
    assert "Report" in parsed.section_headings


def test_parse_dispatch_cursor_mdc():
    raw = (FIXTURES / "cursor" / "beliani-code-style.mdc").read_text(encoding="utf-8")
    parsed = parse(raw, source_format=FORMAT_CURSOR_MDC, name_hint="beliani-code-style")
    assert parsed.source_format == FORMAT_CURSOR_MDC
    assert parsed.name == "beliani-code-style"
    assert parsed.frontmatter["globs"] == ["**/*.php", "**/*.sql"]
    assert parsed.frontmatter["alwaysApply"] is True


def test_compute_hash_is_stable_and_content_sensitive():
    refs = [Reference(path="references/a.md", content="x")]
    h1 = compute_hash("raw", refs)
    h2 = compute_hash("raw", refs)
    h3 = compute_hash("raw!", refs)
    assert h1 == h2
    assert h1 != h3
