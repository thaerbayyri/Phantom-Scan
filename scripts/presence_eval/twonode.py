"""T4: two-node (N1, N2) evaluation harness -- scores, fusion rules, three protocols, leakage-proof API.

    python -m scripts.presence_eval.twonode --write-prereg     # freeze acceptance criteria BEFORE the run
    python -m scripts.presence_eval.twonode                    # run all protocols

Scores: per window and node, ``z = (x - median_ref) / (1.4826 * MAD_ref)`` where the reference is the node's own
training-empty windows. Fusion over (z1, z2): n1, n2, max (== OR), mean, and (== min, i.e. AND). The detection
threshold for a target false-positive rate alpha is the (1 - alpha) quantile of the TRAINING-empty fused scores.
``fit_model`` receives only training recordings, so the test recording cannot influence a threshold or baseline.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .stats import DEFAULT_BLOCK, EMPTY_PAIR_UPPER_BOUND, auc, block_bootstrap_auc, block_bootstrap_rate, empty_pair_control, session_block_auc
from .tables import RecTables, load_all

OUT_DIR = default_out_dir()
NODES = (1, 2)
FEATS = ("perturb", "perturb_agc", "decor")
RULES = ("n1", "n2", "max", "mean", "and")  # "or" is identical to "max" for a threshold on max(z1, z2)
ALPHAS = (0.01, 0.05)
MIN_WIN = 60
N_BOOT = 500
WINDOW_S = 1.5
CRITERIA = {
    "C1": "lower 95% block-bootstrap CI bound of walking-vs-empty AUC >= 0.80 in protocol (b) AND in every applicable train session of protocol (c)",
    "C2": "fan false-positive rate not above empty false-positive rate (pooled, at both alpha = 1% and 5%) in protocols (b) and (c)",
    "C3": "no held-out empty recording flagged occupied in more than 5% of windows at the alpha = 1% threshold, in protocols (b) and (c)",
    "C4": "(added in fix-2026-11, stricter; C1-C3 unchanged) empty-vs-empty negative control: for every pair of held-out empty recordings the symmetric AUC upper 95% bound is <= 0.65, in protocols (b) and (c)",
    "C1_auc_lower_bound": 0.80,
    "C3_max_flag_share": 0.05,
    "C4_max_empty_pair_upper_bound": EMPTY_PAIR_UPPER_BOUND,
    "verdict_rule": "a candidate (feature, rule) meets the criteria only if C1, C2, C3 and C4 all hold; if none does, the report says so and stops",
}


class LeakageError(ValueError):
    """Raised when a model would be fit on something that is not a pure training set."""


class InsufficientData(ValueError):
    pass


def pair_series(rec: RecTables, feature: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Windows where BOTH N1 and N2 have a finite value (inner join; no zero-filling)."""
    if any(n not in rec.nodes for n in NODES):
        e = np.zeros(0)
        return e.astype(np.int64), e, e
    t1, t2 = rec.nodes[1], rec.nodes[2]
    common = np.intersect1d(t1["k"][np.isfinite(t1[feature])], t2["k"][np.isfinite(t2[feature])])
    return common, t1[feature][np.searchsorted(t1["k"], common)], t2[feature][np.searchsorted(t2["k"], common)]


def combine(z1: np.ndarray, z2: np.ndarray, rule: str) -> np.ndarray:
    if rule == "n1":
        return z1
    if rule == "n2":
        return z2
    if rule == "max":
        return np.maximum(z1, z2)
    if rule == "mean":
        return (z1 + z2) / 2.0
    if rule == "and":
        return np.minimum(z1, z2)
    raise ValueError(rule)


@dataclass(frozen=True)
class Model:
    feature: str
    rule: str
    med: tuple[float, float]
    mad: tuple[float, float]
    thr: tuple[tuple[float, float], ...]  # ((alpha, threshold), ...)
    train_ids: tuple[str, ...]

    def threshold(self, alpha: float) -> float:
        return dict(self.thr)[alpha]


def fit_model(train: Sequence[RecTables], feature: str, rule: str, alphas: Sequence[float] = ALPHAS) -> Model:
    """Baseline (median/MAD per node) and thresholds from TRAINING-EMPTY recordings only.

    The test recording is not an argument, so it cannot be seen. Non-empty recordings are refused.
    """
    if any(r.label != "empty" for r in train):
        raise LeakageError("only recordings labelled 'empty' may be used to fit a baseline/threshold")
    ids = tuple(r.rid for r in train)
    if len(set(ids)) != len(ids):
        raise LeakageError("duplicate training recording")
    parts = [pair_series(r, feature) for r in train]
    x1 = np.concatenate([p[1] for p in parts]) if parts else np.zeros(0)
    x2 = np.concatenate([p[2] for p in parts]) if parts else np.zeros(0)
    if x1.size < MIN_WIN:
        raise InsufficientData(f"{x1.size} training windows < {MIN_WIN}")
    med = (float(np.median(x1)), float(np.median(x2)))
    mad = tuple(max(1.4826 * float(np.median(np.abs(x - m))), 1e-9) for x, m in ((x1, med[0]), (x2, med[1])))
    z = combine((x1 - med[0]) / mad[0], (x2 - med[1]) / mad[1], rule)
    return Model(feature, rule, med, mad, tuple((a, float(np.quantile(z, 1.0 - a))) for a in alphas), ids)  # type: ignore[arg-type]


def score(model: Model, rec: RecTables) -> tuple[np.ndarray, np.ndarray]:
    k, x1, x2 = pair_series(rec, model.feature)
    return k, combine((x1 - model.med[0]) / model.mad[0], (x2 - model.med[1]) / model.mad[1], model.rule)


@dataclass(frozen=True)
class Split:
    protocol: str            # adjacent | loro | cross_session
    test_id: str
    train_ids: tuple[str, ...]
    group: str               # which model-group results are pooled in


def assert_disjoint(split: Split) -> None:
    if split.test_id in split.train_ids:
        raise LeakageError(f"test recording {split.test_id} is in its own training set")


def splits_loro(recs: dict[str, RecTables]) -> list[Split]:
    out = []
    for rid in recs:
        train = tuple(r for r, t in recs.items() if t.label == "empty" and r != rid)
        if train:
            out.append(Split("loro", rid, train, "pooled"))
    return out


def splits_adjacent(recs: dict[str, RecTables]) -> list[Split]:
    out = []
    for rid, t in recs.items():
        cands = [(abs(o.t0_ms - t.t0_ms), r) for r, o in recs.items() if o.label == "empty" and r != rid and o.day == t.day]
        if cands:
            base = min(cands)[1]
            out.append(Split("adjacent", rid, (base,), base))
    return out


def splits_cross_session(recs: dict[str, RecTables]) -> list[Split]:
    out = []
    for day in sorted({t.day for t in recs.values() if t.label == "empty"}):
        train = tuple(r for r, t in recs.items() if t.label == "empty" and t.day == day)
        out += [Split("cross_session", rid, train, f"train_{day}") for rid, t in recs.items() if t.day != day]
    return out


def first_detect(k: np.ndarray, flags: np.ndarray, run: int = 1) -> float | None:
    """Seconds from the recording's first window grid origin to the first run of `run` consecutive flagged windows."""
    for i in range(len(flags) - run + 1):
        if flags[i : i + run].all() and (run == 1 or np.all(np.diff(k[i : i + run]) == 1)):
            return float(k[i] * WINDOW_S)
    return None


def run_candidate(recs: dict[str, RecTables], splits: Sequence[Split], feature: str, rule: str) -> list[dict]:
    rows = []
    for sp in splits:
        assert_disjoint(sp)
        try:
            model = fit_model([recs[r] for r in sp.train_ids], feature, rule)
        except InsufficientData:
            continue
        t = recs[sp.test_id]
        k, s = score(model, t)
        ks = [tab["k"].max() for n, tab in t.nodes.items() if n in NODES and tab["k"].size]
        n_grid = int(max(ks)) + 1 if ks else 0  # windows on the recording's time grid; those without a joint N1+N2 score are abstentions
        row = {"protocol": sp.protocol, "group": sp.group, "test": sp.test_id, "label": t.label, "k": k, "s": s, "model": model, "n_grid": n_grid}
        if sp.protocol == "adjacent":  # in-sample reference: the baseline scored by its own model
            bk, bs = score(model, recs[sp.train_ids[0]])
            row["baseline_scores"] = bs
        rows.append(row)
    return rows


def _flags(rows: list[dict], alpha: float) -> np.ndarray:
    return np.concatenate([r["s"] >= r["model"].threshold(alpha) for r in rows]) if rows else np.zeros(0, dtype=bool)


def _grid_flags(rows: list[dict], alpha: float) -> np.ndarray:
    """Detections on the full time grid: windows without a score (abstentions) are counted as NOT detected (misses)."""
    parts = []
    for r in rows:
        arr = np.zeros(r["n_grid"], dtype=bool)
        arr[r["k"]] = r["s"] >= r["model"].threshold(alpha)
        parts.append(arr)
    return np.concatenate(parts) if parts else np.zeros(0, dtype=bool)


def sensitivity_control(recs: dict[str, RecTables]) -> dict:
    """An always-'absent' scorer must be REJECTED by the harness (a model that never fires cannot pass)."""
    walk = [t for t in recs.values() if t.label == "walking" and all(n in t.nodes for n in NODES)]
    emp = [t for t in recs.values() if t.label == "empty" and all(n in t.nodes for n in NODES)]
    n_pos = sum(len(pair_series(t, "decor")[0]) for t in walk)
    n_neg = sum(len(pair_series(t, "decor")[0]) for t in emp)
    if n_pos < MIN_WIN or n_neg < MIN_WIN:
        return {"evaluable": False, "reason": "insufficient data"}
    r = block_bootstrap_auc(np.zeros(n_pos), np.zeros(n_neg), n_boot=N_BOOT)
    tpr = block_bootstrap_rate(np.zeros(n_pos, dtype=bool), n_boot=N_BOOT)  # threshold above every score: never fires
    return {"evaluable": True, "constant_scorer_auc": r, "never_fires_tpr": tpr, "rejected_by_C1": bool(r["lo"] < CRITERIA["C1_auc_lower_bound"])}


def aggregate(rows: list[dict]) -> dict:
    """Per (protocol, group) metrics with block-bootstrap CIs; 'insufficient data' instead of a number when thin."""
    out: dict = {}
    for key in sorted({(r["protocol"], r["group"]) for r in rows}):
        g = [r for r in rows if (r["protocol"], r["group"]) == key]
        by = lambda lab: [r for r in g if r["label"] == lab and len(r["s"]) >= MIN_WIN]
        neg = by("empty")
        negs = np.concatenate([r["s"] for r in neg]) if neg else np.zeros(0)
        cell: dict = {"n_empty_windows": int(negs.size), "auc": {}, "auc_session_blocked": {}, "tpr": {}, "tpr_abstain_as_miss": {}, "abstention_share": {}, "fpr": {}, "ttfd_s": {},
                      "empty_vs_empty_control": empty_pair_control({r["test"]: r["s"] for r in neg})}
        for cls in ("walking", "still", "two_people"):
            pos = by(cls)
            ps = np.concatenate([r["s"] for r in pos]) if pos else np.zeros(0)
            if ps.size < MIN_WIN or negs.size < MIN_WIN:
                cell["auc"][cls] = "insufficient data"
            else:
                cell["auc"][cls] = block_bootstrap_auc(ps, negs, n_boot=N_BOOT)
            cell["auc_session_blocked"][cls] = session_block_auc({r["test"]: r["s"] for r in pos}, {r["test"]: r["s"] for r in neg}, n_boot=N_BOOT) if pos and neg else "insufficient data"
            grid = sum(r["n_grid"] for r in pos)
            cell["abstention_share"][cls] = (1.0 - sum(len(r["s"]) for r in pos) / grid) if grid else None
            for a in ALPHAS:
                cell["tpr_abstain_as_miss"][f"{cls}@{int(a * 100)}%"] = block_bootstrap_rate(_grid_flags(pos, a), n_boot=N_BOOT) if pos else "insufficient data"
            if key[0] == "adjacent" and pos:
                bl = np.concatenate([r["baseline_scores"] for r in pos])
                cell["auc"][cls + "_vs_baseline_in_sample"] = block_bootstrap_auc(ps, bl, n_boot=N_BOOT) if bl.size >= MIN_WIN else "insufficient data"
            for a in ALPHAS:
                cell["tpr"][f"{cls}@{int(a * 100)}%"] = block_bootstrap_rate(_flags(pos, a), n_boot=N_BOOT) if pos else "insufficient data"
            cell["ttfd_s"][cls] = {
                f"{r['test']}@{int(a * 100)}%": [first_detect(r["k"], r["s"] >= r["model"].threshold(a), run) for run in (1, 2)]
                for r in pos for a in ALPHAS
            }
        fan = by("empty_fan")
        if fan and negs.size >= MIN_WIN:
            fs = np.concatenate([r["s"] for r in fan])
            cell["auc"]["empty_fan"] = block_bootstrap_auc(fs, negs, n_boot=N_BOOT)
        for a in ALPHAS:
            lab = f"@{int(a * 100)}%"
            cell["fpr"]["empty" + lab] = block_bootstrap_rate(_flags(neg, a), n_boot=N_BOOT) if neg else "insufficient data"
            cell["fpr"]["empty_fan" + lab] = block_bootstrap_rate(_flags(fan, a), n_boot=N_BOOT) if fan else "insufficient data"
            cell["fpr"]["per_empty_recording" + lab] = {r["test"]: block_bootstrap_rate(r["s"] >= r["model"].threshold(a), n_boot=N_BOOT) for r in neg}
        out["/".join(key)] = cell
    return out


def criteria(per_protocol: dict[str, dict]) -> dict:
    """Evaluate the pre-registered C1-C3 for one candidate from its aggregate() outputs."""
    res = {"C1": True, "C2": True, "C3": True, "notes": []}
    for proto in ("loro", "cross_session"):
        cells = {k: v for k, v in per_protocol.items() if k.startswith(proto + "/")}
        walk = [(k, v["auc"].get("walking")) for k, v in cells.items() if v["auc"].get("walking") not in (None, "insufficient data")]
        if not walk:
            res["C1"] = False
            res["notes"].append(f"{proto}: walking AUC not evaluable")
        for k, w in walk:
            if not w["lo"] >= CRITERIA["C1_auc_lower_bound"]:
                res["C1"] = False
        for k, v in cells.items():
            for a in ALPHAS:
                lab = f"@{int(a * 100)}%"
                e, f = v["fpr"].get("empty" + lab), v["fpr"].get("empty_fan" + lab)
                if isinstance(e, dict) and isinstance(f, dict) and f["rate"] > e["rate"]:
                    res["C2"] = False
            for rid, r in v["fpr"].get("per_empty_recording@1%", {}).items():
                if r["rate"] > CRITERIA["C3_max_flag_share"]:
                    res["C3"] = False
    res["C4"] = True
    for proto in ("loro", "cross_session"):
        controls = [v["empty_vs_empty_control"] for k, v in per_protocol.items() if k.startswith(proto + "/")]
        evaluable = [c for c in controls if c.get("passes") is not None]
        if not evaluable:
            res["C4"] = False
            res["notes"].append(f"{proto}: empty-vs-empty control not evaluable")
        elif not all(c["passes"] for c in evaluable):
            res["C4"] = False
    res["meets_all"] = bool(res["C1"] and res["C2"] and res["C3"] and res["C4"])
    return res


def run(recs: dict[str, RecTables] | None = None) -> dict:
    recs = recs or load_all()
    sp = {"adjacent": splits_adjacent(recs), "loro": splits_loro(recs), "cross_session": splits_cross_session(recs)}
    cands: dict = {}
    for feat in FEATS:
        for rule in RULES:
            rows = [r for p in sp.values() for r in run_candidate(recs, p, feat, rule)]
            per = aggregate(rows)
            cands[f"{feat}/{rule}"] = {"protocols": per, "criteria": criteria(per)}
    return {
        "provenance": provenance("python -m scripts.presence_eval.twonode", sorted(t.name for t in recs.values())),
        "preregistered_criteria": CRITERIA,
        "params": {"nodes": NODES, "features": FEATS, "rules": RULES, "alphas": ALPHAS, "min_windows": MIN_WIN, "n_boot": N_BOOT, "block_windows": DEFAULT_BLOCK},
        "splits": {k: [{"test": s.test_id, "train": list(s.train_ids)} for s in v] for k, v in sp.items()},
        "occupied_sensitivity_control": sensitivity_control(recs),
        "candidates": cands,
        "any_candidate_meets_criteria": any(c["criteria"]["meets_all"] for c in cands.values()),
    }


def _ci(v) -> str:
    if not isinstance(v, dict):
        return "n/a"
    key = "auc" if "auc" in v else "rate"
    return f"{v[key]:.2f} [{v['lo']:.2f}, {v['hi']:.2f}]" if key == "auc" else f"{100 * v[key]:.0f}% [{100 * v['lo']:.0f}, {100 * v['hi']:.0f}]"


def render(res: dict) -> str:
    L = ["| candidate | (a) walking AUC in-sample vs s6 | (b) LORO walking AUC | (b) still AUC | (b) walking TPR@1% / @5% | (c) train-18-Oct walking AUC | (c) walking TPR@1% | (b) empty FPR@1% | (c) empty FPR@1% (18→27 Oct) | (b) fan FPR@1% | worst held-out empty flag share (b) / (c) | C1 | C2 | C3 |",
         "|--|--|--|--|--|--|--|--|--|--|--|--|--|--|"]
    for name, c in res["candidates"].items():
        P, cr = c["protocols"], c["criteria"]
        b, cs = P.get("loro/pooled", {}), P.get("cross_session/train_20261018", {})
        a = P.get("adjacent/s6_empty_1027_1942", {})
        worst = lambda cell: max((v["rate"] for v in cell.get("fpr", {}).get("per_empty_recording@1%", {}).values()), default=float("nan"))
        wc = max((worst(v) for k, v in P.items() if k.startswith("cross_session/")), default=float("nan"))
        L.append("| " + " | ".join([
            name, _ci(a.get("auc", {}).get("walking_vs_baseline_in_sample")), _ci(b.get("auc", {}).get("walking")), _ci(b.get("auc", {}).get("still")),
            f"{_ci(b.get('tpr', {}).get('walking@1%'))} / {_ci(b.get('tpr', {}).get('walking@5%'))}", _ci(cs.get("auc", {}).get("walking")),
            _ci(cs.get("tpr", {}).get("walking@1%")), _ci(b.get("fpr", {}).get("empty@1%")), _ci(cs.get("fpr", {}).get("empty@1%")),
            _ci(b.get("fpr", {}).get("empty_fan@1%")), f"{100 * worst(b):.0f}% / {100 * wc:.0f}%",
            *["pass" if cr[x] else "FAIL" for x in ("C1", "C2", "C3")]]) + " |")
    return "\n".join(L) + "\n"


def render_reference(path) -> str:
    if not path.exists():
        return "(reference run not present)\n"
    ref = json.loads(path.read_text(encoding="utf-8"))
    L = ["| protocol | calibrated on | tested on (label) | s | occupied ticks (tier ≥ still) | still / moving / active | first occupied tick (s) | legacy `fuseTwoNodeTarget` target ticks (gate " + str(ref["rows"][0]["legacyGateThreshold"]) + ") |", "|--|--|--|--|--|--|--|--|"]
    for r in ref["rows"]:
        t = r["tierShare"]
        L.append(f"| {r['protocol']} | {r['calib']} | {r['test']} ({r['label']}) | {r['seconds']:.0f} | {100 * r['occupiedShare']:.1f}% | {100 * t['present_still']:.1f} / {100 * t['present_moving']:.1f} / {100 * t['active']:.1f}% | {r['ttfdSecondsFromTestStart'] if r['ttfdSecondsFromTestStart'] is not None else 'never'} | {100 * r['legacyTargetShare']:.1f}% |")
    return "\n".join(L) + "\n"


def _json_default(o):  # numpy scalars
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-prereg", action="store_true")
    ap.add_argument("--prereg-out", type=Path, default=OUT_DIR / "results" / "preregistered_criteria.json")
    args = ap.parse_args()
    prereg_out = args.prereg_out
    prereg_out.parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    if args.write_prereg:
        doc = {"provenance": provenance("python -m scripts.presence_eval.twonode --write-prereg"), "criteria": CRITERIA,
               "status": "PROPOSAL for Thaer to confirm or change; frozen before the final numbers were computed"}
        dump_json(prereg_out, doc)
        print(f"wrote {prereg_out}")
        return
    res = run()
    dump_json(OUT_DIR / "results" / "two_node_eval.json", res)
    (OUT_DIR / "results" / "two_node_tables.md").write_text(
        "## Candidates\n\n" + render(res) + "\n## Repo reference (TypeScript, nodes 1+2)\n\n" + render_reference(OUT_DIR / "results" / "ref_two_node.json"), encoding="utf-8")
    print("wrote results/two_node_eval.json; any candidate meets criteria:", res["any_candidate_meets_criteria"])


if __name__ == "__main__":
    main()
