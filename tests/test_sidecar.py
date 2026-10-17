import struct

import numpy as np

from phantom.protocol import parse_csi_frame
from phantom.sidecar import (
    PerNodeThrottle,
    fresh_results,
    fuse_vitals,
    route_ws_message,
)
from phantom.subcarriers import LLTF_DATA_INDICES, NUM_DATA_SUBCARRIERS, lltf_amplitudes


def _v1_packet(node_id: int, entries: list[tuple[int, int]]) -> bytes:
    """ADR-018 v1 packet; entries are (real, imag) written imaginary-first."""
    header = struct.pack("<IBBBHIIbbBQI", 0xC5110001, 1, node_id, 1, len(entries), 2437, 7, -40, -90, 6, 123456, 123)
    iq = b"".join(struct.pack("<bb", im, re) for re, im in entries)
    return header + iq


def test_v1_packet_keeps_real_node_id_and_lltf_data_subcarriers():
    entries = [(6, 8) if i in LLTF_DATA_INDICES else (0, 0) for i in range(128)]
    frame = parse_csi_frame(_v1_packet(3, entries))
    assert frame.node_id == 3, "node id must come from byte 5, not the schema-version byte"
    amps = lltf_amplitudes(frame.iq_bytes, frame.n_subcarriers)
    assert amps.shape == (NUM_DATA_SUBCARRIERS,) == (51,)
    assert np.allclose(amps, 10.0)


def test_lltf_amplitudes_reads_imaginary_first():
    entries = [(0, 0)] * 64
    entries[5] = (3, 4)  # real=3, imag=4 -> amplitude 5
    entries[6] = (0, 7)
    amps = lltf_amplitudes(_v1_packet(1, entries)[32:], 64)
    assert amps[LLTF_DATA_INDICES.index(5)] == 5.0
    assert amps[LLTF_DATA_INDICES.index(6)] == 7.0


def test_ws_raw_samples_are_ignored_by_default_no_double_ingest():
    msg = {"type": "rawSample", "data": {"nodeId": 1, "h1": {"re": 1, "im": 1}}}
    assert route_ws_message(msg, ws_fallback_enabled=False, seconds_since_udp=999) == "ignore"
    # Opt-in fallback only while real UDP is silent.
    assert route_ws_message(msg, ws_fallback_enabled=True, seconds_since_udp=0.5) == "ignore"
    assert route_ws_message(msg, ws_fallback_enabled=True, seconds_since_udp=5.0) == "fallback_sample"
    assert route_ws_message({"type": "calibrateBaseline"}, ws_fallback_enabled=False, seconds_since_udp=0) == "calibrate"


def test_per_node_throttle_lets_all_four_nodes_run_at_5hz():
    throttle = PerNodeThrottle(0.2)
    runs = {n: 0 for n in (1, 2, 3, 4)}
    # 4 nodes interleaved at 50 Hz each for 1 s.
    for k in range(50):
        t = k * 0.02
        for n in runs:
            if throttle.should_run(n, t):
                runs[n] += 1
    assert all(4 <= c <= 6 for c in runs.values()), runs


def test_fresh_results_keeps_every_node_within_the_window():
    results = {n: {"result": {"node_id": n}, "t": 10.0 - 0.25 * n} for n in (1, 2, 3, 4)}
    assert sorted(fresh_results(results, now_s=10.0)) == [1, 2, 3, 4]
    # Node 1 (t=9.75) is the freshest; at 11.2 s only it is within 1.5 s.
    assert sorted(fresh_results(results, now_s=11.2)) == [1]


def test_fuse_vitals_returns_none_when_no_node_is_reliable():
    unreliable = [{"breathing": None, "heart_rate": None, "reliable": False}] * 2
    fused = fuse_vitals(unreliable)
    assert (fused.respiration_rpm, fused.heart_bpm, fused.reliable) == (None, None, False)


def test_fuse_vitals_averages_only_reliable_nodes():
    fused = fuse_vitals([
        {"breathing": 12.0, "heart_rate": 60.0, "reliable": True},
        {"breathing": 18.0, "heart_rate": 80.0, "reliable": True},
        {"breathing": 40.0, "heart_rate": 150.0, "reliable": False},
    ])
    assert fused.reliable and fused.respiration_rpm == 15.0 and fused.heart_bpm == 70.0


# ── per-room activity model at runtime ─────────────────────────────────────

def _activity_model(tmp_path):
    from phantom.activity_model import ActivityModel
    from phantom.features import NUM_FEATURES, FEATURE_NAMES

    var_idx = FEATURE_NAMES.index("temporal_variance")
    coef = np.zeros((2, NUM_FEATURES))
    coef[1, var_idx] = 3.0  # class 1 ("walking") grows with variance
    coef[0, var_idx] = -3.0
    return ActivityModel(
        classes=("empty", "walking"),
        mean=np.zeros(NUM_FEATURES),
        std=np.ones(NUM_FEATURES),
        coef=coef,
        intercept=np.zeros(2),
        meta={"room_id": "room1"},
    )


def _feats(variance):
    from phantom.features import NUM_FEATURES, FEATURE_NAMES

    f = np.zeros(NUM_FEATURES)
    f[FEATURE_NAMES.index("temporal_variance")] = variance
    return f


def test_window_features_from_history_uses_only_the_trailing_window():
    from phantom.sidecar import window_features_from_history

    t = [i * 25.0 for i in range(100)]  # 40 Hz, 2.5 s
    amps = [np.full(51, 10.0) for _ in t]
    rssi = [-45.0] * 100
    feats = window_features_from_history(amps, rssi, t, window_s=1.0)
    assert feats is not None and feats.shape[0] == 15
    assert window_features_from_history(amps[:5], rssi[:5], t[:5], window_s=1.0) is None


def test_fuse_activity_reports_class_confidence_and_provenance(tmp_path):
    from phantom.sidecar import fuse_activity

    model = _activity_model(tmp_path)
    out = fuse_activity(model, {1: _feats(2.0), 2: _feats(1.5)}, room_id="room1")
    assert out["advisoryActivity"] == "walking"
    assert 0.5 < out["advisoryActivityConfidence"] <= 1.0
    assert out["roomId"] == "room1" and out["modelId"].startswith("activity-")
    quiet = fuse_activity(model, {1: _feats(-2.0)}, room_id="room1")
    assert quiet["advisoryActivity"] == "empty"


def test_fuse_activity_without_features_returns_none(tmp_path):
    from phantom.sidecar import fuse_activity

    assert fuse_activity(_activity_model(tmp_path), {}, room_id="room1") is None
    assert fuse_activity(None, {1: _feats(1.0)}, room_id="room1") is None


# ── per-room people-count model at runtime ─────────────────────────────────

class _FakePredictor:
    def __init__(self, count, confidence, meta=None):
        self._out = (count, confidence, np.array([0.1, 0.2, 0.7]))
        self.meta = meta or {"data_sha256": "abcdef0123"}

    def predict_fused(self, windows):
        self.seen = windows
        return self._out


def test_fuse_count_reports_count_confidence_and_provenance():
    from phantom.sidecar import fuse_count

    out = fuse_count(_FakePredictor(1, 0.9), {1: "w1", 2: "w2"}, room_id="room1", min_confidence=0.6)
    assert out["advisoryCount"] == 1 and out["advisoryCountConfidence"] == 0.9
    assert out["countLowConfidence"] is False and out["countIsLowerBound"] is False
    assert out["countModelId"] == "count-abcdef01"


def test_fuse_count_flags_low_confidence_and_two_or_more():
    from phantom.sidecar import fuse_count

    out = fuse_count(_FakePredictor(2, 0.55), {1: "w"}, room_id="room1", min_confidence=0.6)
    assert out["countLowConfidence"] is True
    assert out["countIsLowerBound"] is True, "class 2 means two OR MORE people"


def test_fuse_count_without_model_or_windows_returns_none():
    from phantom.sidecar import fuse_count

    assert fuse_count(None, {1: "w"}, room_id="r", min_confidence=0.6) is None
    assert fuse_count(_FakePredictor(1, 0.9), {}, room_id="r", min_confidence=0.6) is None


def test_count_window_from_history_requires_a_full_gapless_window():
    from phantom.sidecar import count_window_from_history

    t = [i * 25.0 for i in range(60)]
    amps = [np.full(51, 10.0) for _ in t]
    window = count_window_from_history(amps, t)
    assert window is not None and window.shape == (40, 51)
    assert count_window_from_history(amps[:30], t[:30]) is None  # too short
    gappy = t[:40] + [x + 5000.0 for x in t[40:]]  # gap inside the newest 40 frames
    assert count_window_from_history(amps, gappy) is None  # a 5 s gap inside the window
    assert count_window_from_history([np.full(30, 1.0)] * 60, t) is None  # wrong subcarrier count
