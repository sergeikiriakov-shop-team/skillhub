"""Unit tests for the Skills services using in-memory fakes — no DB, no FastAPI, no container.

Proves the service logic that the DDD template concentrates in the service layer: not-found →
domain error, the commit is owned by the service on writes, validation happens before persistence,
and the infra duplicate error surfaces as the domain :class:`DuplicateSkill`."""

from __future__ import annotations

import pytest

from skillhub_core.skills.errors import (
    DuplicateSkill,
    InvalidRecommendation,
    RecommendationNotFound,
    SkillNotFound,
)
from skillhub_core.skills.services import IngestService, RecommendationService, SkillService


class FakeSkillRepo:
    def __init__(self, *, detail=None, exists=True, duplicate=None):
        self._detail = detail
        self._exists = exists
        self._duplicate = duplicate
        self.committed = False
        self.deleted = None

    def list(self, *, search, category, evaluated):
        return ["s1", "s2"]

    def get(self, skill_id):
        return self._detail if self._exists else None

    def create(self, *, content, author, references, source_format, user):
        if self._duplicate is not None:
            raise self._duplicate
        return self._detail

    def delete(self, skill_id):
        self.deleted = skill_id
        return self._exists

    def commit(self):
        self.committed = True


def test_get_skill_found_returns_detail():
    assert SkillService(FakeSkillRepo(detail="DETAIL")).get_skill(1) == "DETAIL"


def test_get_skill_missing_raises():
    with pytest.raises(SkillNotFound):
        SkillService(FakeSkillRepo(exists=False)).get_skill(99)


def test_delete_commits_when_present():
    repo = FakeSkillRepo(exists=True)
    SkillService(repo).delete_skill(5)
    assert repo.deleted == 5 and repo.committed is True


def test_delete_missing_raises_and_does_not_commit():
    repo = FakeSkillRepo(exists=False)
    with pytest.raises(SkillNotFound):
        SkillService(repo).delete_skill(5)
    assert repo.committed is False


def test_ingest_surfaces_domain_duplicate():
    repo = FakeSkillRepo(duplicate=DuplicateSkill(7, "green-loop"))
    with pytest.raises(DuplicateSkill):
        IngestService(repo).create(
            content="x", author=None, references=[], source_format="claude_skill", user=object()
        )


class FakeRecRepo:
    def __init__(self, *, found=True):
        self._found = found
        self.committed = False

    def list(self, status):
        return ["r1"]

    def create(self, payload, created_by):
        return "REC"

    def set_status(self, rec_id, status):
        return "REC" if self._found else None

    def commit(self):
        self.committed = True


def test_recommendation_create_rejects_unknown_kind():
    repo = FakeRecRepo()
    with pytest.raises(InvalidRecommendation):
        RecommendationService(repo).create({"kind": "bogus"}, created_by="me")
    assert repo.committed is False


def test_recommendation_create_ok_commits():
    repo = FakeRecRepo()
    out = RecommendationService(repo).create({"kind": "improve", "title": "t"}, created_by="me")
    assert out == "REC" and repo.committed is True


def test_recommendation_set_status_rejects_unknown_status():
    with pytest.raises(InvalidRecommendation):
        RecommendationService(FakeRecRepo()).set_status(1, "bogus")


def test_recommendation_set_status_not_found():
    with pytest.raises(RecommendationNotFound):
        RecommendationService(FakeRecRepo(found=False)).set_status(1, "done")
