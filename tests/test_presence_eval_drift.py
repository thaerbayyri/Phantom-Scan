"""T3: the drift evaluator must REPORT a baseline shift between two 'empty' recordings, not hide it."""
from __future__ import annotations

import numpy as np

from scripts.presence_eval.drift import (
    MIN_SEG_WINDOWS, WIN_PER_SEG, cross_node_correlation, make_segments, pair_table, run, summarize_pairs,
)
from scripts.presence_eval.features import COVARIATES, FEATURES
from scripts.presence_eval.tables import RecTables

DAY = "20261027"


def node_table(n: int, level: float, seed: int, k0: int = 0, noise: float = 0.02) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = {f: level + noise * rng.standard_normal(n) for f in FEATURES}
    t.update({c: -40 + rng.standard_normal(n) * 0.1 for c in COVARIATES})
    t["k"] = np.arange(k0, k0 + n, dtype=np.int64)
    t["nframes"] = np.full(n, 90, dtype=np.int64)
    return t


def rec(subject: str, label: str, levels: dict[int, float], n: int = 2 * WIN_PER_SEG, seed: int = 0) -> RecTables:
    nodes = {node: node_table(n, lvl, seed + node) for node, lvl in levels.items()}
    return RecTables(rid=f"{subject}_{label}_1027_1900", name=f"room1__{subject}__{label}__{DAY}T190000Z.jsonl", label=label,
                     subject=subject, day=DAY, t0_ms=0, duration_s=n * 1.5, parts=1, nodes=nodes)


def world(s8_shift: float) -> dict[str, RecTables]:
    flat = {1: 0.10, 2: 0.10, 3: 0.10, 4: 0.10}
    shifted = {n: v + s8_shift for n, v in flat.items()}
    recs = [rec("s6", "empty", flat, seed=1), rec("s7", "walking", {n: v + 0.05 for n, v in flat.items()}, seed=2),
            rec("s5", "empty_fan", flat, seed=3), rec("s8", "empty", shifted, seed=4), rec("s9", "empty", flat, seed=5)]
    return {r.rid: r for r in recs}


def test_baseline_shift_between_empties_is_reported_as_drift() -> None:
    res = run(world(s8_shift=0.5))
    cell = res["per_node_feature"]["N1/decor"]
    assert cell["empty_vs_empty"]["drift_flag"] is True
    assert cell["empty_vs_empty"]["share_separable"] >= 0.25
    worst = cell["worst_pairs"][0]
    assert abs(worst["auc"] - 0.5) > 0.45 and "s8" in (worst["a"] + worst["b"])
    # the drift is larger than the (small) walking effect, and the report says so numerically
    assert cell["shift_ratio_27oct"]["ratio"] > 1.0


def test_no_shift_means_no_drift_flag() -> None:
    res = run(world(s8_shift=0.0))
    for key, cell in res["per_node_feature"].items():
        assert cell["empty_vs_empty"]["drift_flag"] is False, key


def test_pair_table_marks_shifted_pair_separable_and_matched_pair_not() -> None:
    a = make_segments(rec("a", "empty", {1: 0.1}, seed=1))[0]
    b = make_segments(rec("b", "empty", {1: 0.1}, seed=2))[0]
    c = make_segments(rec("c", "empty", {1: 0.6}, seed=3))[0]
    pairs = {(p["a"][0], p["b"][0]): p["auc"] for p in pair_table([a, b, c], 1, "decor")}
    assert 0.3 < pairs[("a", "b")] < 0.7
    assert pairs[("a", "c")] == 0.0 and pairs[("b", "c")] == 0.0
    assert summarize_pairs(pair_table([a, b, c], 1, "decor"))["drift_flag"] is True


def test_segment_with_too_few_windows_is_absent_not_zero_filled() -> None:
    r = rec("a", "empty", {1: 0.1, 2: 0.1}, n=WIN_PER_SEG + MIN_SEG_WINDOWS - 1)  # tail segment has MIN-1 windows
    r.nodes[2] = node_table(WIN_PER_SEG, 0.1, 9)                                     # node 2 has only the first segment
    segs = make_segments(r)
    assert len(segs) == 1 and set(segs[0].data) == {1, 2}


def test_cross_node_correlation_separates_common_events_from_independent_drift() -> None:
    n = 800
    rng = np.random.default_rng(3)
    common = np.convolve(rng.standard_normal(n), np.ones(5) / 5, mode="same")
    shared = {f: 0.1 + 0.05 * common + 0.005 * rng.standard_normal(n) for f in FEATURES}
    shared.update({c: np.zeros(n) for c in COVARIATES}); shared["k"] = np.arange(n); shared["nframes"] = np.full(n, 90)
    other = {f: 0.1 + 0.05 * common + 0.005 * rng.standard_normal(n) for f in FEATURES}
    other.update({c: np.zeros(n) for c in COVARIATES}); other["k"] = np.arange(n); other["nframes"] = np.full(n, 90)
    indep = {f: 0.1 + 0.05 * rng.standard_normal(n) for f in FEATURES}
    indep.update({c: np.zeros(n) for c in COVARIATES}); indep["k"] = np.arange(n); indep["nframes"] = np.full(n, 90)
    r = RecTables("x", "x", "empty", "s", DAY, 0, 1200.0, 1, {1: shared, 2: other, 3: indep})
    cc = cross_node_correlation(r, "decor")
    assert cc["N1-N2"] > 0.5 and abs(cc["N1-N3"]) < 0.2
