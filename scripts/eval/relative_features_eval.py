"""Compare absolute vs session-relative window features with leave-one-session-out logistic regression.

Usage: python -m scripts.eval.relative_features_eval {reporafin|train-ep2}

Each session must contain an empty recording; its first 30 % of windows calibrate that session (never evaluated).
Prints balanced accuracy and the confusion matrix for both feature sets. Read-only; writes nothing.
"""
from __future__ import annotations

import sys
from collections import defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.preprocessing import StandardScaler

from phantom.activity_model import LABEL_TO_ACTIVITY
from phantom.dataset import Recording, load_room_dataset, without_nodes
from phantom.features import sliding_windows
from phantom.session_norm import relative_to_baseline, split_baseline


def _windows(rec: Recording) -> np.ndarray:
    feats = [f for s in rec.nodes.values() for f, _ in sliding_windows(s.t_ms, s.amps, s.rssi, 1.0, 0.5)]
    return np.vstack(feats) if feats else np.empty((0, 15))


def build(recordings: list[Recording], session_of) -> dict[str, dict[str, np.ndarray]]:
    """session -> {'abs': X, 'rel': X, 'y': labels, 'rec': recording ids}"""
    by_session: dict[str, list[Recording]] = defaultdict(list)
    for r in recordings:
        by_session[session_of(r)].append(r)
    out = {}
    for sess, recs in by_session.items():
        empties = [r for r in recs if LABEL_TO_ACTIVITY.get(r.label) == "empty"]
        if not empties:
            raise SystemExit(f"session {sess} has no empty recording to calibrate")
        calib_rec = sorted(empties, key=lambda r: r.recording_id)[0]
        xs, ys, ids, calib = [], [], [], None
        for r in recs:
            w = _windows(r)
            if r is calib_rec:
                calib, w = split_baseline(w, 0.3)
            xs.append(w)
            ys += [LABEL_TO_ACTIVITY[r.label]] * len(w)
            ids += [r.recording_id] * len(w)
        x = np.vstack(xs)
        out[sess] = {"abs": x, "rel": relative_to_baseline(x, calib), "y": np.asarray(ys), "rec": np.asarray(ids)}
    return out


def _fit_predict(xtr, ytr, xte):
    scaler = StandardScaler().fit(xtr)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(scaler.transform(xtr), ytr)
    return clf.predict(scaler.transform(xte))


def evaluate(data: dict, holdout: str) -> None:
    """holdout = 'session' (leave one session out) or 'recording' (leave one recording out, all sessions)."""
    labels = sorted({c for d in data.values() for c in d["y"]})
    for kind in ("abs", "rel"):
        x = np.vstack([d[kind] for d in data.values()])
        y = np.concatenate([d["y"] for d in data.values()])
        key = np.concatenate([[s] * len(d["y"]) for s, d in data.items()]) if holdout == "session" else np.concatenate(
            [d["rec"] for d in data.values()])
        pred = np.empty(len(y), dtype=object)
        for g in np.unique(key):
            te = key == g
            if len(set(y[~te])) < 2:
                pred[te] = y[~te][0]
                continue
            pred[te] = _fit_predict(x[~te], y[~te], x[te])
        print(f"  {kind:3s}  balanced accuracy {balanced_accuracy_score(y, pred.astype(str)):.3f}  "
              f"confusion {labels}: {confusion_matrix(y, pred.astype(str), labels=labels).tolist()}")


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "reporafin"
    if which == "reporafin":
        from phantom.external.reporafin import load_reporafin_dataset

        recs = load_reporafin_dataset("data/datasets/external-esp32-csi-pipeline/dataset")
        data = build(recs, lambda r: r.day)
        print("reporafin, leave one session out (3 sessions):")
        evaluate(data, "session")
    elif which == "train-ep2":
        recs = without_nodes(load_room_dataset("data/datasets", "train-ep2-2026-11"), (3,))
        data = build(recs, lambda r: r.day)
        print("train-ep2-2026-11 (nodes 1, 2, 4), one session, leave one recording out:")
        evaluate(data, "recording")
    else:
        print("usage: relative_features_eval {reporafin|train-ep2}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
