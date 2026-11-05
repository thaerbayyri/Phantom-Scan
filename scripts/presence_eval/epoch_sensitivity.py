"""Sensitivity of the (POST-HOC) epoch boundary rule to the step threshold and the hold time, and a list of every ambiguous step.

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.epoch_sensitivity

For every combination of step threshold in {4, 6, 8} dB and hold time in {10, 30, 60} s the whole pipeline is re-run (detector,
persistence, boundary rule, epochs for N1+N2) and four things are reported: how many in-recording events there are, how many of them
become boundaries, whether node 1's persistent step in s7 is still a boundary (and its onset), and the structural facts the
evaluation depends on (epochs with >= 2 empty segments; whether any epoch has >= 2 empties AND a positive recording).
"""
from __future__ import annotations

from . import epoch_eval as ee
from . import epochs as ep
from .jsonutil import dump_json
from .provenance import default_out_dir, provenance
from .tables import RecTables, load_all

OUT_DIR = default_out_dir()
STEPS_DB = (4.0, 6.0, 8.0)
HOLDS_S = (10, 30, 60)
DETECTION_POSITIVES = ("walking", "still")   # what walking/still-vs-empty needs; two_people is reported separately
NODES = (1, 2)
LOW_COVERAGE_RECORDING = "s1_walking_1017_2046"   # 11 frames/s pre-fix capture, excluded by the evaluation as well


def ambiguity_reason(rec: ep.RecordingLinks, e: ep.Event) -> str | None:
    """Why an event is NOT used as a boundary (None if it is one)."""
    if ep.is_boundary(rec, e):
        return None
    if e.reversal:
        return "reversal of the previous step (end of an excursion)"
    if rec.label in ep.EMPTY_LABELS:
        return f"empty/fan recording but held only {e.held_s:.0f} s (< {ep.MIN_EMPTY_BOUNDARY_HOLD_S:.0f} s): excursion" if e.held_s is not None else "empty/fan recording, hold unknown"
    if e.persistent is None:
        return "occupied recording, last recording of its day: persistence cannot be confirmed"
    return "occupied recording, not persistent: may be the person's own body"


def one_config(tabs: dict[str, RecTables], step_db: float, hold: int) -> dict:
    links = ee.load_links(step_db=step_db, hold=hold)
    tl = ep.build_timeline(links, NODES, step_db=step_db)
    events = [(r, n, e) for r in links for n in NODES for e in r.events.get(n, [])]
    ambiguous = [
        {"recording": r.rid, "label": r.label, "node": n, "kind": e.kind, "time_utc": ep.iso(e.t_ms), "offset_s": (e.t_ms - r.t_start_ms) / 1000.0,
         "delta_db": e.delta_db, "fps_before": e.fps_before, "fps_after": e.fps_after, "held_s": e.held_s, "persistent": e.persistent, "reversal": e.reversal,
         "why_not_a_boundary": ambiguity_reason(r, e)}
        for r, n, e in events if not ep.is_boundary(r, e)
    ]
    s7 = next(((r, e) for r, n, e in events if r.rid.startswith("s7__walking") and n == 1 and e.kind == "rssi_step" and ep.is_boundary(r, e)), None)
    segs, _ = ee.make_segments({k: t for k, t in tabs.items() if k != LOW_COVERAGE_RECORDING}, tl)
    by_epoch: dict[str, dict[str, int]] = {}
    for s in segs.values():
        counts = by_epoch.setdefault(ee.epoch_of(s), {})
        counts[s.label] = counts.get(s.label, 0) + 1
    two_empties = sorted(e for e, c in by_epoch.items() if c.get("empty", 0) >= 2)
    both = [e for e in two_empties if any(by_epoch[e].get(p, 0) for p in DETECTION_POSITIVES)]
    with_two_people = [e for e in two_empties if by_epoch[e].get("two_people", 0)]
    return {
        "step_db": step_db, "hold_s": hold, "in_recording_events": len(events), "boundaries_total": len(tl.boundaries),
        "boundaries_from_in_recording_events": sum(1 for r, n, e in events if ep.is_boundary(r, e)), "ambiguous_events": len(ambiguous),
        "s7_node1_step_is_boundary": s7 is not None, "s7_onset_offset_s": None if s7 is None else round((s7[1].t_ms - s7[0].t_start_ms) / 1000.0, 1),
        "epochs_with_two_or_more_empty_segments": two_empties, "epochs_with_two_empties_and_walking_or_still": both, "epochs_with_two_empties_and_two_people": with_two_people,
        "segments_by_epoch": by_epoch, "ambiguous": ambiguous,
    }


def run(tabs: dict[str, RecTables] | None = None) -> dict:
    tabs = tabs or load_all()
    out: dict = {
        "provenance": provenance("python -m scripts.presence_eval.epoch_sensitivity", sorted(t.name for t in tabs.values())),
        "rule_status": "POST HOC (chosen after inspecting these recordings; not pre-registered)",
        "grid": {"step_db": STEPS_DB, "hold_s": HOLDS_S, "node_set": NODES, "min_empty_boundary_hold_s_fixed": ep.MIN_EMPTY_BOUNDARY_HOLD_S},
        "configs": {},
    }
    for step in STEPS_DB:
        for hold in HOLDS_S:
            out["configs"][f"{step:g}dB/{hold}s"] = one_config(tabs, step, hold)
    return out


def render(res: dict) -> str:
    L = ["# Sensitivity of the post-hoc epoch boundary rule", "", f"**Rule status: {res['rule_status']}.** Node set N1+N2. The empty-recording hold limit stays at {res['grid']['min_empty_boundary_hold_s_fixed']:.0f} s in every row.", "",
         "| step | hold | in-recording events | boundaries from them | ambiguous | s7 N1 step is a boundary (onset) | epochs with ≥ 2 empties | … and walking or still | … and two_people |", "|--|--|--|--|--|--|--|--|--|"]
    for c in res["configs"].values():
        s7 = f"yes (+{c['s7_onset_offset_s']:.0f} s)" if c["s7_node1_step_is_boundary"] else "NO"
        L.append(f"| {c['step_db']:g} dB | {c['hold_s']} s | {c['in_recording_events']} | {c['boundaries_from_in_recording_events']} | {c['ambiguous_events']} | "
                 f"{s7} | {', '.join(c['epochs_with_two_or_more_empty_segments']) or '–'} | {', '.join(c['epochs_with_two_empties_and_walking_or_still']) or 'none'} | {', '.join(c['epochs_with_two_empties_and_two_people']) or 'none'} |")
    base = res["configs"].get("6dB/10s")
    if base:
        L += ["", "## Every ambiguous step at the default setting (6 dB, 10 s)", "", "| recording | label | node | event | at | Δ dB | fps | held s | persistent | why it is not a boundary |", "|--|--|--|--|--|--|--|--|--|--|"]
        for a in base["ambiguous"]:
            d = "" if a["delta_db"] is None else f"{a['delta_db']:+.0f}"
            f = "" if a["fps_before"] is None else f"{a['fps_before']:.0f}→{a['fps_after']:.0f}"
            h = "" if a["held_s"] is None else f"{a['held_s']:.0f}"
            L.append(f"| {a['recording'][:26]} | {a['label']} | N{a['node']} | {a['kind']} | {a['time_utc'][5:]} (+{a['offset_s']:.0f} s) | {d} | {f} | {h} | {a['persistent']} | {a['why_not_a_boundary']} |")
    return "\n".join(L) + "\n"


def main() -> None:
    res = run()
    (OUT_DIR / "results").mkdir(parents=True, exist_ok=True)
    dump_json(OUT_DIR / "results" / "epoch_sensitivity.json", res)
    (OUT_DIR / "results" / "epoch_sensitivity.md").write_text(render(res), encoding="utf-8")
    print("wrote results/epoch_sensitivity.json and .md;", len(res["configs"]), "configurations")


if __name__ == "__main__":
    main()
