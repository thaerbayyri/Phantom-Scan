"""Loader for labelled CSI recordings written by server/lib/dataset-recorder.ts.

Layout: data/datasets/<roomId>/<roomId>__<subjectId>__<label>__<UTC stamp>.jsonl
(+ ``.part2.jsonl`` … rotation parts). Every file starts with a header line
({"type":"header","schema":1,"roomId","subjectId","label","count",...}) then
{"type":"frame","t":<ms>,"n":<nodeId>,"rssi":<dBm>,"a":[…amplitudes…]} rows.

Parts of one recording are merged. A recording is the unit of evaluation:
training code must split by recording (or day), never by frame, because
consecutive windows of one recording are near-duplicates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SCHEMA_VERSION = 1
_PART_RE = re.compile(r"\.part\d+$")
_STAMP_RE = re.compile(r"__(\d{8})T\d{6}Z$")


@dataclass(frozen=True)
class NodeStream:
    t_ms: np.ndarray  # [N] host receive time, ascending
    amps: np.ndarray  # [N, K]
    rssi: np.ndarray  # [N]


@dataclass(frozen=True)
class Recording:
    recording_id: str
    room_id: str
    subject_id: str
    label: str
    count: int
    day: str  # YYYYMMDD from the file stamp ("" if unparseable)
    nodes: dict[int, NodeStream] = field(default_factory=dict)
    files: tuple[str, ...] = ()


def _recording_id(path: Path) -> str:
    return _PART_RE.sub("", path.stem)


def load_recording(paths: list[Path]) -> Recording:
    """Merge the part files of ONE recording."""
    header: dict | None = None
    rows: dict[int, tuple[list[float], list[list[float]], list[float]]] = {}
    for path in sorted(paths):
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
                kind = obj.get("type")
                if kind == "header":
                    if obj.get("schema") != SCHEMA_VERSION:
                        raise ValueError(f"{path}: unsupported dataset schema {obj.get('schema')!r}")
                    header = header or obj
                elif kind == "frame":
                    t, a, r = rows.setdefault(int(obj["n"]), ([], [], []))
                    t.append(float(obj["t"]))
                    a.append(obj["a"])
                    r.append(float(obj["rssi"]))
    if header is None:
        raise ValueError(f"{paths[0]}: missing header line")

    nodes: dict[int, NodeStream] = {}
    for node_id, (t, a, r) in rows.items():
        width = min(len(v) for v in a)
        order = np.argsort(np.asarray(t), kind="stable")
        nodes[node_id] = NodeStream(
            t_ms=np.asarray(t, dtype=np.float64)[order],
            amps=np.asarray([v[:width] for v in a], dtype=np.float64)[order],
            rssi=np.asarray(r, dtype=np.float64)[order],
        )
    rec_id = _recording_id(sorted(paths)[0])
    stamp = _STAMP_RE.search(rec_id)
    return Recording(
        recording_id=rec_id,
        room_id=str(header["roomId"]),
        subject_id=str(header["subjectId"]),
        label=str(header["label"]),
        count=int(header["count"]),
        day=stamp.group(1) if stamp else "",
        nodes=nodes,
        files=tuple(str(p) for p in sorted(paths)),
    )


def load_room_dataset(root: Path | str, room_id: str) -> list[Recording]:
    """Load every recording under <root>/<room_id>/ (empty list if none)."""
    room_dir = Path(root) / room_id
    if not room_dir.is_dir():
        return []
    groups: dict[str, list[Path]] = {}
    for path in room_dir.glob("*.jsonl"):
        groups.setdefault(_recording_id(path), []).append(path)
    return [load_recording(paths) for _, paths in sorted(groups.items())]
