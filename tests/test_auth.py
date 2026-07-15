"""Unit tests for the auth helpers that need no database.

Covers config parsing and the pure token/user-code helpers. The DB-backed pieces (token table,
device-flow state machine, Google upsert, gating matrix) are exercised against a live API in the
verification smoke, since the ORM engine binds to Postgres at import time."""

from __future__ import annotations

import re

from skillhub_core.auth import _generate_user_code, generate_token, hash_token
from skillhub_core.config import Settings


def _settings(**overrides) -> Settings:
    # _env_file=None keeps the test independent of any .env / process environment.
    return Settings(_env_file=None, **overrides)


def test_hash_token_is_deterministic_sha256_hex():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("anything")) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", hash_token("x"))


def test_generate_token_is_unique_and_urlsafe():
    a, b = generate_token(), generate_token()
    assert a != b
    assert re.fullmatch(r"[A-Za-z0-9_-]+", a)
    assert len(a) >= 32


def test_user_code_format_and_unambiguous_alphabet():
    for _ in range(50):
        code = _generate_user_code()
        assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", code), code
        # No visually ambiguous characters.
        assert not set(code) & set("O0I1L")


def test_bootstrap_admins_parsed_and_normalized():
    s = _settings(skillhub_bootstrap_admins=" Alice@X.com , bob@Y.COM ,")
    assert s.bootstrap_admin_emails == {"alice@x.com", "bob@y.com"}


def test_bootstrap_admins_empty():
    assert _settings(skillhub_bootstrap_admins="").bootstrap_admin_emails == set()


def test_effective_redirect_uri_derived_from_public_url():
    s = _settings(skillhub_public_url="https://hub.example.com/")
    assert s.effective_redirect_uri == "https://hub.example.com/api/auth/callback"


def test_effective_redirect_uri_explicit_override_wins():
    s = _settings(
        skillhub_public_url="https://hub.example.com",
        google_redirect_uri="https://other.example.com/cb",
    )
    assert s.effective_redirect_uri == "https://other.example.com/cb"


def test_google_enabled_requires_both_id_and_secret():
    assert _settings(google_client_id="", google_client_secret="").google_enabled is False
    assert _settings(google_client_id="id", google_client_secret="").google_enabled is False
    assert _settings(google_client_id="id", google_client_secret="sec").google_enabled is True


def test_cors_origins_split():
    s = _settings(skillhub_cors_origins="http://a, http://b ,")
    assert s.cors_origins == ["http://a", "http://b"]
