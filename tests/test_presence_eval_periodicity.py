"""PS-FIX-09: the spectral feature behaves on signals whose truth is known, including the 33.3 Hz ping-cadence alias that dominated the
first version of the analysis on a 50 Hz grid."""
from __future__ import annotations

import numpy as np

from scripts.presence_eval import periodicity as P
from scripts.presence_eval.recordings import NodeSeries


def _series(t_ms: np.ndarray, amp: np.ndarray, seed: int = 0, noise: float = 0.3) -> NodeSeries:
    rng = np.random.default_rng(seed)
    a = 10.0 + amp[:, None] * np.linspace(0.5, 1.5, 51)[None, :] + noise * rng.standard_normal((len(t_ms), 51))
    return NodeSeries(t=t_ms.astype(np.int64), rssi=np.full(len(t_ms), -40.0, np.float32), a=a.astype(np.float32))


def _arrivals(seconds: float, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.cumsum(15.0 + 4.0 * rng.standard_normal(int(seconds * 70)))
    return np.round(t[t < seconds * 1000]).astype(np.int64) + 1_000_000


def test_resample_uniform_recovers_a_slow_sine_and_flags_gaps() -> None:
    t = _arrivals(20)
    sine = np.sin(2 * np.pi * 2.0 * (t - t[0]) / 1000.0)
    a = np.repeat(sine[:, None], 51, axis=1)
    keep = ~((t - t[0] > 8000) & (t - t[0] < 9200))              # a 1.2 s hole
    grid, ag, valid = P.resample_uniform(t[keep], a[keep], int(t[0]), 50.0)
    inside = (grid > 1) & (grid < 7)
    assert np.max(np.abs(ag[inside, 0] - np.sin(2 * np.pi * 2.0 * grid[inside]))) < 0.1
    assert valid[(grid > 1) & (grid < 7)].all()
    assert not valid[(grid > 8.1) & (grid < 9.0)].any()


def test_a_pure_7_hz_line_is_found_and_white_noise_is_not_peaky() -> None:
    fs, n = 64.0, 960
    t = np.arange(n) / fs
    rng = np.random.default_rng(3)
    line = 10 + np.sin(2 * np.pi * 7.0 * t)[:, None] * np.linspace(0.5, 1.5, 51)[None, :] + 0.2 * rng.standard_normal((n, 51))
    noise = 10 + rng.standard_normal((n, 51))
    f_line, f_noise = P.spectral_features(line, fs), P.spectral_features(noise, fs)
    assert abs(f_line["peak_hz"] - 7.0) < 0.15 and f_line["peak_ratio"] > 50 and f_line["narrow_share"] > 0.3
    assert f_noise["peak_ratio"] < 15 and f_noise["narrow_share"] < 0.12


def test_a_constant_signal_gives_nan_not_a_fabricated_number() -> None:
    f = P.spectral_features(np.full((750, 51), 10.0), 50.0)
    assert np.isnan(f["peak_ratio"]) and np.isnan(f["narrow_share"])


def test_the_33_hz_ping_cadence_aliases_to_16_7_hz_on_a_50_hz_grid_but_leaves_the_band_at_64_hz() -> None:
    rng = np.random.default_rng(5)
    k = np.arange(int(40_000 / 30))
    reply = 1_000_000 + 30 * k + np.round(1.5 * rng.standard_normal(k.size))          # type A: one frame per 30 ms ping
    other = 1_000_015 + 30 * k + np.round(1.5 * rng.standard_normal(k.size))          # type B: another frame half a ping later
    t = np.concatenate([reply, other]).astype(np.int64)
    amp = np.concatenate([np.full(k.size, 2.0), np.full(k.size, -2.0)])               # the two frame types differ in amplitude
    order = np.argsort(t, kind="stable")
    s = _series(t[order], amp[order])
    on50 = P.window_table(s, int(t[0]), 15, fs=50.0)
    on64 = P.window_table(s, int(t[0]), 15, fs=64.0)
    assert on50["k"].size >= 2 and on64["k"].size >= 2
    assert np.all(np.abs(on50["peak_hz"] - 16.67) < 0.3), on50["peak_hz"]
    assert np.median(on50["peak_ratio"]) > 3 * np.median(on64["peak_ratio"]), "the alias must dominate on 50 Hz and be gone on 64 Hz"


def test_windows_share_one_grid_across_nodes_and_drop_windows_with_a_gap() -> None:
    t = _arrivals(60)
    amp = np.zeros(len(t))
    early = _series(t, amp, 4)
    late_keep = t > t[0] + 7300                                    # node starts late, off the window grid
    late = NodeSeries(t=t[late_keep], rssi=early.rssi[late_keep], a=early.a[late_keep])
    gap_keep = ~((t - t[0] > 20_000) & (t - t[0] < 22_000))       # 2 s hole kills window k = 1 (15-30 s)
    gappy = NodeSeries(t=t[gap_keep], rssi=early.rssi[gap_keep], a=early.a[gap_keep])
    full = P.window_table(early, int(t[0]), 15)
    assert full["k"].tolist() == [0, 1, 2]
    assert P.window_table(late, int(t[0]), 15)["k"].tolist() == [1, 2]       # same indices as the full node, not renumbered from 0
    assert P.window_table(gappy, int(t[0]), 15)["k"].tolist() == [0, 2]


def test_youden_threshold_separates_two_classes_and_refuses_an_empty_class() -> None:
    tau = P.youden_threshold(np.array([5.0, 6.0, 7.0]), np.array([1.0, 2.0, 3.0]))
    assert 3.0 < tau <= 5.0
    assert P.youden_threshold(np.zeros(0), np.array([1.0])) is None
