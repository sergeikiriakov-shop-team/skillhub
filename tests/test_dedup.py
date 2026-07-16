"""Unit tests for the DB-free dedup helpers. The name-keyed upsert, the identical-content block
and the similar-warning are exercised against a live API in the verification smoke (they need the
ORM engine + pgvector embeddings)."""

from __future__ import annotations

from skillhub_core.skills.repository import DuplicateSkillError, normalize_content


def test_normalize_collapses_whitespace():
    assert normalize_content("a\n\n  b\t c ") == "a b c"
    assert normalize_content("   ") == ""
    assert normalize_content("") == ""
    assert normalize_content(None) == ""  # tolerant of missing text


def test_normalize_makes_reformatted_content_identical():
    a = "# Title\n\nHello   world\n\n- one\n- two\n"
    b = "# Title\nHello world\n- one\n- two"
    assert normalize_content(a) == normalize_content(b)


def test_normalize_keeps_genuinely_different_content_distinct():
    assert normalize_content("run SQL on prod safely") != normalize_content("review a pull request")


def test_duplicate_error_carries_identity():
    err = DuplicateSkillError(7, "beliani-db-schema")
    assert err.existing_id == 7
    assert err.existing_name == "beliani-db-schema"
    assert "beliani-db-schema" in str(err)
