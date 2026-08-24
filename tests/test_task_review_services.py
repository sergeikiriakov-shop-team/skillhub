"""Unit tests for TaskReviewService with in-memory fakes — no DB, no FastAPI, no container.

Covers what the service concentrates: not-found → TaskReviewNotFound, the commit owned on writes
and NOT taken on a read, and the one cross-aggregate rule it enforces — whether the policy demands
a clean run before the lead may approve."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from skillhub_core.reviews.errors import (
    InvalidReviewTransition,
    NotReviewAuthor,
    TaskReviewNotFound,
)
from skillhub_core.reviews.services import TaskReviewService

LEAD = SimpleNamespace(id=1, is_admin=False, is_reviewer=True)
AUTHOR = SimpleNamespace(id=2, is_admin=False, is_reviewer=False)


class FakeTaskRepo:
    def __init__(self, *, found=True, raise_exc=None):
        self._found = found
        self._raise = raise_exc
        self.committed = False
        self.approve_args = None
        self.send_back_args = None

    def list(self, *, status, author_id):
        return ["row"]

    def get(self, task_review_id):
        return "TASK" if self._found else None

    def approve(self, task_review_id, lead, *, require_clean_run):
        if self._raise:
            raise self._raise
        self.approve_args = (task_review_id, lead, require_clean_run)
        return "TASK" if self._found else None

    def send_back(self, task_review_id, lead, comment):
        if self._raise:
            raise self._raise
        self.send_back_args = (task_review_id, lead, comment)
        return "TASK" if self._found else None

    def delete(self, task_review_id, user):
        if self._raise:
            raise self._raise
        return self._found

    def commit(self):
        self.committed = True


class FakePolicyRepo:
    def __init__(self, *, required=False):
        self._required = required

    def self_review_required(self):
        return self._required


def service(repo, *, required=False):
    return TaskReviewService(repo, FakePolicyRepo(required=required))


def test_approve_commits_and_passes_the_policy_flag():
    repo = FakeTaskRepo()
    assert service(repo, required=True).approve(7, LEAD) == "TASK"
    assert repo.approve_args == (7, LEAD, True)
    assert repo.committed is True


def test_approve_passes_false_when_the_policy_does_not_demand_a_clean_run():
    repo = FakeTaskRepo()
    service(repo, required=False).approve(7, LEAD)
    assert repo.approve_args[2] is False


def test_approve_missing_task_raises_and_does_not_commit():
    repo = FakeTaskRepo(found=False)
    with pytest.raises(TaskReviewNotFound):
        service(repo).approve(9, LEAD)
    assert repo.committed is False


def test_approve_refused_by_the_aggregate_propagates_no_commit():
    repo = FakeTaskRepo(raise_exc=InvalidReviewTransition("no run to approve"))
    with pytest.raises(InvalidReviewTransition):
        service(repo).approve(7, LEAD)
    assert repo.committed is False


def test_send_back_commits_and_carries_the_comment():
    repo = FakeTaskRepo()
    service(repo).send_back(7, LEAD, comment="the empty-cart path is still open")
    assert repo.send_back_args == (7, LEAD, "the empty-cart path is still open")
    assert repo.committed is True


def test_send_back_without_a_reason_propagates_no_commit():
    repo = FakeTaskRepo(raise_exc=InvalidReviewTransition("returning a task requires a comment"))
    with pytest.raises(InvalidReviewTransition):
        service(repo).send_back(7, LEAD, comment="   ")
    assert repo.committed is False


def test_get_missing_raises_and_does_not_commit():
    repo = FakeTaskRepo(found=False)
    with pytest.raises(TaskReviewNotFound):
        service(repo).get(9)
    assert repo.committed is False


def test_list_is_a_pass_through_read():
    repo = FakeTaskRepo()
    assert service(repo).list(status="passed") == ["row"]
    assert repo.committed is False


def test_delete_commits():
    repo = FakeTaskRepo()
    service(repo).delete(7, AUTHOR)
    assert repo.committed is True


def test_delete_someone_elses_task_propagates_no_commit():
    repo = FakeTaskRepo(raise_exc=NotReviewAuthor("not yours"))
    with pytest.raises(NotReviewAuthor):
        service(repo).delete(7, AUTHOR)
    assert repo.committed is False


def test_delete_an_approved_task_propagates_no_commit():
    repo = FakeTaskRepo(raise_exc=InvalidReviewTransition("task is approved"))
    with pytest.raises(InvalidReviewTransition):
        service(repo).delete(7, AUTHOR)
    assert repo.committed is False
