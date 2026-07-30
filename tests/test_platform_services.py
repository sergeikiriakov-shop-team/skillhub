"""Unit tests for UserAdminService with an in-memory fake — no DB, no FastAPI, no container."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skillhub_core.platform.errors import InvalidRole, UserNotFound
from skillhub_core.platform.models import ROLES
from skillhub_core.platform.services import UserAdminService

VALID_ROLE = sorted(ROLES)[0]


class FakeUserAdminRepo:
    def __init__(self, *, found=True):
        self._found = found
        self.committed = False

    def list_users(self):
        return ["u1"]

    def create_user(self, *, name, role):
        return {
            "id": 1,
            "name": name,
            "role": role,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "token": "tok",
        }

    def set_role(self, user_id, role):
        return "U" if self._found else None

    def set_reviewer(self, user_id, is_reviewer):
        return "U" if self._found else None

    def commit(self):
        self.committed = True


def test_create_user_rejects_unknown_role():
    repo = FakeUserAdminRepo()
    with pytest.raises(InvalidRole):
        UserAdminService(repo).create_user(name="x", role="bogus")
    assert repo.committed is False


def test_create_user_ok_commits_and_returns_token():
    repo = FakeUserAdminRepo()
    out = UserAdminService(repo).create_user(name="x", role=VALID_ROLE)
    assert out.token == "tok" and repo.committed is True


def test_set_role_rejects_unknown_role():
    with pytest.raises(InvalidRole):
        UserAdminService(FakeUserAdminRepo()).set_role(1, "bogus")


def test_set_role_missing_user_raises_and_no_commit():
    repo = FakeUserAdminRepo(found=False)
    with pytest.raises(UserNotFound):
        UserAdminService(repo).set_role(9, VALID_ROLE)
    assert repo.committed is False


def test_set_reviewer_missing_user_raises():
    with pytest.raises(UserNotFound):
        UserAdminService(FakeUserAdminRepo(found=False)).set_reviewer(9, True)


def test_set_reviewer_ok_commits():
    repo = FakeUserAdminRepo()
    UserAdminService(repo).set_reviewer(1, True)
    assert repo.committed is True
