"""T1: parser + inventory behaviour on synthetic jsonl, and real-folder consistency with results/inventory.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from scripts.presence_eval.inventory import build_inventory, node_metrics, rssi_step_flags
from scripts.presence_eval.recordings import group_recordings, load_recording, part_number

REPO = Path(__file__).resolve().parents[1]
REAL_DIR = REPO / "data" / "datasets" / "room1"
REAL_JSON = REPO / "reports" / "presence-eval-2026-11" / "results" / "inventory.json"
T0 = 1_793_130_000_000


def header(part: int = 1, label: str = "empty", subject: str = "s1") -> dict:
    return {
        "type": "header", "schema": 1, "roomId": "room1", "subjectId": subject, "label": label, "count": 0,
        "notes": "", "startedAtMs": T0, "part": part,
        "geometry": {"roomWidthM": 4, "roomDepthM": 6, "anchors": {"1": {"x": -2, "z": -3}}}, "firmwareFilterMac": None,
    }


def frame(t: int, n: int, rssi: int = -40, base: float = 10.0) -> dict:
    return {"type": "frame", "t": t, "n": n, "rssi": rssi, "a": [base + i * 0.1 for i in range(51)]}


def write(path: Path, records: list, raw_extra: list[str] | None = None) -> Path:
    lines = [json.dumps(r) for r in records] + (raw_extra or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def name(label: str = "empty", subject: str = "s1", part: int = 1) -> str:
    suffix = "" if part == 1 else f".part{part}"
    return f"room1__{subject}__{label}__20261027T194207Z{suffix}.jsonl"


def test_parses_header_and_frames(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [header(), frame(T0 + 10, 1), frame(T0 + 30, 2), frame(T0 + 50, 1)])
    rec = load_recording([p])
    assert rec.label == "empty" and rec.subject == "s1"
    assert sorted(rec.nodes) == [1, 2]
    assert len(rec.nodes[1].t) == 2 and len(rec.nodes[2].t) == 1
    assert rec.nodes[1].a.shape == (2, 51)
    assert rec.stats.frames == 3 and rec.stats.headers == 1 and rec.stats.malformed_lines == 0


def test_part_continuation_is_concatenated_in_numeric_part_order(tmp_path: Path) -> None:
    write(tmp_path / name(), [header(1), frame(T0 + 100, 1)])
    write(tmp_path / name(part=2), [header(2), frame(T0 + 200, 1)])
    write(tmp_path / name(part=10), [header(10), frame(T0 + 300, 1)])
    groups = group_recordings(tmp_path)
    assert list(groups) == [name()]
    assert [part_number(p) for p in groups[name()]] == [1, 2, 10]
    rec = load_recording(groups[name()])
    assert rec.nodes[1].t.tolist() == [T0 + 100, T0 + 200, T0 + 300]
    assert len(rec.headers) == 3 and len(rec.paths) == 3


def test_malformed_lines_are_counted_not_fatal(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [header(), frame(T0 + 10, 1)], raw_extra=['{"type":"frame","t":1', "not json", '{"type":"other"}'])
    rec = load_recording([p])
    assert rec.stats.malformed_lines == 3
    assert rec.stats.frames == 1


def test_bad_length_and_unknown_node_frames_are_counted(tmp_path: Path) -> None:
    short = frame(T0 + 20, 1)
    short["a"] = short["a"][:10]
    p = write(tmp_path / name(), [header(), frame(T0 + 10, 1), short, frame(T0 + 30, 7)])
    rec = load_recording([p])
    assert rec.stats.bad_length_frames == 1 and rec.stats.unknown_node_frames == 1 and rec.stats.frames == 1


def test_missing_node_is_absent_not_zero_filled(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [header(), frame(T0 + 10, 1), frame(T0 + 20, 3)])
    inv = build_inventory(tmp_path, cache_dir=None)
    nodes = inv["recordings"][0]["nodes"]
    assert sorted(nodes) == ["1", "3"]
    assert load_recording([p]).nodes.keys() == {1, 3}


def test_out_of_order_frames_are_sorted_and_counted(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [header(), frame(T0 + 50, 1), frame(T0 + 10, 1), frame(T0 + 30, 1)])
    rec = load_recording([p])
    assert rec.nodes[1].t.tolist() == [T0 + 10, T0 + 30, T0 + 50]
    assert rec.stats.out_of_order_frames == 1


def test_node_metrics_rate_bursts_and_gaps(tmp_path: Path) -> None:
    # 5 s at 50 Hz (20 ms), a duplicated ms, and a 3 s gap.
    ts = list(range(0, 5000, 20)) + [4980] + [8000, 8020]
    recs = [header()] + [frame(T0 + t, 1) for t in sorted(ts)]
    rec = load_recording([write(tmp_path / name(), recs)])
    m = node_metrics(rec.nodes[1])
    assert m["frames"] == len(ts)
    assert m["frac_same_ms_as_prev"] == pytest.approx(1 / (len(ts) - 1), abs=1e-3)
    assert m["gaps_over_1s"] == 1 and m["longest_gap_s"] == pytest.approx(3.02, abs=0.01)
    assert m["per_second_max"] in (50, 51)
    assert m["frac_identical_consecutive_frames"] == 1.0
    assert m["unique_t"] == len(ts) - 1


def test_rssi_step_flag_uses_chronological_neighbours() -> None:
    def s(name_: str, start: int, rssi: float) -> dict:
        return {"name": name_, "_start_ms": start, "nodes": {"1": {"rssi_median": rssi}}}

    flags = rssi_step_flags([s("c", 3000, -47.0), s("a", 1000, -36.0), s("b", 2000, -35.0)])
    assert [(f["from"], f["to"], f["delta_db"]) for f in flags] == [("b", "c", -12.0)]
    assert rssi_step_flags([s("a", 1, -36.0), s("b", 2, -41.0)]) == []


def test_cache_roundtrip_is_identical(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [header(), frame(T0 + 10, 1, -33), frame(T0 + 30, 2, -44)])
    cache = tmp_path / "cache"
    fresh = load_recording([p], cache)
    cached = load_recording([p], cache)
    assert list(cache.glob("*.npz"))
    for n in fresh.nodes:
        assert np.array_equal(fresh.nodes[n].a, cached.nodes[n].a)
        assert np.array_equal(fresh.nodes[n].t, cached.nodes[n].t)
        assert np.array_equal(fresh.nodes[n].rssi, cached.nodes[n].rssi)
    assert cached.stats == fresh.stats and cached.label == fresh.label


@pytest.mark.skipif(not REAL_DIR.is_dir() or not REAL_JSON.is_file(), reason="real dataset or inventory.json not present")
def test_real_folder_counts_match_inventory_json() -> None:
    """Independent byte-level recount of valid frames per node vs results/inventory.json."""
    inv = json.loads(REAL_JSON.read_text(encoding="utf-8"))
    by_name = {r["name"]: r for r in inv["recordings"]}
    groups = group_recordings(REAL_DIR)
    assert set(groups) == set(by_name), "recording set on disk differs from inventory.json"
    # Two writers exist: the dashboard recorder emits compact JSON, the headless Python
    # recorder emits `{"type": "frame", ...}` with spaces. Count both.
    frame_re = re.compile(rb'^\{\s*"type"\s*:\s*"frame"')
    node_re = re.compile(rb'"n"\s*:\s*(\d+)')
    for rec_name, paths in groups.items():
        counts: dict[str, int] = {}
        for p in paths:
            with open(p, "rb") as fh:
                for line in fh:
                    if frame_re.match(line):
                        m = node_re.search(line)
                        key = m.group(1).decode()
                        counts[key] = counts.get(key, 0) + 1
        expected = {n: m["frames"] for n, m in by_name[rec_name]["nodes"].items()}
        bad = by_name[rec_name]["parse"]["bad_length_frames"] + by_name[rec_name]["parse"]["unknown_node_frames"]
        assert sum(counts.values()) == sum(expected.values()) + bad, rec_name
        assert {k: v for k, v in counts.items() if k in expected} == expected or bad > 0, rec_name
        assert by_name[rec_name]["parts"] == len(paths)
