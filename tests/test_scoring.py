"""Unit tests for the server-authoritative overall score.

``compute_overall`` is the weighted mean of the per-dimension scores under the admin-managed
weights. It has no dependencies (pure Python), so this runs without a DB or the app stack."""

from skillhub_core.skills.rubric import compute_overall

FULL = {
    "clarity": 8,
    "trigger_quality": 6,
    "completeness": 9,
    "reusability": 5,
    "safety": 7,
    "structure": 8,
}


def test_equal_weights_is_plain_mean():
    weights = {k: 1.0 for k in FULL}
    assert compute_overall(FULL, weights) == round(sum(FULL.values()) / len(FULL), 2)


def test_weights_shift_the_mean():
    # trigger_quality + completeness weighted x2 pulls the score toward them.
    # num = 8 + 6*2 + 9*2 + 5 + 7 + 8 = 58 ; den = 8 -> 7.25
    weights = {
        "clarity": 1,
        "trigger_quality": 2,
        "completeness": 2,
        "reusability": 1,
        "safety": 1,
        "structure": 1,
    }
    assert compute_overall(FULL, weights) == 7.25


def test_zero_weight_dimension_is_ignored():
    assert compute_overall({"clarity": 10, "safety": 0}, {"clarity": 1, "safety": 0}) == 10.0


def test_only_overlapping_dimensions_count():
    # a weight with no matching score does not contribute.
    assert compute_overall({"clarity": 4}, {"clarity": 3, "safety": 5}) == 4.0


def test_all_zero_weights_returns_none():
    assert compute_overall(FULL, {k: 0 for k in FULL}) is None


def test_empty_inputs_return_none():
    assert compute_overall({}, {}) is None
    assert compute_overall(FULL, {}) is None
    assert compute_overall({}, {"clarity": 1}) is None


def test_rounds_to_two_dp():
    assert compute_overall({"a": 1, "b": 1, "c": 2}, {"a": 1, "b": 1, "c": 1}) == 1.33
