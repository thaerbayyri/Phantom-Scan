#!/usr/bin/env python3
"""Record a labelled CSI dataset straight from the ESP32 nodes (no dashboard).

    python scripts/record_dataset.py --room room1 --subject s1 --label empty --seconds 300

Writes the same JSONL layout as server/lib/dataset-recorder.ts, so
scripts/train/train_*.py read it unchanged:

    data/datasets/<room>/<room>__<subject>__<label>__<UTC stamp>.jsonl
    line 1  {"type":"header","schema":1,"roomId","subjectId","label","count",...}
    then    {"type":"frame","t":<ms>,"n":<node>,"rssi":<dBm>,"a":[51 amplitudes]}

It binds UDP :5005 itself, so the dashboard must be stopped first (the boards
send to one address; two listeners would split the packets). Keep the room in
the labelled condition for the WHOLE run: a mislabelled second poisons the file.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phantom.protocol import CsiFrameV1, parse_csi_frame  # noqa: E402
from phantom.subcarriers import lltf_amplitudes  # noqa: E402

SCHEMA_VERSION = 1
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


def build_header(
    room: str, subject: str, label: str, count: int, started_ms: int, geometry: dict[str, Any], notes: str = ""
) -> dict[str, Any]:
    return {
        "type": "header",
        "schema": SCHEMA_VERSION,
        "roomId": room,
        "subjectId": subject,
        "label": label,
        "count": count,
        "notes": notes,
        "startedAtMs": started_ms,
        "part": 1,
        "geometry": geometry,
        "firmwareFilterMac": None,
    }


def frame_record(t_ms: float, node_id: int, rssi: int, amps: Sequence[float]) -> dict[str, Any]:
    return {"type": "frame", "t": int(t_ms), "n": int(node_id), "rssi": int(rssi), "a": [float(a) for a in amps]}


def load_geometry(path: Path) -> dict[str, Any]:
    """Room geometry as the dashboard stores it (without the router, as its recorder does)."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: raw[k] for k in ("roomWidthM", "roomDepthM", "anchors") if k in raw}


def record(args: argparse.Namespace) -> int:
    started_ms = int(time.time() * 1000)
    out = output_path(Path(args.data_root), args.room, args.subject, args.label, started_ms)
    count = DEFAULT_COUNT[args.label] if args.count is None else args.count
    header = build_header(
        args.room, args.subject, args.label, count, started_ms, load_geometry(Path(args.room_config)), args.notes
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
    deadline = time.monotonic() + args.seconds
    next_progress = time.monotonic() + PROGRESS_EVERY_S
    lines = 0
    print(f"[REC] {args.label} (count={count}) for {args.seconds:.0f}s -> {out}")
    with out.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
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
                handle.write(json.dumps(frame_record(time.time() * 1000.0, frame.node_id, frame.rssi_dbm, amps)) + "\n")
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
    args = parser.parse_args()
    try:
        return record(args)
    except ValueError as exc:
        print(f"[REC] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
