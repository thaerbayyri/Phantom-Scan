"""PS-FIX-07: the frame-rate analysis, on synthetic arrival processes whose truth is known."""
from __future__ import annotations

import numpy as np

from scripts.presence_eval import frame_rate as fr


def test_firmware_constants_are_read_from_the_header_not_typed_in() -> None:
    c = fr.firmware_constants()
    assert c == {"CSI_PING_INTERVAL_MS": 30, "CSI_PING_TIMEOUT_MS": 20, "CSI_MIN_SEND_INTERVAL_MS": 10, "CSI_PING_SLOTS": 4}


def test_interarrival_stats_on_a_regular_15_ms_stream() -> None:
    t = np.arange(0, 60_000, 15, dtype=np.int64)
    s = fr.interarrival_stats(t)
    assert s["gap_ms_quantiles"]["q50"] == 15.0
    assert s["share_gap_le_ms"]["10"] == 0.0 and s["share_gap_le_ms"]["5"] == 0.0
    assert s["share_gap_gt_ms"]["100"] == 0.0 and s["share_zero_gap"] == 0.0


def test_bursts_and_stalls_are_counted() -> None:
    t = np.array([0, 1, 1, 100, 400, 1500], dtype=np.int64)
    s = fr.interarrival_stats(t)
    assert s["share_zero_gap"] == 0.2          # one of five gaps is exactly 0
    assert s["share_gap_le_ms"]["2"] == 0.4    # gaps 1 and 0
    assert s["share_gap_gt_ms"]["1000"] == 0.2 # gap 1100


def test_duplicate_share_counts_only_bit_identical_consecutive_vectors() -> None:
    a = np.array([[1.0, 2.0], [1.0, 2.0], [1.0, 2.5], [1.0, 2.5], [9.0, 9.0]])
    assert fr.duplicate_share(a) == 0.5
    assert np.isnan(fr.duplicate_share(a[:1]))


def test_per_second_counts_drop_the_partial_last_second() -> None:
    t = np.concatenate([np.arange(0, 3000, 100), [3050]]).astype(np.int64)    # 10 frames in each of seconds 0-2, then 1 in second 3
    assert fr.per_second_counts(t).tolist() == [10, 10, 10]
    assert fr.per_second_counts(np.array([0, 10, 20], dtype=np.int64)).size == 0


def test_rate_spread_flags_seconds_far_below_the_median() -> None:
    t = np.concatenate([np.concatenate([np.arange(s * 1000, s * 1000 + 1000, 20) for s in range(9)]),   # 50 fps for 9 s
                        np.arange(9000, 10000, 500), [10000]]).astype(np.int64)                           # 2 fps in the 10th second
    r = fr.rate_spread(t)
    assert r["median_fps"] == 50.0 and r["share_seconds_below_half_median"] == 0.1 and r["share_empty_seconds"] == 0.0


def test_pair_similarity_separates_near_duplicate_pairs_from_distinct_frames() -> None:
    rng = np.random.default_rng(0)
    base = 10 + rng.standard_normal((200, 51))
    a = np.repeat(base, 2, axis=0) + 1e-6 * rng.standard_normal((400, 51))   # every frame twice -> close pair is a near-duplicate
    t = np.cumsum(np.tile([28, 2], 200)).astype(np.int64)                     # diffs 2, 28, 2, ...: 2 ms inside a pair, 28 ms between pairs
    sim = fr.pair_similarity(t, a)
    assert sim["0-5ms"]["median_rel_change"] < 1e-4
    assert sim["15-30ms"]["median_rel_change"] > 0.05


def test_phase_lock_sees_a_30_ms_comb_but_not_random_arrivals() -> None:
    rng = np.random.default_rng(1)
    locked = np.cumsum(30.0 + 0.5 * rng.standard_normal(2000)).astype(np.int64)
    random = np.cumsum(rng.exponential(30.0, 2000)).astype(np.int64)
    r_locked = fr.phase_lock(locked)["mean_best_R"]
    r_random = fr.phase_lock(random)["mean_best_R"]
    assert r_locked["30ms"] > 0.8 and r_locked["30ms"] > 3 * r_locked["27ms"]
    assert r_random["30ms"] < 0.4 and abs(r_random["30ms"] - r_random["27ms"]) < 0.1


def test_node_summary_reports_frames_per_ping_interval() -> None:
    rng = np.random.default_rng(2)
    t = np.arange(0, 20_000, 15, dtype=np.int64)
    s = fr.node_summary(fr.NodeSeries(t=t, rssi=np.full(len(t), -40, np.float32), a=(10 + rng.standard_normal((len(t), 51))).astype(np.float32)))
    assert abs(s["median_frames_per_ping_interval"] - 2.0) < 0.1 and s["duplicate_share"] == 0.0
