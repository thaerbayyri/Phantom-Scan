"""Converter for the reporafin ESP32 CSI dataset (github.com/reporafin/esp32-csi-pipeline, data CC BY 4.0).

Layout: ``<root>/<room>/<state>_trail<n>.csv`` with columns ``Packet_Count, Sub_0 ... Sub_63`` (CSI amplitudes).
The dataset has no timestamps or RSSI; its README says packets arrive at about 100/s, so time is taken as
``(Packet_Count - first) * 10 ms`` (gaps in the counter stay gaps) and RSSI is zero. ``Sub_0``/``Sub_1`` are not CSI
(constant 95/5), 2-5 and 59-63 are zero guards and 32 is the zero DC carrier, so a fixed set of 52 subcarriers
(6-58 without 32) is kept. Each file becomes one single-node ``Recording``; ``day`` holds the room folder name so
``group_by="day"`` holds out whole rooms. These recordings are other people's rooms: never training data for the
Phantom Scan room model.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

from phantom.dataset import NodeStream, Recording

ASSUMED_PERIOD_MS = 10.0
KEEP_SUBCARRIERS: tuple[int, ...] = tuple(i for i in range(6, 59) if i != 32)
LABEL_MAP: dict[str, str] = {"empty": "empty", "stationary": "still", "moving": "walking"}
_STATE_RE = re.compile(r"^([a-z]+)_tri[a-z]*\d*$")


def _state_of(path: Path) -> str:
    match = _STATE_RE.match(path.stem.lower())
    state = match.group(1) if match else path.stem.lower().split("_")[0]
    if state not in LABEL_MAP:
        raise ValueError(f"{path.name}: unknown state '{state}' (expected one of {sorted(LABEL_MAP)})")
    return state


def load_reporafin_csv(path: Path | str) -> Recording:
    """One CSV file as a single-node Recording (label mapped to the project's activity labels)."""
    path = Path(path)
    state = _state_of(path)
    counts: list[float] = []
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        cols = [header.index(f"Sub_{i}") for i in KEEP_SUBCARRIERS]
        count_col = header.index("Packet_Count")
        for raw in reader:
            try:
                count = float(raw[count_col])
                values = [float(raw[c]) for c in cols]
            except (ValueError, IndexError):
                continue  # packet loss leaves corrupted rows (dataset README)
            counts.append(count)
            rows.append(values)
    if len(rows) < 2:
        raise ValueError(f"{path.name}: fewer than 2 readable rows")
    order = np.argsort(np.asarray(counts), kind="stable")
    count_arr = np.asarray(counts)[order]
    t_ms = (count_arr - count_arr[0]) * ASSUMED_PERIOD_MS
    amps = np.asarray(rows, dtype=np.float64)[order]
    stream = NodeStream(t_ms=t_ms, amps=amps, rssi=np.zeros(len(t_ms)))
    room = path.parent.name
    return Recording(
        recording_id=f"reporafin/{room}/{path.stem}",
        room_id=f"external-reporafin-{room}",
        subject_id="reporafin-s1",
        label=LABEL_MAP[state],
        count=0 if state == "empty" else 1,
        day=room,
        nodes={1: stream},
        files=(str(path),),
    )


def load_reporafin_dataset(root: Path | str) -> list[Recording]:
    """Every ``<room>/<state>_*.csv`` under the dataset folder, sorted by path."""
    return [load_reporafin_csv(p) for p in sorted(Path(root).glob("*/*.csv"))]
