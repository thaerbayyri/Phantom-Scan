"""Addendum A: per-node link-state step detector, epochs, transitional exclusion, and no pooling of empties across epochs."""
from __future__ import annotations

import numpy as np
import pytest

from scripts.presence_eval import epoch_eval as ee
from scripts.presence_eval import epochs as ep
from scripts.presence_eval.features import COVARIATES, FEATURES
from scripts.presence_eval.tables import RecTables

T0 = 1_793_130_000_000


def series(n: int, level: float = -36.0, fps: float = 66.0) -> tuple[np.ndarray, np.ndarray]:
    return np.full(n, level), np.full(n, fps)


def detect(r: np.ndarray, f: np.ndarray) -> list[ep.Event]:
    return ep.detect_events(r, f, T0, node=1)


# ---- detector -----------------------------------------------------------------------------------------------------

def test_a_held_rssi_step_is_detected_near_its_onset_with_delta_and_hold() -> None:
    r, f = series(300)
    r[195:] = -47.0                                    # the s7 pattern: -36 -> -47 and it stays
    ev = [e for e in detect(r, f) if e.kind == "rssi_step"]
    assert len(ev) == 1
    e = ev[0]
    assert abs((e.t_ms - T0) / 1000 - 195) <= 2 and e.delta_db == pytest.approx(-11.0, abs=0.5)
    assert e.rssi_before == pytest.approx(-36.0) and e.rssi_after == pytest.approx(-47.0) and e.held_s == pytest.approx(105.0, abs=1)


def test_a_one_second_dip_and_a_short_excursion_are_not_steps() -> None:
    r, f = series(300)
    r[203] = -71.0                                     # node 4's one-second dip
    r[120:127] = -43.0                                 # 7 dB for 7 s: shorter than HOLD_S
    assert [e for e in detect(r, f) if e.kind == "rssi_step"] == []


def test_a_steady_link_has_no_events_and_a_step_below_6_db_is_ignored() -> None:
    r, f = series(300)
    assert detect(r, f) == []
    r[150:] = -41.0                                    # 5 dB
    assert detect(r, f) == []


def test_a_step_and_its_reversal_within_30_s_are_both_detected() -> None:
    r, f = series(300)
    r[100:125] = -47.0                                 # down 11 dB for 25 s, then back
    ev = [e for e in detect(r, f) if e.kind == "rssi_step"]
    assert [round(e.delta_db) for e in ev] == [-11, 11]
    assert [e.reversal for e in ev] == [False, True]               # the return to the old level is not a new link state


def test_a_held_excursion_reports_how_long_it_held() -> None:
    r, f = series(300)
    r[100:116] = -43.0                                 # the s5 flicker: 7 dB for 16 s
    ev = [e for e in detect(r, f) if e.kind == "rssi_step"]
    assert 14 <= ev[0].held_s <= 17 and ev[0].reversal is False
    assert [e.reversal for e in ev[1:]] == [True] * (len(ev) - 1)   # the way back is flagged, never a boundary
    empty = links("e", "empty", 0, 300, -36, -36)
    assert not any(ep.is_boundary(empty, e) for e in ev)           # a 16 s flicker (and its return) never splits an empty recording


def test_frame_rate_collapse_is_detected_and_a_low_baseline_is_not() -> None:
    r, f = series(300)
    f[200:215] = 20.0                                  # 66 -> 20 frames/s for 15 s
    ev = [e for e in detect(r, f) if e.kind == "rate_collapse"]
    assert len(ev) == 1 and ev[0].fps_before == pytest.approx(66.0) and ev[0].fps_after <= 25
    r2, f2 = series(300, fps=11.0)                     # pre-fix recording: baseline below MIN_BASELINE_FPS
    f2[200:215] = 2.0
    assert detect(r2, f2) == []


def test_missing_seconds_do_not_crash_and_count_as_zero_frames() -> None:
    r, f = series(200)
    r[80:100] = np.nan
    f[80:100] = 0.0
    assert all(isinstance(e, ep.Event) for e in detect(r, f))


# ---- gaps, persistence, boundaries ----------------------------------------------------------------------------------

def links(rid: str, label: str, start_s: int, dur_s: int, first: float, last: float, day: str = "20261027", fps: float = 66.0) -> ep.RecordingLinks:
    rl = ep.RecordingLinks(rid, day, T0 + start_s * 1000, T0 + (start_s + dur_s) * 1000, label)
    rl.events = {1: []}
    rl.edges = {1: {"first": (first, fps), "last": (last, fps)}}
    return rl


def test_gap_step_day_boundary_and_no_event() -> None:
    a, b = links("a", "empty", 0, 100, -36, -36), links("b", "empty", 400, 100, -47, -47)
    assert [e.kind for e in ep.gap_events(a, b)] == ["gap_step"] and ep.gap_events(a, b)[0].delta_db == pytest.approx(-11.0)
    assert ep.gap_events(a, links("c", "empty", 400, 100, -38, -38)) == []
    assert [e.kind for e in ep.gap_events(a, links("d", "empty", 400, 100, -36, -36, day="20261028"))] == ["day_boundary"]


def test_persistence_requires_the_new_level_to_hold_to_the_end_and_into_the_next_recording() -> None:
    step = ep.Event(1, T0 + 50_000, "rssi_step", -11.0, 66, 44, -36.0, -47.0, held_s=20.0)
    a = links("a", "walking", 0, 70, -36, -47)
    a.events = {1: [step]}
    b = links("b", "empty", 300, 100, -47, -47)
    ep.classify_persistence([a, b])
    assert a.events[1][0].persistent is True and ep.is_boundary(a, a.events[1][0])
    b2 = links("b2", "empty", 300, 100, -36, -36)                  # the next recording is back at the old level
    a2 = links("a", "walking", 0, 70, -36, -47)
    a2.events = {1: [step]}
    ep.classify_persistence([a2, b2])
    assert a2.events[1][0].persistent is False
    last = links("only", "walking", 0, 70, -36, -47)
    last.events = {1: [step]}
    ep.classify_persistence([last])
    assert last.events[1][0].persistent is None                    # no next recording: cannot be confirmed


def test_boundary_rules_depend_on_the_label_and_the_hold_time() -> None:
    short = ep.Event(1, T0, "rssi_step", -7.0, 65, 60, -36.0, -43.0, persistent=False, held_s=16.0)
    long_ = ep.Event(1, T0, "rssi_step", -7.0, 65, 60, -36.0, -43.0, persistent=False, held_s=120.0)
    occupied, empty = links("o", "still", 0, 100, -36, -36), links("e", "empty", 0, 100, -36, -36)
    assert not ep.is_boundary(occupied, long_)                     # may be the person's own body
    assert not ep.is_boundary(empty, short)                        # a 16 s flicker is an excursion
    assert ep.is_boundary(empty, long_)                            # long-held change in an EMPTY recording splits
    assert ep.is_boundary(occupied, ep.Event(1, T0, "rssi_step", -12.0, 63, 44, -35.0, -48.0, persistent=True, held_s=20.0))


def test_timeline_marks_the_transitional_interval_and_names_epochs() -> None:
    a = links("a", "walking", 0, 220, -36, -47)
    a.events = {1: [ep.Event(1, T0 + 195_000, "rssi_step", -11.0, 66, 44, -36.0, -47.0, persistent=True, held_s=20.0)]}
    tl = ep.build_timeline([a], (1,))
    assert tl.epoch_name(T0 + 100_000) == "E01" and tl.epoch_name(T0 + 200_000) == "E02"
    assert tl.is_transitional(T0 + 191_000) and tl.is_transitional(T0 + 224_000)
    assert not tl.is_transitional(T0 + 150_000) and not tl.is_transitional(T0 + 226_000)
    assert ep.build_timeline([a], (2,)).boundaries == []           # events of OTHER nodes do not split this node set


# ---- evaluation: no pooling across epochs -----------------------------------------------------------------------------

def rec(rid: str, label: str, n_windows: int, mu: float, seed: int, start_k: int = 0) -> RecTables:
    rng = np.random.default_rng(seed)
    t = {f: mu + rng.standard_normal(n_windows) for f in FEATURES}
    t.update({c: np.zeros(n_windows) for c in COVARIATES})
    t["k"] = np.arange(start_k, start_k + n_windows, dtype=np.int64)
    t["nframes"] = np.full(n_windows, 90, dtype=np.int64)
    return RecTables(rid=rid, name=f"x__{rid}__{label}__20261027T000000Z.jsonl", label=label, subject=rid, day="20261027", t0_ms=T0,
                     duration_s=n_windows * 1.5, parts=1, nodes={1: dict(t), 2: {k: v.copy() for k, v in t.items()}})


def two_epoch_timeline(boundary_s: float) -> ep.Timeline:
    return ep.Timeline((1, 2), [(T0 + int(boundary_s * 1000), "test boundary")], [])


def test_segments_split_at_the_boundary_and_never_mix_epochs() -> None:
    tabs = {"e1": rec("e1", "empty", 400, 0.0, 1)}                  # 600 s; boundary at 300 s
    segs, log = ee.make_segments(tabs, two_epoch_timeline(300))
    assert sorted(segs) == ["e1@E01", "e1@E02"]
    assert {s["epoch"] for s in log} == {"E01", "E02"}
    k1, k2 = segs["e1@E01"].nodes[1]["k"], segs["e1@E02"].nodes[1]["k"]
    assert k1.max() < k2.min() and len(k1) + len(k2) == 400


def test_transitional_windows_are_removed_from_the_evaluation_and_logged() -> None:
    tabs = {"w": rec("w", "walking", 300, 0.0, 2)}                  # 450 s
    tl = ep.Timeline((1, 2), [(T0 + 200_000, "step")], [(T0 + 195_000, T0 + 230_000, "step")])
    segs, log = ee.make_segments(tabs, tl)
    kept = np.concatenate([s.nodes[1]["k"] for s in segs.values()])
    centre = T0 + ((kept + 0.5) * 1500).astype(np.int64)
    assert not ((centre >= T0 + 195_000) & (centre < T0 + 230_000)).any()
    assert sum(s["transitional_dropped"] for s in log) == 300 - len(kept)


def test_within_epoch_models_train_only_on_empties_of_the_same_epoch_and_cross_uses_one_source_epoch() -> None:
    tabs = {"eA1": rec("eA1", "empty", 100, 0, 1), "eA2": rec("eA2", "empty", 100, 0, 2, start_k=100),      # epoch E01
            "eB": rec("eB", "empty", 100, 5, 3, start_k=300), "wB": rec("wB", "walking", 100, 9, 4, start_k=400)}  # epoch E02
    segs, _ = ee.make_segments(tabs, two_epoch_timeline(300))      # k >= 200 -> after 300 s
    for sp in ee.splits_within(segs):
        e = ee.epoch_of(segs[sp.test_id])
        assert sp.test_id not in sp.train_ids
        assert all(ee.epoch_of(segs[t]) == e and segs[t].label == "empty" for t in sp.train_ids)
    for sp in ee.splits_cross(segs):
        a, b = sp.group.split("->")
        assert all(ee.epoch_of(segs[t]) == a for t in sp.train_ids) and ee.epoch_of(segs[sp.test_id]) == b and a != b


def test_an_epoch_with_a_single_empty_has_no_held_out_empty_so_the_cell_says_insufficient_data() -> None:
    tabs = {"e": rec("e", "empty", 150, 0, 1), "w": rec("w", "walking", 150, 8, 2, start_k=150)}
    segs, _ = ee.make_segments(tabs, ep.Timeline((1, 2), [], []))   # a single epoch
    rows = [r for sp in [ee.splits_within(segs)] for r in ee.tn.run_candidate(segs, sp, "decor", "max")]
    cell = ee.tn.aggregate(rows)["epoch_within/E01"]
    assert cell["auc"]["walking"] == "insufficient data" and cell["n_empty_windows"] == 0
    assert cell["empty_vs_empty_control"]["passes"] is None
    assert cell["tpr"]["walking@1%"]["rate"] > 0.9                   # positives are still scored against the epoch's empty


def test_low_coverage_recordings_are_excluded_not_evaluated_on_chance_bursts() -> None:
    sparse = rec("old", "walking", 40, 0.0, 5)
    sparse.duration_s = 400.0                                       # 40 windows on a 267-window grid
    res = ee.run(nodes=(1, 2), tabs={"old": sparse, "e": rec("e", "empty", 200, 0, 1)}, links=[])
    assert "old" in res["excluded_low_coverage"] and all("old" not in s["segment"] for s in res["segments"])
    assert "UNCONFIRMED" in res["cause_of_link_changes"]


# ---- PS-FIX-32: post-hoc rule labelling and the ambiguity list ---------------------------------------------------------------

from scripts.presence_eval import epoch_sensitivity as es  # noqa: E402


def test_every_non_boundary_event_gets_a_specific_reason_and_boundaries_get_none() -> None:
    occ, emp = links("o", "still", 0, 300, -36, -36), links("e", "empty", 0, 300, -36, -36)
    persistent = ep.Event(1, T0, "rssi_step", -12.0, 63, 44, -35.0, -48.0, persistent=True, held_s=20.0)
    local = ep.Event(1, T0, "rssi_step", -7.0, 65, 60, -36.0, -43.0, persistent=False, held_s=19.0)
    unknown = ep.Event(1, T0, "rate_collapse", None, 57, 38, -33.0, -45.0, persistent=None)
    flicker = ep.Event(1, T0, "rssi_step", -7.0, 65, 60, -36.0, -43.0, persistent=False, held_s=16.0)
    back = ep.Event(1, T0, "rssi_step", 7.0, 60, 65, -43.0, -36.0, persistent=False, held_s=100.0, reversal=True)
    assert es.ambiguity_reason(occ, persistent) is None
    assert "own body" in es.ambiguity_reason(occ, local)
    assert "cannot be confirmed" in es.ambiguity_reason(occ, unknown)
    assert "excursion" in es.ambiguity_reason(emp, flicker)
    assert "reversal" in es.ambiguity_reason(emp, back)


def test_the_boundary_rule_is_labelled_post_hoc_in_code_and_results() -> None:
    assert "POST HOC" in ep.__doc__ and "4/6/8 dB" in ep.__doc__
    res = {"rule_status": "POST HOC (chosen after inspecting these recordings; not pre-registered)", "grid": {"min_empty_boundary_hold_s_fixed": 60.0}, "configs": {}}
    assert "post-hoc" in es.render(res).lower()
    assert es.STEPS_DB == (4.0, 6.0, 8.0) and es.HOLDS_S == (10, 30, 60)


def test_a_step_detected_with_a_short_hold_is_not_seen_by_a_hold_longer_than_the_recording_tail() -> None:
    r, f = series(213)
    r[193:] = -48.0                                    # the s7 case: only ~19 s of the new level remain before the recording ends
    assert [e for e in ep.detect_events(r, f, T0, 1, hold=10) if e.kind == "rssi_step"]
    assert [e for e in ep.detect_events(r, f, T0, 1, hold=30) if e.kind == "rssi_step"] == []
