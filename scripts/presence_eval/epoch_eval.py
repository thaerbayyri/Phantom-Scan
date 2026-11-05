"""Epoch-stratified evaluation: every analysis is reported WITHIN each link-state epoch and ACROSS epochs, separately.

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.epoch_eval

* Epochs come from scripts/presence_eval/epochs.py for a node set (default N1+N2). Empties from different epochs are never
  pooled: a model is fit on the empties of ONE epoch.
* Transitional windows (PRE_MARGIN_S before to SETTLE_S after a boundary event) are removed from every evaluation; so the tail of
  s7 after node 1's step is not part of walking-vs-empty.
* "within": leave-one-segment-out among the empty segments of the same epoch. A held-out empty is only testable when the epoch
  has >= 2 empty segments; otherwise the cell says "insufficient data" (it never falls back to pooling).
* "cross": train on the empties of epoch A, test every segment of epoch B != A.
The CAUSE of any link-state change is not inferred here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import epochs as ep
from .jsonutil import dump_json
from .provenance import REPO_ROOT, default_out_dir, provenance
from .recordings import group_recordings, load_recording
from .tables import REC_CACHE, ROOM_DIR, RecTables, load_all
from . import twonode as tn

OUT_DIR = default_out_dir()
DEFAULT_NODES = (1, 2)
WINDOW_MS = 1500
MIN_GRID_COVERAGE = 0.5   # a recording needs usable windows for at least half of its time grid to be evaluated


def load_links(room_dir: Path = ROOM_DIR, *, step_db: float = ep.STEP_DB, hold: int = ep.HOLD_S) -> list[ep.RecordingLinks]:
    links = []
    for name, paths in group_recordings(room_dir).items():
        rec = load_recording(paths, REC_CACHE)
        links.append(ep.analyze_recording(name[7:30] if name.startswith("room1__") else name, name.split("__")[3][:8], rec.nodes, rec.t_min, rec.t_max, rec.label, step_db=step_db, hold=hold))
    return ep.classify_persistence(links)


def window_info(rec: RecTables, tl: ep.Timeline, k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(epoch index per window, transitional flag per window) for window indices ``k`` of ``rec`` (window centre time)."""
    centre = rec.t0_ms + ((k + 0.5) * WINDOW_MS).astype(np.int64)
    idx = np.searchsorted(np.asarray(tl._times, dtype=np.int64), centre, side="right")
    trans = np.zeros(k.shape, dtype=bool)
    for a, b, _ in tl.transitional:
        trans |= (centre >= a) & (centre < b)
    return idx, trans


def joint_count(seg: RecTables, need: tuple[int, ...], feat: str = "decor") -> int:
    """Windows with a finite value on EVERY node in ``need`` (inner join; no zero-filling)."""
    ks = None
    for n in need:
        t = seg.nodes.get(n)
        if t is None:
            return 0
        kk = t["k"][np.isfinite(t[feat])]
        ks = kk if ks is None else np.intersect1d(ks, kk)
    return 0 if ks is None else int(len(ks))


def make_segments(tabs: dict[str, RecTables], tl: ep.Timeline, min_windows: int = tn.MIN_WIN, need: tuple[int, ...] = tn.NODES) -> tuple[dict[str, RecTables], list[dict]]:
    """Split every recording into (recording x epoch) segments, dropping transitional windows. Returns (segments, log)."""
    segs: dict[str, RecTables] = {}
    log: list[dict] = []
    for rid, rec in tabs.items():
        per_epoch: dict[int, dict[int, dict[str, np.ndarray]]] = {}
        counts: dict[int, dict] = {}
        for node, table in rec.nodes.items():
            idx, trans = window_info(rec, tl, table["k"])
            for e in np.unique(idx):
                m_all = idx == e
                m_keep = m_all & ~trans
                c = counts.setdefault(int(e), {"windows": 0, "transitional_dropped": 0})
                if node == min(rec.nodes):
                    c["windows"] += int(m_keep.sum())
                    c["transitional_dropped"] += int((m_all & trans).sum())
                if m_keep.any():
                    per_epoch.setdefault(int(e), {})[node] = {c_: v[m_keep] for c_, v in table.items()}
        for e, nodes in per_epoch.items():
            name = f"E{e + 1:02d}"
            seg = RecTables(rid=f"{rid}@{name}", name=rec.name, label=rec.label, subject=rec.subject, day=rec.day, t0_ms=rec.t0_ms,
                            duration_s=rec.duration_s, parts=rec.parts, nodes=nodes)
            usable = joint_count(seg, need)
            log.append({"segment": seg.rid, "epoch": name, "label": rec.label, **counts[e], "joint_N1N2_windows": usable, "kept": usable >= min_windows})
            if usable >= min_windows:
                segs[seg.rid] = seg
        for e, c in counts.items():  # epochs that lost EVERY window to the transitional exclusion are still listed
            if e not in per_epoch:
                log.append({"segment": f"{rid}@E{e + 1:02d}", "epoch": f"E{e + 1:02d}", "label": rec.label, **c, "joint_N1N2_windows": 0, "kept": False})
    return segs, log


def epoch_of(seg: RecTables) -> str:
    return seg.rid.rsplit("@", 1)[1]


def splits_within(segs: dict[str, RecTables]) -> list[tn.Split]:
    out = []
    for sid, seg in segs.items():
        e = epoch_of(seg)
        train = tuple(r for r, o in segs.items() if o.label == "empty" and epoch_of(o) == e and r != sid)
        if train:
            out.append(tn.Split("epoch_within", sid, train, e))
    return out


def splits_cross(segs: dict[str, RecTables]) -> list[tn.Split]:
    out = []
    epochs = sorted({epoch_of(s) for s in segs.values()})
    for a in epochs:
        train = tuple(r for r, o in segs.items() if o.label == "empty" and epoch_of(o) == a)
        if not train:
            continue
        for sid, seg in segs.items():
            if epoch_of(seg) != a:
                out.append(tn.Split("epoch_cross", sid, train, f"{a}->{epoch_of(seg)}"))
    return out


def run(nodes: tuple[int, ...] = DEFAULT_NODES, tabs: dict[str, RecTables] | None = None, links: list[ep.RecordingLinks] | None = None) -> dict:
    tabs = tabs or load_all()
    links = links or load_links()
    tl = ep.build_timeline(links, nodes)
    low_coverage = {}
    for rid, rec in list(tabs.items()):  # e.g. the 11 frames/s pre-fix recording: only chance bursts reach 20 frames/window
        grid = max(1.0, rec.duration_s / (WINDOW_MS / 1000.0))
        cov = min((len(rec.nodes[n]["k"]) / grid for n in nodes if n in rec.nodes), default=0.0)
        if cov < MIN_GRID_COVERAGE:
            low_coverage[rid] = round(cov, 3)
            del tabs[rid]
    segs, log = make_segments(tabs, tl)
    sp = {"epoch_within": splits_within(segs), "epoch_cross": splits_cross(segs)}
    cands: dict = {}
    for feat in tn.FEATS:
        for rule in tn.RULES:
            rows = [r for p in sp.values() for r in tn.run_candidate(segs, p, feat, rule)]
            cands[f"{feat}/{rule}"] = tn.aggregate(rows)
    return {
        "provenance": provenance("python -m scripts.presence_eval.epoch_eval", sorted(t.name for t in tabs.values())),
        "node_set": nodes,
        "params": {"step_db": ep.STEP_DB, "hold_s": ep.HOLD_S, "pre_s": ep.PRE_S, "settle_s": ep.SETTLE_S, "pre_margin_s": ep.PRE_MARGIN_S,
                   "min_empty_boundary_hold_s": ep.MIN_EMPTY_BOUNDARY_HOLD_S, "min_windows": tn.MIN_WIN, "n_boot": tn.N_BOOT},
        "boundary_rule_status": "POST HOC: chosen after inspecting these recordings, not pre-registered; sensitivity in epoch_sensitivity.py",
        "cause_of_link_changes": "UNCONFIRMED. The audit log holds only dataset_recording_started/stopped; nothing records what happened at node 1.",
        "boundaries": [{"time_utc": ep.iso(t), "reason": r} for t, r in tl.boundaries],
        "events": [
            {"recording": r.rid, "label": r.label, "node": n, "time_utc": ep.iso(e.t_ms), "offset_s": (e.t_ms - r.t_start_ms) / 1000.0, "kind": e.kind,
             "delta_db": e.delta_db, "rssi_before": e.rssi_before, "rssi_after": e.rssi_after, "fps_before": e.fps_before, "fps_after": e.fps_after,
             "held_s": e.held_s, "persistent": e.persistent, "boundary": ep.is_boundary(r, e)}
            for r in links for n in sorted(r.events) for e in r.events[n]
        ],
        "excluded_low_coverage": low_coverage,
        "segments": log,
        "candidates": cands,
    }


def _cell(v) -> str:
    if not isinstance(v, dict):
        return "n/a"
    if "auc" in v and v.get("auc") is not None:
        lo = v.get("lo")
        return f"{v['auc']:.2f}" + (f" [{lo:.2f}, {v['hi']:.2f}]" if lo is not None else " [no CI]")
    if "rate" in v:
        return f"{100 * v['rate']:.0f}%"
    return "n/a"


def render(res: dict, show=("decor/max", "perturb_agc/max", "decor/n2", "perturb/max")) -> str:
    nodes = "+".join(f"N{n}" for n in res["node_set"])
    L = [f"## Link-state epochs for {nodes}", "", "Cause of every change: **unconfirmed** (the audit log has only recording start/stop).", "",
         "| boundary (UTC) | reason |", "|--|--|"] + [f"| {b['time_utc']} | {b['reason']} |" for b in res["boundaries"]]
    L += ["", "### Detected events (all nodes; `boundary` = used to split)", "", "| recording | label | event | at | held s | persistent | boundary |", "|--|--|--|--|--|--|--|"]
    for e in res["events"]:
        what = f"N{e['node']} {e['kind']}" + (f" {e['delta_db']:+.0f} dB ({e['rssi_before']:.0f}→{e['rssi_after']:.0f})" if e["delta_db"] is not None else "") + (f" fps {e['fps_before']:.0f}→{e['fps_after']:.0f}" if e["fps_before"] is not None and e["fps_after"] is not None else "")
        held = "" if e["held_s"] is None else f"{e['held_s']:.0f}"
        L.append(f"| {e['recording'][:26]} | {e['label']} | {what} | +{e['offset_s']:.0f} s | {held} | {e['persistent']} | {e['boundary']} |")
    L += ["", "### Segments (recording × epoch); transitional windows removed", "", "| segment | label | kept windows | transitional dropped | N1+N2 windows | evaluated |", "|--|--|--|--|--|--|"]
    L += [f"| {s['segment'][:40]} | {s['label']} | {s['windows']} | {s['transitional_dropped']} | {s['joint_N1N2_windows']} | {'yes' if s['kept'] else 'too few'} |" for s in res["segments"]]
    for cand in show:
        cells = res["candidates"].get(cand)
        if not cells:
            continue
        L += ["", f"### Candidate `{cand}` (window-block CIs, optimistic; session-blocked shown where ≥ 2 recordings per class exist)", "",
              "| protocol/group | empty windows | walking AUC | still AUC | fan AUC | walking TPR@1% | still TPR@1% | empty FPR@1% | fan FPR@1% | empty-vs-empty gate C4 |", "|--|--|--|--|--|--|--|--|--|--|"]
        for g, c in cells.items():
            ctrl = c["empty_vs_empty_control"]
            gate = "n/a (needs ≥ 2 empties)" if ctrl.get("passes") is None else f"{'pass' if ctrl['passes'] else 'FAIL'} (worst sym. upper {ctrl['worst_symmetric_upper_bound']:.2f})"
            L.append(f"| {g} | {c['n_empty_windows']} | {_cell(c['auc'].get('walking'))} | {_cell(c['auc'].get('still'))} | {_cell(c['auc'].get('empty_fan'))} | "
                     f"{_cell(c['tpr'].get('walking@1%'))} | {_cell(c['tpr'].get('still@1%'))} | {_cell(c['fpr'].get('empty@1%'))} | {_cell(c['fpr'].get('empty_fan@1%'))} | {gate} |")
    return "\n".join(L) + "\n"


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "epoch_eval.json", res)
    (OUT_DIR / "results" / "epoch_eval_tables.md").write_text(render(res), encoding="utf-8")
    print("wrote results/epoch_eval.json and results/epoch_eval_tables.md;", len(res["boundaries"]), "boundaries,", len(res["segments"]), "segments")


if __name__ == "__main__":
    main()
