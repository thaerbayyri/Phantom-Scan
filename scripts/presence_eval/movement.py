"""MOVEMENT SCORE for the live movement view -- NOT a presence detector and NOT a detection candidate.

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.movement

    score_n(t) = x_n(t) - P25( x_n over the same node's PREVIOUS L seconds )      (causal: only windows before t)
    fused      = max over the chosen nodes, on windows where every chosen node has a score

x is a per-window feature (perturb, perturb_agc, decor), L in {45, 90} s, node sets N1+N2 and all four. There is no training
set, no reference recording and no threshold: the baseline is the node's own recent past. Consequences that MUST be shown
wherever this is displayed: it fades under SUSTAINED motion (the baseline rises to meet the signal) and it reads ZERO for a
MOTIONLESS person. So it can only say "something changed recently on this link", never "someone is here", never "the room is
empty". It is evaluated within link-state epochs first (epochs.py), with session-blocked CIs where >= 2 recordings per class
exist, the empty-vs-empty gate (C4) and the fan recording as a negative control. Windows closer than L s to a segment start are
warm-up (no score), so a baseline never spans an epoch boundary.
"""
from __future__ import annotations

import numpy as np

from . import epoch_eval as ee
from . import epochs as ep
from .features import fuse_max
from .jsonutil import dump_json
from .provenance import default_out_dir, provenance
from .stats import block_bootstrap_auc, empty_pair_control, session_block_auc
from .tables import RecTables, load_all

OUT_DIR = default_out_dir()
WINDOW_S = 1.5
LS = (45, 90)
FEATS = ("perturb", "perturb_agc", "decor")
NODE_SETS = ((1, 2), (1, 2, 3, 4))
QUANTILE = 25.0
MIN_PREVIOUS_FRACTION = 0.8
N_BOOT = 300
MIN_WIN = 60
POSITIVE = ("walking", "still", "two_people")
CAVEAT = ("movement score: relative to this node's own recent past; fades under sustained motion and is zero for a motionless person; "
          "NOT presence, and never evidence that a room is empty")


def causal_score(k: np.ndarray, x: np.ndarray, l_seconds: int, q: float = QUANTILE, min_fraction: float = MIN_PREVIOUS_FRACTION) -> np.ndarray:
    """x_t minus the q-th percentile of x over the previous ``l_seconds`` (windows strictly before t). NaN when fewer than
    ``min_fraction`` of the expected previous windows exist (warm-up, gaps) or x_t is not finite."""
    span = int(round(l_seconds / WINDOW_S))
    need = int(np.ceil(min_fraction * span))
    out = np.full(len(k), np.nan)
    for i in range(len(k)):
        lo, hi = np.searchsorted(k, k[i] - span), np.searchsorted(k, k[i])  # windows with k in [k_i - span, k_i)
        prev = x[lo:hi]
        prev = prev[np.isfinite(prev)]
        if len(prev) >= need and np.isfinite(x[i]):
            out[i] = x[i] - np.percentile(prev, q)
    return out


def fused_scores(seg: RecTables, feat: str, l_seconds: int, nodes: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    """(window index, fused movement score) of one segment: per-node causal scores, then the max over ``nodes``."""
    if any(n not in seg.nodes for n in nodes):
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    tables = {n: {"k": seg.nodes[n]["k"], "move": causal_score(seg.nodes[n]["k"], seg.nodes[n][feat], l_seconds)} for n in nodes}
    return fuse_max(tables, nodes, "move")


def _ci(r) -> dict | str:
    return r if isinstance(r, dict) else "insufficient data"


def evaluate_group(scores: dict[str, tuple[str, np.ndarray]]) -> dict:
    """scores: segment id -> (label, time-ordered fused scores). Reports each positive class and the fan control against the
    EMPTY segments of this group, plus the empty-vs-empty gate. Cells are 'insufficient data' rather than invented numbers."""
    by = lambda lab: {sid: v for sid, (l, v) in scores.items() if l == lab and len(v) >= MIN_WIN}
    neg = by("empty")
    negs = np.concatenate(list(neg.values())) if neg else np.zeros(0)
    cell: dict = {"n_empty_segments": len(neg), "n_empty_windows": int(negs.size), "auc": {}, "auc_session_blocked": {}}
    for cls in (*POSITIVE, "empty_fan"):
        pos = by(cls)
        ps = np.concatenate(list(pos.values())) if pos else np.zeros(0)
        if ps.size < MIN_WIN or negs.size < MIN_WIN:
            cell["auc"][cls] = cell["auc_session_blocked"][cls] = "insufficient data"
            continue
        cell["auc"][cls] = block_bootstrap_auc(ps, negs, n_boot=N_BOOT)
        cell["auc_session_blocked"][cls] = session_block_auc(pos, neg, n_boot=N_BOOT)
    cell["empty_vs_empty_control"] = empty_pair_control(neg, n_boot=N_BOOT)
    cell["n_segments_per_class"] = {lab: len(by(lab)) for lab in (*POSITIVE, "empty_fan", "empty")}
    return cell


def median_by_third(v: np.ndarray) -> list[float] | None:
    """Median score in the first, middle and last third of a segment (fading under sustained motion shows as a falling sequence)."""
    if len(v) < 3 * 20:
        return None
    return [float(np.median(c)) for c in np.array_split(v, 3)]


def run(tabs: dict[str, RecTables] | None = None, links: list[ep.RecordingLinks] | None = None) -> dict:
    tabs = tabs or load_all()
    links = links or ee.load_links()
    out: dict = {"provenance": provenance("python -m scripts.presence_eval.movement", sorted(t.name for t in tabs.values())), "caveat": CAVEAT,
                 "definition": {"quantile": QUANTILE, "L_seconds": LS, "features": FEATS, "node_sets": NODE_SETS, "min_previous_fraction": MIN_PREVIOUS_FRACTION},
                 "not_a_detection_candidate": True, "variants": {}}
    for nodes in NODE_SETS:
        tl = ep.build_timeline(links, nodes)
        usable = {rid: t for rid, t in tabs.items() if all(n in t.nodes for n in nodes)}
        low = [rid for rid, t in usable.items() if min(len(t.nodes[n]["k"]) for n in nodes) / max(1.0, t.duration_s / WINDOW_S) < ee.MIN_GRID_COVERAGE]
        segs, log = ee.make_segments({r: t for r, t in usable.items() if r not in low}, tl, need=nodes)
        for feat in FEATS:
            for l_s in LS:
                scored = {sid: (seg.label, fused_scores(seg, feat, l_s, nodes)[1]) for sid, seg in segs.items()}
                epochs = sorted({ee.epoch_of(s) for s in segs.values()})
                variant = {
                    "within_epoch": {e: evaluate_group({sid: v for sid, v in scored.items() if ee.epoch_of(segs[sid]) == e}) for e in epochs},
                    "across_epochs": evaluate_group(scored),
                    "median_score_by_third": {sid: median_by_third(v[1]) for sid, v in scored.items()},
                    "warmup_windows_without_score": {sid: int(len(segs[sid].nodes[min(nodes)]["k"]) - len(v[1])) for sid, v in scored.items()},
                }
                out["variants"][f"{'+'.join(f'N{n}' for n in nodes)}/{feat}/L{l_s}"] = variant
        out.setdefault("segments", {})["+".join(f"N{n}" for n in nodes)] = log
        out.setdefault("excluded_low_coverage", {})["+".join(f"N{n}" for n in nodes)] = low
    return out


# ── Reproduction of the externally reported "pooled" protocol (RuView-vs-Phantom note, section 3) ───────────────────────
# Pooled empties = s6 + first PART of s8 + first PART of s9 (last window of part 1 taken from the part files' own time range);
# positives s7 walking, s10 and s1(27 Oct) still, s5 fan; first L seconds of each recording dropped; the drift control is
# AUC(s8 part 1 vs s6). NO epochs here: this is the protocol as reported, kept only to check the reported numbers.
POOLED = {
    "empty": {"s6_empty_1027_1942": None, "s8_empty_1027_1953": 281, "s9_empty_1027_2047": 264},   # value = last window index kept
    "walking": {"s7_walking_1027_1945": None},
    "still": {"s10_still_1027_2121": None, "s1_still_1027_1936": None},
    "fan": {"s5_empty_fan_1027_1938": None},
}
S7_HEAD_LAST_K = 125   # s7 windows before node 1's persistent step (+188 s): the variant without the transitional tail


def truncate(rec: RecTables, last_k: int | None) -> RecTables:
    if last_k is None:
        return rec
    nodes = {n: {c: v[t["k"] <= last_k] for c, v in t.items()} for n, t in rec.nodes.items()}
    return RecTables(rec.rid, rec.name, rec.label, rec.subject, rec.day, rec.t0_ms, rec.duration_s, rec.parts, nodes)


def _raw_fused(rec: RecTables, feat: str, nodes: tuple[int, ...]) -> np.ndarray:
    if any(n not in rec.nodes for n in nodes):
        return np.zeros(0)
    return fuse_max(rec.nodes, nodes, feat)[1]


def pooled_reproduction(tabs: dict[str, RecTables], pooled: dict | None = None, n_boot: int = N_BOOT, block: int = 7) -> dict:
    pooled = pooled or POOLED
    out: dict = {"protocol": "pooled empties s6 + s8 part 1 + s9 part 1, no epochs (as reported externally)", "configs": {}}
    configs = [("decor", (1, 2, 3, 4), "raw", None), ("decor", (1, 2, 3, 4), "self", 90), ("perturb", (1, 2), "raw", None), ("perturb", (1, 2), "self", 90),
               ("decor", (1, 2, 3, 4), "self", 45), ("perturb", (1, 2), "self", 45)]
    for feat, nodes, mode, l_s in configs:
        def score(rid: str, last_k: int | None) -> np.ndarray:
            rec = truncate(tabs[rid], last_k)
            return _raw_fused(rec, feat, nodes) if mode == "raw" else fused_scores(rec, feat, l_s, nodes)[1]

        pos_by_class = {c: np.concatenate([score(r, k) for r, k in m.items()]) for c, m in pooled.items()}
        neg = pos_by_class["empty"]
        s8 = score("s8_empty_1027_1953", pooled["empty"]["s8_empty_1027_1953"])
        s6 = score("s6_empty_1027_1942", None)
        cell: dict = {}
        for cls in ("walking", "still", "fan"):
            cell[cls] = block_bootstrap_auc(pos_by_class[cls], neg, block=block, n_boot=n_boot)
        cell["walking_head_only_no_tail"] = block_bootstrap_auc(score("s7_walking_1027_1945", S7_HEAD_LAST_K), neg, block=block, n_boot=n_boot)
        for rid in pooled["still"]:
            cell[f"still:{rid}"] = block_bootstrap_auc(score(rid, None), neg, block=block, n_boot=n_boot)
        cell["drift_control_s8p1_vs_s6"] = block_bootstrap_auc(s8, s6, block=block, n_boot=n_boot)
        out["configs"][f"{'+'.join(f'N{n}' for n in nodes)}/{feat}/{mode}" + (f"/L{l_s}" if l_s else "")] = cell
    return out


def render_pooled(res: dict) -> str:
    L = ["# Reproduction of the externally reported pooled self-baseline table", "", res["protocol"], "",
         "AUC [window-block 95 % CI]; 0.5 = chance. NOT a detection claim; one walking recording; the choice of two lookbacks and four configurations is in-sample.", "",
         "| config | walking (s7 whole) | walking (head only, no step tail) | still s10 | still s1 | fan s5 | drift control s8p1 vs s6 |", "|--|--|--|--|--|--|--|"]
    for name, c in res["configs"].items():
        L.append(f"| {name} | {_c(c['walking'])} | {_c(c['walking_head_only_no_tail'])} | {_c(c['still:s10_still_1027_2121'])} | {_c(c['still:s1_still_1027_1936'])} | {_c(c['fan'])} | {_c(c['drift_control_s8p1_vs_s6'])} |")
    return "\n".join(L) + "\n"


def _c(v) -> str:
    if not isinstance(v, dict):
        return "n/a"
    if v.get("auc") is None:
        return "n/a"
    lo = v.get("lo")
    return f"{v['auc']:.2f}" + (f" [{lo:.2f}, {v['hi']:.2f}]" if lo is not None else " [no CI]")


def render(res: dict) -> str:
    L = ["# Movement score (not a presence detector)", "", f"**{res['caveat']}.**", "",
         "AUC = movement score of the named class vs the EMPTY segments of the same group (an epoch, or all epochs). The first interval is a "
         "window-block bootstrap (optimistic); `sb` is the session-blocked interval (needs ≥ 2 recordings in each class, otherwise `[no CI]`).", ""]
    for name, v in res["variants"].items():
        L += [f"## {name}", "", "| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |", "|--|--|--|--|--|--|--|"]
        groups = {**{f"epoch {e}": c for e, c in v["within_epoch"].items()}, "ACROSS epochs": v["across_epochs"]}
        for g, c in groups.items():
            ctrl = c["empty_vs_empty_control"]
            gate = "n/a (< 2 empties)" if ctrl.get("passes") is None else f"{'pass' if ctrl['passes'] else 'FAIL'} ({ctrl['worst_symmetric_upper_bound']:.2f})"
            sb = {k: c["auc_session_blocked"].get(k) for k in (*POSITIVE, "empty_fan")}
            cells = [f"{_c(c['auc'].get(k))}" + (f" sb {_c(sb[k])}" if isinstance(sb[k], dict) and sb[k].get("lo") is not None else "") for k in (*POSITIVE, "empty_fan")]
            L.append(f"| {g} | {c['n_empty_segments']} seg / {c['n_empty_windows']} win | " + " | ".join(cells) + f" | {gate} |")
        L.append("")
    fade = res["variants"].get("N1+N2/decor/L45")
    if fade:
        L += ["## Does it fade? median score by third of each segment (N1+N2/decor/L45)", "", "| segment | first third | middle | last third |", "|--|--|--|--|"]
        L += [f"| {sid} | {m[0]:.3g} | {m[1]:.3g} | {m[2]:.3g} |" for sid, m in fade["median_score_by_third"].items() if m]
        L.append("")
    return "\n".join(L)


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "movement_score.json", res)
    (OUT_DIR / "results" / "movement_score_tables.md").write_text(render(res), encoding="utf-8")
    pooled = pooled_reproduction(load_all())
    pooled["provenance"] = provenance("python -m scripts.presence_eval.movement (pooled reproduction)", [])
    dump_json(OUT_DIR / "results" / "movement_pooled_reproduction.json", pooled)
    (OUT_DIR / "results" / "movement_pooled_reproduction.md").write_text(render_pooled(pooled), encoding="utf-8")
    print("wrote results/movement_score.json and results/movement_score_tables.md;", len(res["variants"]), "variants; plus the pooled reproduction")


if __name__ == "__main__":
    main()
