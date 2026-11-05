"""T3: how separable are EMPTY recordings from each other (drift), per node and feature, versus time.

    python -m scripts.presence_eval.drift

Recordings are cut into 5-minute segments (the long s8/s9 recordings span many). For every pair of empty
segments the rank AUC is computed; an AUC far from 0.5 between two segments that are both labelled empty is
drift (or an unlabelled occupant) -- a presence score that has it cannot be calibrated from one empty reference.
``SEP_LO``/``SEP_HI``/``FLAG_SHARE`` are REPORTING conventions, not detector thresholds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import spearmanr

from .features import COVARIATES, FEATURES
from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .stats import auc
from .tables import RecTables, load_all, pick

OUT_DIR = default_out_dir()
SEG_S = 300
WIN_PER_SEG = int(SEG_S / 1.5)
MIN_SEG_WINDOWS = 60
SEP_LO, SEP_HI = 0.3, 0.7
FLAG_SHARE = 0.25
NODES = (1, 2, 3, 4)


@dataclass
class Segment:
    rid: str
    idx: int
    day: str
    start_s: float
    data: dict[int, dict[str, np.ndarray]]  # node -> column -> values (windows of this segment, NaNs removed per feature at use)


def make_segments(rec: RecTables, win_per_seg: int = WIN_PER_SEG, min_windows: int = MIN_SEG_WINDOWS) -> list[Segment]:
    segs: dict[int, dict[int, dict[str, np.ndarray]]] = {}
    for node, t in rec.nodes.items():
        sid = t["k"] // win_per_seg
        for s in np.unique(sid):
            m = sid == s
            if m.sum() >= min_windows:  # a node with too few windows in a segment is absent, never zero-filled
                segs.setdefault(int(s), {})[node] = {c: v[m] for c, v in t.items()}
    return [Segment(rec.rid, s, rec.day, s * win_per_seg * 1.5, d) for s, d in sorted(segs.items())]


def _vals(seg: Segment, node: int, col: str) -> np.ndarray | None:
    d = seg.data.get(node)
    if d is None:
        return None
    v = d[col]
    v = v[np.isfinite(v)]
    return v if v.size >= MIN_SEG_WINDOWS else None


def separable(a: float) -> bool:
    return bool(a <= SEP_LO or a >= SEP_HI)


def pair_table(segs: list[Segment], node: int, feat: str) -> list[dict]:
    out = []
    for a, b in combinations(segs, 2):
        va, vb = _vals(a, node, feat), _vals(b, node, feat)
        if va is None or vb is None:
            continue
        x = auc(va, vb)
        out.append({"a": f"{a.rid}#{a.idx}", "b": f"{b.rid}#{b.idx}", "auc": x, "same_day": a.day == b.day})
    return out


def summarize_pairs(pairs: list[dict]) -> dict:
    if not pairs:
        return {"n_pairs": 0, "share_separable": None, "median_abs_dev": None, "share_separable_same_day": None, "share_separable_cross_day": None, "drift_flag": None}
    sep = np.array([separable(p["auc"]) for p in pairs])
    same = np.array([p["same_day"] for p in pairs])
    return {
        "n_pairs": len(pairs),
        "share_separable": float(sep.mean()),
        "median_abs_dev": float(np.median([abs(p["auc"] - 0.5) for p in pairs])),
        "share_separable_same_day": float(sep[same].mean()) if same.any() else None,
        "share_separable_cross_day": float(sep[~same].mean()) if (~same).any() else None,
        "drift_flag": bool(sep.mean() >= FLAG_SHARE),
    }


def contrast_vs_empties(pos_segs: list[Segment], empties: list[Segment], node: int, feat: str) -> dict:
    aucs = []
    for p in pos_segs:
        vp = _vals(p, node, feat)
        for e in empties:
            ve = _vals(e, node, feat)
            if vp is not None and ve is not None:
                aucs.append(auc(vp, ve))
    if not aucs:
        return {"n": 0, "share_separable": None, "share_detect_dir": None, "median_auc": None}
    a = np.array(aucs)
    return {"n": len(a), "share_separable": float(np.mean([separable(x) for x in a])), "share_detect_dir": float(np.mean(a >= SEP_HI)), "median_auc": float(np.median(a))}


def seg_medians(segs: list[Segment], node: int, col: str) -> list[float | None]:
    out = []
    for s in segs:
        v = _vals(s, node, col) if col in FEATURES else (s.data[node][col] if node in s.data else None)
        out.append(None if v is None or len(v) == 0 else float(np.nanmedian(v)))
    return out


def shift_ratio(empty_day_segs: list[Segment], walk_seg: Segment | None, ref_seg: Segment | None, node: int, feat: str) -> dict:
    """Range of segment medians among same-day empties, versus the walking-minus-reference median shift."""
    meds = [m for m in seg_medians(empty_day_segs, node, feat) if m is not None]
    if len(meds) < 2 or walk_seg is None or ref_seg is None:
        return {"empty_median_range": None, "walking_shift": None, "ratio": None}
    vw, vr = _vals(walk_seg, node, feat), _vals(ref_seg, node, feat)
    if vw is None or vr is None:
        return {"empty_median_range": None, "walking_shift": None, "ratio": None}
    rng, shift = max(meds) - min(meds), float(np.median(vw) - np.median(vr))
    return {"empty_median_range": float(rng), "walking_shift": shift, "ratio": float(rng / abs(shift)) if shift else None}


def covariate_corr(segs: list[Segment], node: int, feat: str) -> dict:
    f, out = seg_medians(segs, node, feat), {}
    for cov in COVARIATES:
        c = seg_medians(segs, node, cov)
        pts = [(x, y) for x, y in zip(f, c) if x is not None and y is not None]
        if len(pts) < 6:
            out[cov] = None
            continue
        r = spearmanr([p[0] for p in pts], [p[1] for p in pts])
        out[cov] = {"rho": float(r.statistic), "p": float(r.pvalue), "n_segments": len(pts)}
    return out


def cross_node_correlation(rec: RecTables, feat: str, detrend_windows: int = 40) -> dict[str, float]:
    """Spearman correlation of window scores between node pairs on shared windows, after removing a slow
    running median (``detrend_windows`` = 60 s). A common occupant should co-elevate nodes at the same
    moments; independent per-node drift should not."""
    out: dict[str, float] = {}
    for a, b in combinations(sorted(rec.nodes), 2):
        ta, tb = rec.nodes[a], rec.nodes[b]
        common = np.intersect1d(ta["k"][np.isfinite(ta[feat])], tb["k"][np.isfinite(tb[feat])])
        if common.size < 4 * detrend_windows:
            continue
        va = ta[feat][np.searchsorted(ta["k"], common)]
        vb = tb[feat][np.searchsorted(tb["k"], common)]
        out[f"N{a}-N{b}"] = float(spearmanr(va - _running_median(va, detrend_windows), vb - _running_median(vb, detrend_windows)).statistic)
    return out


def _running_median(x: np.ndarray, w: int) -> np.ndarray:
    pad = np.pad(x, (w // 2, w - w // 2 - 1), mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(pad, w), axis=1)


def run(tabs: dict[str, RecTables] | None = None) -> dict:
    tabs = tabs or load_all()
    empties = [s for t in tabs.values() if t.label == "empty" for s in make_segments(t)]
    day27 = [s for s in empties if s.day == "20261027"]
    walk = make_segments(pick(tabs, "s7", "walking"))
    ref = [s for s in make_segments(pick(tabs, "s6", "empty"))]
    fan = make_segments(pick(tabs, "s5", "empty_fan"))
    res: dict = {
        "provenance": provenance("python -m scripts.presence_eval.drift", sorted(t.name for t in tabs.values() if t.label in ("empty", "walking", "empty_fan"))),
        "params": {"segment_s": SEG_S, "min_segment_windows": MIN_SEG_WINDOWS, "separable_if_auc_le": SEP_LO, "or_ge": SEP_HI, "drift_flag_if_share_ge": FLAG_SHARE, "note": "reporting conventions, not detector thresholds"},
        "empty_segments": [{"seg": f"{s.rid}#{s.idx}", "day": s.day, "start_s": s.start_s, "windows": {n: int(len(d["k"])) for n, d in s.data.items()}} for s in empties],
        "per_node_feature": {},
        "trajectory_27oct": {},
        "cross_node_detrended_spearman": {
            f"{sub}/{feat}": cross_node_correlation(pick(tabs, sub, "empty"), feat)
            for sub in ("s8", "s9") for feat in ("decor", "perturb_agc")
        },
    }
    for node in NODES:
        for feat in FEATURES:
            pairs = pair_table(empties, node, feat)
            res["per_node_feature"][f"N{node}/{feat}"] = {
                "empty_vs_empty": summarize_pairs(pairs),
                "walking_s7_vs_empty": contrast_vs_empties(walk, empties, node, feat),
                "fan_s5_vs_empty": contrast_vs_empties(fan, empties, node, feat),
                "shift_ratio_27oct": shift_ratio(day27, walk[0] if walk else None, ref[0] if ref else None, node, feat),
                "covariate_spearman_empty_segments": covariate_corr(empties, node, feat),
                "worst_pairs": sorted(pairs, key=lambda p: -abs(p["auc"] - 0.5))[:3],
            }
        for col in (*FEATURES, *COVARIATES):
            res["trajectory_27oct"][f"N{node}/{col}"] = {f"{s.rid}#{s.idx}": m for s, m in zip(day27, seg_medians(day27, node, col))}
    return res


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def render(res: dict) -> str:
    p = res["provenance"]
    L = [
        "# 03 — Drift characterisation (empty vs empty)",
        "",
        f"**Provenance.** `{p['command']}`, {p['date_utc']}, commit `{p['commit'][:7]}` (tree dirty: {p['working_tree_dirty']}), eval code `{p['eval_code_sha256_16']}`. Inputs: every recording labelled `empty` (and `empty_fan`, `walking` s7 for contrast) in `data/datasets/room1/`; listed in `results/drift.json`.",
        f"**Method.** Recordings cut into {SEG_S} s segments (all parts of s8/s9 included; segments with < {MIN_SEG_WINDOWS} windows per node are absent for that node). For each pair of *empty* segments, rank AUC of one against the other. \"Separable\" means AUC ≤ {SEP_LO} or ≥ {SEP_HI}; a node/feature is flagged DRIFT when ≥ {int(FLAG_SHARE * 100)} % of empty-vs-empty pairs are separable. These are reporting conventions chosen before the run, not detector thresholds. Segment-level AUCs have no CI here (the within-segment bootstrap does not cover the question being asked).",
        f"**Empty segments used:** {len(res['empty_segments'])}.",
        "",
        "## Table A — share of separable pairs (empty vs empty) against the walking and fan contrasts",
        "",
        "| node / feature | empty-vs-empty pairs | separable | same-day | cross-day | flag | walking s7 vs empties: separable / detect-direction (AUC ≥ 0.7) | fan s5 vs empties: separable |",
        "|--|--|--|--|--|--|--|--|",
    ]
    for key, d in res["per_node_feature"].items():
        e, w, f = d["empty_vs_empty"], d["walking_s7_vs_empty"], d["fan_s5_vs_empty"]
        L.append(f"| {key} | {e['n_pairs']} | {_pct(e['share_separable'])} | {_pct(e['share_separable_same_day'])} | {_pct(e['share_separable_cross_day'])} | {'**DRIFT**' if e['drift_flag'] else 'ok' if e['drift_flag'] is not None else '–'} | {_pct(w['share_separable'])} / {_pct(w['share_detect_dir'])} | {_pct(f['share_separable'])} |")
    L += ["", "## Table B — 27 Oct: spread of empty-segment medians versus the walking effect (s7 minus s6)", "", "| node / feature | range of empty-segment medians | walking shift (s7 − s6 median) | ratio range / |shift| |", "|--|--|--|--|"]
    for key, d in res["per_node_feature"].items():
        s = d["shift_ratio_27oct"]
        if s["ratio"] is not None:
            L.append(f"| {key} | {s['empty_median_range']:.4g} | {s['walking_shift']:.4g} | {s['ratio']:.1f} |")
    L += ["", "## Table C — Spearman correlation across empty segments: segment-median feature vs segment-median covariate", "", "| node / feature | vs RSSI (rho, p, n) | vs mean amplitude (rho, p, n) |", "|--|--|--|"]
    for key, d in res["per_node_feature"].items():
        c = d["covariate_spearman_empty_segments"]
        cell = lambda v: "–" if v is None else f"{v['rho']:+.2f}, p={v['p']:.3f}, n={v['n_segments']}"
        L.append(f"| {key} | {cell(c['rssi_med'])} | {cell(c['amp_mean'])} |")
    L += ["", "## Table D — 27 Oct empty segments: segment medians over time (`decor`, `perturb_agc`; RSSI dBm; windows of 5 min)", ""]
    segs = list(res["trajectory_27oct"]["N1/decor"].keys())
    L += ["| segment | " + " | ".join(f"N{n} decor / agc / rssi" for n in NODES) + " |", "|--|" + "--|" * len(NODES)]
    fmt = lambda v, n=3: "–" if v is None else f"{v:.{n}g}"
    for s in segs:
        row = [" / ".join([fmt(res["trajectory_27oct"][f"N{n}/decor"][s]), fmt(res["trajectory_27oct"][f"N{n}/perturb_agc"][s]), fmt(res["trajectory_27oct"][f"N{n}/rssi_med"][s], 3)]) for n in NODES]
        L.append(f"| {s} | " + " | ".join(row) + " |")
    L += ["", "## Table E — cross-node correlation of window scores inside the long empties (60 s running median removed)", "", "| recording / feature | " + " | ".join(["N1-N2", "N1-N3", "N1-N4", "N2-N3", "N2-N4", "N3-N4"]) + " |", "|--|--|--|--|--|--|--|"]
    for key, d in res["cross_node_detrended_spearman"].items():
        L.append(f"| {key} | " + " | ".join(f"{d[p]:+.2f}" if p in d else "–" for p in ("N1-N2", "N1-N3", "N1-N4", "N2-N3", "N2-N4", "N3-N4")) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "drift.json", res)
    (OUT_DIR / "results" / "drift_tables.md").write_text(render(res), encoding="utf-8")
    print("wrote results/drift.json and results/drift_tables.md")


if __name__ == "__main__":
    main()
