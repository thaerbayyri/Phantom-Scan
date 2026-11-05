"""Window features for the offline presence evaluation.

Definitions (from the task brief; own implementation). ``a`` is a (k, 51) amplitude
window, ``rssi`` is (k,). All statistics are population (ddof=0).

* ``perturb``     mean over subcarriers of std_t / mean_t (raw amplitudes; invariant to a gain
                  applied to the WHOLE window, NOT to a per-frame gain).
* ``perturb_agc`` the repo's ``computeAgcNormalizedPerturbation``: each frame divided by its own
                  mean first (per-frame gain invariant), then as ``perturb`` with std on normalised values.
* ``decor``       1 - mean cosine similarity of consecutive frames after subtracting each frame's
                  mean across subcarriers and L2-normalising (per-frame gain invariant). A TEMPORAL
                  signal feature: it is not a spatial angle.
* ``gainstd``     std_t / mean_t of the per-frame mean amplitude.
* ``rssistd``     std of RSSI in the window.
"""
from __future__ import annotations

import numpy as np

from .recordings import NodeSeries

WINDOW_MS = 1500
MIN_FRAMES = 20
EPS = 1e-9
FEATURES = ("perturb", "perturb_agc", "decor", "gainstd", "rssistd")
COVARIATES = ("rssi_med", "amp_mean")  # per-window context, never used as detection scores


def window_features(a: np.ndarray, rssi: np.ndarray | None = None) -> dict[str, float]:
    a = np.asarray(a, dtype=np.float64)
    out = {f: float("nan") for f in FEATURES}
    if a.ndim != 2 or a.shape[0] < 2:
        return out
    mean_t, std_t = a.mean(axis=0), a.std(axis=0)
    ok = mean_t > EPS
    if ok.any():
        out["perturb"] = float(np.mean(std_t[ok] / mean_t[ok]))
    frame_mean = a.mean(axis=1)
    good = frame_mean > EPS
    if good.sum() >= 2:
        n = a[good] / frame_mean[good, None]
        # repo definition: mean over subcarriers of the std (over time) of mean-normalised amplitudes
        out["perturb_agc"] = float(np.mean(n.std(axis=0)))
    if frame_mean.mean() > EPS:
        out["gainstd"] = float(frame_mean.std() / frame_mean.mean())
    v = a - frame_mean[:, None]
    norm = np.linalg.norm(v, axis=1)
    valid = norm > EPS
    v = v / np.where(valid, norm, 1.0)[:, None]
    pair_ok = valid[1:] & valid[:-1]
    if pair_ok.any():
        cos = np.sum(v[1:] * v[:-1], axis=1)[pair_ok]
        out["decor"] = float(1.0 - cos.mean())
    if rssi is not None:
        r = np.asarray(rssi, dtype=np.float64)
        r = r[np.isfinite(r)]
        if r.size >= 2:
            out["rssistd"] = float(r.std())
    return out


def node_windows(series: NodeSeries, t0_ms: int, win_ms: int = WINDOW_MS, min_frames: int = MIN_FRAMES) -> dict[str, np.ndarray]:
    """Tumbling windows (index k = (t - t0) // win_ms). Windows with < ``min_frames`` frames are dropped."""
    k_all = (series.t - t0_ms) // win_ms
    bounds = np.flatnonzero(np.diff(k_all)) + 1
    starts = np.concatenate([[0], bounds])
    ends = np.concatenate([bounds, [len(k_all)]])
    keep = [(s, e) for s, e in zip(starts, ends) if e - s >= min_frames and k_all[s] >= 0]
    cols: dict[str, list[float]] = {f: [] for f in (*FEATURES, *COVARIATES)}
    ks, nf = [], []
    for s, e in keep:
        feats = window_features(series.a[s:e], series.rssi[s:e])
        for f in FEATURES:
            cols[f].append(feats[f])
        r = series.rssi[s:e]
        cols["rssi_med"].append(float(np.nanmedian(r)) if np.isfinite(r).any() else float("nan"))
        cols["amp_mean"].append(float(series.a[s:e].mean()))
        ks.append(int(k_all[s]))
        nf.append(e - s)
    out = {f: np.asarray(v, dtype=np.float64) for f, v in cols.items()}
    out["k"] = np.asarray(ks, dtype=np.int64)
    out["nframes"] = np.asarray(nf, dtype=np.int64)
    return out


def fuse_max(tables: dict[int, dict[str, np.ndarray]], nodes: tuple[int, ...], feature: str) -> tuple[np.ndarray, np.ndarray]:
    """Per-window max over ``nodes`` on the windows where ALL those nodes have a finite value (inner join)."""
    return fuse(tables, nodes, feature, np.max)


def fuse(tables: dict[int, dict[str, np.ndarray]], nodes: tuple[int, ...], feature: str, reducer) -> tuple[np.ndarray, np.ndarray]:
    if any(n not in tables for n in nodes):
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    common = None
    for n in nodes:
        t = tables[n]
        ks = t["k"][np.isfinite(t[feature])]
        common = ks if common is None else np.intersect1d(common, ks)
    cols = []
    for n in nodes:
        t = tables[n]
        idx = np.searchsorted(t["k"], common)
        cols.append(t[feature][idx])
    if common is None or common.size == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    return common, reducer(np.vstack(cols), axis=0)
