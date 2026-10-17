"""Train the per-room activity classifier from labelled recordings.

Honesty rules (docs/DATASET_PROTOCOL.md, JODDB Phase-2.3 gate):

* Evaluation is leave-one-GROUP-out, where a group is a whole recording (or a
  whole day). Windows of one recording are near-duplicates, so a random
  window split would report fantasy accuracy.
* The model is compared to two baselines on the SAME held-out groups:
  the majority class, and a "motion-energy heuristic" — a depth-3 decision
  tree on temporal_variance alone (what a threshold gate can already do).
* The model is EXPORTED ONLY if it beats both by a margin. Otherwise
  TrainingRefused is raised and nothing is written.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from phantom.activity_model import ACTIVITY_CLASSES, LABEL_TO_ACTIVITY, ActivityModel
from phantom.dataset import Recording
from phantom.features import FEATURE_NAMES, sliding_windows

MIN_GROUPS = 3
MIN_RECORDINGS_PER_CLASS = 2
MIN_WINDOWS_PER_CLASS = 20
MARGIN = 0.02
WINDOW_S = 1.0
HOP_S = 0.5
VARIANCE_IDX = FEATURE_NAMES.index("temporal_variance")


class TrainingRefused(RuntimeError):
    """The data/model did not meet the bar for export; nothing was written."""


def build_windows(
    recordings: Sequence[Recording], group_by: str, window_s: float = WINDOW_S, hop_s: float = HOP_S
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], np.ndarray]:
    """Return (X [N,F], y [N] class names, groups [N] group keys, skipped labels, rec_ids [N])."""
    xs: list[np.ndarray] = []
    ys: list[str] = []
    groups: list[str] = []
    rec_ids: list[str] = []
    skipped: list[str] = []
    for rec in recordings:
        activity = LABEL_TO_ACTIVITY.get(rec.label)
        if activity is None:
            skipped.append(rec.label)
            continue
        key = (rec.day or rec.recording_id) if group_by == "day" else rec.recording_id
        for stream in rec.nodes.values():
            for feats, _ in sliding_windows(stream.t_ms, stream.amps, stream.rssi, window_s, hop_s):
                xs.append(feats)
                ys.append(activity)
                groups.append(key)
                rec_ids.append(rec.recording_id)
    if not xs:
        return np.empty((0, len(FEATURE_NAMES))), np.array([]), np.array([]), skipped, np.array([])
    return np.vstack(xs), np.asarray(ys), np.asarray(groups), skipped, np.asarray(rec_ids)


def _permutation_null(
    x: np.ndarray, y: np.ndarray, groups: np.ndarray, rec_ids: np.ndarray, n_permutations: int, seed: int = 0
) -> np.ndarray:
    """Balanced accuracies of the same leave-one-group-out model when whole
    recordings' labels are shuffled among recordings — what the model scores
    when labels carry no information about the signal. With few recordings,
    chance alone can beat the fixed baselines by a small margin; the real
    score must also clear this null."""
    rng = np.random.default_rng(seed)
    unique_recs = np.unique(rec_ids)
    label_of = {r: y[rec_ids == r][0] for r in unique_recs}
    scores = []
    for _ in range(n_permutations):
        shuffled = rng.permutation([label_of[r] for r in unique_recs])
        mapping = dict(zip(unique_recs, shuffled))
        y_perm = np.asarray([mapping[r] for r in rec_ids])
        try:
            preds = _leave_one_group_out(x, y_perm, groups)
        except TrainingRefused:
            continue
        scores.append(float(balanced_accuracy_score(y_perm, preds["model"].astype(str))))
    return np.asarray(scores)


def _fit_logreg(x: np.ndarray, y: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler().fit(x)
    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    clf.fit(scaler.transform(x), y)
    return scaler, clf


def _leave_one_group_out(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> dict[str, np.ndarray]:
    preds = {
        "model": np.empty(len(y), dtype=object),
        "majority": np.empty(len(y), dtype=object),
        "heuristic": np.empty(len(y), dtype=object),
    }
    for g in np.unique(groups):
        test = groups == g
        train = ~test
        if len(np.unique(y[train])) < 2:
            raise TrainingRefused(f"holding out group '{g}' leaves fewer than 2 classes to train on")
        scaler, clf = _fit_logreg(x[train], y[train])
        preds["model"][test] = clf.predict(scaler.transform(x[test]))
        preds["majority"][test] = Counter(y[train]).most_common(1)[0][0]
        tree = DecisionTreeClassifier(max_depth=3, class_weight="balanced", random_state=0)
        tree.fit(x[train][:, [VARIANCE_IDX]], y[train])
        preds["heuristic"][test] = tree.predict(x[test][:, [VARIANCE_IDX]])
    return preds


def train_activity(
    recordings: Sequence[Recording],
    out_dir: Path | str,
    group_by: str = "recording",
    n_permutations: int = 50,
) -> dict[str, Any]:
    if group_by not in {"recording", "day"}:
        raise ValueError("group_by must be 'recording' or 'day'")
    out = Path(out_dir)
    x, y, groups, skipped, rec_ids = build_windows(recordings, group_by)

    rec_per_class = Counter(
        LABEL_TO_ACTIVITY[r.label] for r in recordings if LABEL_TO_ACTIVITY.get(r.label) is not None
    )
    class_counts = {c: int((y == c).sum()) for c in ACTIVITY_CLASSES}
    present = [c for c in ACTIVITY_CLASSES if class_counts[c] > 0]
    if len(present) < 2:
        raise TrainingRefused(f"need windows from at least 2 activity classes, found {present}")
    short = [
        c for c in present if rec_per_class[c] < MIN_RECORDINGS_PER_CLASS or class_counts[c] < MIN_WINDOWS_PER_CLASS
    ]
    if short:
        raise TrainingRefused(
            f"too few recordings/windows for {short} (need >= {MIN_RECORDINGS_PER_CLASS} recordings and "
            f">= {MIN_WINDOWS_PER_CLASS} windows each; have recordings={dict(rec_per_class)}, windows={class_counts})"
        )
    if len(np.unique(groups)) < MIN_GROUPS:
        raise TrainingRefused(f"need >= {MIN_GROUPS} held-out groups, found {len(np.unique(groups))} by {group_by}")

    preds = _leave_one_group_out(x, y, groups)
    scores = {name: float(balanced_accuracy_score(y, p.astype(str))) for name, p in preds.items()}
    metrics = {
        "model_balanced_accuracy": scores["model"],
        "majority_balanced_accuracy": scores["majority"],
        "heuristic_balanced_accuracy": scores["heuristic"],
        "margin_required": MARGIN,
    }
    null = _permutation_null(x, y, groups, rec_ids, n_permutations)
    null_p95 = float(np.percentile(null, 95)) if null.size else 1.0
    metrics["permutation_null_p95"] = null_p95
    metrics["permutation_null_runs"] = int(null.size)
    beats = scores["model"] > max(scores["majority"], scores["heuristic"]) + MARGIN and scores["model"] > null_p95
    labels = [c for c in ACTIVITY_CLASSES if c in present]
    report: dict[str, Any] = {
        "kind": "activity",
        "group_by": group_by,
        "groups": sorted(set(groups.tolist())),
        "classes": labels,
        "class_counts": class_counts,
        "skipped_labels": sorted(set(skipped)),
        "metrics": metrics,
        "confusion_matrix": {
            "labels": labels,
            "rows_true_cols_pred": confusion_matrix(y, preds["model"].astype(str), labels=labels).tolist(),
        },
        "exported": False,
        "note": "Per-room, advisory only. Do not claim accuracy outside the recorded room/subjects.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "activity.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not beats:
        raise TrainingRefused(
            f"model balanced accuracy {scores['model']:.3f} does not beat both baselines by {MARGIN} "
            f"(majority {scores['majority']:.3f}, motion heuristic {scores['heuristic']:.3f}) or the shuffled-label "
            f"null (95th pct {null_p95:.3f}); not exporting"
        )

    scaler, clf = _fit_logreg(x, y)
    digest = hashlib.sha256()
    for rec in sorted(recordings, key=lambda r: r.recording_id):
        digest.update(rec.recording_id.encode())
    model = ActivityModel(
        classes=tuple(str(c) for c in clf.classes_),
        mean=scaler.mean_,
        std=scaler.scale_,
        coef=clf.coef_,
        intercept=clf.intercept_,
        window_s=WINDOW_S,
        hop_s=HOP_S,
        meta={
            "room_id": recordings[0].room_id if recordings else "",
            "metrics": metrics,
            "group_by": group_by,
            "data_sha256": digest.hexdigest(),
            "recordings": len(recordings),
        },
    )
    model.save(out / "activity.json")
    report["exported"] = True
    (out / "activity.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
