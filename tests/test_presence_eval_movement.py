"""Addendum B: the movement score is causal, baseline-free, fades under sustained motion, is zero for a motionless person,
never spans an epoch boundary, and is labelled as NOT presence."""
from __future__ import annotations

import numpy as np
import pytest

from scripts.presence_eval import epoch_eval as ee
from scripts.presence_eval import epochs as ep
from scripts.presence_eval import movement as mv
from scripts.presence_eval.features import COVARIATES, FEATURES
from scripts.presence_eval.tables import RecTables

T0 = 1_793_130_000_000
L45 = 45
SPAN45 = 30  # windows of 1.5 s in 45 s


def ks(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.int64)


# ---- causality and baseline ---------------------------------------------------------------------------------------

def test_the_score_is_causal_future_values_never_change_past_scores() -> None:
    rng = np.random.default_rng(1)
    x = rng.standard_normal(200)
    k = ks(200)
    full = mv.causal_score(k, x, L45)
    changed = x.copy()
    changed[120:] += 50.0                                   # rewrite the future
    after = mv.causal_score(k, changed, L45)
    assert np.array_equal(full[:120], after[:120], equal_nan=True)
    assert not np.array_equal(full[120:], after[120:], equal_nan=True)


def test_score_is_the_window_minus_the_25th_percentile_of_the_previous_L_seconds() -> None:
    x = np.arange(100, dtype=float)
    k = ks(100)
    s = mv.causal_score(k, x, L45)
    i = 60
    prev = x[i - SPAN45:i]
    assert s[i] == pytest.approx(x[i] - np.percentile(prev, 25))


def test_warmup_has_no_score_and_gaps_below_the_required_history_give_none() -> None:
    x = np.zeros(100)
    s = mv.causal_score(ks(100), x, L45)
    assert np.isnan(s[:int(np.ceil(0.8 * SPAN45))]).all() and np.isfinite(s[SPAN45 + 5])
    k = np.concatenate([ks(40), ks(40) + 200])               # a long gap: the history before the gap is too old
    g = mv.causal_score(k, np.zeros(80), L45)
    assert np.isfinite(g[39]) and np.isnan(g[40])


# ---- what it can and cannot say -------------------------------------------------------------------------------------

def test_a_motionless_person_reads_zero_once_the_baseline_has_settled() -> None:
    x = np.full(200, 5.0)                                    # elevated from the start and constant: nothing is CHANGING
    s = mv.causal_score(ks(200), x, L45)
    assert np.allclose(s[SPAN45:], 0.0)


def test_sustained_motion_fades_as_the_baseline_catches_up() -> None:
    x = np.concatenate([np.zeros(100), np.full(200, 5.0)])  # onset of motion at window 100 that then simply continues
    s = mv.causal_score(ks(300), x, L45)
    assert s[100] == pytest.approx(5.0) and s[105] == pytest.approx(5.0)   # the change is visible at first
    assert s[100 + SPAN45 + 5] == pytest.approx(0.0)                       # ... and is gone after ~L seconds
    assert np.allclose(s[100 + SPAN45:], 0.0)


def test_a_new_burst_after_quiet_is_visible_again() -> None:
    x = np.zeros(300)
    x[200:210] = 4.0
    s = mv.causal_score(ks(300), x, L45)
    assert s[205] == pytest.approx(4.0) and s[250] == pytest.approx(0.0)


# ---- fusion --------------------------------------------------------------------------------------------------------

def seg(rid: str, label: str, n: int, series: dict[int, np.ndarray], start_k: int = 0) -> RecTables:
    nodes = {}
    for node, x in series.items():
        t = {f: x.copy() for f in FEATURES}
        t.update({c: np.zeros(n) for c in COVARIATES})
        t["k"] = np.arange(start_k, start_k + n, dtype=np.int64)
        t["nframes"] = np.full(n, 90, dtype=np.int64)
        nodes[node] = t
    return RecTables(rid=rid, name=f"x__{rid}__{label}__20261027T000000Z.jsonl", label=label, subject=rid, day="20261027", t0_ms=T0,
                     duration_s=n * 1.5, parts=1, nodes=nodes)


def test_fusion_is_the_max_over_the_chosen_nodes_on_windows_where_all_have_a_score() -> None:
    n = 120
    a, b = np.zeros(n), np.zeros(n)
    a[80] = 1.0
    b[80] = 3.0
    b[90] = 2.0
    s = seg("s", "walking", n, {1: a, 2: b})
    k, v = mv.fused_scores(s, "decor", L45, (1, 2))
    assert v[list(k).index(80)] == pytest.approx(3.0) and v[list(k).index(90)] == pytest.approx(2.0)
    only1 = mv.fused_scores(s, "decor", L45, (1,))[1]
    assert only1[list(k).index(80)] == pytest.approx(1.0)
    assert mv.fused_scores(s, "decor", L45, (1, 2, 3))[1].size == 0     # node 3 absent -> nothing, not zero-filled


def test_the_baseline_never_spans_an_epoch_boundary() -> None:
    n = 200
    x = np.concatenate([np.zeros(100), np.full(100, 9.0)])          # the link-state level changes at window 100
    s = seg("r", "empty", n, {1: x, 2: x})
    tl = ep.Timeline((1, 2), [(T0 + int(100 * 1500), "boundary")], [])
    segs, _ = ee.make_segments({"r": s}, tl)
    after = segs["r@E02"]
    k, v = mv.fused_scores(after, "decor", L45, (1, 2))
    assert k.min() >= 100 + int(np.ceil(0.8 * SPAN45))               # warm-up restarts at the boundary
    assert np.allclose(v, 0.0)                                       # the +9 level change is NOT reported as movement


# ---- evaluation and labelling -----------------------------------------------------------------------------------------

def test_a_class_with_too_few_windows_or_recordings_is_insufficient_not_a_number() -> None:
    rng = np.random.default_rng(3)
    sc = {"w": ("walking", rng.normal(1, 1, 200)), "e1": ("empty", rng.normal(0, 1, 200)), "e2": ("empty", rng.normal(0, 1, 200))}
    cell = mv.evaluate_group(sc)
    assert cell["auc"]["walking"]["auc"] > 0.6
    assert cell["auc_session_blocked"]["walking"]["lo"] is None                 # one walking recording: no session-blocked CI
    assert "insufficient" in cell["auc_session_blocked"]["walking"]["reason"]
    assert cell["auc"]["still"] == "insufficient data" and cell["auc"]["empty_fan"] == "insufficient data"
    assert cell["empty_vs_empty_control"]["passes"] is True
    shifted = {**sc, "e3": ("empty", rng.normal(1.5, 1, 200))}
    assert mv.evaluate_group(shifted)["empty_vs_empty_control"]["passes"] is False


def test_the_result_is_labelled_a_movement_score_and_never_presence() -> None:
    rng = np.random.default_rng(4)
    res = {"caveat": mv.CAVEAT, "variants": {"v": {"within_epoch": {"E01": mv.evaluate_group({"e1": ("empty", rng.normal(0, 1, 100)), "e2": ("empty", rng.normal(0, 1, 100))})},
                                                   "across_epochs": mv.evaluate_group({}), "median_score_by_third": {}}}}
    text = mv.render(res)
    assert "NOT presence" in mv.CAVEAT and "empty" in mv.CAVEAT and "not a presence detector" in text.lower()
    assert mv.POSITIVE == ("walking", "still", "two_people")


def test_median_by_third_shows_a_fade() -> None:
    fading = np.concatenate([np.full(40, 3.0), np.full(40, 1.0), np.full(40, 0.1)])
    assert mv.median_by_third(fading) == [3.0, 1.0, 0.1] and mv.median_by_third(np.ones(30)) is None


# ---- reproduction of the externally reported pooled protocol -------------------------------------------------------------

def test_truncate_keeps_only_windows_up_to_the_last_index() -> None:
    s = seg("r", "empty", 100, {1: np.arange(100.0), 2: np.arange(100.0)})
    t = mv.truncate(s, 40)
    assert t.nodes[1]["k"].max() == 40 and len(t.nodes[1]["decor"]) == 41 and mv.truncate(s, None) is s


def test_pooled_reproduction_runs_with_a_custom_mapping_and_reports_every_cell() -> None:
    rng = np.random.default_rng(11)

    def make(rid: str, label: str, level: float, n: int = 260) -> RecTables:
        return seg(rid, label, n, {k: level + rng.standard_normal(n) * 0.1 for k in (1, 2, 3, 4)})

    tabs = {r: make(r, l, lv) for r, l, lv in [("s6_empty_1027_1942", "empty", 0.0), ("s8_empty_1027_1953", "empty", 0.0), ("s9_empty_1027_2047", "empty", 0.0),
                                                ("s7_walking_1027_1945", "walking", 0.0), ("s10_still_1027_2121", "still", 0.0), ("s1_still_1027_1936", "still", 0.0),
                                                ("s5_empty_fan_1027_1938", "empty_fan", 0.0)]}
    res = mv.pooled_reproduction(tabs, n_boot=20)
    assert len(res["configs"]) == 6
    for cell in res["configs"].values():
        for key in ("walking", "walking_head_only_no_tail", "fan", "drift_control_s8p1_vs_s6", "still:s10_still_1027_2121", "still:s1_still_1027_1936"):
            assert key in cell and cell[key]["auc"] is not None
    assert "drift control" in mv.render_pooled(res) and "NOT a detection claim" in mv.render_pooled(res)
