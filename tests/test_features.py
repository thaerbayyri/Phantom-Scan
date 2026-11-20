import numpy as np
import pytest

from phantom.features import (
    FEATURE_NAMES,
    NUM_FEATURES,
    RESAMPLE_HZ,
    extract_window_features,
    resampled_window_features,
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


def _scene(t_ms: np.ndarray, motion_amp: float = 1.0, k: int = 51) -> tuple[np.ndarray, np.ndarray]:
    """The same physical scene (a 1.5 Hz motion on a fixed spectrum) sampled at the given times."""
    t_s = t_ms / 1000.0
    base = 10.0 + 2.0 * np.sin(np.linspace(0, 4 * np.pi, k))
    gain = np.linspace(0.5, 1.5, k)
    amps = base[None, :] + motion_amp * np.sin(2 * np.pi * 1.5 * t_s)[:, None] * gain[None, :]
    return amps, np.full(len(t_ms), -45.0)


SLOW_MS = np.arange(0.0, 1000.0, 1000.0 / 40.0)
FAST_MS = np.arange(0.0, 1000.0, 1000.0 / 66.0)
RATE_SENSITIVE = ("motion_band_power", "change_points")


def _noisy_empty(t_ms: np.ndarray, seed: int, k: int = 51) -> tuple[np.ndarray, np.ndarray]:
    """An empty room: a fixed spectrum plus per-packet measurement noise."""
    rng = np.random.default_rng(seed)
    base = 10.0 + 2.0 * np.sin(np.linspace(0, 4 * np.pi, k))
    return base[None, :] + rng.normal(0.0, 0.3, size=(len(t_ms), k)), np.full(len(t_ms), -45.0)


def _mean_ratio(extract) -> dict[str, float]:
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    slow = np.mean([extract(SLOW_MS, 40.0, _noisy_empty(SLOW_MS, s)) for s in range(30)], axis=0)
    fast = np.mean([extract(FAST_MS, 66.0, _noisy_empty(FAST_MS, s)) for s in range(30)], axis=0)
    return {n: slow[idx[n]] / fast[idx[n]] for n in RATE_SENSITIVE}


def test_raw_features_of_a_noisy_empty_room_depend_on_the_frame_rate():
    # Why resampling exists: at 40 vs 66 fps the same empty room gives different motion power and change counts.
    ratios = _mean_ratio(lambda t, fs, ar: extract_window_features(ar[0], ar[1], fs))
    assert any(abs(r - 1.0) > 0.4 for r in ratios.values()), ratios


def test_resampled_features_of_a_noisy_empty_room_barely_depend_on_the_frame_rate():
    ratios = _mean_ratio(lambda t, fs, ar: resampled_window_features(t, ar[0], ar[1]))
    assert all(abs(r - 1.0) < 0.25 for r in ratios.values()), ratios


def test_resampled_features_of_a_clean_scene_match_across_rates():
    a = resampled_window_features(SLOW_MS, *_scene(SLOW_MS))
    b = resampled_window_features(FAST_MS, *_scene(FAST_MS))
    np.testing.assert_allclose(a, b, rtol=0.05, atol=1e-6)


def test_bursty_timestamps_with_duplicates_are_handled():
    rng = np.random.default_rng(3)
    t_ms = np.sort(rng.uniform(0.0, 1000.0, 45)).round()
    t_ms[10] = t_ms[11]  # two packets arriving in the same millisecond
    feats = resampled_window_features(t_ms, *_scene(t_ms))
    assert feats.shape == (NUM_FEATURES,)
    assert np.all(np.isfinite(feats))


def test_resampled_features_use_the_fixed_rate():
    t_ms = np.arange(0.0, 1000.0, 1000.0 / 66.0)
    amps, rssi = _scene(t_ms)
    grid = np.linspace(t_ms[0], t_ms[-1], int(round((t_ms[-1] - t_ms[0]) / 1000.0 * RESAMPLE_HZ)) + 1)
    expected = extract_window_features(*_scene(grid), RESAMPLE_HZ)
    np.testing.assert_allclose(resampled_window_features(t_ms, amps, rssi), expected, rtol=0.02, atol=1e-6)


def test_sliding_windows_skip_sparse_windows():
    t_ms = np.concatenate([np.arange(0, 1000, 25.0), np.arange(3000, 4000, 25.0)])
    amps = np.ones((len(t_ms), 51))
    rssi = np.full(len(t_ms), -45.0)
    wins = list(sliding_windows(t_ms, amps, rssi, window_s=1.0, hop_s=0.5, min_frames=20))
    assert all(np.isfinite(f).all() for f, _ in wins)
    assert len(wins) <= 4
