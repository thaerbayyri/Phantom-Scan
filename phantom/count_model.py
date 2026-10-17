"""Small CNN people-count model (advisory) — architecture, input prep, calibration.

Fixes the two defects found in RuView's cog-person-count when porting it:

1. NORMALIZATION: training and runtime both call `prepare_window`, the single
   place where raw amplitudes become network input, and the learned scale is
   stored in the checkpoint metadata. (RuView z-scored subcarriers in its
   training script but not in the runtime.)
2. LAYOUT: the network input is channel-major [subcarriers K, time T] and
   `prepare_window` asserts a [T, K] time-major window before transposing.
   (RuView appended frames time-major and read the buffer as (1, K, T).)

Confidence is the temperature-scaled softmax maximum, not a separate
confidence head (RuView's head had Spearman 0.013 with correctness).

Counts are the classes {0, 1, 2+}: 2 means "two or more".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

WINDOW_FRAMES = 40  # ~0.8-1 s at 40-50 fps
NUM_SUBCARRIERS = 51  # LLTF data subcarriers (phantom.subcarriers)
COUNT_CLASSES = (0, 1, 2)  # 2 == "2 or more"
EPS = 1e-9


def count_to_class(count: int) -> int:
    return min(max(int(count), 0), COUNT_CLASSES[-1])


def prepare_window(amps_tk: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """[T, K] time-major amplitudes -> [K, T] channel-major float32 network input.

    Each subcarrier's window mean (the static multipath of THIS room) is
    removed and the deviation is divided by the window's overall mean
    amplitude, so the input is a gain-invariant relative fluctuation; `scale`
    (learned at training time, stored with the model) standardizes it.
    """
    a = np.asarray(amps_tk, dtype=np.float64)
    if a.shape != (WINDOW_FRAMES, NUM_SUBCARRIERS):
        raise ValueError(
            f"expected a time-major window of shape ({WINDOW_FRAMES}, {NUM_SUBCARRIERS}), got {a.shape}"
        )
    if scale <= 0 or not np.isfinite(scale):
        raise ValueError("scale must be a positive finite number")
    relative = (a - a.mean(axis=0, keepdims=True)) / (a.mean() + EPS)
    return (relative / scale).T.astype(np.float32)


class CountNet(nn.Module):
    """Conv1d(K->64, d=1) -> Conv1d(64->128, d=2) -> Conv1d(128->128, d=4) -> mean over time -> Linear."""

    def __init__(self, num_subcarriers: int = NUM_SUBCARRIERS, num_classes: int = len(COUNT_CLASSES)) -> None:
        super().__init__()
        self.c1 = nn.Conv1d(num_subcarriers, 64, kernel_size=3, dilation=1, padding=1)
        self.c2 = nn.Conv1d(64, 128, kernel_size=3, dilation=2, padding=2)
        self.c3 = nn.Conv1d(128, 128, kernel_size=3, dilation=4, padding=4)
        self.head = nn.Linear(128, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: [B, K, T]
        h = F.gelu(self.c1(x))
        h = F.gelu(self.c2(h))
        h = F.gelu(self.c3(h))
        return self.head(h.mean(dim=-1))


def temperature_scale(logits: np.ndarray, y: np.ndarray) -> float:
    """Temperature minimizing NLL on held-out logits (grid search; deterministic)."""
    grid = np.exp(np.linspace(np.log(0.25), np.log(8.0), 64))
    best_t, best_nll = 1.0, np.inf
    for t in grid:
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        log_p = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
        nll = -float(log_p[np.arange(len(y)), y].mean())
        if nll < best_nll:
            best_nll, best_t = nll, float(t)
    return best_t


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=-1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(axis=-1, keepdims=True)


def expected_calibration_error(probs: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


@dataclass
class CountPredictor:
    net: CountNet
    scale: float
    temperature: float
    classes: tuple[int, ...]
    meta: dict[str, Any]

    def window_logits(self, windows_tk: Sequence[np.ndarray]) -> np.ndarray:
        batch = torch.from_numpy(np.stack([prepare_window(w, self.scale) for w in windows_tk]))
        with torch.no_grad():
            return self.net(batch).numpy().astype(np.float64)

    def predict_fused(self, windows_by_node: dict[int, np.ndarray]) -> tuple[int, float, np.ndarray]:
        """Sum per-node log-probabilities (calibrated), return (count, confidence, probs)."""
        if not windows_by_node:
            raise ValueError("no node windows to fuse")
        probs = softmax(self.window_logits(list(windows_by_node.values())), self.temperature)
        log_p = np.log(np.clip(probs, 1e-9, 1.0)).sum(axis=0)
        fused = softmax(log_p[None, :])[0]
        best = int(np.argmax(fused))
        return self.classes[best], float(fused[best]), fused

    @classmethod
    def load(cls, directory: Path | str) -> "CountPredictor":
        from safetensors.torch import load_file

        d = Path(directory)
        meta = json.loads((d / "count.json").read_text(encoding="utf-8"))
        if meta.get("kind") != "count-cnn" or meta.get("window_frames") != WINDOW_FRAMES:
            raise ValueError("unsupported count model file")
        net = CountNet(num_classes=len(meta["classes"]))
        net.load_state_dict(load_file(str(d / "count.safetensors")))
        net.eval()
        return cls(
            net=net,
            scale=float(meta["scale"]),
            temperature=float(meta["temperature"]),
            classes=tuple(int(c) for c in meta["classes"]),
            meta=meta,
        )
