"""Per-room activity classifier: numpy-only inference for the AI sidecar.

Training (scripts/train/train_activity.py) fits a multinomial logistic
regression with scikit-learn and exports plain arrays to activity.json, so the
sidecar needs no sklearn at runtime. Output is ADVISORY (F1): it labels the
activity of an already-detected situation and can never assert or clear
presence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from phantom.features import FEATURE_NAMES, NUM_FEATURES

ACTIVITY_CLASSES: tuple[str, ...] = ("empty", "still", "walking", "active")
# Dataset label -> activity class (None = not an activity-model label).
LABEL_TO_ACTIVITY: dict[str, str | None] = {
    "empty": "empty",
    "empty_fan": "empty",
    "still": "still",
    "walking": "walking",
    "active": "active",
    "two_people": None,
    "three_people": None,
}
MODEL_SCHEMA = 1


@dataclass(frozen=True)
class ActivityModel:
    classes: tuple[str, ...]
    mean: np.ndarray  # [F]
    std: np.ndarray  # [F]
    coef: np.ndarray  # [C, F]
    intercept: np.ndarray  # [C]
    window_s: float = 1.0
    hop_s: float = 0.5
    meta: dict[str, Any] = field(default_factory=dict)

    def predict_proba(self, feats: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(feats, dtype=np.float64))
        if x.shape[1] != NUM_FEATURES:
            raise ValueError(f"expected {NUM_FEATURES} features, got {x.shape[1]}")
        z = (x - self.mean) / np.where(self.std > 1e-12, self.std, 1.0)
        logits = z @ self.coef.T + self.intercept
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def predict_fused(self, per_node_feats: Sequence[np.ndarray]) -> tuple[str, float, np.ndarray]:
        """Fuse several fresh nodes by summing per-node log-probabilities.

        Returns (class, confidence, fused_probabilities). Confidence is the
        fused posterior of the winning class.
        """
        if len(per_node_feats) == 0:
            raise ValueError("no node features to fuse")
        log_p = np.log(np.clip(self.predict_proba(np.vstack(per_node_feats)), 1e-9, 1.0)).sum(axis=0)
        log_p -= log_p.max()
        p = np.exp(log_p)
        p /= p.sum()
        best = int(np.argmax(p))
        return self.classes[best], float(p[best]), p

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": MODEL_SCHEMA,
            "kind": "activity-logreg",
            "classes": list(self.classes),
            "feature_names": list(FEATURE_NAMES),
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "coef": self.coef.tolist(),
            "intercept": self.intercept.tolist(),
            "window_s": self.window_s,
            "hop_s": self.hop_s,
            "meta": self.meta,
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ActivityModel":
        if data.get("schema") != MODEL_SCHEMA or data.get("kind") != "activity-logreg":
            raise ValueError("unsupported activity model file")
        if list(data["feature_names"]) != list(FEATURE_NAMES):
            raise ValueError("activity model was trained with a different feature set")
        return cls(
            classes=tuple(data["classes"]),
            mean=np.asarray(data["mean"], dtype=np.float64),
            std=np.asarray(data["std"], dtype=np.float64),
            coef=np.asarray(data["coef"], dtype=np.float64),
            intercept=np.asarray(data["intercept"], dtype=np.float64),
            window_s=float(data.get("window_s", 1.0)),
            hop_s=float(data.get("hop_s", 0.5)),
            meta=dict(data.get("meta", {})),
        )

    @classmethod
    def load(cls, path: Path | str) -> "ActivityModel":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
