"""c2 amendment A2: the soak gate checker. READ-ONLY. Never writes into data/.

    python -m scripts.presence_eval.soak_check <soak recording .jsonl> [--nodes 1,2,4] [--block1-start UTC] [--change TEXT ...] [--json OUT.json]

A soak is an empty-room recording of at least 3 h in the c2 link state. It passes when, for every analysed node over the whole soak:
  rate      the 60 s rolling median frame rate never falls below 0.7 x the node's reference rate (median rate of the first 10 min),
            and the existing per-recording gates hold (>= 90 % of seconds with frames, median rate inside [20, 100] fps);
  level     the median frame rate of the first 10 min is at least 54 fps;
  RSSI      no held step: the 60 s rolling median RSSI never differs from the first-10-min median RSSI by 6 dB or more;
and the timing rule holds when it is given: c2 block 1 starts at most 1 h after the soak ends, and no router, firmware, node placement or
channel change occurred in between (otherwise a new soak is needed). The produced rate from `seq` and the D+P / D / D? / P labels of
seq_report are printed as REPORT-ONLY and never decide the verdict. Observation only: nothing here says anything about a cause.

Exit 0 = every evaluated condition passed; 1 = at least one failed; 2 = usage error. The timing rule is reported "not evaluated" until
--block1-start is given. Parameters other than the spec values exist only so the tests can use short synthetic soaks; using them prints a warning.
"""
from __future__ import annotations

import argparse
import json
import sys
from array import array
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from . import seq_report as sr
from .campaign import MAX_FPS
from .epochs import HELD_FRACTION, MIN_BASELINE_FPS, STEP_DB
from .recordings import iter_lines

MIN_SOAK_H = 3.0
REF_S = 600                 # reference window: the first 10 minutes
WINDOW_S = 60               # rolling window
COLLAPSE_RATIO = 0.7        # the pre-registered rate-collapse ratio
MIN_LEVEL_FPS = 54.0        # 0.8 x about 67 fps
TIMING_MAX_H = 1.0
RSSI_BINS = 128
REPO_DATA = Path(__file__).resolve().parents[2] / "data"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class SoakResult:
    checks: list[Check] = field(default_factory=list)
    timing: str = "not evaluated"
    report_only: dict = field(default_factory=dict)
    soak_start_utc: str = ""
    soak_end_utc: str = ""
    duration_h: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_series(paths: Sequence[Path]) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """node -> (t_ms, rssi) for every frame; only these two fields are kept so a multi-hour soak stays small in memory."""
    ts: dict[int, array] = {}
    rs: dict[int, array] = {}
    for path in paths:
        for kind, obj in iter_lines(path):
            if kind != "frame":
                continue
            n, t, r = obj.get("n"), obj.get("t"), obj.get("rssi")  # type: ignore[union-attr]
            if not isinstance(n, int) or isinstance(n, bool) or not isinstance(t, (int, float)) or not isinstance(r, (int, float)):
                continue
            ts.setdefault(n, array("q")).append(int(t))
            rs.setdefault(n, array("h")).append(int(r))
    return {n: (np.asarray(ts[n], dtype=np.int64), np.asarray(rs[n], dtype=np.int64)) for n in ts}


def per_second_counts(t_ms: np.ndarray, t0: int, n_sec: int) -> np.ndarray:
    idx = (t_ms - t0) // 1000
    return np.bincount(idx[(idx >= 0) & (idx < n_sec)], minlength=n_sec)


def per_second_rssi_hist(t_ms: np.ndarray, rssi: np.ndarray, t0: int, n_sec: int) -> np.ndarray:
    idx = (t_ms - t0) // 1000
    ok = (idx >= 0) & (idx < n_sec)
    flat = idx[ok] * RSSI_BINS + np.clip(-rssi[ok], 0, RSSI_BINS - 1)
    return np.bincount(flat, minlength=n_sec * RSSI_BINS).reshape(n_sec, RSSI_BINS)


def hist_median(h: np.ndarray) -> np.ndarray:
    """True median (mean of the two middle values for an even count) of each histogram row; RSSI = -bin. NaN for an empty row."""
    n = h.sum(axis=1)
    cum = np.cumsum(h, axis=1)
    lo, hi = (n - 1) // 2, n // 2
    i_lo = (cum > lo[:, None]).argmax(axis=1)
    i_hi = (cum > hi[:, None]).argmax(axis=1)
    return np.where(n > 0, -(i_lo + i_hi) / 2.0, np.nan)


def rolling_rssi_median(hist: np.ndarray, window_s: int) -> np.ndarray:
    cum = np.vstack([np.zeros((1, hist.shape[1]), dtype=hist.dtype), np.cumsum(hist, axis=0)])
    return hist_median(cum[window_s:] - cum[: len(cum) - window_s])


def check_node(node: int, t_ms: np.ndarray, rssi: np.ndarray, t0: int, n_sec: int, ref_s: int, window_s: int, collapse: float, min_level: float, step_db: float) -> list[Check]:
    out: list[Check] = []
    fps = per_second_counts(t_ms, t0, n_sec)
    coverage = float(np.mean(fps > 0))
    med_fps = float(np.median(fps[fps > 0])) if (fps > 0).any() else 0.0
    out.append(Check(f"per-recording gates, node {node}", coverage >= HELD_FRACTION and MIN_BASELINE_FPS <= med_fps <= MAX_FPS,
                     f"frames in {coverage:.0%} of the seconds (needs {HELD_FRACTION:.0%}); median rate {med_fps:.1f} fps (needs {MIN_BASELINE_FPS:g} to {MAX_FPS:g})"))
    ref_rate = float(np.median(fps[:ref_s]))
    out.append(Check(f"level, node {node}", ref_rate >= min_level, f"median rate of the first {ref_s} s is {ref_rate:.1f} fps (needs at least {min_level:g})"))
    if n_sec < window_s:
        out.append(Check(f"rate, node {node}", False, f"the soak is shorter than the {window_s} s rolling window"))
        out.append(Check(f"RSSI, node {node}", False, f"the soak is shorter than the {window_s} s rolling window"))
        return out
    roll = np.median(sliding_window_view(fps, window_s), axis=1)
    low = roll < collapse * ref_rate if ref_rate > 0 else np.ones_like(roll, dtype=bool)
    detail = f"lowest {window_s} s rolling median {float(roll.min()):.1f} fps = {float(roll.min()) / ref_rate:.2f} x reference {ref_rate:.1f}" if ref_rate > 0 else "reference rate is 0"
    if low.any():
        detail += f"; first below {collapse:g} x at +{int(np.argmax(low))} s ({int(low.sum())} windows)"
    out.append(Check(f"rate, node {node}", not low.any(), detail))
    hist = per_second_rssi_hist(t_ms, rssi, t0, n_sec)
    ref_rssi = float(hist_median(hist[:ref_s].sum(axis=0, keepdims=True))[0])
    dev = np.abs(rolling_rssi_median(hist, window_s) - ref_rssi)
    dev = np.where(np.isnan(dev), 0.0, dev)
    held = dev >= step_db
    detail = f"largest difference of the {window_s} s rolling median RSSI from the first-{ref_s}-s median {ref_rssi:.1f} dBm is {float(dev.max()):.2f} dB (fails at {step_db:g} or more)"
    if held.any():
        detail += f"; first at +{int(np.argmax(held))} s"
    out.append(Check(f"RSSI, node {node}", not held.any(), detail))
    return out


def timing_check(soak_end_ms: float, block1_start: datetime | None, changes: Sequence[str], max_h: float) -> tuple[str, list[Check]]:
    checks: list[Check] = []
    if changes:
        checks.append(Check("timing rule: no change in between", False, "declared change(s) between the soak and c2 block 1, a new soak is needed: " + "; ".join(changes)))
    if block1_start is None:
        return ("fail" if changes else "not evaluated"), checks
    delta = block1_start - datetime.fromtimestamp(soak_end_ms / 1000, timezone.utc)
    ok = timedelta(0) <= delta <= timedelta(hours=max_h)
    checks.append(Check("timing rule: block 1 within 1 h of the soak end", ok, f"c2 block 1 starts {delta.total_seconds() / 60:+.1f} min after the soak ended (needs 0 to {max_h * 60:g} min)"))
    return ("pass" if all(c.ok for c in checks) else "fail"), checks


def seq_report_only(paths: Sequence[Path]) -> dict:
    try:
        _, s = sr.build(paths, 10, None, COLLAPSE_RATIO)
    except ValueError as exc:
        return {"note": str(exc)}
    frames = sum(n["frames"] for n in s["nodes"].values())
    with_seq = sum(n["with_seq"] for n in s["nodes"].values())
    if not with_seq:
        return {"note": "no seq in this recording (made before the step 0 recorder): the produced rate and the D/P labels are not available"}
    return {"frames": frames, "frames_with_seq": with_seq, "flagged_windows": s["flagged_windows"], "cases": s["cases"], "cross_node": s["cross_node"],
            "reboots": {n: len(v["reboots"]) for n, v in s["nodes"].items()}}


def check_soak(paths: Sequence[Path], nodes: Sequence[int] | None = None, *, min_hours: float = MIN_SOAK_H, ref_s: int = REF_S, window_s: int = WINDOW_S,
               collapse: float = COLLAPSE_RATIO, min_level_fps: float = MIN_LEVEL_FPS, step_db: float = STEP_DB, block1_start: datetime | None = None,
               changes: Sequence[str] = (), timing_max_h: float = TIMING_MAX_H) -> SoakResult:
    res = SoakResult()
    non_spec = [f"{k}={v}" for k, v, spec in (("min_hours", min_hours, MIN_SOAK_H), ("reference_s", ref_s, REF_S), ("window_s", window_s, WINDOW_S), ("collapse", collapse, COLLAPSE_RATIO),
                                              ("min_level_fps", min_level_fps, MIN_LEVEL_FPS), ("step_db", step_db, STEP_DB), ("timing_max_h", timing_max_h, TIMING_MAX_H)) if v != spec]
    if non_spec:
        res.warnings.append("NON-SPEC PARAMETERS (tests only; this is not the pre-registered gate): " + ", ".join(non_spec))
    series = load_series(paths)
    if not series:
        raise ValueError("no usable frames in the recording")
    analysed = sorted(nodes) if nodes else sorted(series)
    t0 = min(int(t[0]) for t, _ in series.values())
    t1 = max(int(t[-1]) for t, _ in series.values())
    n_sec = int((t1 - t0) // 1000) + 1
    res.soak_start_utc, res.soak_end_utc, res.duration_h = _iso(t0), _iso(t1), (t1 - t0) / 3_600_000
    res.checks.append(Check("duration", res.duration_h >= min_hours, f"{res.duration_h:.2f} h of frames (needs at least {min_hours:g} h)"))
    for n in analysed:
        if n not in series:
            res.checks.append(Check(f"node {n} present", False, f"node {n} delivered no frames"))
            continue
        res.checks += check_node(n, series[n][0], series[n][1], t0, n_sec, ref_s, window_s, collapse, min_level_fps, step_db)
    res.timing, timing_checks = timing_check(float(t1), block1_start, changes, timing_max_h)
    res.checks += timing_checks
    res.report_only = seq_report_only(paths)
    return res


def render(res: SoakResult) -> list[str]:
    out = list(res.warnings)
    out.append(f"soak {res.soak_start_utc} to {res.soak_end_utc} ({res.duration_h:.2f} h of frames)")
    out += [f"{'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}" for c in res.checks]
    if res.timing == "not evaluated":
        out.append("timing rule: not evaluated (give --block1-start; declare any router, firmware, node placement or channel change with --change)")
    ro = res.report_only
    out.append("REPORT-ONLY (does not decide the verdict): " + (ro["note"] if "note" in ro else
               f"{ro['frames_with_seq']}/{ro['frames']} frames carry seq; flagged windows {ro['flagged_windows']}; cases {ro['cases']}; reboots {ro['reboots']}"))
    out.append(f"VERDICT: {'PASS' if res.passed else 'FAIL'} (recording conditions" + (", timing rule" if res.timing != "not evaluated" else "") + ")"
               + ("; c2 may start only if block 1 starts within 1 h of the soak end with no router, firmware, node placement or channel change in between" if res.passed and res.timing == "not evaluated" else ""))
    return out


def _under_data(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_DATA.resolve())
        return True
    except ValueError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="c2 soak gate checker (read-only)")
    ap.add_argument("recording", type=Path, nargs="+", help="the soak .jsonl recording (its .partN siblings are added automatically)")
    ap.add_argument("--nodes", default=None, help="comma-separated node ids to analyse (default: every node in the recording)")
    ap.add_argument("--block1-start", default=None, help="UTC ISO time at which c2 block 1 starts or started (enables the timing rule)")
    ap.add_argument("--change", action="append", default=[], help="a router, firmware, node placement or channel change since the soak (repeatable)")
    ap.add_argument("--min-hours", type=float, default=MIN_SOAK_H)
    ap.add_argument("--reference-s", type=int, default=REF_S)
    ap.add_argument("--window-s", type=int, default=WINDOW_S)
    ap.add_argument("--json", type=Path, default=None, help="also write the result here (never under data/)")
    args = ap.parse_args(argv)
    if args.json is not None and _under_data(args.json):
        print(f"error: refusing to write a report under data/: {args.json}", file=sys.stderr)
        return 2
    paths = [p for rec in args.recording for p in sr.expand_parts(rec)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        print(f"error: not a file: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        nodes = [int(x) for x in args.nodes.split(",")] if args.nodes else None
        b1 = datetime.fromisoformat(args.block1_start.replace("Z", "+00:00")) if args.block1_start else None
        if b1 is not None and b1.tzinfo is None:
            b1 = b1.replace(tzinfo=timezone.utc)
        res = check_soak(paths, nodes, min_hours=args.min_hours, ref_s=args.reference_s, window_s=args.window_s, block1_start=b1, changes=args.change)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(render(res)))
    if args.json is not None:
        args.json.write_text(json.dumps({"passed": res.passed, "timing": res.timing, "soak_start_utc": res.soak_start_utc, "soak_end_utc": res.soak_end_utc, "duration_h": res.duration_h,
                                         "checks": [c.__dict__ for c in res.checks], "report_only": res.report_only, "warnings": res.warnings}, indent=2, default=float), encoding="utf-8")
    return 0 if res.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
