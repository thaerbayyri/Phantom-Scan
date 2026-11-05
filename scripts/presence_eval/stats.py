"""Rank-based AUC and moving-block bootstrap confidence intervals.

AUC = P(score_pos > score_neg) + 0.5 P(equal); 0.5 is chance. Consecutive windows are
autocorrelated, so the CI resamples contiguous BLOCKS of windows (default >= 10 s) separately
within each class, with a fixed seed. The CI covers within-recording sampling variability only;
it does not cover between-session drift (that is what the cross-recording protocols are for).
"""
from __future__ import annotations

import math

import numpy as np

WINDOW_S = 1.5
BLOCK_S = 10.0
DEFAULT_BLOCK = math.ceil(BLOCK_S / WINDOW_S)  # 7 windows = 10.5 s
DEFAULT_BOOT = 1000
DEFAULT_SEED = 20261102


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney AUC with average ranks for ties. NaN if either class is empty."""
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    n_p, n_n = pos.size, neg.size
    if n_p == 0 or n_n == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    _, inv, counts = np.unique(allv, return_inverse=True, return_counts=True)
    first_rank = np.cumsum(counts) - counts + 1
    avg_rank = first_rank + (counts - 1) / 2.0
    ranks = avg_rank[inv]
    u = ranks[:n_p].sum() - n_p * (n_p + 1) / 2.0
    return float(u / (n_p * n_n))


def _block_resample(x: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    m = x.size
    b = max(1, min(block, m))
    n_blocks = math.ceil(m / b)
    starts = rng.integers(0, m - b + 1, size=n_blocks)
    idx = (starts[:, None] + np.arange(b)[None, :]).ravel()[:m]
    return x[idx]


def block_bootstrap_rate(
    flags: np.ndarray, block: int = DEFAULT_BLOCK, n_boot: int = DEFAULT_BOOT, seed: int = DEFAULT_SEED
) -> dict:
    """Share of True in a time-ordered boolean series, with a moving-block bootstrap 95 % CI."""
    x = np.asarray(flags, dtype=np.float64)
    if x.size == 0:
        return {"rate": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    vals = np.array([_block_resample(x, block, rng).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"rate": float(x.mean()), "lo": float(lo), "hi": float(hi), "n": int(x.size)}


def block_bootstrap_rate_diff(
    a_flags: np.ndarray, b_flags: np.ndarray, block: int = DEFAULT_BLOCK, n_boot: int = DEFAULT_BOOT, seed: int = DEFAULT_SEED
) -> dict:
    """d = share(a) - share(b) of two time-ordered boolean series, with a 95 % percentile CI from a moving-block bootstrap (each series resampled on its own)."""
    a = np.asarray(a_flags, dtype=np.float64)
    b = np.asarray(b_flags, dtype=np.float64)
    if a.size == 0 or b.size == 0:
        return {"d": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_a": int(a.size), "n_b": int(b.size)}
    rng = np.random.default_rng(seed)
    vals = np.array([_block_resample(a, block, rng).mean() - _block_resample(b, block, rng).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"d": float(a.mean() - b.mean()), "lo": float(lo), "hi": float(hi), "n_a": int(a.size), "n_b": int(b.size), "block": block, "n_boot": n_boot, "seed": seed}


def session_block_auc(
    pos_by_rec: dict[str, np.ndarray],
    neg_by_rec: dict[str, np.ndarray],
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_BOOT,
    seed: int = DEFAULT_SEED,
    min_windows: int = 20,
) -> dict:
    """AUC with a CI that resamples whole RECORDINGS (sessions) with replacement, then blocks inside each.

    This is the honest interval when windows come from few recordings: it includes between-recording variance.
    Needs >= 2 recordings per class; otherwise the interval is null with a reason (never a fabricated one).
    """
    pos_by_rec = {k: np.asarray(v, dtype=np.float64) for k, v in pos_by_rec.items() if len(v) >= min_windows}
    neg_by_rec = {k: np.asarray(v, dtype=np.float64) for k, v in neg_by_rec.items() if len(v) >= min_windows}
    pos = np.concatenate(list(pos_by_rec.values())) if pos_by_rec else np.zeros(0)
    neg = np.concatenate(list(neg_by_rec.values())) if neg_by_rec else np.zeros(0)
    out = {"auc": auc(pos, neg), "lo": None, "hi": None, "n_pos_recordings": len(pos_by_rec), "n_neg_recordings": len(neg_by_rec)}
    if len(pos_by_rec) < 2 or len(neg_by_rec) < 2:
        out["reason"] = "insufficient data: session-blocked CI needs >= 2 recordings in each class"
        return out
    rng = np.random.default_rng(seed)
    pk, nk = list(pos_by_rec), list(neg_by_rec)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        ps = np.concatenate([_block_resample(pos_by_rec[pk[j]], block, rng) for j in rng.integers(0, len(pk), len(pk))])
        ns = np.concatenate([_block_resample(neg_by_rec[nk[j]], block, rng) for j in rng.integers(0, len(nk), len(nk))])
        vals[i] = auc(ps, ns)
    out["lo"], out["hi"] = (float(x) for x in np.percentile(vals, [2.5, 97.5]))
    return out


EMPTY_PAIR_UPPER_BOUND = 0.65


def empty_pair_control(by_rec: dict[str, np.ndarray], block: int = DEFAULT_BLOCK, n_boot: int = DEFAULT_BOOT, seed: int = DEFAULT_SEED, min_windows: int = 60) -> dict:
    """Negative control: a score that separates two EMPTY recordings is drifting, not detecting.

    For every pair the AUC is symmetrised (max(AUC, 1-AUC) with the matching CI bound); the control passes only if
    the symmetric UPPER bound is <= EMPTY_PAIR_UPPER_BOUND for every pair. Fewer than 2 usable empties -> null.
    """
    usable = {k: np.asarray(v, dtype=np.float64) for k, v in by_rec.items() if len(v) >= min_windows}
    names = sorted(usable)
    if len(names) < 2:
        return {"passes": None, "reason": "insufficient data: needs >= 2 empty recordings", "pairs": []}
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r = block_bootstrap_auc(usable[a], usable[b], block=block, n_boot=n_boot, seed=seed)
            sym_hi = max(r["hi"], 1.0 - r["lo"])
            pairs.append({"a": a, "b": b, "auc": r["auc"], "lo": r["lo"], "hi": r["hi"], "symmetric_upper_bound": sym_hi, "ok": bool(sym_hi <= EMPTY_PAIR_UPPER_BOUND)})
    worst = max(p["symmetric_upper_bound"] for p in pairs)
    return {"passes": bool(all(p["ok"] for p in pairs)), "worst_symmetric_upper_bound": worst, "threshold": EMPTY_PAIR_UPPER_BOUND, "pairs": pairs}


def block_bootstrap_auc(
    pos: np.ndarray, neg: np.ndarray, block: int = DEFAULT_BLOCK, n_boot: int = DEFAULT_BOOT, seed: int = DEFAULT_SEED
) -> dict:
    """Point AUC and a 95 % percentile CI from a moving-block bootstrap (time-ordered inputs)."""
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    point = auc(pos, neg)
    if pos.size == 0 or neg.size == 0:
        return {"auc": point, "lo": float("nan"), "hi": float("nan"), "n_pos": int(pos.size), "n_neg": int(neg.size)}
    rng = np.random.default_rng(seed)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        vals[i] = auc(_block_resample(pos, block, rng), _block_resample(neg, block, rng))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"auc": point, "lo": float(lo), "hi": float(hi), "n_pos": int(pos.size), "n_neg": int(neg.size), "block": block, "n_boot": n_boot, "seed": seed}
