"""Input mapping and empty-room drift for the RuView csi-embed-v2 encoder.

csi-embed-v2 maps 8 features to a 128-dim L2-normalised embedding. It has NO
classification head, so the only honest signal Phantom takes from it is how far
a node's live embedding has moved from that node's own empty-room embedding.
That is "the signal environment changed", not "someone is there": a moved
door or router drift moves it too. Advisory only (F1).

Pure numpy (no torch) so it is unit-testable; scripts/ai_inference.py runs the
network and feeds the embeddings in here.

Feature contract (RuView edge_processing.c, all clamped to 0-1):
  0 presence/10, 1 motion/10, 2 breathing_bpm/30, 3 heart_bpm/120,
  4 phase variance, 5 person_count/4, 6 fall, 7 (rssi_dbm + 100)/100
Dims 4, 5, 6 were constant in the training capture (std ~1e-6) and Phantom has
no equivalent measurement, so they are masked to 0 instead of being divided by
a vanishing std.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

EMBED_DIM_IN = 8
STANDARDIZER_BYTES = 32  # fp16 mean[8] then fp16 std[8], at the start of the int4 bin
MASKED_DIMS: tuple[int, ...] = (4, 5, 6)
STD_FLOOR = 0.05
EPS = 1e-12


def load_standardizer(bin_path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """(mean[8], std[8]) from the first 32 bytes of csi-embed-v2-int4.bin."""
    with Path(bin_path).open("rb") as handle:
        raw = handle.read(STANDARDIZER_BYTES)
    if len(raw) < STANDARDIZER_BYTES:
        raise ValueError(f"{bin_path}: standardizer needs {STANDARDIZER_BYTES} bytes, found {len(raw)}")
    values = np.frombuffer(raw, dtype="<f2").astype(np.float64)
    return values[:EMBED_DIM_IN].copy(), values[EMBED_DIM_IN:].copy()


def _unit_clip(value: float) -> float:
    return float(min(max(value, 0.0), 1.0))


def ruview_scale_features(
    presence: float,
    motion: float,
    breathing_bpm: float | None,
    heart_bpm: float | None,
    rssi_dbm: float,
) -> np.ndarray:
    """Raw Phantom measurements -> the 0-1 scale the encoder was trained on."""
    feats = np.zeros(EMBED_DIM_IN)
    feats[0] = _unit_clip(presence / 10.0)
    feats[1] = _unit_clip(motion / 10.0)
    feats[2] = _unit_clip(breathing_bpm / 30.0) if breathing_bpm and breathing_bpm > 0 else 0.0
    feats[3] = _unit_clip(heart_bpm / 120.0) if heart_bpm and heart_bpm > 0 else 0.0
    feats[7] = _unit_clip((rssi_dbm + 100.0) / 100.0)
    return feats


def standardize(raw: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """(raw - mean) / max(std, STD_FLOOR), with the constant training dims zeroed."""
    out = (np.asarray(raw, dtype=np.float64) - mean) / np.maximum(std, STD_FLOOR)
    out[list(MASKED_DIMS)] = 0.0
    return out


def _unit(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > EPS else vec


def mean_embedding(embeddings: Sequence[np.ndarray]) -> np.ndarray | None:
    """L2-normalised mean of unit embeddings (the empty-room reference), None if empty."""
    if len(embeddings) == 0:
        return None
    return _unit(np.mean(np.asarray(embeddings, dtype=np.float64), axis=0))


def cosine_drift(embedding: np.ndarray, reference: np.ndarray) -> float:
    """1 - cosine similarity, in [0, 2]; 0 means identical direction."""
    sim = float(np.dot(_unit(np.asarray(embedding, dtype=np.float64)), _unit(np.asarray(reference, dtype=np.float64))))
    return float(min(max(1.0 - sim, 0.0), 2.0))
