"""Unit tests for the Skills services using in-memory fakes — no DB, no FastAPI, no container.

Proves the service logic that the DDD template concentrates in the service layer: not-found →
domain error, the commit is owned by the service on writes, validation happens before persistence,
and the infra duplicate error surfaces as the domain :class:`DuplicateSkill`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from skillhub_core.skills.errors import (
    DuplicateSkill,
    InvalidRecommendation,
    RecommendationNotFound,
    SkillNotFound,
)
from skillhub_core.skills.repositories import _effectiveness
from skillhub_core.skills.services import (
    IngestService,
    RecommendationService,
    RubricService,
    SkillService,
)


_OUTCOME = {
    "skill_id": 1, "version_id": 1, "is_new_version": True,
    "embedded": True, "similar_warning": None, "notes": [],
}


class FakeSkillRepo:
    def __init__(self, *, detail=None, exists=True, name_exists=False, duplicate=None, outcome=None):
        self._detail = detail
        self._exists = exists
        self._name_exists = name_exists
        self._duplicate = duplicate
        self._outcome = outcome or dict(_OUTCOME)
        self.committed = False
        self.deleted = None
        self.saved = None

    def list(self, *, search, category, evaluated):
        return ["s1", "s2"]

    def get(self, skill_id):
        return self._detail if self._exists else None

    def delete(self, skill_id):
        self.deleted = skill_id
        return self._exists

    # ingest primitives
    def embed(self, text):
        return [0.1, 0.2]

    def name_exists(self, name):
        return self._name_exists

    def duplicate_for_new_name(self, name, content_hash, body_md, vector):
        return self._duplicate

    def save_parsed(self, parsed, **kwargs):
        self.saved = parsed
        return self._outcome

    def commit(self):
        self.committed = True


def _parsed():
    return SimpleNamespace(
        name="x", raw_content="raw", references=[], body_md="body", searchable_text=lambda: "text"
    )


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


class FakeRubricRepo:
    def get_taxonomy(self):
        return [{"key": "data-access", "label": "Data access"}]

    def get_weights(self):
        return {"trigger_quality": 2.0, "completeness": 2.0}


def test_get_rubric_serves_strategy_and_judge_panel():
    """Regression: get_rubric must build a valid RubricOut (a dropped import once made it 500),
    and it must serve the server-side trial-result judge strategy (panel + dimensions)."""
    out = RubricService(FakeRubricRepo()).get_rubric()
    assert out.rubric_version and out.result_judge_version
    assert out.result_judge_panel["aggregate"] == "median"
    assert [d["key"] for d in out.result_judge_dimensions] == [
        "completeness", "correctness", "scope_discipline", "process_fidelity", "clarity"
    ]


def _summary(grade=None, passed=0, failed=0):
    s = {"entries": [{"passed": ["x"] * passed, "failed": ["y"] * failed}]}
    if grade is not None:
        s["result_grade"] = grade
    return s


def test_effectiveness_is_grade_over_ten_capped_by_the_objective_gate():
    # graded: grade/10 when the mechanics gate is fully passed …
    assert _effectiveness(_summary(grade=9.0, passed=13, failed=0)) == 0.9
    # … but the objective pass-rate is a ceiling (a partial run can't score above what it did)
    assert _effectiveness(_summary(grade=8.0, passed=5, failed=5)) == 0.5
    # ungraded (older trials) fall back to the objective pass-rate unchanged
    assert _effectiveness(_summary(passed=11, failed=2)) == 0.8462
    assert _effectiveness({}) is None


def test_ingest_new_name_duplicate_raises():
    repo = FakeSkillRepo(name_exists=False, duplicate=(7, "green-loop"))
    with pytest.raises(DuplicateSkill):
        IngestService(repo).ingest_parsed(_parsed(), author=None, source_type="upload")
    assert repo.saved is None  # gate blocked before persisting


def test_ingest_same_name_skips_gate_and_saves():
    # A same-name re-upload is a new version — the dedupe gate must not fire even if a dup exists.
    repo = FakeSkillRepo(name_exists=True, duplicate=(1, "dup"))
    out = IngestService(repo).ingest_parsed(_parsed(), author=None, source_type="upload")
    assert out == _OUTCOME and repo.saved is not None


def test_ingest_new_name_no_dup_saves():
    repo = FakeSkillRepo(name_exists=False, duplicate=None)
    out = IngestService(repo).ingest_parsed(_parsed(), author=None, source_type="upload")
    assert out["skill_id"] == 1 and repo.saved is not None


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
