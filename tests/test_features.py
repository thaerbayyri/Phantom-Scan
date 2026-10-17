import numpy as np
import pytest

from phantom.features import (
    FEATURE_NAMES,
    NUM_FEATURES,
    extract_window_features,
    sliding_windows,
)

FS = 40.0


def _window(motion_amp: float, seconds: float = 1.0, k: int = 51, seed: int = 0):
    rng = np.random.default_rng(seed)
    t = int(seconds * FS)
    base = 10.0 + 2.0 * np.sin(np.linspace(0, 4 * np.pi, k))
    walk = motion_amp * np.sin(2 * np.pi * 1.5 * np.arange(t) / FS)[:, None]
    amps = base[None, :] + walk * rng.uniform(0.5, 1.5, size=(1, k)) + rng.normal(0, 0.05, size=(t, k))
    rssi = np.full(t, -45.0)
    return amps, rssi


def test_feature_vector_has_the_documented_15_named_features():
    amps, rssi = _window(0.5)
    feats = extract_window_features(amps, rssi, FS)
    assert NUM_FEATURES == 15 == len(FEATURE_NAMES) == feats.shape[0]
    assert np.all(np.isfinite(feats))


def test_extraction_is_deterministic():
    amps, rssi = _window(0.5)
    a = extract_window_features(amps, rssi, FS)
    b = extract_window_features(amps.copy(), rssi.copy(), FS)
    assert np.array_equal(a, b)


def test_motion_raises_variance_and_motion_band_power_and_finds_the_dominant_frequency():
    quiet = extract_window_features(*_window(0.0), FS)
    moving = extract_window_features(*_window(1.5), FS)
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    assert moving[idx["temporal_variance"]] > 20 * quiet[idx["temporal_variance"]]
    assert moving[idx["motion_band_power"]] > 20 * quiet[idx["motion_band_power"]]
    assert abs(moving[idx["dominant_freq_hz"]] - 1.5) < 0.4


def test_features_ignore_dc_gain_in_shape_statistics_but_not_in_mean():
    amps, rssi = _window(0.5)
    base = extract_window_features(amps, rssi, FS)
    scaled = extract_window_features(amps * 3.0, rssi, FS)
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    assert scaled[idx["spec_mean"]] == pytest.approx(3.0 * base[idx["spec_mean"]])
    assert scaled[idx["spec_skew"]] == pytest.approx(base[idx["spec_skew"]], abs=1e-9)
    assert scaled[idx["spec_entropy"]] == pytest.approx(base[idx["spec_entropy"]], abs=1e-9)


def test_degenerate_windows_return_zeros_not_nan():
    assert np.all(extract_window_features(np.zeros((1, 51)), np.zeros(1), FS) == 0.0)
    assert np.all(np.isfinite(extract_window_features(np.zeros((40, 51)), np.full(40, -50.0), FS)))


def test_sliding_windows_cover_the_stream_with_the_requested_hop():
    t_ms = np.arange(0, 5000, 25.0)  # 40 Hz, 5 s
    amps = np.random.default_rng(1).normal(10, 1, size=(len(t_ms), 51))
    rssi = np.full(len(t_ms), -45.0)
    wins = list(sliding_windows(t_ms, amps, rssi, window_s=1.0, hop_s=0.5))
    # Window ends at 1000, 1500, ..., 4500 ms (the next end, 5000, is past the
    # last frame at 4975 ms).
    assert len(wins) == 8
    feats, t_end = wins[0]
    assert feats.shape == (NUM_FEATURES,)
    assert t_end == pytest.approx(1000.0, abs=25.0)


def test_sliding_windows_skip_sparse_windows():
    t_ms = np.concatenate([np.arange(0, 1000, 25.0), np.arange(3000, 4000, 25.0)])
    amps = np.ones((len(t_ms), 51))
    rssi = np.full(len(t_ms), -45.0)
    wins = list(sliding_windows(t_ms, amps, rssi, window_s=1.0, hop_s=0.5, min_frames=20))
    assert all(np.isfinite(f).all() for f, _ in wins)
    assert len(wins) <= 4
