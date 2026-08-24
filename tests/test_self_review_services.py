"""Unit tests for SelfReviewService with an in-memory fake — no DB, no FastAPI, no container.

Covers what the service itself concentrates: not-found → SelfReviewNotFound, commit owned on the
writes (submit / set_policy) and NOT taken on a read, and the catalog/policy-coupled errors
propagating untouched from the repository."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from skillhub_core.reviews.errors import (
    NotReviewAuthor,
    SelfReviewNotFound,
    SelfReviewPolicyNotSet,
    UnknownReviewSkill,
)
from skillhub_core.reviews.services import SelfReviewPolicyService, SelfReviewService

USER = SimpleNamespace(id=1, is_admin=False)
ADMIN = SimpleNamespace(id=2, is_admin=True)


class FakePolicyRepo:
    """The policy aggregate's own repository — a separate seam since the split."""

    def __init__(self, *, found=True, raise_exc=None):
        self._found = found
        self._raise = raise_exc
        self.committed = False
        self.set_lane_args = None

    def all_lanes(self):
        return "POLICY"

    def lane(self, lane):
        return "LANE" if self._found else None

    def set_lane(self, lane, skill, required, admin):
        if self._raise:
            raise self._raise
        self.set_lane_args = (lane, skill, required, admin)
        return "LANE"

    def self_review_required(self):
        return False

    def commit(self):
        self.committed = True


class FakeSelfReviewRepo:
    def __init__(self, *, found=True, raise_exc=None):
        self._found = found
        self._raise = raise_exc
        self.committed = False

    def submit(self, author, data):
        if self._raise:
            raise self._raise
        return "SR"

    def list(self, *, author_id, task_ref, task_review_id):
        return ["s1"]

    def get(self, self_review_id):
        return "SR" if self._found else None

    def record_fixes(self, self_review_id, user, fixes):
        if self._raise:
            raise self._raise
        return "SR" if self._found else None

    def has_self_review(self, author_id, task_ref):
        return self._found

    def delete(self, self_review_id, user):
        if self._raise:
            raise self._raise
        return self._found

    def commit(self):
        self.committed = True


def test_submit_commits():
    repo = FakeSelfReviewRepo()
    assert SelfReviewService(repo).submit(USER, SimpleNamespace()) == "SR"
    assert repo.committed is True


def test_submit_unknown_skill_propagates_no_commit():
    repo = FakeSelfReviewRepo(raise_exc=UnknownReviewSkill("no such skill"))
    with pytest.raises(UnknownReviewSkill):
        SelfReviewService(repo).submit(USER, SimpleNamespace())
    assert repo.committed is False


def test_submit_unconfigured_lane_propagates_no_commit():
    repo = FakeSelfReviewRepo(raise_exc=SelfReviewPolicyNotSet("lane not configured"))
    with pytest.raises(SelfReviewPolicyNotSet):
        SelfReviewService(repo).submit(USER, SimpleNamespace())
    assert repo.committed is False


def test_get_missing_raises():
    with pytest.raises(SelfReviewNotFound):
        SelfReviewService(FakeSelfReviewRepo(found=False)).get(9)


def test_get_does_not_commit():
    repo = FakeSelfReviewRepo()
    assert SelfReviewService(repo).get(1) == "SR"
    assert repo.committed is False


def test_set_policy_commits_and_passes_the_admin():
    repo = FakePolicyRepo()
    service = SelfReviewPolicyService(repo)
    assert service.set_policy(ADMIN, lane="backend", skill="pr-review", required=True) == "LANE"
    assert repo.set_lane_args == ("backend", "pr-review", True, ADMIN)
    assert repo.committed is True


def test_set_policy_unknown_skill_propagates_no_commit():
    repo = FakePolicyRepo(raise_exc=UnknownReviewSkill("no such skill"))
    with pytest.raises(UnknownReviewSkill):
        SelfReviewPolicyService(repo).set_policy(ADMIN, lane="backend", skill="nope", required=False)
    assert repo.committed is False


def test_list_is_a_pass_through_read():
    repo = FakeSelfReviewRepo()
    assert SelfReviewService(repo).list(author_id=1) == ["s1"]
    assert repo.committed is False


# --- verdict derivation (pure rule, no DB) -------------------------------------------------------


def _finding(severity: str):
    from skillhub_core.reviews.schemas import SelfReviewFinding

    return SelfReviewFinding(severity=severity, title="x")


@pytest.mark.parametrize(
    "severities,expected",
    [
        ([], "pass"),
        (["nit"], "pass"),
        (["minor", "nit"], "pass"),
        (["major"], "changes_needed"),
        (["blocker"], "changes_needed"),
        (["nit", "blocker"], "changes_needed"),
    ],
)
def test_verdict_derived_from_severities(severities, expected):
    from skillhub_core.reviews.models import derive_verdict

    assert derive_verdict([_finding(s) for s in severities], None) == expected


def test_stated_verdict_wins_over_the_findings():
    from skillhub_core.reviews.models import derive_verdict

    assert derive_verdict([_finding("blocker")], "pass") == "pass"


def test_unknown_stated_verdict_rejected():
    from skillhub_core.reviews.errors import InvalidSelfReview
    from skillhub_core.reviews.models import derive_verdict

    with pytest.raises(InvalidSelfReview):
        derive_verdict([], "looks-fine")


# --- fixes (what the developer did about a finding) ----------------------------------------------


def test_record_fixes_commits():
    repo = FakeSelfReviewRepo()
    assert SelfReviewService(repo).record_fixes(1, USER, []) == "SR"
    assert repo.committed is True


def test_record_fixes_on_a_missing_review_raises_and_does_not_commit():
    repo = FakeSelfReviewRepo(found=False)
    with pytest.raises(SelfReviewNotFound):
        SelfReviewService(repo).record_fixes(9, USER, [])
    assert repo.committed is False


def test_record_fixes_propagates_a_foreign_review_no_commit():
    repo = FakeSelfReviewRepo(raise_exc=NotReviewAuthor("not yours"))
    with pytest.raises(NotReviewAuthor):
        SelfReviewService(repo).record_fixes(1, USER, [])
    assert repo.committed is False


# --- deletion ------------------------------------------------------------------------------------


def test_delete_commits():
    repo = FakeSelfReviewRepo()
    SelfReviewService(repo).delete(1, USER)
    assert repo.committed is True


def test_delete_missing_raises_and_does_not_commit():
    repo = FakeSelfReviewRepo(found=False)
    with pytest.raises(SelfReviewNotFound):
        SelfReviewService(repo).delete(9, USER)
    assert repo.committed is False


def test_delete_someone_elses_self_review_propagates():
    repo = FakeSelfReviewRepo(raise_exc=NotReviewAuthor("not yours"))
    with pytest.raises(NotReviewAuthor):
        SelfReviewService(repo).delete(1, USER)
    assert repo.committed is False
