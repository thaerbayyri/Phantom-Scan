#!/usr/bin/env python3
"""Record a labelled CSI dataset straight from the ESP32 nodes (no dashboard).

    python scripts/record_dataset.py --room room1 --subject s1 --label empty --seconds 300

Writes the same JSONL layout as server/lib/dataset-recorder.ts, so
scripts/train/train_*.py read it unchanged:

    data/datasets/<room>/<room>__<subject>__<label>__<UTC stamp>.jsonl
    line 1  {"type":"header","schema":2,"roomId","subjectId","label","count",...}
    then    {"type":"frame","t":<ms>,"n":<node>,"rssi":<dBm>,"a":[51 amplitudes]}

Schema 2 (identical field set to the dashboard recorder; see its header comment) only ADDS fields to
schema 1: partStartedAtMs, geometryHash, capture{channel,bandwidthMHz,bssid,firmwareVersion,firmwareHash,
source}, annotation{nodeMoved,roomNotEmpty,text}, recorder. Unknown values are null, never guessed. Both
recorders write compact JSON (no spaces); older files from this script contain spaces and still parse.

It binds UDP :5005 itself, so the dashboard must be stopped first (the boards
send to one address; two listeners would split the packets). Keep the room in
the labelled condition for the WHOLE run: a mislabelled second poisons the file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import statistics
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phantom.protocol import CsiFrameV1, parse_csi_frame  # noqa: E402
from phantom.subcarriers import lltf_amplitudes  # noqa: E402

SCHEMA_VERSION = 2
LABELS = ("empty", "empty_fan", "still", "walking", "active", "two_people", "three_people")
DEFAULT_COUNT = {"empty": 0, "empty_fan": 0, "still": 1, "walking": 1, "active": 1, "two_people": 2, "three_people": 3}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PROGRESS_EVERY_S = 30.0
FLUSH_EVERY_LINES = 200


def _require_safe_id(value: str, field: str) -> str:
    if not SAFE_ID.fullmatch(value or ""):
        raise ValueError(f"invalid {field}: use 1-64 letters, digits, '_' or '-'")
    return value


def output_path(root: Path, room: str, subject: str, label: str, started_ms: int) -> Path:
    if label not in LABELS:
        raise ValueError(f"invalid label {label!r}: expected one of {', '.join(LABELS)}")
    stamp = datetime.fromtimestamp(started_ms / 1000.0, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "__".join([_require_safe_id(room, "room"), _require_safe_id(subject, "subject"), label, stamp])
    return Path(root) / room / f"{name}.jsonl"


def dumps(obj: Any) -> str:
    """Compact JSON, the same byte layout as the dashboard recorder's JSON.stringify."""
    return json.dumps(obj, separators=(",", ":"))


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def geometry_hash(geometry: dict[str, Any] | None) -> str | None:
    """First 16 hex of sha256(canonical {roomWidthM, roomDepthM, anchors}); equals the TS recorder's value."""
    if not geometry:
        return None
    picked = {k: geometry[k] for k in ("roomWidthM", "roomDepthM", "anchors") if k in geometry}
    return hashlib.sha256(canonical_json(picked).encode("utf-8")).hexdigest()[:16]


def capture_from_env(env: Any) -> dict[str, Any]:
    """Operator-supplied capture conditions; invalid values become None (same rules as the TS captureFromEnv)."""
    def num(key: str) -> float | None:
        try:
            return float(env.get(key))
        except (TypeError, ValueError):
            return None

    channel, bandwidth = num("PHANTOM_CAPTURE_CHANNEL"), num("PHANTOM_CAPTURE_BANDWIDTH_MHZ")
    bssid = (env.get("PHANTOM_ROUTER_BSSID") or "").lower()
    version = env.get("PHANTOM_FIRMWARE_VERSION") or ""
    fw_hash = (env.get("PHANTOM_FIRMWARE_HASH") or "").lower()
    capture = {
        "channel": int(channel) if channel is not None and channel.is_integer() and 1 <= channel <= 196 else None,
        "bandwidthMHz": int(bandwidth) if bandwidth in (20, 40, 80, 160) else None,
        "bssid": bssid if re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", bssid) else None,
        "firmwareVersion": version if re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", version) else None,
        "firmwareHash": fw_hash if re.fullmatch(r"[0-9a-f]{7,64}", fw_hash) else None,
    }
    capture["source"] = "operator_env" if any(v is not None for v in capture.values()) else "not_recorded"
    return capture


def build_header(
    room: str,
    subject: str,
    label: str,
    count: int,
    started_ms: int,
    geometry: dict[str, Any],
    notes: str = "",
    *,
    capture: dict[str, Any] | None = None,
    annotation: dict[str, Any] | None = None,
    part_started_ms: int | None = None,
) -> dict[str, Any]:
    ann = annotation or {}
    return {
        "type": "header",
        "schema": SCHEMA_VERSION,
        "roomId": room,
        "subjectId": subject,
        "label": label,
        "count": count,
        "notes": notes,
        "startedAtMs": started_ms,
        "partStartedAtMs": started_ms if part_started_ms is None else part_started_ms,
        "part": 1,
        "geometry": geometry,
        "geometryHash": geometry_hash(geometry),
        "firmwareFilterMac": None,
        "capture": capture if capture is not None else capture_from_env({}),
        "annotation": {
            "nodeMoved": ann.get("nodeMoved") if isinstance(ann.get("nodeMoved"), bool) else None,
            "roomNotEmpty": ann.get("roomNotEmpty") if isinstance(ann.get("roomNotEmpty"), bool) else None,
            "text": str(ann.get("text") or "")[:500],
        },
        "recorder": "headless",
    }


def frame_record(t_ms: float, node_id: int, rssi: int, amps: Sequence[float]) -> dict[str, Any]:
    return {"type": "frame", "t": int(t_ms), "n": int(node_id), "rssi": int(rssi), "a": [float(a) for a in amps]}


def load_geometry(path: Path) -> dict[str, Any]:
    """Room geometry as the dashboard stores it (without the router, as its recorder does)."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: raw[k] for k in ("roomWidthM", "roomDepthM", "anchors") if k in raw}


# ── Per-part link summary sidecar (PS-FIX-29) ────────────────────────────────
# Same definitions and JSON as server/lib/dataset-recorder.ts (parity vector pinned in both test suites). Written when the
# file closes to `<file minus .jsonl>.summary.json`; never matched by the *.jsonl dataset glob. Observation only: it says
# nothing about the CAUSE of a change.
SUMMARY_WINDOW_MS = 10_000
SUMMARY_STEP_DB = 6
SUMMARY_COLLAPSE_RATIO = 0.7
SUMMARY_MIN_FPS = 20


class PartNodeStats:
    def __init__(self) -> None:
        self.frames = 0
        self.first_t: int | None = None
        self.last_t: int | None = None
        self._first: list[float] = []
        self._last: deque[tuple[int, float]] = deque()
        self._all: list[float] = []

    def add(self, t: int, rssi: float) -> None:
        self.frames += 1
        if self.first_t is None:
            self.first_t = t
        self.last_t = t
        if t - self.first_t < SUMMARY_WINDOW_MS:
            self._first.append(rssi)
        self._last.append((t, rssi))
        while self._last and t - self._last[0][0] >= SUMMARY_WINDOW_MS:
            self._last.popleft()
        self._all.append(rssi)

    def summary(self) -> dict[str, Any]:
        first_t, last_t = int(self.first_t), int(self.last_t)  # type: ignore[arg-type]
        last = [r for t, r in self._last if last_t - t < SUMMARY_WINDOW_MS]

        def win(values: list[float]) -> dict[str, Any]:
            return {"frames": len(values), "fps": len(values) / (SUMMARY_WINDOW_MS / 1000), "rssiMedian": statistics.median(values) if values else None}

        first10, last10 = win(self._first), win(last)
        short = last_t - first_t < 2 * SUMMARY_WINDOW_MS  # windows would overlap: no step statement possible
        reasons: list[str] = []
        delta: float | None = None
        ratio: float | None = None
        flag: bool | None = None
        if not short:
            delta = last10["rssiMedian"] - first10["rssiMedian"]
            if abs(delta) >= SUMMARY_STEP_DB:
                reasons.append("rssi_step")
            if first10["fps"] >= SUMMARY_MIN_FPS:
                ratio = last10["fps"] / first10["fps"]
                if ratio <= SUMMARY_COLLAPSE_RATIO:
                    reasons.append("rate_collapse")
            flag = bool(reasons)
        return {
            "frames": self.frames, "firstFrameMs": first_t, "lastFrameMs": last_t, "rssiMedianPart": statistics.median(self._all),
            "first10s": first10, "last10s": last10, "shortPart": short,
            "rssiDeltaDb": None if delta is None else round(delta, 3), "fpsRatio": None if ratio is None else round(ratio, 3),
            "stepFlag": flag, "stepReasons": reasons,
        }


def summary_path_for(part_file: Path) -> Path:
    name = part_file.name[:-len(".jsonl")] if part_file.name.endswith(".jsonl") else part_file.name
    return part_file.with_name(name + ".summary.json")


def build_part_summary(file: Path, part: int, started_ms: int, part_started_ms: int, closed_ms: int, stats: dict[int, PartNodeStats]) -> dict[str, Any]:
    return {
        "type": "part_summary", "schema": 1, "file": file.name, "part": part, "startedAtMs": started_ms, "partStartedAtMs": part_started_ms,
        "closedAtMs": closed_ms, "windowSeconds": SUMMARY_WINDOW_MS / 1000, "stepThresholdDb": SUMMARY_STEP_DB,
        "collapseRatio": SUMMARY_COLLAPSE_RATIO, "minBaselineFps": SUMMARY_MIN_FPS,
        "perNode": {str(n): s.summary() for n, s in sorted(stats.items()) if s.frames > 0},
    }


def write_part_summary(summary: dict[str, Any], part_file: Path) -> Path | None:
    """Best effort (exclusive create): a failure here must never lose or break the recording."""
    if not summary["perNode"]:
        return None
    target = summary_path_for(part_file)
    try:
        with target.open("x", encoding="utf-8") as fh:
            fh.write(dumps(summary) + "\n")
    except OSError as exc:
        print(f"[REC] could not write link summary {target.name}: {exc}")
        return None
    return target


def record(args: argparse.Namespace) -> int:
    started_ms = int(time.time() * 1000)
    out = output_path(Path(args.data_root), args.room, args.subject, args.label, started_ms)
    count = DEFAULT_COUNT[args.label] if args.count is None else args.count
    env = dict(os.environ)
    for key, value in (
        ("PHANTOM_CAPTURE_CHANNEL", args.channel), ("PHANTOM_CAPTURE_BANDWIDTH_MHZ", args.bandwidth_mhz),
        ("PHANTOM_ROUTER_BSSID", args.bssid), ("PHANTOM_FIRMWARE_VERSION", args.firmware_version),
        ("PHANTOM_FIRMWARE_HASH", args.firmware_hash),
    ):
        if value is not None:
            env[key] = str(value)  # command-line flags override the environment
    header = build_header(
        args.room, args.subject, args.label, count, started_ms, load_geometry(Path(args.room_config)), args.notes,
        capture=capture_from_env(env),
        annotation={"nodeMoved": args.node_moved, "roomNotEmpty": args.room_not_empty, "text": args.annotation},
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", args.port))
    except OSError as exc:
        print(f"[REC] cannot bind UDP :{args.port} ({exc}). Stop the dashboard first so this script owns the port.")
        return 1
    sock.settimeout(0.5)

    out.parent.mkdir(parents=True, exist_ok=True)
    per_node: Counter[int] = Counter()
    link_stats: dict[int, PartNodeStats] = {}
    deadline = time.monotonic() + args.seconds
    next_progress = time.monotonic() + PROGRESS_EVERY_S
    lines = 0
    print(f"[REC] {args.label} (count={count}) for {args.seconds:.0f}s -> {out}")
    with out.open("w", encoding="utf-8") as handle:
        handle.write(dumps(header) + "\n")
        try:
            while time.monotonic() < deadline:
                try:
                    data, (ip, port) = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                frame = parse_csi_frame(data, ip, port)
                if not isinstance(frame, CsiFrameV1):
                    continue  # heartbeats / malformed packets
                try:
                    amps = lltf_amplitudes(frame.iq_bytes, frame.n_subcarriers)
                except ValueError:
                    continue
                now_ms = time.time() * 1000.0
                handle.write(dumps(frame_record(now_ms, frame.node_id, frame.rssi_dbm, amps)) + "\n")
                link_stats.setdefault(frame.node_id, PartNodeStats()).add(int(now_ms), int(frame.rssi_dbm))
                per_node[frame.node_id] += 1
                lines += 1
                if lines % FLUSH_EVERY_LINES == 0:
                    handle.flush()
                if time.monotonic() >= next_progress:
                    next_progress += PROGRESS_EVERY_S
                    left = max(0.0, deadline - time.monotonic())
                    print(f"[REC] {left:4.0f}s left, frames per node {dict(sorted(per_node.items()))}")
        except KeyboardInterrupt:
            print("[REC] interrupted; keeping what was captured")
    sock.close()
    write_part_summary(build_part_summary(out, 1, started_ms, started_ms, int(time.time() * 1000), link_stats), out)

    print(f"[REC] done: {lines} frames, per node {dict(sorted(per_node.items()))} -> {out}")
    if len(per_node) < args.expect_nodes:
        print(f"[REC] WARNING: only {len(per_node)} of {args.expect_nodes} nodes were heard; this recording is incomplete")
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--room", required=True)
    parser.add_argument("--subject", default="s1")
    parser.add_argument("--label", required=True, choices=LABELS)
    parser.add_argument("--count", type=int, default=None, help="people in the room (default from the label)")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--expect-nodes", type=int, default=4)
    parser.add_argument("--notes", default="headless scripts/record_dataset.py")
    parser.add_argument("--data-root", default="data/datasets")
    parser.add_argument("--room-config", default="config/room.json")
    parser.add_argument("--channel", type=int, default=None, help="Wi-Fi channel the AP uses (recorded as stated; not verified)")
    parser.add_argument("--bandwidth-mhz", type=int, default=None, help="20/40/80/160 (recorded as stated)")
    parser.add_argument("--bssid", default=None, help="router/AP MAC aa:bb:cc:dd:ee:ff")
    parser.add_argument("--firmware-version", default=None)
    parser.add_argument("--firmware-hash", default=None, help="git hash of the firmware flashed on the nodes")
    parser.add_argument("--node-moved", action=argparse.BooleanOptionalAction, default=None,
                        help="operator states a node was moved/obstructed during or just before this recording")
    parser.add_argument("--room-not-empty", action=argparse.BooleanOptionalAction, default=None,
                        help="operator states someone/something was in the room although the label says otherwise")
    parser.add_argument("--annotation", default="", help="free text, max 500 chars")
    args = parser.parse_args()
    try:
        return record(args)
    except ValueError as exc:
        print(f"[REC] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
