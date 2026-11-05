"""PS-FIX-02: phantom.dataset loader tolerates malformed input with counters, never truncates widths, supports strict mode."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phantom import dataset
from phantom.dataset import load_recording, load_room_dataset

HEADER = {"type": "header", "schema": 1, "roomId": "room", "subjectId": "s1", "label": "empty", "count": 0}


def frame(t: int, n: int = 1, width: int = 8, base: float = 10.0, rssi: int | None = -40) -> dict:
    f = {"type": "frame", "t": t, "n": n, "a": [base + i for i in range(width)]}
    if rssi is not None:
        f["rssi"] = rssi
    return f


def write(path: Path, records: list, raw: list[str] | None = None) -> Path:
    path.write_text("\n".join([json.dumps(r) for r in records] + (raw or [])) + "\n", encoding="utf-8")
    return path


def name(part: int = 1) -> str:
    return "room__s1__empty__20261027T190000Z" + ("" if part == 1 else f".part{part}") + ".jsonl"


def test_clean_file_has_clean_report_and_float64_arrays(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [HEADER, frame(2000), frame(1000), frame(3000, n=2)])
    rec = load_recording([p])
    assert rec.report is not None and rec.report.clean
    assert rec.report.frames == 3 and rec.report.lines == 4
    assert rec.nodes[1].t_ms.tolist() == [1000.0, 2000.0]            # sorted by time
    assert rec.nodes[1].amps.dtype == np.float64 and rec.nodes[1].amps.shape == (2, 8)
    assert rec.report.modal_width == {1: 8, 2: 8}


def test_malformed_lines_are_skipped_and_counted(tmp_path: Path) -> None:
    p = write(tmp_path / name(), [HEADER, frame(1000)], raw=["not json", '{"type":"frame","t":2', '{"type":"mystery"}', "[1,2]"])
    rec = load_recording([p])
    assert rec.report.malformed_lines == 4 and rec.report.frames == 1 and not rec.report.clean


def test_truncated_final_line_does_not_lose_the_rest(tmp_path: Path) -> None:
    good = [json.dumps(r) for r in (HEADER, frame(1000), frame(2000))]
    p = tmp_path / name()
    p.write_text("\n".join(good) + '\n{"type":"frame","t":3000,"n":1,"a":[1,2', encoding="utf-8")
    rec = load_recording([p])
    assert rec.nodes[1].t_ms.size == 2 and rec.report.malformed_lines == 1


def test_bad_frames_are_counted(tmp_path: Path) -> None:
    nan_amp = frame(2000)
    nan_amp["a"][3] = None
    bad = [
        nan_amp,                                                    # null amplitude
        {"type": "frame", "t": 3000, "n": "1", "a": [1.0] * 8},      # node id is a string
        {"type": "frame", "t": "x", "n": 1, "a": [1.0] * 8},         # timestamp is a string
        {"type": "frame", "t": 4000, "n": 1, "a": []},               # empty amplitudes
        {"type": "frame", "t": 5000, "n": 1, "a": "abc"},            # not a list of numbers
    ]
    rec = load_recording([write(tmp_path / name(), [HEADER, frame(1000), *bad])])
    assert rec.report.bad_frames == 5 and rec.nodes[1].t_ms.tolist() == [1000.0]


def test_missing_rssi_becomes_nan_not_a_crash(tmp_path: Path) -> None:
    rec = load_recording([write(tmp_path / name(), [HEADER, frame(1000, rssi=None), frame(2000)])])
    assert np.isnan(rec.nodes[1].rssi[0]) and rec.nodes[1].rssi[1] == -40.0 and rec.report.clean


def test_mixed_widths_are_never_truncated_minority_is_dropped_and_counted(tmp_path: Path) -> None:
    frames = [frame(1000 + i, width=8) for i in range(5)] + [frame(2000, width=5), frame(2001, width=11)]
    rec = load_recording([write(tmp_path / name(), [HEADER, *frames])])
    assert rec.nodes[1].amps.shape == (5, 8)                         # old loader would have cut everything to 5
    assert rec.report.width_mismatch_frames == {1: 2} and rec.report.modal_width == {1: 8}


def test_strict_mode_raises_on_every_irregularity(tmp_path: Path) -> None:
    cases = {
        "bad json": ([HEADER, frame(1000)], ["not json"]),
        "unknown type": ([HEADER, {"type": "mystery"}], []),
        "unusable frame": ([HEADER, {"type": "frame", "t": 1, "n": 1, "a": []}], []),
        "mixed widths": ([HEADER, frame(1000, width=8), frame(2000, width=5)], []),
    }
    for label, (records, raw) in cases.items():
        p = write(tmp_path / f"{label.replace(' ', '_')}__s1__empty__20261027T190000Z.jsonl", records, raw)
        with pytest.raises(ValueError):
            load_recording([p], strict=True)
        assert load_recording([p]).report is not None, label          # the tolerant default still loads it


def test_header_and_schema_errors_always_raise(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing header"):
        load_recording([write(tmp_path / name(), [frame(1000)])])
    with pytest.raises(ValueError, match="schema"):
        load_recording([write(tmp_path / name(), [{**HEADER, "schema": 9}, frame(1000)])])


def test_parts_are_read_in_numeric_order_part10_after_part2(tmp_path: Path) -> None:
    paths = [write(tmp_path / name(1), [HEADER, frame(100)])]
    for part in (2, 10):
        paths.append(write(tmp_path / name(part), [{**HEADER, "label": "WRONG"}, frame(part * 1000)]))
    rec = load_recording(list(reversed(paths)))                      # caller order must not matter
    assert rec.label == "empty"                                       # header comes from part 1, not a later part
    assert [Path(f).name for f in rec.files] == [name(1), name(2), name(10)]
    assert rec.nodes[1].t_ms.tolist() == [100.0, 2000.0, 10000.0]


def test_chunked_accumulation_matches_single_chunk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = write(tmp_path / name(), [HEADER, *[frame(1000 + 7 * i, n=1 + i % 2, base=float(i)) for i in range(25)]])
    big = load_recording([p])
    monkeypatch.setattr(dataset, "_CHUNK_ROWS", 3)
    small = load_recording([p])
    for n in big.nodes:
        assert np.array_equal(big.nodes[n].amps, small.nodes[n].amps)
        assert np.array_equal(big.nodes[n].t_ms, small.nodes[n].t_ms)
        assert np.array_equal(big.nodes[n].rssi, small.nodes[n].rssi, equal_nan=True)


def test_load_room_dataset_passes_strict_through(tmp_path: Path) -> None:
    room = tmp_path / "room"
    room.mkdir()
    write(room / name(), [HEADER, frame(1000), frame(2000, width=5), frame(2001, width=8), frame(2002, width=8)])
    assert load_room_dataset(tmp_path, "room")[0].report.width_mismatch_frames == {1: 1}
    with pytest.raises(ValueError):
        load_room_dataset(tmp_path, "room", strict=True)


def test_schema_2_headers_load_and_the_header_is_exposed(tmp_path: Path) -> None:
    h2 = {**HEADER, "schema": 2, "partStartedAtMs": 5, "geometryHash": "abc", "annotation": {"nodeMoved": True, "roomNotEmpty": None, "text": ""},
          "capture": {"channel": 6, "source": "operator_env"}, "recorder": "headless"}
    rec = load_recording([write(tmp_path / name(), [h2, frame(1000)])])
    assert rec.header["annotation"]["nodeMoved"] is True and rec.header["capture"]["channel"] == 6 and rec.report.clean
    old = load_recording([write(tmp_path / name(2), [HEADER, frame(1000)])])
    assert old.header["schema"] == 1                                   # schema 1 files keep loading unchanged
