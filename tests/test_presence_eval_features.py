"""T2: feature invariances, AUC correctness, bootstrap determinism, window dropping."""
from __future__ import annotations

import numpy as np
import pytest

from scripts.presence_eval.features import MIN_FRAMES, fuse_max, node_windows, window_features
from scripts.presence_eval.recordings import NodeSeries
from scripts.presence_eval.stats import DEFAULT_BLOCK, auc, block_bootstrap_auc

RNG = np.random.default_rng(7)
SHAPE = 12.0 + 3.0 * np.sin(np.linspace(0, 4 * np.pi, 51))  # a fixed subcarrier shape


def make_window(noise: float, k: int = 40, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return SHAPE[None, :] * (1.0 + noise * rng.standard_normal((k, 51)))


def series_from(ts: list[int], a: np.ndarray) -> NodeSeries:
    return NodeSeries(t=np.asarray(ts, dtype=np.int64), rssi=np.full(len(ts), -40.0, dtype=np.float32), a=a.astype(np.float32))


# ---- invariances ---------------------------------------------------------------------------

def test_window_gain_leaves_perturb_decor_gainstd_unchanged() -> None:
    w = make_window(0.1)
    base, scaled = window_features(w), window_features(w * 3.7)
    for f in ("perturb", "decor", "gainstd", "perturb_agc"):
        assert scaled[f] == pytest.approx(base[f], rel=1e-9), f


def test_per_frame_gain_leaves_decor_and_agc_perturb_unchanged_but_not_raw_perturb() -> None:
    w = make_window(0.1)
    gains = np.linspace(0.5, 2.0, w.shape[0])[:, None]
    base, scaled = window_features(w), window_features(w * gains)
    assert scaled["decor"] == pytest.approx(base["decor"], rel=1e-9)
    assert scaled["perturb_agc"] == pytest.approx(base["perturb_agc"], rel=1e-9)
    # raw perturb is NOT per-frame gain invariant; documenting that honestly
    assert scaled["perturb"] > 2 * base["perturb"]
    assert scaled["gainstd"] > 2 * base["gainstd"]


def test_single_frame_scaled_leaves_decor_unchanged() -> None:
    w = make_window(0.1)
    w2 = w.copy()
    w2[10] *= 5.0
    assert window_features(w2)["decor"] == pytest.approx(window_features(w)["decor"], rel=1e-9)


def test_constant_signal_scores_zero() -> None:
    w = np.tile(SHAPE, (30, 1))
    feats = window_features(w, np.full(30, -40.0))
    for f in ("perturb", "perturb_agc", "decor", "gainstd", "rssistd"):
        assert feats[f] == pytest.approx(0.0, abs=1e-9), f


def test_flat_frames_do_not_crash_and_decor_is_undefined() -> None:
    feats = window_features(np.full((30, 51), 12.0))
    assert np.isnan(feats["decor"]) and feats["perturb"] == pytest.approx(0.0, abs=1e-12)


def test_injected_motion_raises_scores_monotonically() -> None:
    levels = [0.0, 0.02, 0.05, 0.1, 0.2, 0.4]
    feats = [window_features(make_window(n, k=80, seed=3)) for n in levels]
    for f in ("perturb", "perturb_agc", "decor"):
        vals = [x[f] for x in feats]
        assert all(b > a for a, b in zip(vals, vals[1:])), (f, vals)


# ---- AUC -----------------------------------------------------------------------------------

def test_auc_hand_computed_with_ties() -> None:
    # pos=[1,2,3], neg=[0,2]: wins 1>0, 2>0, 3>0, 3>2 = 4; tie 2=2 = .5; loss 1<2 -> 4.5/6
    assert auc(np.array([1, 2, 3]), np.array([0, 2])) == pytest.approx(0.75)
    assert auc(np.array([2, 2, 2]), np.array([2, 2])) == pytest.approx(0.5)
    assert auc(np.array([5, 6]), np.array([1, 2, 3])) == 1.0
    assert auc(np.array([1, 2, 3]), np.array([5, 6])) == 0.0


def test_auc_matches_brute_force_on_random_data() -> None:
    rng = np.random.default_rng(11)
    pos, neg = np.round(rng.normal(0.3, 1, 60), 1), np.round(rng.normal(0, 1, 80), 1)  # rounding forces ties
    brute = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
    assert auc(pos, neg) == pytest.approx(brute)


def test_auc_empty_class_is_nan() -> None:
    assert np.isnan(auc(np.array([]), np.array([1.0])))


# ---- bootstrap -----------------------------------------------------------------------------

def test_bootstrap_is_deterministic_for_fixed_seed_and_differs_across_seeds() -> None:
    rng = np.random.default_rng(5)
    pos, neg = rng.normal(0.5, 1, 200), rng.normal(0, 1, 200)
    a = block_bootstrap_auc(pos, neg, n_boot=200, seed=42)
    b = block_bootstrap_auc(pos, neg, n_boot=200, seed=42)
    c = block_bootstrap_auc(pos, neg, n_boot=200, seed=43)
    assert a == b
    assert (a["lo"], a["hi"]) != (c["lo"], c["hi"])
    assert a["lo"] <= a["auc"] <= a["hi"]


def test_block_bootstrap_is_wider_than_iid_for_autocorrelated_series() -> None:
    rng = np.random.default_rng(9)
    slow = np.cumsum(rng.standard_normal(400)) * 0.2  # strongly autocorrelated
    pos, neg = slow + 0.3, np.cumsum(rng.standard_normal(400)) * 0.2
    block = block_bootstrap_auc(pos, neg, block=DEFAULT_BLOCK * 4, n_boot=300, seed=1)
    iid = block_bootstrap_auc(pos, neg, block=1, n_boot=300, seed=1)
    assert (block["hi"] - block["lo"]) > (iid["hi"] - iid["lo"])


def test_default_block_is_at_least_ten_seconds() -> None:
    assert DEFAULT_BLOCK * 1.5 >= 10.0


# ---- windowing -----------------------------------------------------------------------------

def test_windows_with_fewer_than_min_frames_are_dropped() -> None:
    n_short, n_ok = MIN_FRAMES - 1, MIN_FRAMES + 5
    ts = list(range(0, 1500, 1500 // n_short))[:n_short] + [1500 + i * 10 for i in range(n_ok)]
    s = series_from(ts, make_window(0.1, k=len(ts)))
    tab = node_windows(s, t0_ms=0)
    assert tab["k"].tolist() == [1] and tab["nframes"].tolist() == [n_ok]


def test_window_with_exactly_min_frames_is_kept() -> None:
    ts = [i * 20 for i in range(MIN_FRAMES)]
    tab = node_windows(series_from(ts, make_window(0.1, k=MIN_FRAMES)), t0_ms=0)
    assert tab["k"].tolist() == [0]


def test_fuse_max_uses_only_windows_where_every_node_is_present() -> None:
    def tab(ks: list[int], vals: list[float]) -> dict[str, np.ndarray]:
        return {"k": np.array(ks), "decor": np.array(vals)}

    tables = {1: tab([0, 1, 2], [0.1, 0.5, 0.2]), 2: tab([1, 2, 3], [0.3, 0.9, 0.4])}
    k, v = fuse_max(tables, (1, 2), "decor")
    assert k.tolist() == [1, 2] and v.tolist() == [0.5, 0.9]
    k0, v0 = fuse_max(tables, (1, 3), "decor")  # node 3 absent -> nothing, not zero-filled
    assert k0.size == 0 and v0.size == 0
