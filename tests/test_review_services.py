"""Unit tests for ReviewService with an in-memory fake — no DB, no FastAPI, no container.

Covers the logic the service concentrates: not-found → ReviewNotFound, commit owned on writes, and
the data-coupled errors (NotReviewAuthor / InvalidReviewTransition) propagating from the repo."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from skillhub_core.reviews.errors import (
    InvalidReviewTransition,
    NotReviewAuthor,
    ReviewNotFound,
)
from skillhub_core.reviews.services import ReviewService

USER = SimpleNamespace(id=1, is_admin=False)


class FakeReviewRepo:
    def __init__(self, *, found=True, raise_exc=None):
        self._found = found
        self._raise = raise_exc
        self.committed = False

    def submit(self, author, data):
        return "R"

    def list(self, *, status, author_id, reviewer_id):
        return ["s1"]

    def get(self, review_id):
        return "R" if self._found else None

    def _write(self):
        if self._raise:
            raise self._raise
        return "R" if self._found else None

    def submit_result(self, review_id, reviewer, verdict, comments):
        return self._write()

    def resubmit(self, review_id, user, commit_shas, note):
        return self._write()

    def acknowledge(self, review_id, user):
        return self._write()

    def commit(self):
        self.committed = True


def test_submit_commits():
    repo = FakeReviewRepo()
    assert ReviewService(repo).submit(USER, SimpleNamespace()) == "R"
    assert repo.committed is True


def test_get_missing_raises():
    with pytest.raises(ReviewNotFound):
        ReviewService(FakeReviewRepo(found=False)).get(9)


def test_submit_result_missing_raises_and_no_commit():
    repo = FakeReviewRepo(found=False)
    with pytest.raises(ReviewNotFound):
        ReviewService(repo).submit_result(9, USER, verdict="approve", comments="")
    assert repo.committed is False


def test_submit_result_transition_error_propagates_no_commit():
    repo = FakeReviewRepo(raise_exc=InvalidReviewTransition("not awaiting review"))
    with pytest.raises(InvalidReviewTransition):
        ReviewService(repo).submit_result(1, USER, verdict="approve", comments="")
    assert repo.committed is False


def test_resubmit_not_author_propagates():
    repo = FakeReviewRepo(raise_exc=NotReviewAuthor("only the author"))
    with pytest.raises(NotReviewAuthor):
        ReviewService(repo).resubmit(1, USER, commit_shas=[], note="")


def test_acknowledge_ok_commits():
    repo = FakeReviewRepo()
    assert ReviewService(repo).acknowledge(1, USER) == "R"
    assert repo.committed is True
