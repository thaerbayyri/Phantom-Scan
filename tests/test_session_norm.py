"""Session-relative features: scale each session's windows by that session's own empty-room baseline."""
from __future__ import annotations

import numpy as np

from phantom.features import FEATURE_NAMES, NUM_FEATURES
from phantom.session_norm import RATIO_FEATURES, SHIFT_FEATURES, relative_to_baseline, split_baseline

IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


def test_ratio_features_are_divided_by_the_baseline_median_and_shift_features_subtracted() -> None:
    baseline = np.ones((4, NUM_FEATURES))
    baseline[:, IDX["temporal_variance"]] = 2.0
    baseline[:, IDX["rssi_mean"]] = -50.0
    x = np.ones((1, NUM_FEATURES))
    x[0, IDX["temporal_variance"]] = 10.0
    x[0, IDX["rssi_mean"]] = -44.0

    out = relative_to_baseline(x, baseline)

    assert out[0, IDX["temporal_variance"]] == 5.0
    assert out[0, IDX["rssi_mean"]] == 6.0
    assert out[0, IDX["spec_skew"]] == 1.0  # shape features left as they are
    assert x[0, IDX["temporal_variance"]] == 10.0  # input not modified


def test_same_activity_in_a_louder_session_gives_the_same_relative_features() -> None:
    quiet_base = np.full((5, NUM_FEATURES), 1.0)
    loud_base = np.full((5, NUM_FEATURES), 8.0)
    quiet_walk = np.full((1, NUM_FEATURES), 3.0)
    loud_walk = np.full((1, NUM_FEATURES), 24.0)
    a = relative_to_baseline(quiet_walk, quiet_base)
    b = relative_to_baseline(loud_walk, loud_base)
    for name in RATIO_FEATURES:
        assert a[0, IDX[name]] == b[0, IDX[name]] == 3.0


def test_zero_baseline_does_not_divide_by_zero() -> None:
    out = relative_to_baseline(np.ones((2, NUM_FEATURES)), np.zeros((3, NUM_FEATURES)))
    assert np.all(np.isfinite(out))


def test_split_baseline_keeps_the_first_part_for_calibration_and_the_rest_as_data() -> None:
    windows = np.arange(10 * NUM_FEATURES, dtype=float).reshape(10, NUM_FEATURES)
    calib, rest = split_baseline(windows, fraction=0.3)
    assert calib.shape[0] == 3 and rest.shape[0] == 7
    assert np.array_equal(calib[0], windows[0]) and np.array_equal(rest[0], windows[3])


def test_feature_groups_cover_every_feature_once() -> None:
    other = set(FEATURE_NAMES) - set(RATIO_FEATURES) - set(SHIFT_FEATURES)
    assert not set(RATIO_FEATURES) & set(SHIFT_FEATURES)
    assert other == {"dominant_freq_hz", "spec_skew", "spec_kurt", "spec_entropy"}
