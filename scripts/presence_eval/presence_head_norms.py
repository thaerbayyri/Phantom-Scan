"""PS-FIX-28: what does the shipped presence head actually see on OUR recordings?

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.presence_head_norms     (needs torch)

The guard in phantom/presence_guard.py refuses the head because ||w|| (3.67) < |bias| (8.19) for UNIT-norm input. The sidecar's own
docstring says the head is meant for the UN-normalised bn2 activation (||pre|| ~ 15) where it "gives a full 0..1 spread". This
measures that: it reproduces the sidecar's real path (100-frame window every 0.2 s -> 8 standardised features -> csi-embed-v2 ->
un-normalised activation) on every recording and reports ||pre||, the head's logit and probability per label and node, plus how
well the probability separates occupied from empty. No LoRA adapter is applied (opt-in, trained for other rooms).

The sidecar functions are NOT re-implemented: estimate_vitals / extract_features_8d / Enc are extracted from scripts/ai_inference.py
with ast and executed, so the measurement cannot drift from the code that runs live (that script cannot be imported: it starts
the sidecar).
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import numpy as np

from phantom.embedding import load_standardizer, ruview_scale_features, standardize
from phantom.presence_guard import presence_head_check

from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .recordings import group_recordings, load_recording
from .stats import block_bootstrap_auc
from .tables import REC_CACHE, ROOM_DIR

OUT_DIR = default_out_dir()
SIDECAR = REPO_ROOT / "scripts" / "ai_inference.py"
MODEL_DIR = REPO_ROOT / "ai model and densepose" / "model"
HISTORY_LEN = 100        # frames per window (ai_inference.HISTORY_LEN)
INFER_EVERY_S = 0.2      # 5 Hz inference throttle
QUANTILES = (0.05, 0.5, 0.95)
LABELS = ("empty", "empty_fan", "walking", "still", "two_people")


def load_sidecar_code(embed_mean: np.ndarray, embed_std: np.ndarray) -> dict:
    """Execute estimate_vitals, extract_features_8d, Enc and DEFAULT_FS exactly as written in scripts/ai_inference.py."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    tree = ast.parse(SIDECAR.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in {"estimate_vitals", "extract_features_8d"})
            or (isinstance(n, ast.ClassDef) and n.name == "Enc")
            or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULT_FS" for t in n.targets))]
    found = {getattr(n, "name", "DEFAULT_FS") for n in keep}
    if found != {"estimate_vitals", "extract_features_8d", "Enc", "DEFAULT_FS"}:
        raise RuntimeError(f"sidecar layout changed: extracted {sorted(found)}")
    ns: dict = {"np": np, "torch": torch, "nn": nn, "F": F, "math": math, "ruview_scale_features": ruview_scale_features,
                "standardize": standardize, "EMBED_MEAN": embed_mean, "EMBED_STD": embed_std}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "scripts/ai_inference.py (extracted)", "exec"), ns)  # noqa: S102 (our own repo file)
    return ns


def estimate_fs(timestamps_ms: np.ndarray, default_fs: float) -> float:
    """ai_inference._estimate_fs: samples per second from millisecond timestamps, guarded to 1..200 Hz."""
    if len(timestamps_ms) < 2:
        return default_fs
    span_s = (timestamps_ms[-1] - timestamps_ms[0]) / 1000.0
    if span_s <= 0:
        return default_fs
    fs = (len(timestamps_ms) - 1) / span_s
    return fs if 1.0 <= fs <= 200.0 else default_fs


def windows_for_node(t_ms: np.ndarray, amps: np.ndarray, rssi: np.ndarray, code: dict) -> tuple[np.ndarray, np.ndarray]:
    """(features [W, 8], sample times of each window end) for one node, the way the sidecar slides its 100-frame history."""
    feats, ends = [], []
    prev_mean = None
    i = HISTORY_LEN
    while i <= len(t_ms):
        sl = slice(i - HISTORY_LEN, i)
        fs = estimate_fs(t_ms[sl].astype(float), code["DEFAULT_FS"])
        f, _motion, mean, _vitals = code["extract_features_8d"](amps[sl].astype(np.float64), rssi[sl].astype(np.float64), fs, prev_mean)
        feats.append(f)
        ends.append(t_ms[i - 1])
        prev_mean = mean
        step = max(1, int(round(fs * INFER_EVERY_S)))
        i += step
    return (np.asarray(feats, dtype=np.float32), np.asarray(ends)) if feats else (np.zeros((0, 8), dtype=np.float32), np.zeros(0))


def q(x: np.ndarray) -> list[float | None]:
    return [float(np.quantile(x, p)) for p in QUANTILES] if x.size else [None] * len(QUANTILES)


def run(room_dir: Path = ROOM_DIR) -> dict:
    import torch
    from safetensors.torch import load_file

    mean, std = load_standardizer(MODEL_DIR / "csi-embed-v2-int4.bin")
    code = load_sidecar_code(mean, std)
    net = code["Enc"]()
    net.load_state_dict(load_file(str(MODEL_DIR / "csi-embed-v2.safetensors")), strict=True)
    net.eval()
    head = json.loads((MODEL_DIR / "presence-head.json").read_text(encoding="utf-8"))
    w, b = np.asarray(head["weights"], dtype=np.float64), float(head["bias"])
    per: dict[tuple[str, int], dict[str, list[np.ndarray]]] = {}
    by_rec: dict[str, dict] = {}
    for name, paths in group_recordings(room_dir).items():
        rec = load_recording(paths, REC_CACHE)
        for node, s in rec.nodes.items():
            feats, ends = windows_for_node(s.t, s.a, np.nan_to_num(s.rssi, nan=-100.0), code)
            if not len(feats):
                continue
            with torch.no_grad():
                z_t, pre_t = net(torch.from_numpy(feats))
            pre, z = pre_t.numpy().astype(np.float64), z_t.numpy().astype(np.float64)
            cell = per.setdefault((rec.label, node), {"norm": [], "logit": [], "p": [], "zlogit": []})
            logit = pre @ w + b
            cell["norm"].append(np.linalg.norm(pre, axis=1))
            cell["logit"].append(logit)
            cell["p"].append(1.0 / (1.0 + np.exp(-np.clip(logit, -60, 60))))
            cell["zlogit"].append(z @ w + b)
            by_rec.setdefault(rec.name, {})[node] = (ends, cell["p"][-1])
    cells: dict = {}
    for (label, node), c in sorted(per.items()):
        norm, logit, p, zl = (np.concatenate(c[k]) for k in ("norm", "logit", "p", "zlogit"))
        cells[f"{label}/N{node}"] = {"windows": int(norm.size), "pre_norm_q05_q50_q95": q(norm), "logit_q05_q50_q95": q(logit), "p_q05_q50_q95": q(p),
                                     "share_p_gt_0.5": float((p > 0.5).mean()), "share_p_gt_0.99": float((p > 0.99).mean()),
                                     "l2_normalised_input_logit_min_max": [float(zl.min()), float(zl.max())]}
    pooled = {lab: np.concatenate([np.concatenate(c["p"]) for (l, _n), c in per.items() if l == lab]) for lab in LABELS if any(l == lab for l, _ in per)}
    aucs = {lab: block_bootstrap_auc(pooled[lab], pooled["empty"], block=7, n_boot=300) for lab in pooled if lab != "empty" and "empty" in pooled}
    all_norms = np.concatenate([np.concatenate(c["norm"]) for c in per.values()])
    r_lo = float(np.quantile(all_norms, 0.05))
    return {
        "provenance": provenance("python -m scripts.presence_eval.presence_head_norms", sorted(group_recordings(room_dir))),
        "head": {"weight_norm": float(np.linalg.norm(w)), "bias": b},
        "cells": cells,
        "pre_norm_all_windows_q05_q50_q95": q(all_norms),
        "guard_unit_norm": presence_head_check(w, b, 1.0).__dict__,
        "guard_with_measured_q05_norm": presence_head_check(w, b, r_lo).__dict__,
        "auc_p_vs_empty": aucs,
        "note": "No LoRA adapter applied. AUC is window-level, pooled across nodes and recordings; window-block CI only (optimistic).",
    }


def render(res: dict) -> str:
    L = ["# Presence head on our recordings (PS-FIX-28)", "", f"Head: ||w|| = {res['head']['weight_norm']:.3f}, bias = {res['head']['bias']:.3f}.",
         f"Un-normalised activation ||pre||, all windows: q05 / q50 / q95 = {' / '.join(f'{x:.1f}' for x in res['pre_norm_all_windows_q05_q50_q95'])}.", "",
         "| label/node | windows | ‖pre‖ q05/q50/q95 | logit q05/q50/q95 | p q05/q50/q95 | share p>0.5 | share p>0.99 | logit range on L2-normalised input |", "|--|--|--|--|--|--|--|--|"]
    f = lambda xs: " / ".join("–" if x is None else f"{x:.2f}" for x in xs)
    for k, c in res["cells"].items():
        L.append(f"| {k} | {c['windows']} | {f(c['pre_norm_q05_q50_q95'])} | {f(c['logit_q05_q50_q95'])} | {f(c['p_q05_q50_q95'])} | {100 * c['share_p_gt_0.5']:.0f}% | {100 * c['share_p_gt_0.99']:.0f}% | {f(c['l2_normalised_input_logit_min_max'])} |")
    L += ["", "AUC of p(present) vs empty (window-level, pooled):", ""]
    L += [f"* {lab}: {a['auc']:.2f} [{a['lo']:.2f}, {a['hi']:.2f}]" for lab, a in res["auc_p_vs_empty"].items()]
    L += ["", f"Guard at unit norm: ok={res['guard_unit_norm']['ok']}; with the measured q05 norm: ok={res['guard_with_measured_q05_norm']['ok']}.", "", res["note"]]
    return "\n".join(L) + "\n"


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "presence_head_norms.json", res)
    (OUT_DIR / "results" / "presence_head_norms.md").write_text(render(res), encoding="utf-8")
    print("wrote results/presence_head_norms.json and .md;", len(res["cells"]), "cells")


if __name__ == "__main__":
    main()
