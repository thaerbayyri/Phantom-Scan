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
