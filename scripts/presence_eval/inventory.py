"""T1 data inventory: per-recording, per-node rates, RSSI, amplitude and drift flags.

    python -m scripts.presence_eval.inventory [--room-dir data/datasets/room1]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .recordings import NodeSeries, Recording, group_recordings, load_recording

RSSI_STEP_DB = 6.0
RSSI_BIN_S = 300
OUT_DIR = default_out_dir()
CACHE_DIR = REPO_ROOT / ".tmp" / "presence_eval_cache" / "recordings"


def iso_utc(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _f(x: float, digits: int = 3) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), digits)


def node_metrics(s: NodeSeries) -> dict:
    """Rates and quality counters for one node. ``fps_span`` is frames / (last t - first t)."""
    n = len(s.t)
    span_s = (int(s.t[-1]) - int(s.t[0])) / 1000.0
    dt = np.diff(s.t).astype(np.float64)
    per_second = np.bincount(((s.t - s.t[0]) // 1000).astype(np.int64)) if n else np.zeros(0)
    rssi = s.rssi[np.isfinite(s.rssi)]
    dup = float(np.mean(np.all(s.a[1:] == s.a[:-1], axis=1))) if n > 1 else float("nan")
    bins = (s.t - s.t[0]) // (RSSI_BIN_S * 1000)
    rssi_bins = [
        _f(np.nanmedian(s.rssi[bins == b]), 1) for b in range(int(bins[-1]) + 1) if np.any(bins == b)
    ]
    unique_t = int(np.unique(s.t).size)
    counts = np.bincount(bins.astype(np.int64))
    fps_bins = [_f(c / RSSI_BIN_S, 1) for c in counts[: len(counts) - 1]]  # last bin is partial: omitted
    return {
        "frames": n,
        "span_s": _f(span_s, 2),
        "fps_span": _f(n / span_s if span_s > 0 else float("nan"), 2),
        "unique_t": unique_t,
        "fps_unique_t": _f(unique_t / span_s if span_s > 0 else float("nan"), 2),
        "frac_same_ms_as_prev": _f(float(np.mean(dt == 0)) if dt.size else float("nan"), 4),
        "dt_ms_median": _f(np.median(dt) if dt.size else float("nan"), 1),
        "dt_ms_p99": _f(np.percentile(dt, 99) if dt.size else float("nan"), 1),
        "gaps_over_1s": int(np.count_nonzero(dt > 1000)),
        "longest_gap_s": _f(dt.max() / 1000.0 if dt.size else float("nan"), 2),
        "per_second_median": _f(np.median(per_second), 1),
        "per_second_p95": _f(np.percentile(per_second, 95), 1),
        "per_second_max": int(per_second.max()) if per_second.size else 0,
        "frac_seconds_zero": _f(float(np.mean(per_second == 0)), 4),
        "frac_identical_consecutive_frames": _f(dup, 4),
        "mean_amp": _f(float(np.mean(s.a)), 3),
        "rssi_median": _f(np.median(rssi) if rssi.size else float("nan"), 1),
        "rssi_p5": _f(np.percentile(rssi, 5) if rssi.size else float("nan"), 1),
        "rssi_p95": _f(np.percentile(rssi, 95) if rssi.size else float("nan"), 1),
        "rssi_median_per_5min": rssi_bins,
        "fps_per_5min_full_bins": fps_bins,
        "first_t_ms": int(s.t[0]),
        "last_t_ms": int(s.t[-1]),
    }


def recording_summary(rec: Recording) -> dict:
    h0 = rec.headers[0] if rec.headers else {}
    first_t, last_t = (rec.t_min, rec.t_max) if rec.nodes else (None, None)
    started = h0.get("startedAtMs")
    part_starts = [
        {"part": h.get("part"), "started_utc": iso_utc(h["startedAtMs"]) if h.get("startedAtMs") else None}
        for h in rec.headers
    ]
    return {
        "name": rec.name,
        "label": rec.label,
        "subject": rec.subject,
        "declared_count": h0.get("count"),
        "notes": h0.get("notes"),
        "parts": len(rec.paths),
        "files": [Path(p).name for p in rec.paths],
        "headers_consistent": len({(h.get("label"), h.get("subjectId"), json.dumps(h.get("geometry"), sort_keys=True)) for h in rec.headers}) <= 1,
        "geometry": h0.get("geometry"),
        "firmware_filter_mac": h0.get("firmwareFilterMac"),
        "header_started_utc": iso_utc(started) if started else None,
        "first_frame_utc": iso_utc(first_t) if first_t is not None else None,
        "last_frame_utc": iso_utc(last_t) if last_t is not None else None,
        "header_to_first_frame_s": _f((first_t - started) / 1000.0, 2) if first_t is not None and started else None,
        "duration_s": _f((last_t - first_t) / 1000.0, 1) if first_t is not None else None,
        "part_starts": part_starts,
        "parse": rec.stats.__dict__,
        "nodes": {str(n): node_metrics(s) for n, s in sorted(rec.nodes.items())},
        "_start_ms": first_t,
    }


def rssi_step_flags(summaries: list[dict]) -> list[dict]:
    """Flag per-node median-RSSI jumps greater than RSSI_STEP_DB between chronologically adjacent recordings."""
    ordered = sorted((s for s in summaries if s["_start_ms"] is not None), key=lambda s: s["_start_ms"])
    flags = []
    for prev, cur in zip(ordered, ordered[1:]):
        for node in sorted(set(prev["nodes"]) & set(cur["nodes"])):
            a, b = prev["nodes"][node]["rssi_median"], cur["nodes"][node]["rssi_median"]
            if a is None or b is None or abs(b - a) <= RSSI_STEP_DB:
                continue
            flags.append({
                "node": int(node), "from": prev["name"], "to": cur["name"], "delta_db": _f(b - a, 1),
                "gap_hours": _f((cur["_start_ms"] - prev["_start_ms"]) / 3.6e6, 2),
                "same_utc_day": iso_utc(prev["_start_ms"])[:10] == iso_utc(cur["_start_ms"])[:10],
            })
    return flags


def build_inventory(room_dir: Path, cache_dir: Path | None = CACHE_DIR) -> dict:
    summaries = []
    for _, paths in group_recordings(room_dir).items():
        rec = load_recording(paths, cache_dir)
        if rec.nodes:
            summaries.append(recording_summary(rec))
    summaries.sort(key=lambda s: s["_start_ms"])
    flags = rssi_step_flags(summaries)
    for s in summaries:
        del s["_start_ms"]
    return {
        "provenance": provenance(
            "python -m scripts.presence_eval.inventory", [f"{room_dir.name}/{f}" for s in summaries for f in s["files"]]
        ),
        "rssi_step_threshold_db": RSSI_STEP_DB,
        "recordings": summaries,
        "rssi_step_flags": flags,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room-dir", type=Path, default=REPO_ROOT / "data" / "datasets" / "room1")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "results" / "inventory.json")
    args = ap.parse_args()
    inv = build_inventory(args.room_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    dump_json(args.out, inv)
    print(f"wrote {args.out} ({len(inv['recordings'])} recordings, {len(inv['rssi_step_flags'])} RSSI step flags)")


if __name__ == "__main__":
    main()
