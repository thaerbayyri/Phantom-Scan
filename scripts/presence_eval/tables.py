"""Per-recording, per-node window feature tables (cached under .tmp/presence_eval_cache/windows/)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .features import COVARIATES, FEATURES, MIN_FRAMES, WINDOW_MS, node_windows
from .provenance import PACKAGE_DIR, REPO_ROOT
from .recordings import NODE_IDS, group_recordings, load_recording

ROOM_DIR = REPO_ROOT / "data" / "datasets" / "room1"
REC_CACHE = REPO_ROOT / ".tmp" / "presence_eval_cache" / "recordings"
WIN_CACHE = REPO_ROOT / ".tmp" / "presence_eval_cache" / "windows"
TABLE_COLS = (*FEATURES, *COVARIATES, "k", "nframes")


@dataclass
class RecTables:
    rid: str          # short unique id: subject_label_MMDD_HHMM
    name: str
    label: str
    subject: str
    day: str          # YYYYMMDD from the file stamp
    t0_ms: int
    duration_s: float
    parts: int
    nodes: dict[int, dict[str, np.ndarray]]


def short_id(name: str, subject: str, label: str) -> str:
    stamp = name.split("__")[3][:15] if name.count("__") >= 3 else "00000000T000000"
    return f"{subject}_{label}_{stamp[4:8]}_{stamp[9:13]}"


def _key(paths: list[Path]) -> str:
    src = hashlib.sha256((PACKAGE_DIR / "features.py").read_bytes()).hexdigest()[:12]
    return json.dumps([src, WINDOW_MS, MIN_FRAMES, [[p.name, p.stat().st_size] for p in paths]])


def load_tables(paths: list[Path], cache_dir: Path | None = WIN_CACHE, rec_cache: Path | None = REC_CACHE) -> RecTables:
    rec = load_recording(paths, rec_cache)
    day = rec.name.split("__")[3][:8] if rec.name.count("__") >= 3 else ""
    cache_file = None
    key = _key(paths)
    nodes: dict[int, dict[str, np.ndarray]] | None = None
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        cache_file = Path(cache_dir) / (rec.name.replace(".jsonl", "") + ".npz")
        if cache_file.exists():
            with np.load(cache_file, allow_pickle=False) as z:
                if str(z["key"]) == key:
                    nodes = {n: {c: z[f"n{n}_{c}"] for c in TABLE_COLS} for n in json.loads(str(z["nodes"]))}
    if nodes is None:
        nodes = {n: node_windows(s, rec.t_min) for n, s in rec.nodes.items()}
        if cache_file is not None:
            arrays = {f"n{n}_{c}": t[c] for n, t in nodes.items() for c in TABLE_COLS}
            np.savez_compressed(cache_file, key=np.array(key), nodes=np.array(json.dumps(sorted(nodes))), **arrays)
    return RecTables(
        rid=short_id(rec.name, rec.subject, rec.label), name=rec.name, label=rec.label, subject=rec.subject, day=day,
        t0_ms=rec.t_min, duration_s=(rec.t_max - rec.t_min) / 1000.0, parts=len(rec.paths), nodes=nodes,
    )


def load_all(room_dir: Path = ROOM_DIR) -> dict[str, RecTables]:
    """All recordings keyed by short id, in chronological order of file stamp."""
    out = {}
    for _, paths in group_recordings(room_dir).items():
        t = load_tables(paths)
        if t.nodes:
            out[t.rid] = t
    return dict(sorted(out.items(), key=lambda kv: (kv[1].day, kv[0].split("_")[-1])))


def pick(tabs: dict[str, RecTables], subject: str, label: str, day: str | None = None) -> RecTables:
    hits = [t for t in tabs.values() if t.subject == subject and t.label == label and (day is None or t.day == day)]
    if len(hits) != 1:
        raise LookupError(f"expected exactly one recording for {subject}/{label}/{day}, found {len(hits)}")
    return hits[0]


__all__ = ["RecTables", "load_tables", "load_all", "pick", "short_id", "NODE_IDS"]
