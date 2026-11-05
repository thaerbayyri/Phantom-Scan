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
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SCHEMA_VERSION = 1  # the oldest layout; kept for callers that import it
# Schema 2 only ADDS header fields (partStartedAtMs, geometryHash, capture, annotation, recorder), so it reads the same way.
SUPPORTED_SCHEMAS = (1, 2)
_PART_RE = re.compile(r"\.part\d+$")
_PART_NUM_RE = re.compile(r"\.part(\d+)$")
_STAMP_RE = re.compile(r"__(\d{8})T\d{6}Z$")
# Rows are converted to numpy in chunks of this size so a long recording is never held as a list of Python lists.
_CHUNK_ROWS = 4096


@dataclass(frozen=True)
class LoadReport:
    """What the loader saw and skipped (PS-EVAL-004). Nothing is dropped silently."""

    lines: int = 0
    frames: int = 0                                   # frames kept
    malformed_lines: int = 0                          # not JSON / not an object / unknown record type
    bad_frames: int = 0                               # wrong field types, empty or non-finite amplitudes/timestamp
    modal_width: dict[int, int] = field(default_factory=dict)             # node -> subcarrier count kept
    width_mismatch_frames: dict[int, int] = field(default_factory=dict)   # node -> frames dropped for another width

    @property
    def clean(self) -> bool:
        return not (self.malformed_lines or self.bad_frames or self.width_mismatch_frames)


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
    report: LoadReport | None = None  # None for recordings built by hand (tests)
    header: dict = field(default_factory=dict)  # first header verbatim: capture/annotation/geometryHash for schema 2


def _recording_id(path: Path) -> str:
    return _PART_RE.sub("", path.stem)


def _part_key(path: Path) -> tuple[int, str]:
    """Numeric part order (``part10`` after ``part2``); the base file counts as part 1."""
    m = _PART_NUM_RE.search(path.stem)
    return (int(m.group(1)) if m else 1, path.name)


class _NodeWidthAcc:
    """Chunked accumulator for the frames of one node with ONE subcarrier width."""

    def __init__(self) -> None:
        self.count = 0
        self._cur: tuple[list[float], list[np.ndarray], list[float]] = ([], [], [])
        self._t: list[np.ndarray] = []
        self._a: list[np.ndarray] = []
        self._r: list[np.ndarray] = []

    def add(self, t: float, a: np.ndarray, r: float) -> None:
        self._cur[0].append(t)
        self._cur[1].append(a)
        self._cur[2].append(r)
        self.count += 1
        if len(self._cur[0]) >= _CHUNK_ROWS:
            self._flush()

    def _flush(self) -> None:
        t, a, r = self._cur
        if t:
            self._t.append(np.asarray(t, dtype=np.float64))
            self._a.append(np.stack(a))
            self._r.append(np.asarray(r, dtype=np.float64))
        self._cur = ([], [], [])

    def arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self._flush()
        return np.concatenate(self._t), np.concatenate(self._a), np.concatenate(self._r)


def _frame_fields(obj: dict) -> tuple[int, float, np.ndarray, float] | None:
    """(node, t, amplitudes, rssi) or None when the frame is unusable (wrong types, empty/non-finite data)."""
    n, t, r = obj.get("n"), obj.get("t"), obj.get("rssi")
    if isinstance(n, bool) or not isinstance(n, int):
        return None
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
        return None
    try:
        a = np.asarray(obj.get("a"), dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if a.ndim != 1 or a.size == 0 or not np.isfinite(a).all():
        return None
    rssi = float(r) if isinstance(r, (int, float)) and not isinstance(r, bool) and math.isfinite(r) else float("nan")
    return n, float(t), a, rssi


def load_recording(paths: list[Path], *, strict: bool = False) -> Recording:
    """Merge the part files of ONE recording, streaming line by line.

    Default (tolerant): lines that are not JSON, frames with unusable fields, and frames whose subcarrier
    count differs from the node's most common count are SKIPPED and COUNTED in ``Recording.report`` --
    amplitudes are never truncated to the shortest frame. ``strict=True`` raises ``ValueError`` on any of
    those instead (the pre-PS-FIX-02 loader raised on invalid JSON and silently truncated mixed widths).
    A missing header or an unsupported schema always raises.
    """
    header: dict | None = None
    accs: dict[int, dict[int, _NodeWidthAcc]] = {}
    lines = malformed = bad = 0
    for path in sorted(paths, key=_part_key):
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                lines += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    if strict:
                        raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
                    malformed += 1
                    continue
                kind = obj.get("type") if isinstance(obj, dict) else None
                if kind == "header":
                    if obj.get("schema") not in SUPPORTED_SCHEMAS:
                        raise ValueError(f"{path}: unsupported dataset schema {obj.get('schema')!r}")
                    header = header or obj
                elif kind == "frame":
                    fields = _frame_fields(obj)
                    if fields is None:
                        if strict:
                            raise ValueError(f"{path}:{line_no}: unusable frame")
                        bad += 1
                        continue
                    n, t, a, r = fields
                    accs.setdefault(n, {}).setdefault(a.size, _NodeWidthAcc()).add(t, a, r)
                else:
                    if strict:
                        raise ValueError(f"{path}:{line_no}: unknown record type {kind!r}")
                    malformed += 1
    if header is None:
        raise ValueError(f"{paths[0]}: missing header line")

    nodes: dict[int, NodeStream] = {}
    modal: dict[int, int] = {}
    mismatch: dict[int, int] = {}
    kept = 0
    for node_id, by_width in accs.items():
        counts = Counter({w: acc.count for w, acc in by_width.items()})
        width = max(counts, key=lambda w: (counts[w], w))  # most frames; ties -> wider
        dropped = sum(c for w, c in counts.items() if w != width)
        if dropped:
            if strict:
                raise ValueError(f"node {node_id}: mixed subcarrier counts {dict(counts)}")
            mismatch[node_id] = dropped
        modal[node_id] = width
        t, a, r = by_width[width].arrays()
        order = np.argsort(t, kind="stable")
        nodes[node_id] = NodeStream(t_ms=t[order], amps=a[order], rssi=r[order])
        kept += int(t.size)
    report = LoadReport(lines=lines, frames=kept, malformed_lines=malformed, bad_frames=bad, modal_width=modal, width_mismatch_frames=mismatch)
    rec_id = _recording_id(sorted(paths, key=_part_key)[0])
    stamp = _STAMP_RE.search(rec_id)
    return Recording(
        recording_id=rec_id,
        room_id=str(header["roomId"]),
        subject_id=str(header["subjectId"]),
        label=str(header["label"]),
        count=int(header["count"]),
        day=stamp.group(1) if stamp else "",
        nodes=nodes,
        files=tuple(str(p) for p in sorted(paths, key=_part_key)),
        report=report,
        header=dict(header),
    )


def load_room_dataset(root: Path | str, room_id: str, *, strict: bool = False) -> list[Recording]:
    """Load every recording under <root>/<room_id>/ (empty list if none)."""
    room_dir = Path(root) / room_id
    if not room_dir.is_dir():
        return []
    groups: dict[str, list[Path]] = {}
    for path in room_dir.glob("*.jsonl"):
        groups.setdefault(_recording_id(path), []).append(path)
    return [load_recording(paths, strict=strict) for _, paths in sorted(groups.items())]
