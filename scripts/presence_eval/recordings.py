"""Streaming parser and loader for data/datasets/<room>/*.jsonl recordings.

Read-only with respect to the dataset folder. A recording is one base file plus
its ``.partN`` continuations; they are concatenated in part order. Parsed
recordings are cached as compressed npz under ``.tmp/presence_eval_cache/``.

File format (scripts/record_dataset.py): one header line, then
``{"type":"frame","t":<ms>,"n":<node>,"rssi":<dBm>,"a":[51 amplitudes]}`` lines.
``t`` is the recorder host's wall clock when the datagram was written, NOT a
device timestamp.

Unlike phantom/dataset.py this loader tolerates malformed lines and reports
every skipped line in ``ParseStats`` instead of raising or truncating silently.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

N_SUBCARRIERS = 51
NODE_IDS = (1, 2, 3, 4)
_PART_RE = re.compile(r"\.part(\d+)\.jsonl$")
_NAME_RE = re.compile(r"^(?P<room>[^_]+)__(?P<subject>[^_]+)__(?P<label>.+?)__(?P<stamp>\d{8}T\d{6}Z)")


@dataclass
class ParseStats:
    """Counters for lines that were seen but not used. Nothing is dropped silently."""

    lines: int = 0
    headers: int = 0
    frames: int = 0
    malformed_lines: int = 0
    bad_length_frames: int = 0
    unknown_node_frames: int = 0
    out_of_order_frames: int = 0


@dataclass
class NodeSeries:
    t: np.ndarray       # int64 ms (recorder host clock), sorted
    rssi: np.ndarray    # float32 dBm, NaN when missing
    a: np.ndarray       # float32 (k, 51)


@dataclass
class Recording:
    name: str                      # base file name (".jsonl", no part suffix)
    label: str
    subject: str
    paths: list[str]
    headers: list[dict]
    nodes: dict[int, NodeSeries]
    stats: ParseStats = field(default_factory=ParseStats)

    @property
    def t_min(self) -> int:
        return min(int(s.t[0]) for s in self.nodes.values())

    @property
    def t_max(self) -> int:
        return max(int(s.t[-1]) for s in self.nodes.values())


def part_number(path: Path) -> int:
    m = _PART_RE.search(path.name)
    return int(m.group(1)) if m else 1


def base_name(path: Path) -> str:
    return _PART_RE.sub(".jsonl", path.name)


def group_recordings(directory: Path) -> dict[str, list[Path]]:
    """Group ``*.jsonl`` into recordings; parts sorted ascending; groups sorted by name."""
    groups: dict[str, list[Path]] = {}
    for p in sorted(Path(directory).glob("*.jsonl")):
        groups.setdefault(base_name(p), []).append(p)
    return {k: sorted(v, key=part_number) for k, v in sorted(groups.items())}


def name_fields(name: str) -> tuple[str, str]:
    """(subject, label) from ``room__subject__label__stamp.jsonl``; ('?','?') if it does not match."""
    m = _NAME_RE.match(name)
    return (m.group("subject"), m.group("label")) if m else ("?", "?")


def iter_lines(path: Path) -> Iterator[tuple[str, object]]:
    """Yield ('header'|'frame'|'malformed', payload) per non-empty line, streaming."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                yield "malformed", raw[:80]
                continue
            kind = obj.get("type") if isinstance(obj, dict) else None
            if kind in ("header", "frame"):
                yield kind, obj
            else:
                yield "malformed", raw[:80]


def _is_num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _valid_frame(obj: dict, stats: ParseStats) -> bool:
    a, n, t = obj.get("a"), obj.get("n"), obj.get("t")
    if not _is_num(t) or not isinstance(n, int) or isinstance(n, bool):
        stats.malformed_lines += 1
        return False
    if not isinstance(a, list) or len(a) != N_SUBCARRIERS or not all(_is_num(x) for x in a):
        stats.bad_length_frames += 1
        return False
    if n not in NODE_IDS:
        stats.unknown_node_frames += 1
        return False
    return True


def parse_files(paths: list[Path]) -> Recording:
    """Parse the parts of ONE recording (already in part order) into per-node arrays."""
    stats = ParseStats()
    headers: list[dict] = []
    buf: dict[int, tuple[list, list, list]] = {n: ([], [], []) for n in NODE_IDS}
    for path in paths:
        for kind, payload in iter_lines(path):
            stats.lines += 1
            if kind == "malformed":
                stats.malformed_lines += 1
            elif kind == "header":
                stats.headers += 1
                headers.append(payload)  # type: ignore[arg-type]
            elif _valid_frame(payload, stats):  # type: ignore[arg-type]
                stats.frames += 1
                ts, rs, am = buf[payload["n"]]  # type: ignore[index]
                ts.append(int(payload["t"]))  # type: ignore[index]
                rssi = payload.get("rssi")  # type: ignore[union-attr]
                rs.append(float(rssi) if _is_num(rssi) else np.nan)
                am.append(payload["a"])  # type: ignore[index]
    nodes: dict[int, NodeSeries] = {}
    for n, (ts, rs, am) in buf.items():
        if not ts:
            continue
        t = np.asarray(ts, dtype=np.int64)
        order = np.argsort(t, kind="stable")
        stats.out_of_order_frames += int(np.count_nonzero(np.diff(t) < 0))
        nodes[n] = NodeSeries(t=t[order], rssi=np.asarray(rs, dtype=np.float32)[order], a=np.asarray(am, dtype=np.float32)[order])
    name = base_name(paths[0])
    subject, label = name_fields(name)
    if headers:
        subject = str(headers[0].get("subjectId", subject))
        label = str(headers[0].get("label", label))
    return Recording(name=name, label=label, subject=subject, paths=[str(p) for p in paths], headers=headers, nodes=nodes, stats=stats)


def _cache_key(paths: list[Path]) -> str:
    return json.dumps([[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in paths])


def load_recording(paths: list[Path], cache_dir: Path | None = None) -> Recording:
    """Load (and cache) one recording. The cache never lives under data/."""
    if cache_dir is None:
        return parse_files(paths)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / (base_name(paths[0]).replace(".jsonl", "") + ".npz")
    key = _cache_key(paths)
    if cache_file.exists():
        with np.load(cache_file, allow_pickle=False) as z:
            if str(z["key"]) == key:
                meta = json.loads(str(z["meta"]))
                nodes = {int(n): NodeSeries(t=z[f"t{n}"], rssi=z[f"r{n}"], a=z[f"a{n}"]) for n in meta["node_ids"]}
                return Recording(
                    name=meta["name"], label=meta["label"], subject=meta["subject"], paths=meta["paths"],
                    headers=meta["headers"], nodes=nodes, stats=ParseStats(**meta["stats"]),
                )
    rec = parse_files(paths)
    arrays = {"key": np.array(key)}
    for n, s in rec.nodes.items():
        arrays[f"t{n}"], arrays[f"r{n}"], arrays[f"a{n}"] = s.t, s.rssi, s.a
    meta = {
        "name": rec.name, "label": rec.label, "subject": rec.subject, "paths": rec.paths, "headers": rec.headers,
        "node_ids": sorted(rec.nodes), "stats": rec.stats.__dict__,
    }
    arrays["meta"] = np.array(json.dumps(meta))
    np.savez_compressed(cache_file, **arrays)
    return rec
