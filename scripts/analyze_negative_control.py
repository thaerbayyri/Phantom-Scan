#!/usr/bin/env python3
"""Negative-control false-positive analysis (Item 2, PhantomScan_Research_Gap_Analysis.md).

Consumes REAL recorded session CSVs produced by the live TS dashboard's
recording feature (server/lib/recording-export.ts, saved under
data/sessions/<name>_<timestamp>.csv). It does not generate, simulate, or
fabricate any data -- if no matching real session files are found, it says so
explicitly rather than inventing a number.

For each session it reports:
  - total ticks, ticks with target_visible=1 (a "false trigger" IF the
    session's device is a known non-human mover -- fan/curtain/HVAC/empty
    room; for a real-human session this same column is the true-positive
    rate instead, so --device is required to interpret the numbers).
  - a breakdown by classifier_corroboration (Item 1's new column): how many
    visible-target ticks were "confirmed"/"inconclusive"/"not_evaluated" by
    the deterministic MicroDopplerClassifier gate, and -- as a sanity check --
    how many (should be zero) were "contradicted" yet still visible, which
    would indicate a bug in the Item 1 gating logic.
  - NOTE: sessions recorded before Item 1 shipped have no
    classifier_corroboration column at all; those ticks are reported as
    "column_absent (pre-Item-1 recording)", not "not_evaluated", so the two
    cases are never conflated.

Usage:
    python scripts/analyze_negative_control.py --device fan data/sessions/emty_room_with_fan_*.csv
    python scripts/analyze_negative_control.py --device empty data/sessions/empty_room_fan_off_*.csv
    python scripts/analyze_negative_control.py --glob "data/sessions/*fan*.csv"

This script deliberately does NOT compute a single repo-wide "the false
positive rate is X%" headline -- negative-control sessions differ in device,
distance, and firmware/threshold version (see the session's own
phantom_session_meta header, printed per-file). Aggregate only sessions you
know are comparable.
"""

from __future__ import annotations

import argparse
import csv
import glob as globmod
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionResult:
    path: str
    device: str | None
    meta: dict
    total_rows: int
    visible_rows: int
    node_mode_counts: Counter
    corroboration_on_visible: Counter
    corroboration_on_suppressed: Counter
    has_corroboration_column: bool
    suspicious_contradicted_but_visible: int


def load_session(path: str, device: str | None) -> SessionResult:
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        meta: dict = {}
        if first_line.startswith("# phantom_session_meta "):
            try:
                meta = json.loads(first_line[len("# phantom_session_meta "):])
            except json.JSONDecodeError:
                meta = {}
        else:
            # Not our format's meta line -- rewind so the header row isn't lost.
            f.seek(0)

        reader = csv.DictReader(f)
        rows = list(reader)

    has_corroboration_column = bool(rows) and "classifier_corroboration" in rows[0]
    node_mode_counts: Counter = Counter()
    corroboration_on_visible: Counter = Counter()
    corroboration_on_suppressed: Counter = Counter()
    visible_rows = 0
    suspicious = 0

    for row in rows:
        node_mode_counts[row.get("node_mode", "")] += 1
        visible = row.get("target_visible") == "1"
        corroboration = row.get("classifier_corroboration") if has_corroboration_column else None

        if visible:
            visible_rows += 1
            key = corroboration if has_corroboration_column else "column_absent (pre-Item-1 recording)"
            corroboration_on_visible[key] += 1
            if corroboration == "contradicted":
                suspicious += 1
        else:
            key = corroboration if has_corroboration_column else "column_absent (pre-Item-1 recording)"
            corroboration_on_suppressed[key] += 1

    return SessionResult(
        path=path,
        device=device,
        meta=meta,
        total_rows=len(rows),
        visible_rows=visible_rows,
        node_mode_counts=node_mode_counts,
        corroboration_on_visible=corroboration_on_visible,
        corroboration_on_suppressed=corroboration_on_suppressed,
        has_corroboration_column=has_corroboration_column,
        suspicious_contradicted_but_visible=suspicious,
    )


def print_result(r: SessionResult) -> None:
    print(f"\n=== {r.path} ===")
    if r.device:
        print(f"  device (as labeled by --device / caller): {r.device}")
    if r.meta:
        print(f"  session_name: {r.meta.get('session_name')}")
        print(
            f"  motion_threshold={r.meta.get('motion_threshold')} "
            f"scalar_motion_threshold={r.meta.get('scalar_motion_threshold')} "
            f"node1_fps_start={r.meta.get('node1_fps_start')} node2_fps_start={r.meta.get('node2_fps_start')}"
        )
    if r.total_rows == 0:
        print("  [UNVERIFIED] empty/unreadable session file -- 0 rows parsed.")
        return

    rate = r.visible_rows / r.total_rows
    print(f"  total ticks: {r.total_rows}")
    print(f"  node_mode breakdown: {dict(r.node_mode_counts)}")
    print(
        f"  target_visible=1 ticks: {r.visible_rows} "
        f"({rate:.1%}) -- this is a FALSE-POSITIVE rate only if the device is a "
        f"known non-human mover (fan/curtain/HVAC/empty room)."
    )
    if not r.has_corroboration_column:
        print(
            "  [UNVERIFIED] this recording predates Item 1's classifier-corroboration "
            "gate (no classifier_corroboration column) -- it cannot show whether the "
            "Item 1 fix would have suppressed any of these false triggers. Re-run this "
            "same negative control with the current build to measure that."
        )
    else:
        print(f"  classifier_corroboration on VISIBLE ticks: {dict(r.corroboration_on_visible)}")
        print(f"  classifier_corroboration on SUPPRESSED ticks: {dict(r.corroboration_on_suppressed)}")
        if r.suspicious_contradicted_but_visible:
            print(
                f"  [BUG SUSPECTED] {r.suspicious_contradicted_but_visible} ticks were "
                "visible AND classifier_corroboration=='contradicted' -- this should be "
                "impossible per Item 1's gating logic (a confident 'mechanical' call must "
                "suppress the target). Investigate before trusting this session's numbers."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Session CSV file path(s)")
    parser.add_argument("--glob", dest="glob_pattern", help="Glob pattern for session CSV files")
    parser.add_argument(
        "--device",
        default=None,
        help="Label for what this session's negative control was (fan/curtain/hvac/empty/human). "
        "Applied to all files in this invocation -- run separately per device.",
    )
    args = parser.parse_args()

    paths: list[str] = list(args.paths)
    if args.glob_pattern:
        paths.extend(sorted(globmod.glob(args.glob_pattern)))

    if not paths:
        print(
            "[TO BE MEASURED] No session file(s) given. This script only analyzes REAL "
            "recorded sessions (data/sessions/*.csv produced by the live dashboard's "
            "recording feature) -- it does not fabricate a substitute answer. Record a "
            "negative-control session first (see docs/NEGATIVE_CONTROL_CHECKLIST.md), "
            "then re-run:\n"
            "  python scripts/analyze_negative_control.py --device fan data/sessions/<file>.csv",
            file=sys.stderr,
        )
        return 1

    results = [load_session(p, args.device) for p in paths if Path(p).is_file()]
    missing = [p for p in paths if not Path(p).is_file()]
    for m in missing:
        print(f"[UNVERIFIED] file not found, skipped: {m}", file=sys.stderr)

    for r in results:
        print_result(r)

    if len(results) > 1:
        total = sum(r.total_rows for r in results)
        visible = sum(r.visible_rows for r in results)
        print(f"\n=== Aggregate across {len(results)} file(s) (only if truly comparable -- see per-file meta above) ===")
        if total:
            print(f"  total ticks: {total}, target_visible=1 ticks: {visible} ({visible / total:.1%})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
