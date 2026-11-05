"""PS-FIX-04: harness controls -- session-blocked AUC, empty-vs-empty control (C4), occupied-sensitivity control,
abstentions counted as misses, null for undefined metrics."""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.presence_eval import twonode
from scripts.presence_eval.features import COVARIATES, FEATURES
from scripts.presence_eval.jsonutil import clean, dumps
from scripts.presence_eval.stats import block_bootstrap_auc, empty_pair_control, session_block_auc
from scripts.presence_eval.tables import RecTables
from scripts.presence_eval.twonode import aggregate, criteria, run_candidate, sensitivity_control, splits_loro, splits_cross_session

DAY = "20261027"


def table(n: int, mu: float, seed: int, drop: set[int] | None = None) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = {f: mu + rng.standard_normal(n) for f in FEATURES}
    t.update({c: np.zeros(n) for c in COVARIATES})
    t["k"] = np.arange(n, dtype=np.int64)
    t["nframes"] = np.full(n, 90, dtype=np.int64)
    if drop:
        keep = np.array([i not in drop for i in range(n)])
        t = {c: v[keep] for c, v in t.items()}
    return t


def rec(subject: str, label: str, mu1: float, mu2: float, seed: int, day: str = DAY, n: int = 300, t0: int = 0, drop: set[int] | None = None) -> RecTables:
    return RecTables(rid=f"{subject}_{label}_{day[4:]}_{t0:04d}", name=f"x__{subject}__{label}__{day}T000000Z.jsonl", label=label, subject=subject,
                     day=day, t0_ms=t0, duration_s=n * 1.5, parts=1, nodes={1: table(n, mu1, seed + 1, drop), 2: table(n, mu2, seed + 2, drop)})


def world(shift_e4: float = 0.0) -> dict[str, RecTables]:
    recs = [rec("e1", "empty", 0, 0, 10, "20261018", t0=1), rec("e2", "empty", 0, 0, 20, "20261018", t0=2),
            rec("e3", "empty", 0, 0, 30, t0=3), rec("e4", "empty", shift_e4, shift_e4, 40, t0=4),
            rec("w1", "walking", 10, 10, 50, t0=5), rec("w2", "walking", 10, 10, 55, t0=6)]
    return {r.rid: r for r in recs}


# ---- session-blocked AUC ---------------------------------------------------------------------------------------

def test_session_block_auc_needs_two_recordings_per_class_else_null_with_reason() -> None:
    rng = np.random.default_rng(1)
    one = session_block_auc({"w": rng.normal(1, 1, 200)}, {"a": rng.normal(0, 1, 200), "b": rng.normal(0, 1, 200)}, n_boot=50)
    assert one["lo"] is None and one["hi"] is None and "insufficient" in one["reason"] and one["auc"] is not None
    two = session_block_auc({"w1": rng.normal(1, 1, 200), "w2": rng.normal(1, 1, 200)}, {"a": rng.normal(0, 1, 200), "b": rng.normal(0, 1, 200)}, n_boot=50)
    assert two["lo"] is not None and two["lo"] <= two["auc"] <= two["hi"]


def test_session_block_auc_is_deterministic_and_wider_when_recordings_differ_in_level() -> None:
    rng = np.random.default_rng(2)
    pos = {f"w{i}": rng.normal(0.5 + 0.8 * (i % 2), 1, 200) for i in range(4)}       # recordings differ in level
    neg = {f"e{i}": rng.normal(0.9 * (i % 2), 1, 200) for i in range(4)}
    a = session_block_auc(pos, neg, n_boot=200, seed=3)
    assert a == session_block_auc(pos, neg, n_boot=200, seed=3)
    windows = block_bootstrap_auc(np.concatenate(list(pos.values())), np.concatenate(list(neg.values())), n_boot=200, seed=3)
    assert (a["hi"] - a["lo"]) > (windows["hi"] - windows["lo"])


# ---- empty-vs-empty control ---------------------------------------------------------------------------------------

def test_empty_pair_control_passes_for_matched_empties_and_fails_for_a_baseline_shift() -> None:
    rng = np.random.default_rng(4)
    same = {f"e{i}": rng.normal(0, 1, 300) for i in range(3)}
    assert empty_pair_control(same, n_boot=100)["passes"] is True
    drift = {**same, "e_shifted": rng.normal(1.0, 1, 300)}
    res = empty_pair_control(drift, n_boot=100)
    assert res["passes"] is False and res["worst_symmetric_upper_bound"] > 0.65
    assert any(not p["ok"] and "e_shifted" in (p["a"] + p["b"]) for p in res["pairs"])


def test_empty_pair_control_is_null_with_fewer_than_two_usable_empties() -> None:
    assert empty_pair_control({"only": np.zeros(300)})["passes"] is None
    assert empty_pair_control({"a": np.zeros(300), "short": np.zeros(10)})["passes"] is None


def test_c4_is_reported_and_fails_when_an_empty_recording_drifts() -> None:
    def c4(shift: float) -> bool:
        w = world(shift)
        rows = [r for sp in (splits_loro(w), splits_cross_session(w)) for r in run_candidate(w, sp, "decor", "max")]
        return criteria(aggregate(rows))["C4"]

    assert c4(0.0) is True
    assert c4(3.0) is False


# ---- occupied-sensitivity control ----------------------------------------------------------------------------------

def test_a_model_that_never_fires_is_rejected_by_the_harness() -> None:
    res = sensitivity_control(world())
    assert res["evaluable"] is True and res["rejected_by_C1"] is True
    assert res["constant_scorer_auc"]["auc"] == pytest.approx(0.5) and res["never_fires_tpr"]["rate"] == 0.0


def test_sensitivity_control_reports_insufficient_data_instead_of_a_number() -> None:
    assert sensitivity_control({"e": rec("e1", "empty", 0, 0, 1)})["evaluable"] is False


# ---- abstentions count as misses ------------------------------------------------------------------------------------

def test_abstentions_on_a_positive_recording_are_misses_not_ignored() -> None:
    w = world()
    drop = set(range(0, 300, 2))                                         # half of the walking windows have no joint score
    gappy = rec("w3", "walking", 10, 10, 60, t0=7, drop=drop)
    w[gappy.rid] = gappy
    cell = aggregate([r for r in run_candidate(w, splits_loro(w), "decor", "max") if r["test"] == gappy.rid])["loro/pooled"]
    assert cell["abstention_share"]["walking"] == pytest.approx(0.5, abs=0.02)
    scored = cell["tpr"]["walking@5%"]["rate"]
    with_misses = cell["tpr_abstain_as_miss"]["walking@5%"]["rate"]
    assert scored > 0.9 and with_misses == pytest.approx(scored * 0.5, abs=0.03)


# ---- null, never NaN -----------------------------------------------------------------------------------------------

def test_undefined_metrics_serialise_as_null_not_nan() -> None:
    obj = {"a": float("nan"), "b": np.float64("inf"), "c": [np.float32("nan"), 1.5], "d": np.int64(3), "e": np.bool_(True), "f": np.array([1.0, np.nan])}
    text = dumps(obj)
    assert "NaN" not in text and "Infinity" not in text
    back = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    assert back == {"a": None, "b": None, "c": [None, 1.5], "d": 3, "e": True, "f": [1.0, None]}
    assert clean(float("-inf")) is None


def test_block_bootstrap_of_an_empty_class_serialises_with_nulls() -> None:
    res = block_bootstrap_auc(np.zeros(0), np.ones(5))
    assert json.loads(dumps(res))["auc"] is None


def test_twonode_result_json_is_strictly_valid_json() -> None:
    old = (twonode.N_BOOT, twonode.FEATS, twonode.RULES)
    try:
        twonode.N_BOOT, twonode.FEATS, twonode.RULES = 20, ("decor",), ("max",)
        text = dumps(twonode.run(world()))
    finally:
        twonode.N_BOOT, twonode.FEATS, twonode.RULES = old
    json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
