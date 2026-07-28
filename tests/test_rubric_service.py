"""Unit tests for RubricService using an in-memory fake repository — no DB, no container.

This is the payoff of the Protocol-based repositories: the service's orchestration and validation
are tested in isolation by injecting a fake that satisfies ``RubricRepository``."""

import pytest

from skillhub_core.skills.errors import InvalidWeights
from skillhub_core.skills.services import RubricService

BASE = {
    "clarity": 1.0,
    "trigger_quality": 2.0,
    "completeness": 2.0,
    "reusability": 1.0,
    "safety": 1.0,
    "structure": 1.0,
}


class FakeRubricRepository:
    """In-memory RubricRepository."""

    def __init__(self, weights: dict[str, float]):
        self._weights = dict(weights)
        self.recomputed_calls = 0
        self.committed = False

    def get_weights(self) -> dict[str, float]:
        return dict(self._weights)

    def set_weights(self, weights: dict[str, float]) -> dict[str, float]:
        self._weights.update(weights)
        return dict(self._weights)

    def recompute_overall_scores(self) -> int:
        self.recomputed_calls += 1
        return 7  # pretend 7 evaluations were rescored

    def get_taxonomy(self) -> list[dict]:
        return []

    def commit(self) -> None:
        self.committed = True


def test_set_weights_happy_path_persists_recomputes_and_commits():
    repo = FakeRubricRepository(BASE)
    result = RubricService(repo).set_weights({"safety": 3})
    assert result["weights"]["safety"] == 3
    assert result["rescored"] == 7
    assert repo.recomputed_calls == 1
    assert repo.committed is True


def test_unknown_dimension_is_rejected_without_commit():
    repo = FakeRubricRepository(BASE)
    with pytest.raises(InvalidWeights):
        RubricService(repo).set_weights({"nonsense": 1})
    assert repo.committed is False
    assert repo.recomputed_calls == 0


def test_negative_weight_is_rejected():
    repo = FakeRubricRepository(BASE)
    with pytest.raises(InvalidWeights):
        RubricService(repo).set_weights({"safety": -1})


def test_all_zero_weights_are_rejected():
    repo = FakeRubricRepository(BASE)
    with pytest.raises(InvalidWeights):
        RubricService(repo).set_weights({k: 0 for k in BASE})


def test_get_rubric_reads_weights_and_taxonomy_from_repo():
    repo = FakeRubricRepository(BASE)
    out = RubricService(repo).get_rubric()
    assert out.weights == BASE
    assert out.categories == []
    assert out.rubric_version  # non-empty
