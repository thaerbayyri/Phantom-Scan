"""Converter for the ESP32-S3 HAR dataset (huggingface.co/datasets/imPiglet/esp32s3-csi-har-2025, CC BY 4.0).

Layout: ``<root>/data/<class><n>.csv`` in the Espressif ``CSI_DATA`` column schema. ``data`` holds 384 signed ints =
192 complex subcarriers, imaginary first; amplitude = sqrt(imag^2 + real^2). ``local_timestamp`` is in microseconds
(about 20 Hz). The postures sitting / standing / lying map to ``still`` and walking to ``walking``; there is no
empty-room class. One board, one session (29 July 2025); each file becomes a single-node Recording. Other people's
room: never training data for the Phantom Scan room model.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np

from phantom.dataset import NodeStream, Recording

LABEL_MAP: dict[str, str] = {"sitting": "still", "standing": "still", "lying": "still", "walking": "walking"}
_NAME_RE = re.compile(r"^([a-z]+)(\d+)$")


def load_har_csv(path: Path | str) -> Recording:
    path = Path(path)
    match = _NAME_RE.match(path.stem.lower())
    posture = match.group(1) if match else path.stem.lower()
    if posture not in LABEL_MAP:
        raise ValueError(f"{path.name}: unknown label '{posture}' (expected one of {sorted(LABEL_MAP)})")
    t_us: list[float] = []
    rssi: list[float] = []
    amps: list[np.ndarray] = []
    width: int | None = None
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                iq = np.asarray(json.loads(row["data"]), dtype=np.float64)
                ts, level = float(row["local_timestamp"]), float(row["rssi"])
            except (KeyError, TypeError, ValueError):
                continue
            if iq.size < 2 or iq.size % 2:
                continue
            width = width or iq.size
            if iq.size != width:
                continue
            amps.append(np.hypot(iq[0::2], iq[1::2]))
            t_us.append(ts)
            rssi.append(level)
    if len(amps) < 2:
        raise ValueError(f"{path.name}: fewer than 2 readable rows")
    order = np.argsort(np.asarray(t_us), kind="stable")
    t = np.asarray(t_us)[order]
    stream = NodeStream(t_ms=(t - t[0]) / 1000.0, amps=np.vstack(amps)[order], rssi=np.asarray(rssi)[order])
    return Recording(
        recording_id=f"esp32s3-har/{path.stem}",
        room_id="external-esp32s3-har-2025",
        subject_id="esp32s3-har-s1",
        label=LABEL_MAP[posture],
        count=1,
        day="20250729",
        nodes={1: stream},
        files=(str(path),),
    )


def load_har_dataset(root: Path | str) -> list[Recording]:
    return [load_har_csv(p) for p in sorted(Path(root).glob("data/*.csv"))]
