#!/usr/bin/env python3
"""Per-node signal-health comparison for real recorded two-node sessions.

Consumes REAL recorded session CSVs produced by the live TS dashboard's
recording feature (server/lib/recording-export.ts, saved under
data/sessions/<name>_<timestamp>.csv). It does not generate, simulate, or
fabricate any data -- if a file has no `# phantom_session_meta` header or no
motion_n1/motion_n2 columns, it is skipped and reported as skipped, not
silently ignored or backfilled with invented numbers.

Background: PhantomScan_RealLiveFailure_Analysis.md (2026-08-07) found that in
one real session, motion_n2 (node 2's gain-normalized motion statistic, see
computeNodeMotionFromMatrix in server/lib/node-fusion.ts) never approached the
presence-gate threshold, effectively making node 2 a silent contributor to
Math.max(motion1, motion2). This script makes that comparison repeatable
across any session, so it can be re-run after a physical adjustment (antenna
move, connector reseat, node swap) to see immediately whether it helped --
without needing another full investigation each time.

IMPORTANT SCHEMA LIMITATION (documented, not worked around): the recording
format's h1_re/h1_im/h2_re/h2_im/rssi columns are per-PACKET (whichever node's
packet triggered that tick), not per-node-tagged, so this script cannot
recover each node's raw resting RF amplitude/RSSI directly. `motion_n1` /
`motion_n2` (present on every row, computed identically for both nodes by
computeNodeMotionFromMatrix) are the best available per-node signal proxy in
the current recording format, and are what this script uses throughout. A
future recording-format change that tags raw samples with node_id, or exports
each node's absStd/mean directly, would let a future version of this script
compare true raw baseline amplitude instead of the already-normalized motion
ratio -- out of scope here.

Usage:
    python scripts/node_health_diagnostic.py data/sessions/dsgdfsg_*.csv
    python scripts/node_health_diagnostic.py --glob "data/sessions/case*.csv"
    python scripts/node_health_diagnostic.py --glob "data/sessions/*.csv" --summary-only
"""

from __future__ import annotations

import argparse
import csv
import glob as globmod
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NodeMotionStats:
    n: int = 0
    total: float = 0.0
    max_v: float = 0.0

    def add(self, v: float) -> None:
        self.n += 1
        self.total += v
        if v > self.max_v:
            self.max_v = v

    @property
    def avg(self) -> float:
        return self.total / self.n if self.n else 0.0


@dataclass
class SessionHealth:
    path: str
    session_name: str | None
    skipped_reason: str | None = None
    fused_motion_threshold: float | None = None
    node1_fps_avg: float = 0.0
    node2_fps_avg: float = 0.0
    # Buckets mirror target_state: "moving" (gate fired), "resting" (none/stale).
    n1_moving: NodeMotionStats = field(default_factory=NodeMotionStats)
    n2_moving: NodeMotionStats = field(default_factory=NodeMotionStats)
    n1_resting: NodeMotionStats = field(default_factory=NodeMotionStats)
    n2_resting: NodeMotionStats = field(default_factory=NodeMotionStats)

    @property
    def health_ratio_moving(self) -> float | None:
        """node2's moving-state avg motion as a fraction of node1's.

        1.0 = equal contribution. Near 0 = node2 essentially silent (the
        Aug-7 finding). This is the single number to watch across re-runs
        after a physical adjustment.
        """
        if self.n1_moving.n == 0 or self.n1_moving.avg == 0:
            return None
        return self.n2_moving.avg / self.n1_moving.avg

    @property
    def fps_ratio(self) -> float | None:
        if self.node1_fps_avg == 0:
            return None
        return self.node2_fps_avg / self.node1_fps_avg


def load_session(path: str) -> SessionHealth:
    name = Path(path).name
    with open(path, "r", encoding="utf-8", newline="") as f:
        first_line = f.readline()
        meta: dict = {}
        if first_line.startswith("# phantom_session_meta "):
            try:
                meta = json.loads(first_line[len("# phantom_session_meta "):])
            except json.JSONDecodeError:
                meta = {}
        else:
            f.seek(0)

        reader = csv.DictReader(f)
        rows = list(reader)

    if not meta:
        return SessionHealth(path=path, session_name=None, skipped_reason="no phantom_session_meta header")
    if not rows or "motion_n1" not in rows[0] or "motion_n2" not in rows[0]:
        return SessionHealth(
            path=path,
            session_name=meta.get("session_name"),
            skipped_reason="no motion_n1/motion_n2 columns (pre-dates this recording format)",
        )

    result = SessionHealth(
        path=path,
        session_name=meta.get("session_name"),
        fused_motion_threshold=meta.get("fused_motion_threshold"),
    )

    fps1_vals: list[float] = []
    fps2_vals: list[float] = []

    for row in rows:
        state = row.get("target_state", "")
        m1_raw = row.get("motion_n1", "")
        m2_raw = row.get("motion_n2", "")
        try:
            m1 = float(m1_raw)
            m2 = float(m2_raw)
        except ValueError:
            continue

        bucket1, bucket2 = (
            (result.n1_moving, result.n2_moving)
            if state == "moving"
            else (result.n1_resting, result.n2_resting)
        )
        bucket1.add(m1)
        bucket2.add(m2)

        try:
            fps1_vals.append(float(row.get("node1_fps", "")))
            fps2_vals.append(float(row.get("node2_fps", "")))
        except ValueError:
            pass

    if fps1_vals:
        result.node1_fps_avg = sum(fps1_vals) / len(fps1_vals)
    if fps2_vals:
        result.node2_fps_avg = sum(fps2_vals) / len(fps2_vals)

    return result


def format_session_report(h: SessionHealth) -> str:
    if h.skipped_reason:
        return f"{h.path}\n  SKIPPED: {h.skipped_reason}"

    lines = [f"{h.path}  (session_name={h.session_name!r})"]
    if h.fps_ratio is not None:
        lines.append(
            f"  fps: node1={h.node1_fps_avg:.1f} node2={h.node2_fps_avg:.1f}"
            f" (ratio n2/n1={h.fps_ratio:.2f})"
        )
    else:
        lines.append(f"  fps: node1={h.node1_fps_avg:.1f} node2={h.node2_fps_avg:.1f}")
    if h.fused_motion_threshold is not None:
        lines.append(f"  fused_motion_threshold: {h.fused_motion_threshold}")
    if h.n1_moving.n or h.n2_moving.n:
        lines.append(
            f"  moving ({h.n1_moving.n} rows): "
            f"motion_n1 avg={h.n1_moving.avg:.3f} max={h.n1_moving.max_v:.3f} | "
            f"motion_n2 avg={h.n2_moving.avg:.3f} max={h.n2_moving.max_v:.3f}"
        )
    else:
        lines.append("  moving (0 rows): gate never fired this session")
    lines.append(
        f"  resting ({h.n1_resting.n} rows): "
        f"motion_n1 avg={h.n1_resting.avg:.3f} max={h.n1_resting.max_v:.3f} | "
        f"motion_n2 avg={h.n2_resting.avg:.3f} max={h.n2_resting.max_v:.3f}"
    )
    ratio = h.health_ratio_moving
    if ratio is not None:
        pct = ratio * 100
        flag = " <-- node2 contributing <25% of node1's moving-state signal" if ratio < 0.25 else ""
        lines.append(f"  node2/node1 moving-state motion ratio: {pct:.1f}%{flag}")
    else:
        lines.append("  node2/node1 moving-state motion ratio: n/a (no moving rows)")
    return "\n".join(lines)


def format_summary_table(results: list[SessionHealth]) -> str:
    usable = [r for r in results if r.skipped_reason is None and r.health_ratio_moving is not None]
    if not usable:
        return "(no sessions with moving-state data to summarize)"
    lines = [f"{'session':<40} {'n1_avg':>8} {'n2_avg':>8} {'ratio%':>8}"]
    for r in usable:
        lines.append(
            f"{(r.session_name or Path(r.path).name)[:40]:<40} "
            f"{r.n1_moving.avg:>8.3f} {r.n2_moving.avg:>8.3f} "
            f"{r.health_ratio_moving * 100:>7.1f}%"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Explicit CSV paths")
    parser.add_argument("--glob", dest="glob_pattern", help="Glob pattern for session CSVs")
    parser.add_argument("--summary-only", action="store_true", help="Print only the cross-session summary table")
    args = parser.parse_args()

    paths = list(args.paths)
    if args.glob_pattern:
        paths.extend(sorted(globmod.glob(args.glob_pattern)))

    if not paths:
        print("No session files given. Use positional paths or --glob.", file=sys.stderr)
        return 1

    results = [load_session(p) for p in paths]

    if not args.summary_only:
        for r in results:
            print(format_session_report(r))
            print()

    print("=== Cross-session summary (moving-state motion ratio, node2/node1) ===")
    print(format_summary_table(results))

    skipped = [r for r in results if r.skipped_reason]
    if skipped:
        print(f"\n{len(skipped)} file(s) skipped (see SKIPPED lines above for reasons).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
