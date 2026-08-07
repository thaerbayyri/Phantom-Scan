"""Regression coverage for scripts/node_health_diagnostic.py's comparison math.

Built alongside PhantomScan_Node2_Diagnostic_Report.md (2026-08-07), which
found node2's moving-state motion signal at ~51% of node1's in one real
session but ~75-140% (normal) in every comparable same-week session. This
test proves the ratio/bucketing math itself on synthetic, clearly-labeled
known-asymmetric input, independent of any real recording -- the script's
own module docstring is explicit that it must never fabricate session data,
so real data is never used here either.
"""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from node_health_diagnostic import load_session  # noqa: E402


def _write_session_csv(path: Path, rows: list[dict], meta: dict) -> None:
    import json

    columns = [
        "target_state",
        "motion_n1",
        "motion_n2",
        "node1_fps",
        "node2_fps",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(f"# phantom_session_meta {json.dumps(meta)}\n")
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _meta(**overrides) -> dict:
    base = {
        "session_name": "synthetic",
        "fused_motion_threshold": 0.6,
    }
    base.update(overrides)
    return base


def test_symmetric_nodes_report_ratio_near_100_percent(tmp_path: Path) -> None:
    rows = [
        {"target_state": "moving", "motion_n1": "0.70", "motion_n2": "0.68", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "moving", "motion_n1": "0.65", "motion_n2": "0.66", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "none", "motion_n1": "0.30", "motion_n2": "0.28", "node1_fps": "43", "node2_fps": "43"},
    ]
    path = tmp_path / "symmetric.csv"
    _write_session_csv(path, rows, _meta())

    result = load_session(str(path))

    assert result.skipped_reason is None
    assert result.health_ratio_moving is not None
    assert 90.0 <= result.health_ratio_moving * 100 <= 110.0


def test_known_asymmetric_node2_reports_low_ratio(tmp_path: Path) -> None:
    """Mirrors the real dsgdfsg finding: node1 clears the gate, node2 barely
    registers at all -- the ratio must land far below 100%, and well under
    the report's 25% "flag" line."""
    rows = [
        {"target_state": "moving", "motion_n1": "0.80", "motion_n2": "0.10", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "moving", "motion_n1": "0.75", "motion_n2": "0.08", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "moving", "motion_n1": "0.70", "motion_n2": "0.12", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "none", "motion_n1": "0.40", "motion_n2": "0.05", "node1_fps": "43", "node2_fps": "43"},
    ]
    path = tmp_path / "asymmetric.csv"
    _write_session_csv(path, rows, _meta())

    result = load_session(str(path))

    assert result.skipped_reason is None
    assert result.n1_moving.avg == pytest.approx(0.75)
    assert result.n2_moving.avg == pytest.approx(0.10)
    ratio_pct = result.health_ratio_moving * 100
    assert ratio_pct < 25.0


def test_resting_and_moving_rows_are_bucketed_separately(tmp_path: Path) -> None:
    rows = [
        {"target_state": "moving", "motion_n1": "0.90", "motion_n2": "0.90", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "stale", "motion_n1": "0.10", "motion_n2": "0.10", "node1_fps": "43", "node2_fps": "43"},
        {"target_state": "none", "motion_n1": "0.05", "motion_n2": "0.05", "node1_fps": "43", "node2_fps": "43"},
    ]
    path = tmp_path / "buckets.csv"
    _write_session_csv(path, rows, _meta())

    result = load_session(str(path))

    assert result.n1_moving.n == 1
    assert result.n1_resting.n == 2
    assert result.n1_moving.avg == pytest.approx(0.90)
    assert result.n1_resting.avg == pytest.approx(0.075)


def test_session_without_meta_header_is_skipped_not_fabricated(tmp_path: Path) -> None:
    path = tmp_path / "no_meta.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("target_state,motion_n1,motion_n2,node1_fps,node2_fps\n")
        f.write("moving,0.7,0.7,43,43\n")

    result = load_session(str(path))

    assert result.skipped_reason == "no phantom_session_meta header"
    assert result.health_ratio_moving is None


def test_session_with_no_moving_rows_reports_ratio_as_none(tmp_path: Path) -> None:
    rows = [
        {"target_state": "none", "motion_n1": "0.30", "motion_n2": "0.30", "node1_fps": "43", "node2_fps": "43"},
    ]
    path = tmp_path / "no_moving.csv"
    _write_session_csv(path, rows, _meta())

    result = load_session(str(path))

    assert result.skipped_reason is None
    assert result.n1_moving.n == 0
    assert result.health_ratio_moving is None
