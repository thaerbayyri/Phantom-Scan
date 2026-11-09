"""PS-FIX-36 step 0: the offline seq report (scripts/presence_eval/seq_report.py). Synthetic recordings in temp folders for every rule,
plus a read-only structural check on data/datasets/smoke-test when that folder exists (it is local, gitignored data)."""
from __future__ import annotations

import json
from itertools import cycle
from pathlib import Path
from typing import Sequence

import pytest

from scripts.presence_eval import seq_report as sr

ROOT = Path(__file__).resolve().parents[1]
BASE_MS = 1_794_000_000_000
HEADER = {"type": "header", "schema": 2, "roomId": "lab", "subjectId": "s1", "label": "empty", "count": 0, "notes": "", "startedAtMs": BASE_MS, "part": 1}


def write_rows(path: Path, rows: Sequence[tuple[int, float, int | None, int | None]]) -> Path:
    """rows = (node, t_ms, seq or None, nsc or None); written sorted by time like the recorder."""
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(HEADER) + "\n")
        for node, t, seq, nsc in sorted(rows, key=lambda r: r[1]):
            obj: dict = {"type": "frame", "t": int(t), "n": node, "rssi": -40, "a": [1.0] * 51}
            if seq is not None:
                obj["seq"] = seq
            if nsc is not None:
                obj["nsc"] = nsc
            fh.write(json.dumps(obj) + "\n")
    return path


def plan_rows(plan: dict[int, list[tuple[int, int, Sequence[int]]]], *, seq: bool = True) -> list[tuple[int, float, int | None, int | None]]:
    """plan[node] = per minute (frames, seq step per frame, nsc pattern); frames evenly spaced inside the minute."""
    rows: list[tuple[int, float, int | None, int | None]] = []
    for node, minutes in plan.items():
        counter = 1000 * node
        for m, (frames, step, pattern) in enumerate(minutes):
            nsc_iter = cycle(pattern)
            for i in range(frames):
                counter += step
                rows.append((node, BASE_MS + m * 60_000 + i * 60_000 / max(frames, 1), counter if seq else None, next(nsc_iter) if seq else None))
    return rows


def summary(path: Path, **kw) -> dict:
    return sr.build(sr.expand_parts(path), kw.get("reference_minutes", 10), kw.get("override"), kw.get("collapse", 0.7))[1]


def minute(s: dict, node: int, i: int) -> dict:
    return s["nodes"][str(node)]["minutes"][i]


def test_delivered_produced_ratio_and_nsc_mix(tmp_path: Path) -> None:
    plan = {1: [(600, 4, (128, 128, 128, 64))] * 3, 2: [(600, 2, (128,))] * 3}
    s = summary(write_rows(tmp_path / "r.jsonl", plan_rows(plan)))
    m = minute(s, 1, 0)
    assert m["delivered_rate"] == pytest.approx(10.0)
    assert m["produced_rate"] == pytest.approx(40.0, rel=0.01)
    assert m["ratio"] == pytest.approx(0.25)
    assert m["nsc"] == {128: 450, 64: 150}
    assert minute(s, 2, 1)["ratio"] == pytest.approx(0.5)
    assert s["flagged_windows"] == 0


def test_a_backward_jump_is_logged_as_a_reboot_and_adds_no_step(tmp_path: Path) -> None:
    seqs = [100, 104, 108, 112, 3, 7, 11]
    rows = [(1, BASE_MS + i * 1000, q, 128) for i, q in enumerate(seqs)]
    s = summary(write_rows(tmp_path / "r.jsonl", rows))
    node = s["nodes"]["1"]
    assert len(node["reboots"]) == 1
    assert (node["reboots"][0]["from_seq"], node["reboots"][0]["to_seq"]) == (112, 3)
    m = minute(s, 1, 0)
    assert m["delivered_rate"] > 0
    produced_total = m["produced_rate"] * 6.0  # the recording spans 6 s, so this one minute is partial and lasts the recording span
    assert produced_total == pytest.approx(5 * 4)  # five forward steps of 4; the jump contributes none


def test_wraparound_at_the_u32_limit_is_a_forward_step_not_a_reboot(tmp_path: Path) -> None:
    rows = [(1, BASE_MS + i * 1000, q, 128) for i, q in enumerate([4294967290, 2, 3])]
    s = summary(write_rows(tmp_path / "r.jsonl", rows))
    assert s["nodes"]["1"]["reboots"] == []
    assert minute(s, 1, 0)["ratio"] == pytest.approx(2 / 9)  # steps 8 and 1: two frames, nine produced


def test_a_minute_below_the_collapse_ratio_is_flagged_and_one_above_is_not(tmp_path: Path) -> None:
    rates = [1200, 1200, 1200, 600, 900, 1200, 1200]  # per minute: 20, 20, 20, 10 (0.5x), 15 (0.75x), 20, last (partial)
    s = summary(write_rows(tmp_path / "r.jsonl", plan_rows({1: [(f, 3, (128,)) for f in rates]})))
    node = s["nodes"]["1"]
    assert node["reference_delivered_rate"] == pytest.approx(20.0)
    assert node["flagged_minutes"] == [3]
    assert s["flagged_windows"] == 1


def test_the_reference_can_be_overridden_and_the_collapse_ratio_changed(tmp_path: Path) -> None:
    path = write_rows(tmp_path / "r.jsonl", plan_rows({1: [(f, 3, (128,)) for f in [1200, 1200, 1200, 1200]]}))
    assert summary(path, override=40.0)["nodes"]["1"]["flagged_minutes"] == [0, 1, 2]  # 20 fps < 0.7 x 40; the last minute is partial
    assert summary(path, collapse=0.7)["flagged_windows"] == 0


def test_a_final_partial_minute_is_never_flagged(tmp_path: Path) -> None:
    plan = {1: [(1200, 3, (128,))] * 3 + [(5, 3, (128,))]}
    s = summary(write_rows(tmp_path / "r.jsonl", plan_rows(plan)))
    assert minute(s, 1, 3)["partial"] is True
    assert s["flagged_windows"] == 0


def test_a_minute_with_no_frames_is_flagged_as_a_dropout(tmp_path: Path) -> None:
    rows = plan_rows({1: [(1200, 3, (128,)), (0, 3, (128,)), (1200, 3, (128,)), (1200, 3, (128,))], 2: [(1200, 3, (128,))] * 4})
    s = summary(write_rows(tmp_path / "r.jsonl", rows))
    assert s["nodes"]["1"]["flagged_minutes"] == [1]
    assert s["nodes"]["2"]["flagged_minutes"] == []


def test_a_recording_without_seq_reports_only_the_delivered_rate(tmp_path: Path) -> None:
    path = write_rows(tmp_path / "r.jsonl", plan_rows({1: [(600, 3, (128,))] * 3}, seq=False))
    s = summary(path)
    m = minute(s, 1, 0)
    assert m["delivered_rate"] == pytest.approx(10.0)
    assert m["produced_rate"] is None and m["ratio"] is None and m["nsc"] == {}
    assert s["nodes"]["1"]["with_seq"] == 0
    lines, _ = sr.build([path], 10, None, 0.7)
    assert any("with seq" in line for line in lines)


def test_part_files_are_followed_and_read_in_order(tmp_path: Path) -> None:
    rows = plan_rows({1: [(600, 3, (128,))] * 4})
    half = len(rows) // 2
    base = write_rows(tmp_path / "lab__s1__empty__20261110T080000Z.jsonl", rows[:half])
    write_rows(tmp_path / "lab__s1__empty__20261110T080000Z.part2.jsonl", rows[half:])
    assert [p.name for p in sr.expand_parts(base)] == ["lab__s1__empty__20261110T080000Z.jsonl", "lab__s1__empty__20261110T080000Z.part2.jsonl"]
    assert summary(base)["nodes"]["1"]["frames"] == len(rows)
    assert summary(base)["nodes"]["1"]["reboots"] == []


def test_the_cli_exit_codes_and_the_data_folder_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ok = write_rows(tmp_path / "ok.jsonl", plan_rows({1: [(1200, 3, (128,))] * 3}))
    bad = write_rows(tmp_path / "bad.jsonl", plan_rows({1: [(1200, 3, (128,)), (300, 3, (128,)), (1200, 3, (128,)), (1200, 3, (128,))]}))
    out_json = tmp_path / "report.json"
    assert sr.main([str(ok), "--json", str(out_json)]) == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["flagged_windows"] == 0
    assert sr.main([str(bad)]) == 0 and "FLAG" in capsys.readouterr().out
    assert sr.main([str(bad), "--fail-on-flag"]) == 3
    under_data = ROOT / "data" / "seq_report_must_not_exist.json"
    assert sr.main([str(ok), "--json", str(under_data)]) == 2 and not under_data.exists()
    assert sr.main([str(tmp_path / "missing.jsonl")]) == 2
    empty = tmp_path / "empty.jsonl"
    empty.write_text(json.dumps(HEADER) + "\n", encoding="utf-8")
    assert sr.main([str(empty)]) == 2


SMOKE = sorted((ROOT / "data" / "datasets" / "smoke-test").glob("*.jsonl")) if (ROOT / "data" / "datasets" / "smoke-test").is_dir() else []


@pytest.mark.skipif(not SMOKE, reason="data/datasets/smoke-test is local, gitignored data and is not present")
def test_the_report_on_the_real_smoke_test_recording_is_structurally_sound() -> None:
    parts = [p for p in SMOKE if ".part" not in p.name]
    s = sr.build(sr.expand_parts(parts[0]), 10, None, 0.7)[1]
    assert set(s["nodes"]) == {"1", "2", "3", "4"}
    for n, node in s["nodes"].items():
        assert node["with_seq"] == node["frames"] > 1000, n          # every frame carries seq
        assert node["reboots"] == [], n
        full = [m for m in node["minutes"] if not m["partial"] and m["ratio"] is not None]
        assert full and all(0.0 < m["ratio"] < 1.0 for m in full), n    # more frames produced than delivered
        assert all(60 <= m["delivered_rate"] <= 75 for m in full), n    # the steady ~67 fps of this recording
    assert s["flagged_windows"] == 0
