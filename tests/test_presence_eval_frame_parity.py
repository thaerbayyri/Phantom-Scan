"""PS-FIX-37: frame_parity on synthetic streams with KNOWN structure (no recordings are read)."""
from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

from scripts.presence_eval import frame_parity as fp
from scripts.presence_eval.recordings import NodeSeries, ParseStats, Recording

N_SUB = 51
RNG_SEED = 20261104


def _rng() -> np.random.Generator:
    return np.random.default_rng(RNG_SEED)


def interleaved(n: int = 4000, depth: float = 0.8, noise: float = 0.02) -> np.ndarray:
    """Two frame 'types' alternate: each adds a fixed +/- signature to the same static channel."""
    rng = _rng()
    sig = rng.normal(0, 1, N_SUB)
    sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)[:, None]
    return 10.0 + depth * sign * sig[None, :] + rng.normal(0, noise, (n, N_SUB))


def smooth(n: int = 4000, phi: float = 0.97, step: float = 0.1) -> np.ndarray:
    """Per-subcarrier AR(1): a smooth process, correlation decays monotonically with lag."""
    rng = _rng()
    x = np.zeros((n, N_SUB))
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal(0, step, N_SUB)
    return 10.0 + x


def white(n: int = 4000) -> np.ndarray:
    return 10.0 + _rng().normal(0, 0.5, (n, N_SUB))


def series(a: np.ndarray, gap_ms: int = 15, rssi: np.ndarray | None = None) -> NodeSeries:
    n = len(a)
    return NodeSeries(t=(np.arange(n) * gap_ms).astype(np.int64),
                      rssi=np.full(n, -45.0, dtype=np.float32) if rssi is None else rssi.astype(np.float32),
                      a=a.astype(np.float32))


# ---- lag correlation ------------------------------------------------------------------------


def test_interleaved_stream_shows_a_zigzag() -> None:
    c = fp.lag_correlations(interleaved())
    assert c[2] > c[1] + 0.5 and c[2] > c[3] + 0.5, c
    assert c[1] < 0 < c[2]  # adjacent frames are opposite types, frames two apart are the same type
    assert fp._zigzag(c) is True


def test_smooth_stream_decays_monotonically_and_is_not_a_zigzag() -> None:
    c = fp.lag_correlations(smooth())
    assert c[1] > c[2] > c[3] > c[4], c
    assert fp._zigzag(c) is False


def test_white_noise_has_no_lag_structure() -> None:
    c = fp.lag_correlations(white())
    assert all(abs(v) < 0.05 for v in c.values()), c
    assert fp._zigzag(c) is False


def test_highpass_variant_keeps_the_zigzag_and_does_not_invent_one() -> None:
    assert fp._zigzag(fp.lag_correlations(interleaved(), highpass=True)) is True
    assert fp._zigzag(fp.lag_correlations(smooth(), highpass=True)) is False


def test_too_few_frames_gives_nan_not_a_number() -> None:
    c = fp.lag_correlations(white(fp.MIN_FRAMES_FOR_LAGS - 1))
    assert all(math.isnan(v) for v in c.values())
    assert fp._zigzag(c) is None


def test_constant_frames_do_not_crash_or_produce_numbers() -> None:
    c = fp.lag_correlations(np.full((500, N_SUB), 10.0))
    assert all(math.isnan(v) for v in c.values())


# ---- RSSI steps and gap histogram -----------------------------------------------------------


def test_rssi_lag_diffs_alternating_values() -> None:
    r = np.where(np.arange(100) % 2 == 0, -40.0, -50.0)
    d = fp.rssi_lag_diffs(r)
    assert d[1] == pytest.approx(10.0) and d[2] == pytest.approx(0.0) and d[3] == pytest.approx(10.0)


def test_rssi_lag_diffs_ignore_nan() -> None:
    d = fp.rssi_lag_diffs(np.array([-40.0, np.nan, -42.0, -41.0, -43.0]))
    assert d[1] == pytest.approx(np.mean([1.0, 2.0]))
    assert math.isnan(fp.rssi_lag_diffs(np.full(5, np.nan))[1])  # NaN, not 0


def test_gap_histogram_known_gaps_and_shares_sum_to_one() -> None:
    gaps = [3, 7, 12, 17, 25, 35, 50, 90]  # one gap per bin
    h = fp.gap_histogram(np.cumsum([0, *gaps]))
    assert h["n"] == 8
    for key in ("0-5ms", "5-10ms", "10-15ms", "15-20ms", "20-30ms", "30-40ms", "40-60ms", "60-infms"):
        assert h["share"][key] == pytest.approx(1 / 8), key
    assert sum(h["share"].values()) == pytest.approx(1.0)


def test_gap_histogram_single_timestamp() -> None:
    assert fp.gap_histogram(np.array([5]))["n"] == 0


# ---- parity substreams and decor ------------------------------------------------------------


def test_parity_substreams_partition_the_frames() -> None:
    s = series(white(101))
    e, o = fp.parity_substream(s, 0), fp.parity_substream(s, 1)
    assert len(e.t) + len(o.t) == len(s.t)
    assert np.array_equal(e.t, s.t[0::2]) and np.array_equal(o.t, s.t[1::2])


def test_parity_decor_drops_for_an_interleaved_stream() -> None:
    d = fp.parity_decor(series(interleaved(6000)))
    assert d["all"]["median"] > 1.5          # adjacent frames are opposite types: nearly anti-correlated
    assert d["ratio_parity_over_all"] < 0.3, d


def test_parity_decor_does_not_drop_for_a_smooth_stream() -> None:
    d = fp.parity_decor(series(smooth(6000)))
    assert d["ratio_parity_over_all"] > 1.0, d  # a lag-2 pair is LESS similar than a lag-1 pair in a smooth process


def test_node_report_flags_the_interleaved_stream_and_not_the_smooth_one() -> None:
    assert fp.node_report(series(interleaved(3000)))["zigzag"] is True
    assert fp.node_report(series(smooth(3000)))["zigzag"] is False
    assert fp.node_report(series(white(3000)))["zigzag"] is False


# ---- empty-vs-empty AUC with parity ----------------------------------------------------------


def _rec(subject: str, a: np.ndarray) -> Recording:
    return Recording(name=f"room1__{subject}__empty__x.jsonl", label="empty", subject=subject, paths=[], headers=[],
                     nodes={1: series(a)}, stats=ParseStats())


def test_empty_pair_auc_separates_a_real_level_change_in_all_and_parity_columns() -> None:
    rng = _rng()
    quiet = 10.0 + rng.normal(0, 0.05, (6000, N_SUB))
    noisy = 10.0 + rng.normal(0, 1.5, (6000, N_SUB))
    row = fp.empty_pair_aucs({"a": _rec("s8", noisy), "b": _rec("s6", quiet)})["s8_vs_s6/N1/perturb"]
    assert row["all"] > 0.95 and row["even"] > 0.95 and row["odd"] > 0.95, row


def test_empty_pair_auc_is_near_half_for_identical_statistics() -> None:
    rng = _rng()
    a = 10.0 + rng.normal(0, 0.5, (6000, N_SUB))
    b = 10.0 + rng.normal(0, 0.5, (6000, N_SUB))
    row = fp.empty_pair_aucs({"a": _rec("s8", a), "b": _rec("s6", b)})["s8_vs_s6/N1/decor"]
    assert all(0.3 < row[k] < 0.7 for k in ("all", "even", "odd")), row


def test_empty_pair_auc_skips_pairs_whose_sessions_are_absent() -> None:
    assert fp.empty_pair_aucs({"a": _rec("s8", white(3000))}) == {}


# ---- read-only guarantee ---------------------------------------------------------------------


def test_module_only_writes_from_main_under_the_out_dir() -> None:
    src = inspect.getsource(fp)
    assert src.count(".write_text(") == 1 and src.count("dump_json(") == 1
    main_src = inspect.getsource(fp.main)
    assert ".write_text(" in main_src and "dump_json(" in main_src and "OUT_DIR" in main_src
    for banned in ("write_bytes(", "open(", "shutil", "os.remove", "unlink("):
        assert banned not in src, banned


# ---- preprocessing modes, parity AUC summary, conclusion (added with the Item B finish) ---------


def test_raw_and_shape_modes_are_high_for_any_stream_so_only_demeaned_modes_can_show_alternation() -> None:
    a = interleaved()
    raw = fp.lag_correlations(a, mode="raw")
    td = fp.lag_correlations(a, mode="timedemean")
    assert all(v > 0.98 for v in raw.values()), raw  # the static channel dominates every lag
    raw_gap, td_gap = raw[2] - raw[1], td[2] - td[1]
    assert 0 < raw_gap < 0.02, raw                    # the zigzag is present but squeezed into the 2nd decimal
    assert td_gap > 50 * raw_gap, (raw_gap, td_gap)   # removing the static channel makes it ~100x larger


def test_mode_defaults_and_validation() -> None:
    a = smooth(600)
    assert fp.lag_correlations(a) == fp.lag_correlations(a, mode="timedemean")
    assert fp.lag_correlations(a, highpass=True) == fp.lag_correlations(a, mode="highpass")
    with pytest.raises(ValueError):
        fp.lag_correlations(a, mode="nope")


def test_every_mode_has_a_description() -> None:
    assert set(fp.MODES) == set(fp.MODE_DESCRIPTION)


def test_separation_is_symmetric_in_auc_direction() -> None:
    assert fp._sep(0.9) == pytest.approx(fp._sep(0.1)) == pytest.approx(0.9)
    assert fp._sep(0.5) == pytest.approx(0.5)
    assert math.isnan(fp._sep(None))


def test_parity_auc_summary_reports_the_drop_for_cross_session_pairs_only() -> None:
    pairs = {
        "s8_vs_s6/N2/decor": {"all": 0.95, "even": 0.55, "odd": 0.60},   # parity removes most of the gap
        "s9_vs_s6/N2/decor": {"all": 0.90, "even": 0.60, "odd": 0.60},
        "s9_vs_s8/N2/decor": {"all": 0.50, "even": 0.50, "odd": 0.50},   # within-day pair: not in the cross-session group
        "s8_vs_s6/N1/decor": {"all": 1.00, "even": 0.99, "odd": 0.99},   # parity changes nothing
    }
    s = fp.parity_auc_summary(pairs)
    assert s["N2/decor"]["cross_session_pairs"]["pairs"] == 2
    assert s["N2/decor"]["cross_session_pairs"]["drop"] == pytest.approx(((0.95 - 0.575) + (0.90 - 0.60)) / 2)
    assert s["N2/decor"]["all_pairs"]["pairs"] == 3
    assert s["N1/decor"]["cross_session_pairs"]["drop"] == pytest.approx(0.01)


def test_conclusion_is_computed_from_the_data_not_fixed_text() -> None:
    def node(zz: bool) -> dict:
        return {"lag_cos": {}, "zigzag": zz}
    res = {"recordings": {"a.jsonl": {"nodes": {"1": node(True), "2": node(True)}}, "b.jsonl": {"nodes": {"1": node(True), "2": node(False)}}},
           "summary_by_node": {"1": {"median_decor_ratio_parity_over_all": 0.7}, "2": {"median_decor_ratio_parity_over_all": 0.6}},
           "parity_auc_summary": {"N1/decor": {"cross_session_pairs": {"drop": 0.01}}, "N2/decor": {"cross_session_pairs": {"drop": 0.30}}}}
    text = "\n".join(fp.conclusion_lines(res))
    assert "1 of 2 recordings" in text and "b" in text           # the exception is named
    assert "part explained on N2" in text and "not explained on N1" in text
    assert "No threshold or feature change follows" in text
    res["parity_auc_summary"]["N2/decor"]["cross_session_pairs"]["drop"] = 0.02
    assert "part explained on none" in "\n".join(fp.conclusion_lines(res))
