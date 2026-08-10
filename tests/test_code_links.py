"""Unit tests for the finding → source-line links (no DB, no framework).

The repository comes from whatever ``git remote get-url origin`` printed on the developer's
machine, so the spellings below are the ones that actually arrive."""

from __future__ import annotations

import pytest

from skillhub_core.reviews.code_links import finding_url, normalize_repo_url

GITHUB = "https://github.com/prologisticsbeliani/prologistics"


@pytest.mark.parametrize(
    "raw",
    [
        "git@github.com:prologisticsbeliani/prologistics.git",
        "git@github.com:prologisticsbeliani/prologistics",
        "https://github.com/prologisticsbeliani/prologistics.git",
        "https://github.com/prologisticsbeliani/prologistics",
        "https://github.com/prologisticsbeliani/prologistics/",
        "ssh://git@github.com/prologisticsbeliani/prologistics.git",
        "  git@github.com:prologisticsbeliani/prologistics.git  ",
    ],
)
def test_every_remote_spelling_normalizes_to_one_browsable_url(raw):
    assert normalize_repo_url(raw) == GITHUB


def test_self_hosted_host_and_port_survive():
    assert normalize_repo_url("ssh://git@git.internal:2222/team/app.git") == (
        "https://git.internal:2222/team/app"
    )


def test_nested_group_path_is_kept():
    assert normalize_repo_url("git@gitlab.com:group/sub/app.git") == "https://gitlab.com/group/sub/app"


@pytest.mark.parametrize("raw", [None, "", "   ", "/home/me/checkout", "C:/work/repo"])
def test_unlinkable_remotes_yield_none(raw):
    assert normalize_repo_url(raw) is None


def test_link_points_at_the_reviewed_commit():
    url = finding_url(repo=GITHUB, ref="abc123", path="lib/Rma.php", line=42)
    assert url == f"{GITHUB}/blob/abc123/lib/Rma.php#L42"


def test_leading_slash_in_path_does_not_double_up():
    url = finding_url(repo=GITHUB, ref="abc123", path="/lib/Rma.php", line=1)
    assert url == f"{GITHUB}/blob/abc123/lib/Rma.php#L1"


def test_no_line_drops_the_anchor_rather_than_linking_line_zero():
    url = finding_url(repo=GITHUB, ref="abc123", path="lib/Rma.php", line=None)
    assert url == f"{GITHUB}/blob/abc123/lib/Rma.php"


def test_bitbucket_gets_its_own_path_shape():
    url = finding_url(repo="https://bitbucket.org/team/app", ref="abc123", path="a.py", line=7)
    assert url == "https://bitbucket.org/team/app/src/abc123/a.py#lines-7"


def test_change_wide_finding_has_no_link():
    assert finding_url(repo=GITHUB, ref="abc123", path=None, line=None) is None


def test_without_a_ref_there_is_nothing_to_pin_to():
    assert finding_url(repo=GITHUB, ref=None, path="a.py", line=1) is None


def test_without_a_repo_or_template_there_is_no_link():
    assert finding_url(repo=None, ref="abc123", path="a.py", line=1) is None


def test_explicit_template_overrides_the_host_default():
    url = finding_url(
        repo=GITHUB,
        ref="abc123",
        path="a.py",
        line=5,
        template="https://code.example/{ref}/{path}#line-{line}",
    )
    assert url == "https://code.example/abc123/a.py#line-5"
