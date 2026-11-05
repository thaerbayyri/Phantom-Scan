"""One-command analysis of a validated 2026-11 recording campaign. Reads recordings; writes only a report under reports/ (never under data/).

    python -m scripts.presence_eval.run_campaign <campaign folder> [--out DIR] [--min-fan-person-min N] [--allow-uncommitted-prereg]

Refuses (non-zero exit) unless (1) the validator passes (``validate_campaign``) and (2) the pre-registration file is tracked by git and
unmodified (its SHA-256 goes into the report). Then, with the repo's own tools: window features, parity-aware decor (K7, PS-FIX-37), the
causal self-baseline movement score (windows strictly before t; defined only when >= 80 % of the lookback windows exist), AUC with moving-block
bootstrap intervals, and the C4 empty-versus-empty control. Every number in the report is labelled ``measured``; a quantity that cannot be computed
is ``[TO BE MEASURED]``. If no candidate meets the pre-registered criteria the report says so and stops: no accuracy, detection-rate or
false-alarm figure is claimed. Nothing here changes a threshold or a setting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from . import campaign as cp
from . import epoch_eval as ee
from . import epochs as ep
from .features import fuse_max, node_windows
from .frame_parity import parity_substream
from .jsonutil import dump_json
from .movement import fused_scores
from .provenance import provenance
from .recordings import load_recording
from .stats import DEFAULT_BLOCK, DEFAULT_BOOT, DEFAULT_SEED, auc, block_bootstrap_auc, block_bootstrap_rate_diff, empty_pair_control
from .tables import RecTables, load_tables

REPO = cp.REPO
PREREG = REPO / "reports" / "presence-eval-2026-11" / "PREREG-2026-11-recording-campaign.md"
# Pre-registered numbers (PREREG section 4). C1b and C2b are separate claims (they never change the verdict); C7 is report-only (no number).
C1_LOWER_MIN = 0.80
C1B_LOWER_MIN = 0.80
C2B_LOWER_MIN = 0.80
C3_MAX_EMPTY_SHARE = 0.05
C4_UPPER_MAX = 0.65
MIN_WINDOWS = 60
ALPHAS = (0.01, 0.05)
WINDOW_S = 1.5
MOVEMENT_LS = (45, 90)
NODE_SETS = {"fused4": (1, 2, 3, 4), "fused12": (1, 2)}
FEATURES = ("perturb_agc", "decor", "perturb")


class Refused(Exception):
    """The analysis must not run (validator failed, or the pre-registration is not committed)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def prereg_state(path: Path = PREREG, repo: Path = REPO) -> dict:
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
    rel = path.relative_to(repo).as_posix() if path.is_absolute() else str(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    tracked = git("ls-files", "--error-unmatch", rel).returncode == 0
    clean = tracked and git("diff", "--quiet", "HEAD", "--", rel).returncode == 0
    commit = git("log", "-1", "--format=%h", "--", rel).stdout.strip() if tracked else None
    return {"path": rel, "sha256": sha, "tracked": tracked, "clean": bool(clean), "commit": commit or None}


def parity_decor_table(series_by_node: dict, t0_ms: int) -> dict[int, dict[str, np.ndarray]]:
    """K7: per node, ``decor`` of the even and the odd sub-stream on the same 1.5 s windows, averaged (windows where both are finite)."""
    out = {}
    for node, s in series_by_node.items():
        ev, od = node_windows(parity_substream(s, 0), t0_ms), node_windows(parity_substream(s, 1), t0_ms)
        ke, ko, common = ev["k"], od["k"], np.intersect1d(ev["k"], od["k"])
        ie, io = np.searchsorted(ke, common), np.searchsorted(ko, common)
        val = 0.5 * (ev["decor"][ie] + od["decor"][io])
        keep = np.isfinite(val)
        out[node] = {"k": common[keep], "decor_parity": val[keep]}
    return out


def candidate_scores(seg: RecTables, parity: dict | None) -> dict[str, np.ndarray]:
    """{candidate id: time-ordered fused scores of one block}. ``parity`` (K7) is skipped when no per-frame series is available (legacy segments)."""
    out: dict[str, np.ndarray] = {}
    for set_name, nodes in NODE_SETS.items():
        if any(n not in seg.nodes for n in nodes):
            continue
        for feat in FEATURES:
            out[f"{feat}/{set_name}"] = fuse_max(seg.nodes, nodes, feat)[1]
        if parity is not None and all(n in parity for n in nodes):
            out[f"decor_parity/{set_name}"] = fuse_max(parity, nodes, "decor_parity")[1]
        for feat in ("decor", "perturb_agc"):
            for length in MOVEMENT_LS:
                out[f"move_{feat}_L{length}/{set_name}"] = fused_scores(seg, feat, length, nodes)[1]
    return out


def legacy_epoch_segments(tabs: dict[str, RecTables], nodes: tuple[int, ...] = (1, 2)) -> dict[str, RecTables]:
    """Dry-run helper for the EXISTING recordings (which contain link steps): the repo's own epoch segmentation, unchanged (epochs.build_timeline +
    epoch_eval.make_segments). A real campaign needs no such cut: the validator refuses a block with a held step, so its blocks ARE its epochs."""
    timeline = ep.build_timeline(ee.load_links(), nodes)
    usable = {rid: t for rid, t in tabs.items() if all(n in t.nodes for n in nodes)}
    segs, _log = ee.make_segments(usable, timeline, need=nodes)
    return segs


def _clean(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64)[np.isfinite(x)]


def _ci(pos: np.ndarray, neg: np.ndarray) -> dict:
    pos, neg = _clean(pos), _clean(neg)
    if len(pos) < MIN_WINDOWS or len(neg) < MIN_WINDOWS:
        return {"status": "[TO BE MEASURED]", "reason": f"insufficient data: {len(pos)} / {len(neg)} windows (< {MIN_WINDOWS})", "n_pos": len(pos), "n_neg": len(neg)}
    return {"status": "measured", **block_bootstrap_auc(pos, neg, block=DEFAULT_BLOCK, n_boot=DEFAULT_BOOT, seed=DEFAULT_SEED)}


def _flag_share(scores: np.ndarray, thr: float) -> float | None:
    s = _clean(scores)
    return float(np.mean(s > thr)) if len(s) >= MIN_WINDOWS else None


def _share_diff(fan: np.ndarray | None, empty_2: np.ndarray | None, thr: float) -> dict | None:
    """C2: d = (fan flagged share) - (empty_2 flagged share) with its moving-block bootstrap interval; None when either side has < MIN_WINDOWS."""
    if fan is None or empty_2 is None:
        return None
    f, e = _clean(fan), _clean(empty_2)
    if len(f) < MIN_WINDOWS or len(e) < MIN_WINDOWS:
        return None
    return block_bootstrap_rate_diff(f > thr, e > thr, block=DEFAULT_BLOCK, n_boot=DEFAULT_BOOT, seed=DEFAULT_SEED)


def _flagged_seconds(s: np.ndarray | None, thr: float) -> float | None:
    return None if s is None or len(_clean(s)) < MIN_WINDOWS else float(np.sum(_clean(s) > thr) * WINDOW_S)


def _unflagged_seconds(s: np.ndarray | None, thr: float) -> float | None:
    return None if s is None or len(_clean(s)) < MIN_WINDOWS else float(np.sum(_clean(s) <= thr) * WINDOW_S)


def evaluate(scores: dict[str, dict[str, np.ndarray]]) -> dict:
    """``scores[candidate][block_type]`` -> per-candidate comparisons, the C4 control, C1-C3 and the pre-registered verdict."""
    res: dict[str, dict] = {}
    for cand, by_block in scores.items():
        e1, e2 = by_block.get("empty_1"), by_block.get("empty_2")
        r: dict = {}
        r["c4_empty_vs_empty"] = (empty_pair_control({"empty_1": e1, "empty_2": e2}) if e1 is not None and e2 is not None else {"passes": None, "reason": "[TO BE MEASURED]"})
        for name, blk in (("walking_vs_empty_2", "walking"), ("still_vs_empty_2", "still")):
            r[name] = _ci(by_block[blk], e2) if blk in by_block and e2 is not None else {"status": "[TO BE MEASURED]"}
        r["walking_vs_empty_1"] = _ci(by_block["walking"], e1) if "walking" in by_block and e1 is not None else {"status": "[TO BE MEASURED]"}
        r["fan_person_vs_fan_alone"] = _ci(by_block["fan_with_person"], by_block["fan_alone"]) if "fan_with_person" in by_block and "fan_alone" in by_block else {"status": "[TO BE MEASURED]"}
        rates = {}
        if e1 is not None and len(_clean(e1)) >= MIN_WINDOWS:
            for alpha in ALPHAS:
                thr = float(np.quantile(_clean(e1), 1 - alpha))          # threshold fitted on the FIRST empty block only
                rates[f"alpha_{alpha:g}"] = {"threshold": thr, "status": "measured",
                                              "empty_2_flagged_share": _flag_share(e2, thr) if e2 is not None else None,
                                              "fan_alone_flagged_share": _flag_share(by_block["fan_alone"], thr) if "fan_alone" in by_block else None,
                                              "fan_minus_empty_2": _share_diff(by_block.get("fan_alone"), e2, thr),
                                              "walking_unflagged_seconds": _unflagged_seconds(by_block.get("walking"), thr),
                                              "still_unflagged_seconds": _unflagged_seconds(by_block.get("still"), thr),
                                              "empty_2_flagged_seconds": _flagged_seconds(e2, thr), "fan_alone_flagged_seconds": _flagged_seconds(by_block.get("fan_alone"), thr)}
        r["rates"] = rates or {"status": "[TO BE MEASURED]"}
        r["criteria"] = _criteria(r)
        res[cand] = r
    return res


C7_NOTE = ("report-only: both failure directions are measured and reported in seconds per block; no limit is pre-registered; "
           "C7 cannot make a candidate meet or fail the criteria")


def _lower_ok(c: dict, minimum: float) -> bool | None:
    return (c["lo"] >= minimum) if c.get("status") == "measured" else None


def _criteria(r: dict) -> dict:
    """Verdict = C4 gate and C1-C3 only. C1b, C2b are separate claims (reported, never in the verdict); C7 is report-only."""
    c4_pass = r["c4_empty_vs_empty"].get("passes")
    c1_pass = _lower_ok(r["walking_vs_empty_2"], C1_LOWER_MIN)
    rates = r["rates"] if isinstance(r["rates"], dict) else {}
    a1 = rates.get("alpha_0.01")
    c3_pass = (a1["empty_2_flagged_share"] <= C3_MAX_EMPTY_SHARE) if a1 and a1.get("empty_2_flagged_share") is not None else None
    diffs = [a["fan_minus_empty_2"] for a in rates.values() if isinstance(a, dict) and a.get("fan_minus_empty_2")]
    c2_pass = all(d["lo"] <= 0.0 for d in diffs) if len(diffs) == len(ALPHAS) else None      # fails only if the fan is flagged significantly MORE than the empty
    parts = {"C4": c4_pass, "C1": c1_pass, "C2": c2_pass, "C3": c3_pass}
    verdict = "[TO BE MEASURED]" if any(v is None for v in parts.values()) else ("MEETS" if all(parts.values()) else "DOES NOT MEET")
    return {**parts, "verdict": verdict, "C1b_still": _lower_ok(r["still_vs_empty_2"], C1B_LOWER_MIN),
            "C2b_fan_with_person": _lower_ok(r["fan_person_vs_fan_alone"], C2B_LOWER_MIN), "C7": C7_NOTE}


def run(folder: Path, out_dir: Path | None = None, *, allow_uncommitted_prereg: bool = False, min_minutes: dict | None = None) -> dict:
    vrep = cp.validate(folder, min_minutes)
    if not vrep.ok:
        raise Refused(1, "the campaign is INVALID, nothing was analysed:\n  " + "\n  ".join(vrep.failures))
    pre = prereg_state()
    committed = bool(pre["tracked"] and pre["clean"])
    if not committed and not allow_uncommitted_prereg:
        raise Refused(3, f"the pre-registration {pre['path']} is not committed and unmodified (tracked={pre['tracked']}, clean={pre['clean']}): commit it BEFORE analysing recordings "
                         "(--allow-uncommitted-prereg is for dry runs only and is recorded in the report)")
    states = {f["link_state_id"] for f in vrep.blocks.values()}
    complete = sorted(ls for ls in states if {f["block_type"] for f in vrep.blocks.values() if f["link_state_id"] == ls} >= set(cp.BLOCK_RULES))
    link_state = complete[0]
    scores: dict[str, dict[str, np.ndarray]] = {}
    for bid, facts in sorted(vrep.blocks.items()):
        if facts["link_state_id"] != link_state:
            continue
        parts = [Path(folder) / "blocks" / bid / p for p in facts["parts"]]
        seg = load_tables(parts, None, None)
        rec = load_recording(parts, None)
        for cand, vals in candidate_scores(seg, parity_decor_table(rec.nodes, seg.t0_ms)).items():
            scores.setdefault(cand, {})[facts["block_type"]] = vals
    results = evaluate(scores)
    meets = sorted(c for c, r in results.items() if r["criteria"]["verdict"] == "MEETS")
    report = {"provenance": provenance("python -m scripts.presence_eval.run_campaign", [str(folder)]), "prereg": pre, "dry_run_uncommitted_prereg": bool(allow_uncommitted_prereg and not committed),
              "validator": {"valid": True, "warnings": vrep.warnings, "blocks": vrep.blocks}, "link_state": link_state,
              "criteria_numbers": {"C1_lower_min": C1_LOWER_MIN, "C1b_lower_min": C1B_LOWER_MIN, "C2b_lower_min": C2B_LOWER_MIN, "C3_max_empty_share": C3_MAX_EMPTY_SHARE, "C4_upper_max": C4_UPPER_MAX, "min_windows": MIN_WINDOWS},
              "candidates": results, "candidates_meeting_criteria": meets,
              "conclusion": ("no candidate met the criteria; no accuracy, detection-rate or false-alarm figure is claimed" if not meets else "see the candidates listed; the pre-registered limits still apply"),
              "labels": "every number is `measured`; anything not computable is [TO BE MEASURED]; C7 is report-only (no limit pre-registered)"}
    out_dir = out_dir or (REPO / "reports" / "presence-eval-2026-11" / "results" / f"campaign-{Path(folder).name}")
    if cp._under_data(out_dir):
        raise Refused(2, f"refusing to write a report under data/: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_json(out_dir / "campaign_report.json", report)
    (out_dir / "campaign-report.md").write_text(render(report), encoding="utf-8")
    return report


def _f(v: object, spec: str = ".3f") -> str:
    return "[TO BE MEASURED]" if v is None or (isinstance(v, float) and v != v) else (format(v, spec) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v))


def render(rep: dict) -> str:
    pre = rep["prereg"]
    L = ["# Campaign analysis report", "", f"Pre-registration `{pre['path']}` sha256 `{pre['sha256']}` (tracked={pre['tracked']}, clean={pre['clean']}, commit={pre['commit']})"
         + ("; **DRY RUN: the pre-registration was not committed**" if rep["dry_run_uncommitted_prereg"] else ""),
         f"Link state analysed: `{rep['link_state']}`. {rep['labels']}.", "", f"**Conclusion: {rep['conclusion']}.**", "",
         "## C4 first: empty versus empty (a drifting score cannot be evaluated)", "", "| candidate | worst symmetric upper bound (limit 0.65) | passes |", "|--|--|--|"]
    for cand, r in rep["candidates"].items():
        c4 = r["c4_empty_vs_empty"]
        L.append(f"| {cand} | {_f(c4.get('worst_symmetric_upper_bound'))} | {_f(c4.get('passes'))} |")
    L += ["", "## C1-C3 and the two failure directions (measured; thresholds fitted on the FIRST empty block only)", "",
          "| candidate | walking vs empty_2 AUC [95 % CI] | still vs empty_2 AUC | empty_2 flagged share (alpha 1 %) | fan alone flagged share | walking seconds NOT flagged | empty_2 seconds flagged | C1 / C2 / C3 / C4 | verdict |", "|--|--|--|--|--|--|--|--|--|"]
    for cand, r in rep["candidates"].items():
        w, s = r["walking_vs_empty_2"], r["still_vs_empty_2"]
        a = r["rates"].get("alpha_0.01", {}) if isinstance(r["rates"], dict) else {}
        c = r["criteria"]
        L.append(f"| {cand} | {_f(w.get('auc'))} [{_f(w.get('lo'))}, {_f(w.get('hi'))}] | {_f(s.get('auc'))} | {_f(a.get('empty_2_flagged_share'))} | {_f(a.get('fan_alone_flagged_share'))} | "
                 f"{_f(a.get('walking_unflagged_seconds'), '.1f')} | {_f(a.get('empty_2_flagged_seconds'), '.1f')} | {_f(c['C1'])} / {_f(c['C2'])} / {_f(c['C3'])} / {_f(c['C4'])} | {c['verdict']} |")
    L += ["", "C2 is the interval rule: it fails only if the lower 95 % bound of d = (fan flagged share) - (empty_2 flagged share) is above 0, at alpha 1 % and 5 %.", "",
          "## Separate claims (never part of the verdict)", "", "| candidate | C1b still vs empty_2, lower bound >= 0.80 | C2b fan with a person vs fan alone, lower bound >= 0.80 |", "|--|--|--|"]
    for cand, r in rep["candidates"].items():
        c = r["criteria"]
        L.append(f"| {cand} | {_f(c['C1b_still'])} (lower {_f(r['still_vs_empty_2'].get('lo'))}) | {_f(c['C2b_fan_with_person'])} (lower {_f(r['fan_person_vs_fan_alone'].get('lo'))}) |")
    L += ["", f"## C7 ({C7_NOTE})", "", "Seconds per block at alpha 1 %: under-detection (walking / still seconds with no marker) and ghost (empty_2 / fan-alone seconds with a marker).", "",
          "| candidate | walking seconds NOT flagged | still seconds NOT flagged | empty_2 seconds flagged | fan alone seconds flagged |", "|--|--|--|--|--|"]
    for cand, r in rep["candidates"].items():
        a = r["rates"].get("alpha_0.01", {}) if isinstance(r["rates"], dict) else {}
        L.append(f"| {cand} | {_f(a.get('walking_unflagged_seconds'), '.1f')} | {_f(a.get('still_unflagged_seconds'), '.1f')} | {_f(a.get('empty_2_flagged_seconds'), '.1f')} | {_f(a.get('fan_alone_flagged_seconds'), '.1f')} |")
    L += ["", "K7 = `decor_parity`; movement scores are labelled \"movement, not presence\"."]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One-command analysis of a 2026-11 recording campaign")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--min-fan-person-min", type=float, default=None)
    ap.add_argument("--allow-uncommitted-prereg", action="store_true", help="dry runs only; recorded in the report")
    args = ap.parse_args(argv)
    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a folder", file=sys.stderr)
        return 2
    try:
        rep = run(args.folder, args.out, allow_uncommitted_prereg=args.allow_uncommitted_prereg,
                  min_minutes={"fan_with_person": args.min_fan_person_min} if args.min_fan_person_min is not None else None)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return e.code
    print(rep["conclusion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
