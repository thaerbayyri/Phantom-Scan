"""Train the per-room people-count CNN (advisory) from labelled recordings.

Same honesty rules as phantom.activity_train:

* Cross-validation is GROUPED by whole recording — windows from one recording
  never appear in both train and test folds.
* Temperature is fitted on the OUT-OF-FOLD logits, and ECE before/after is
  reported, so the confidence the dashboard shows tracks real accuracy.
* The model is compared on the same held-out folds with a majority baseline
  and a 2-feature motion-energy decision tree (what a threshold gate can do),
  plus a shuffled-label permutation null. It is EXPORTED ONLY if it beats all
  three; otherwise TrainingRefused is raised and only the report is written.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn.functional as F
from safetensors.torch import save_file
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.tree import DecisionTreeClassifier

from phantom.activity_train import MARGIN, MIN_GROUPS, TrainingRefused
from phantom.count_model import (
    COUNT_CLASSES,
    NUM_SUBCARRIERS,
    WINDOW_FRAMES,
    CountNet,
    count_to_class,
    expected_calibration_error,
    prepare_window,
    softmax,
    temperature_scale,
)
from phantom.dataset import Recording

HOP_FRAMES = 20
MAX_WINDOW_SPAN_MS = 3000.0  # a 40-frame window spanning more than this has a gap
MIN_RECORDINGS_PER_CLASS = 2
MIN_WINDOWS_PER_CLASS = 40
MAX_FOLDS = 5


def build_count_windows(
    recordings: Sequence[Recording],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (windows [N, T, K], class index per window [N], recording id per window [N])."""
    wins: list[np.ndarray] = []
    ys: list[int] = []
    recs: list[str] = []
    for rec in recordings:
        cls = count_to_class(rec.count)
        for stream in rec.nodes.values():
            if stream.amps.shape[1] != NUM_SUBCARRIERS:
                continue
            for lo in range(0, len(stream.t_ms) - WINDOW_FRAMES + 1, HOP_FRAMES):
                hi = lo + WINDOW_FRAMES
                if stream.t_ms[hi - 1] - stream.t_ms[lo] > MAX_WINDOW_SPAN_MS:
                    continue
                wins.append(stream.amps[lo:hi])
                ys.append(cls)
                recs.append(rec.recording_id)
    if not wins:
        return np.empty((0, WINDOW_FRAMES, NUM_SUBCARRIERS)), np.array([], dtype=int), np.array([])
    return np.stack(wins), np.asarray(ys, dtype=int), np.asarray(recs)


def _fit_scale(windows: np.ndarray) -> float:
    raw = np.stack([prepare_window(w, 1.0) for w in windows])
    return float(max(raw.std(), 1e-6))


def _train_net(
    windows: np.ndarray, y: np.ndarray, num_classes: int, scale: float, epochs: int, seed: int
) -> CountNet:
    torch.manual_seed(seed)
    net = CountNet(num_classes=num_classes)
    x = torch.from_numpy(np.stack([prepare_window(w, scale) for w in windows]))
    t = torch.from_numpy(y).long()
    counts = np.bincount(y, minlength=num_classes).astype(np.float64)
    weight = torch.tensor(counts.sum() / (num_classes * np.maximum(counts, 1.0)), dtype=torch.float32)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    gen = torch.Generator().manual_seed(seed)
    net.train()
    for _ in range(epochs):
        order = torch.randperm(len(t), generator=gen)
        for i in range(0, len(order), 64):
            idx = order[i : i + 64]
            opt.zero_grad()
            F.cross_entropy(net(x[idx]), t[idx], weight=weight).backward()
            opt.step()
    net.eval()
    return net


def _logits(net: CountNet, windows: np.ndarray, scale: float) -> np.ndarray:
    x = torch.from_numpy(np.stack([prepare_window(w, scale) for w in windows]))
    with torch.no_grad():
        return net(x).numpy().astype(np.float64)


def _grouped_folds(rec_ids: np.ndarray, k: int) -> list[np.ndarray]:
    unique = sorted(np.unique(rec_ids).tolist())
    fold_of = {r: i % k for i, r in enumerate(unique)}
    assignment = np.asarray([fold_of[r] for r in rec_ids])
    return [np.where(assignment == f)[0] for f in range(k)]


def _out_of_fold(
    windows: np.ndarray, y: np.ndarray, rec_ids: np.ndarray, n_classes: int, epochs: int, seed: int
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Out-of-fold logits [N, C] plus baseline predictions (in compact class ids)."""
    k = min(MAX_FOLDS, len(np.unique(rec_ids)))
    logits = np.zeros((len(y), n_classes))
    majority = np.zeros(len(y), dtype=int)
    heuristic = np.zeros(len(y), dtype=int)
    rel = np.stack([prepare_window(w, 1.0) for w in windows])  # [N, K, T]
    feats = np.stack([rel.var(axis=(1, 2)), np.abs(np.diff(rel, axis=2)).mean(axis=(1, 2))], axis=1)
    for fold, test_idx in enumerate(_grouped_folds(rec_ids, k)):
        if test_idx.size == 0:
            continue
        train_mask = np.ones(len(y), dtype=bool)
        train_mask[test_idx] = False
        if len(np.unique(y[train_mask])) < 2:
            raise TrainingRefused("a held-out fold leaves fewer than 2 count classes to train on")
        scale = _fit_scale(windows[train_mask])
        net = _train_net(windows[train_mask], y[train_mask], n_classes, scale, epochs, seed + fold)
        logits[test_idx] = _logits(net, windows[test_idx], scale)
        majority[test_idx] = Counter(y[train_mask].tolist()).most_common(1)[0][0]
        tree = DecisionTreeClassifier(max_depth=3, class_weight="balanced", random_state=0)
        tree.fit(feats[train_mask], y[train_mask])
        heuristic[test_idx] = tree.predict(feats[test_idx])
    return logits, {"majority": majority, "heuristic": heuristic}


def _permutation_null(
    windows: np.ndarray, y: np.ndarray, rec_ids: np.ndarray, n_classes: int, epochs: int, n: int
) -> np.ndarray:
    rng = np.random.default_rng(0)
    unique = np.unique(rec_ids)
    label_of = {r: y[rec_ids == r][0] for r in unique}
    scores = []
    for i in range(n):
        shuffled = rng.permutation([label_of[r] for r in unique])
        mapping = dict(zip(unique, shuffled))
        y_perm = np.asarray([mapping[r] for r in rec_ids])
        try:
            logits, _ = _out_of_fold(windows, y_perm, rec_ids, n_classes, epochs, seed=100 + i)
        except TrainingRefused:
            continue
        scores.append(float(balanced_accuracy_score(y_perm, logits.argmax(axis=1))))
    return np.asarray(scores)


def train_count(
    recordings: Sequence[Recording],
    out_dir: Path | str,
    epochs: int = 25,
    n_permutations: int = 10,
    seed: int = 0,
) -> dict[str, Any]:
    out = Path(out_dir)
    windows, y_raw, rec_ids = build_count_windows(recordings)
    present = [c for c in COUNT_CLASSES if (y_raw == c).any()]
    if len(present) < 2:
        raise TrainingRefused(f"need windows from at least 2 count classes, found {present}")
    class_map = {c: i for i, c in enumerate(present)}  # count class -> compact id
    y = np.asarray([class_map[c] for c in y_raw])

    recs_per_class = Counter(count_to_class(r.count) for r in recordings)
    short = [
        c
        for c in present
        if recs_per_class[c] < MIN_RECORDINGS_PER_CLASS or int((y_raw == c).sum()) < MIN_WINDOWS_PER_CLASS
    ]
    if short:
        raise TrainingRefused(
            f"too few recordings/windows for count class(es) {short} (need >= {MIN_RECORDINGS_PER_CLASS} "
            f"recordings and >= {MIN_WINDOWS_PER_CLASS} windows each; recordings={dict(recs_per_class)})"
        )
    if len(np.unique(rec_ids)) < MIN_GROUPS:
        raise TrainingRefused(f"need >= {MIN_GROUPS} recordings, found {len(np.unique(rec_ids))}")

    n_classes = len(present)
    logits, baselines = _out_of_fold(windows, y, rec_ids, n_classes, epochs, seed)
    temperature = temperature_scale(logits, y)
    pred = logits.argmax(axis=1)
    scores = {
        "model": float(balanced_accuracy_score(y, pred)),
        "majority": float(balanced_accuracy_score(y, baselines["majority"])),
        "heuristic": float(balanced_accuracy_score(y, baselines["heuristic"])),
    }
    null = _permutation_null(windows, y, rec_ids, n_classes, epochs, n_permutations)
    null_p95 = float(np.percentile(null, 95)) if null.size else 1.0
    metrics = {
        "model_balanced_accuracy": scores["model"],
        "majority_balanced_accuracy": scores["majority"],
        "heuristic_balanced_accuracy": scores["heuristic"],
        "permutation_null_p95": null_p95,
        "permutation_null_runs": int(null.size),
        "margin_required": MARGIN,
        "temperature": temperature,
        "ece_before": expected_calibration_error(softmax(logits), y),
        "ece_after": expected_calibration_error(softmax(logits, temperature), y),
    }
    labels = list(range(n_classes))
    report: dict[str, Any] = {
        "kind": "count",
        "classes": present,
        "window_counts": {int(c): int((y_raw == c).sum()) for c in present},
        "recordings": len(np.unique(rec_ids)),
        "metrics": metrics,
        "confusion_matrix": {
            "labels": present,
            "rows_true_cols_pred": confusion_matrix(y, pred, labels=labels).tolist(),
        },
        "exported": False,
        "note": "Per-room, advisory only; '2' means two or more. Do not claim accuracy outside the recorded room.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "count.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    beats = scores["model"] > max(scores["majority"], scores["heuristic"]) + MARGIN and scores["model"] > null_p95
    if not beats:
        raise TrainingRefused(
            f"model balanced accuracy {scores['model']:.3f} does not beat both baselines by {MARGIN} "
            f"(majority {scores['majority']:.3f}, motion heuristic {scores['heuristic']:.3f}) or the shuffled-label "
            f"null (95th pct {null_p95:.3f}); not exporting"
        )

    scale = _fit_scale(windows)
    net = _train_net(windows, y, n_classes, scale, epochs, seed + 999)
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(out / "count.safetensors"))
    digest = hashlib.sha256("".join(sorted(r.recording_id for r in recordings)).encode()).hexdigest()
    (out / "count.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "count-cnn",
                "classes": present,
                "window_frames": WINDOW_FRAMES,
                "num_subcarriers": NUM_SUBCARRIERS,
                "scale": scale,
                "temperature": temperature,
                "metrics": metrics,
                "data_sha256": digest,
                "room_id": recordings[0].room_id if recordings else "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report["exported"] = True
    (out / "count.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
