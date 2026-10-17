"""Pure scheduling / routing / fusion helpers for the AI sidecar.

Kept free of torch and socket I/O so they are unit-testable
(tests/test_sidecar.py); scripts/ai_inference.py wires them to the models.
All outputs are ADVISORY — nothing here can touch the deterministic gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Per-node inference rate cap. Previously one GLOBAL 5 Hz throttle was shared
# by every node, so 4 nodes got ~1.25 Hz each and fusion windows dropped nodes.
PER_NODE_MIN_INTERVAL_S = 0.2
# Fuse per-node results fresher than this. Must exceed 1 / per-node rate with
# margin so all live nodes contribute to every fused output.
FUSION_WINDOW_S = 1.5
# WS rawSample vectors are synthesized from two scalars, never real CSI; they
# are only used (opt-in) when no real UDP frame has arrived for this long.
WS_FALLBACK_UDP_SILENCE_S = 2.0


class PerNodeThrottle:
    """Allow at most one inference per node per `min_interval_s`."""

    def __init__(self, min_interval_s: float = PER_NODE_MIN_INTERVAL_S) -> None:
        self._min_interval_s = min_interval_s
        self._last_run: dict[int, float] = {}

    def should_run(self, node_id: int, now_s: float) -> bool:
        last = self._last_run.get(node_id)
        if last is not None and now_s - last < self._min_interval_s:
            return False
        self._last_run[node_id] = now_s
        return True


def route_ws_message(
    message: Mapping[str, Any],
    *,
    ws_fallback_enabled: bool,
    seconds_since_udp: float,
) -> str:
    """Decide what an inbound dashboard WS message means for the sidecar.

    Returns "calibrate", "fallback_sample" or "ignore". rawSample is ignored by
    default: the server already forwards the REAL packet over UDP, and the
    old path appended a second, synthetic vector for the same frame into the
    same node history (double-ingest that inflated motion on every node).
    """
    msg_type = message.get("type")
    if msg_type == "calibrateBaseline":
        return "calibrate"
    if msg_type == "rawSample" and ws_fallback_enabled and seconds_since_udp >= WS_FALLBACK_UDP_SILENCE_S:
        return "fallback_sample"
    return "ignore"


def fresh_results(
    node_results: Mapping[int, Mapping[str, Any]],
    now_s: float,
    window_s: float = FUSION_WINDOW_S,
) -> dict[int, Mapping[str, Any]]:
    """Per-node results whose timestamp `t` is within the fusion window."""
    return {nid: r["result"] for nid, r in node_results.items() if now_s - r["t"] <= window_s}


MIN_WINDOW_FRAMES = 16


def window_features_from_history(
    amps_hist: Sequence[Any],
    rssi_hist: Sequence[float],
    timestamps_ms: Sequence[float],
    window_s: float,
) -> "np.ndarray | None":
    """Features of the trailing `window_s` of one node's history (None if sparse).

    Uses the same extract_window_features as training, with the frame rate
    estimated from the window's own timestamps.
    """
    import numpy as np

    from phantom.features import extract_window_features

    if len(timestamps_ms) < MIN_WINDOW_FRAMES:
        return None
    t = np.asarray(timestamps_ms, dtype=np.float64)
    lo = int(np.searchsorted(t, t[-1] - window_s * 1000.0, side="left"))
    if len(t) - lo < MIN_WINDOW_FRAMES:
        return None
    span_s = (t[-1] - t[lo]) / 1000.0
    if span_s <= 0:
        return None
    fs = (len(t) - lo - 1) / span_s
    return extract_window_features(
        np.asarray(amps_hist[lo:], dtype=np.float64), np.asarray(rssi_hist[lo:], dtype=np.float64), fs
    )


def fuse_activity(model: Any, feats_by_node: Mapping[int, Any], room_id: str) -> "dict[str, Any] | None":
    """Advisory per-room activity from the fresh nodes' window features.

    Returns the identity-message fields (advisoryActivity, confidence, model
    provenance) or None when there is no model or no usable node. The result
    is advisory only: it never feeds the deterministic gate (F1).
    """
    if model is None or not feats_by_node:
        return None
    label, confidence, _ = model.predict_fused(list(feats_by_node.values()))
    sha = str(model.meta.get("data_sha256", ""))[:8]
    return {
        "advisoryActivity": label,
        "advisoryActivityConfidence": confidence,
        "modelId": f"activity-{sha or 'local'}",
        "roomId": room_id,
    }


COUNT_MAX_WINDOW_SPAN_MS = 3000.0


def count_window_from_history(amps_hist: Sequence[Any], timestamps_ms: Sequence[float]) -> "np.ndarray | None":
    """Newest [WINDOW_FRAMES, K] time-major window for the count model, or None.

    None when the history is too short, the subcarrier count is not the live
    51, or the window contains a gap (same rule as training's window builder).
    """
    import numpy as np

    from phantom.count_model import NUM_SUBCARRIERS, WINDOW_FRAMES

    if len(amps_hist) < WINDOW_FRAMES or len(timestamps_ms) < WINDOW_FRAMES:
        return None
    window = np.asarray(amps_hist[-WINDOW_FRAMES:], dtype=np.float64)
    if window.shape != (WINDOW_FRAMES, NUM_SUBCARRIERS):
        return None
    if timestamps_ms[-1] - timestamps_ms[-WINDOW_FRAMES] > COUNT_MAX_WINDOW_SPAN_MS:
        return None
    return window


def fuse_count(
    predictor: Any, windows_by_node: Mapping[int, Any], room_id: str, min_confidence: float
) -> "dict[str, Any] | None":
    """Advisory people count from the fresh nodes' windows (None without a model).

    advisoryCount is the class index: 2 means "two or more" (countIsLowerBound).
    Low-confidence outputs are flagged, not suppressed. Never feeds the
    deterministic gate (F1).
    """
    if predictor is None or not windows_by_node:
        return None
    count, confidence, _ = predictor.predict_fused(dict(windows_by_node))
    sha = str(predictor.meta.get("data_sha256", ""))[:8]
    return {
        "advisoryCount": int(count),
        "advisoryCountConfidence": float(confidence),
        "countLowConfidence": bool(confidence < min_confidence),
        "countIsLowerBound": bool(count >= 2),
        "countModelId": f"count-{sha or 'local'}",
        "roomId": room_id,
    }


@dataclass(frozen=True)
class FusedVitals:
    respiration_rpm: float | None
    heart_bpm: float | None
    reliable: bool


def fuse_vitals(per_node: Sequence[Mapping[str, Any]]) -> FusedVitals:
    """Average vitals over RELIABLE nodes only; None when no node is reliable.

    Replaces the old behaviour of averaging unreliable estimates and fixed
    14 rpm / 72 bpm fallbacks, which the dashboard showed as real readings.
    """
    reliable = [
        v
        for v in per_node
        if v.get("reliable") and v.get("breathing") is not None and v.get("heart_rate") is not None
    ]
    if not reliable:
        return FusedVitals(None, None, False)
    resp = sum(float(v["breathing"]) for v in reliable) / len(reliable)
    heart = sum(float(v["heart_rate"]) for v in reliable) / len(reliable)
    return FusedVitals(resp, heart, True)
