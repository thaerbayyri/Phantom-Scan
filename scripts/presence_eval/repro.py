"""T2: independently reproduce the exploratory section-2 numbers, each with a block-bootstrap 95 % CI.

    python -m scripts.presence_eval.repro

Positive class = the first-named recording, negative = the second (AUC 0.5 = chance).
"fused" = per-window max over the nodes (all four, and N1+N2 only), on windows present on every fused node.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .features import FEATURES, fuse_max
from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .stats import block_bootstrap_auc
from .tables import RecTables, load_all, pick

OUT_DIR = default_out_dir()
TOL_OK, TOL_APPROX = 0.05, 0.10

# (subject, label, day) specs
S6 = ("s6", "empty", None)
S7 = ("s7", "walking", None)
S8 = ("s8", "empty", None)
S9 = ("s9", "empty", None)
S5 = ("s5", "empty_fan", None)
S1_STILL_1027 = ("s1", "still", "20261027")

# (row id, pos, neg, feature, scope, claimed AUC)  scope: int node or "fused4"
CLAIMS: list[tuple[str, tuple, tuple, str, int | str, float]] = [
    ("C1 fused perturb, walking s7 vs empty s6", S7, S6, "perturb", "fused4", 0.53),
    ("C1b fused decor, walking s7 vs empty s6", S7, S6, "decor", "fused4", 0.64),
    ("C2 fused perturb, empty s8 vs empty s6", S8, S6, "perturb", "fused4", 1.00),
    ("C2 fused decor, empty s8 vs empty s6", S8, S6, "decor", "fused4", 1.00),
    ("C2 fused perturb, empty s9 vs empty s6", S9, S6, "perturb", "fused4", 1.00),
    ("C2 fused decor, empty s9 vs empty s6", S9, S6, "decor", "fused4", 1.00),
    ("C2 fused perturb, empty s9 vs empty s8", S9, S8, "perturb", "fused4", 0.84),
    ("C2 fused decor, empty s9 vs empty s8", S9, S8, "decor", "fused4", 0.49),
]
for scope_name, pos, claims in (
    ("walking s7 vs empty s6", S7, (1.00, 0.95, 0.45, 0.91)),
    ("still s1 (27 Oct) vs empty s6", S1_STILL_1027, (0.92, 0.88, 0.35, 0.70)),
    ("fan s5 vs empty s6", S5, (0.42, 0.28, 0.02, 0.13)),
):
    for node, c in zip((1, 2, 3, 4), claims):
        CLAIMS.append((f"C3 N{node} decor, {scope_name}", pos, S6, "decor", node, c))


def series(rec: RecTables, feature: str, scope: int | str | tuple[int, ...]) -> np.ndarray:
    """Time-ordered window scores for one node, or the per-window max over a node set."""
    if isinstance(scope, int):
        t = rec.nodes.get(scope)
        if t is None:
            return np.zeros(0)
        v = t[feature]
        return v[np.isfinite(v)]
    nodes = (1, 2, 3, 4) if scope == "fused4" else (1, 2) if scope == "fused12" else tuple(scope)
    return fuse_max(rec.nodes, nodes, feature)[1]


def verdict(measured: float, claimed: float) -> str:
    d = abs(measured - claimed)
    return "reproduces" if d <= TOL_OK else "approx" if d <= TOL_APPROX else "does NOT reproduce"


def run(tabs: dict[str, RecTables] | None = None, n_boot: int = 1000) -> dict:
    tabs = tabs or load_all()
    rows = []
    for rid, pos_spec, neg_spec, feat, scope, claimed in CLAIMS:
        pos_rec, neg_rec = pick(tabs, *pos_spec), pick(tabs, *neg_spec)
        res = block_bootstrap_auc(series(pos_rec, feat, scope), series(neg_rec, feat, scope), n_boot=n_boot)
        row = {"row": rid, "pos": pos_rec.rid, "neg": neg_rec.rid, "feature": feat, "scope": scope, "claimed": claimed, **res}
        row["verdict"] = verdict(res["auc"], claimed)
        row["claimed_inside_ci"] = bool(res["lo"] <= claimed <= res["hi"])
        rows.append(row)
        if scope == "fused4":  # also report the two-node variant of the same fused contrast
            r12 = block_bootstrap_auc(series(pos_rec, feat, "fused12"), series(neg_rec, feat, "fused12"), n_boot=n_boot)
            rows.append({"row": rid + " [N1+N2 fused]", "pos": pos_rec.rid, "neg": neg_rec.rid, "feature": feat, "scope": "fused12", "claimed": None, **r12, "verdict": "extra", "claimed_inside_ci": None})
    extra = []
    for label, pos_spec in (("walking s7", S7), ("still s1 27Oct", S1_STILL_1027), ("fan s5", S5), ("empty s8", S8), ("empty s9", S9)):
        pos_rec, neg_rec = pick(tabs, *pos_spec), pick(tabs, *S6)
        for feat in FEATURES:
            for node in (1, 2, 3, 4):
                res = block_bootstrap_auc(series(pos_rec, feat, node), series(neg_rec, feat, node), n_boot=n_boot)
                extra.append({"contrast": f"{label} vs empty s6", "feature": feat, "node": node, **res})
    return {
        "provenance": provenance("python -m scripts.presence_eval.repro", sorted(t.name for t in tabs.values())),
        "params": {"window_s": 1.5, "min_frames": 20, "block_windows": 7, "n_boot": n_boot, "tol_reproduces": TOL_OK, "tol_approx": TOL_APPROX},
        "claims": rows,
        "all_features_per_node": extra,
    }


def _ci(r: dict) -> str:
    return f"{r['auc']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]"


def render(res: dict) -> str:
    p = res["provenance"]
    lines = [
        "# 02 — Independent reproduction of the exploratory numbers",
        "",
        f"**Provenance.** `{p['command']}` — date {p['date_utc']}, commit `{p['commit'][:7]}` (working tree dirty: {p['working_tree_dirty']}), eval code sha256[:16] `{p['eval_code_sha256_16']}`, Python {p['python']}, numpy {p['numpy']}. Inputs: the 14 recordings of `data/datasets/room1/` (file list in `results/reproduction.json`).",
        f"**Method.** 1.5 s tumbling windows per node, windows with < 20 frames dropped; features as defined in `scripts/presence_eval/features.py`; rank-based AUC with average ranks for ties; 95 % CI from a moving-block bootstrap (block = 7 windows = 10.5 s, {res['params']['n_boot']} resamples, fixed seed, resampled separately inside each class). The CI describes within-recording sampling variability only; it does not include between-session drift. In-sample, one subject, one evening (27 Oct). Positive = first recording named, negative = second.",
        f"**Tolerance.** `reproduces` = |measured − claimed| ≤ {TOL_OK}; `approx` ≤ {TOL_APPROX}; otherwise `does NOT reproduce`. Claimed values are the exploratory ones from the task brief; they were not used in any computation.",
        "",
        "## Table A — section-2 claims",
        "",
        "| row | feature / scope | claimed | measured AUC [95 % CI] | verdict | claim inside CI |",
        "|--|--|--|--|--|--|",
    ]
    for r in res["claims"]:
        if r["verdict"] == "extra":
            lines.append(f"| ↳ {r['row'].split(' [')[0]} — N1+N2 fused only | {r['feature']} / fused N1+N2 | – | {_ci(r)} | extra | – |")
        else:
            lines.append(f"| {r['row']} | {r['feature']} / {r['scope']} | {r['claimed']:.2f} | {_ci(r)} | {r['verdict']} | {'yes' if r['claimed_inside_ci'] else 'no'} |")
    lines += ["", "## Table B — every feature, every node, against empty s6 (positive = named recording)", "",
              "| contrast | feature | N1 | N2 | N3 | N4 |", "|--|--|--|--|--|--|"]
    by: dict[tuple, dict[int, dict]] = {}
    for e in res["all_features_per_node"]:
        by.setdefault((e["contrast"], e["feature"]), {})[e["node"]] = e
    for (contrast, feat), d in by.items():
        lines.append(f"| {contrast} | {feat} | " + " | ".join(_ci(d[n]) if n in d else "–" for n in (1, 2, 3, 4)) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "reproduction.json", res)
    Path(OUT_DIR / "results" / "reproduction_tables.md").write_text(render(res), encoding="utf-8")
    print("wrote results/reproduction.json and results/reproduction_tables.md")


if __name__ == "__main__":
    main()
