"""Headless dataset recorder: file layout must match server/lib/dataset-recorder.ts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.record_dataset import build_header, frame_record, output_path


GEOMETRY = {"roomWidthM": 4, "roomDepthM": 6, "anchors": {"1": {"x": -2, "z": -3}}}


def test_header_has_the_fields_the_loader_requires() -> None:
    header = build_header("room1", "s1", "empty", 0, 1792346161097, GEOMETRY, notes="headless")

    assert header["type"] == "header"
    assert header["schema"] == 2
    assert (header["roomId"], header["subjectId"], header["label"], header["count"]) == ("room1", "s1", "empty", 0)
    assert header["part"] == 1
    assert header["geometry"] == GEOMETRY
    assert header["firmwareFilterMac"] is None
    json.dumps(header)  # serialisable


def test_frame_record_matches_recorder_schema() -> None:
    rec = frame_record(1792346161104.4, 3, -42, [1.5, 2.5])

    assert rec == {"type": "frame", "t": 1792346161104, "n": 3, "rssi": -42, "a": [1.5, 2.5]}


def test_output_path_follows_naming_convention(tmp_path: Path) -> None:
    path = output_path(tmp_path, "room1", "s1", "empty", 1792346161097)

    assert path.parent == tmp_path / "room1"
    assert re.fullmatch(r"room1__s1__empty__\d{8}T\d{6}Z\.jsonl", path.name)


@pytest.mark.parametrize("bad", ["../evil", "a/b", "", "x" * 100, "sp ace"])
def test_unsafe_ids_are_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        output_path(tmp_path, bad, "s1", "empty", 0)


def test_unknown_label_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        output_path(tmp_path, "room1", "s1", "dancing", 0)


# ── PS-FIX-03: header schema 2 ─────────────────────────────────────────────

from scripts.record_dataset import canonical_json, capture_from_env, dumps, geometry_hash  # noqa: E402

# Same literal as server/lib/dataset-recorder.test.ts: both recorders must hash the same geometry identically.
GEOMETRY_HASH = "5ad06de70373cbe1"


def test_geometry_hash_matches_the_dashboard_recorder_and_ignores_key_order_and_router() -> None:
    assert geometry_hash(GEOMETRY) == GEOMETRY_HASH
    assert geometry_hash({"anchors": {"1": {"z": -3, "x": -2}}, "roomDepthM": 6, "roomWidthM": 4}) == GEOMETRY_HASH
    assert geometry_hash({**GEOMETRY, "router": {"x": 9, "z": 9}}) == GEOMETRY_HASH
    assert geometry_hash({}) is None and geometry_hash(None) is None
    assert canonical_json({"b": 1, "a": {"d": [2, {"z": 1, "y": 2}], "c": None}}) == '{"a":{"c":null,"d":[2,{"y":2,"z":1}]},"b":1}'


def test_schema2_header_fields_and_defaults_are_null_not_guesses() -> None:
    h = build_header("room1", "s1", "empty", 0, 1792346161097, GEOMETRY)
    assert h["schema"] == 2 and h["geometryHash"] == GEOMETRY_HASH and h["recorder"] == "headless"
    assert h["startedAtMs"] == h["partStartedAtMs"] == 1792346161097
    assert h["capture"] == {"channel": None, "bandwidthMHz": None, "bssid": None, "firmwareVersion": None, "firmwareHash": None, "source": "not_recorded"}
    assert h["annotation"] == {"nodeMoved": None, "roomNotEmpty": None, "text": ""}
    h2 = build_header("room1", "s1", "empty", 0, 1, GEOMETRY, part_started_ms=99)
    assert (h2["startedAtMs"], h2["partStartedAtMs"]) == (1, 99)


def test_capture_from_env_accepts_valid_values_and_nulls_invalid_ones() -> None:
    ok = capture_from_env({
        "PHANTOM_CAPTURE_CHANNEL": "6", "PHANTOM_CAPTURE_BANDWIDTH_MHZ": "20", "PHANTOM_ROUTER_BSSID": "AA:BB:CC:00:11:22",
        "PHANTOM_FIRMWARE_VERSION": "v0.8.13-esp32", "PHANTOM_FIRMWARE_HASH": "428D3A5",
    })
    assert ok == {"channel": 6, "bandwidthMHz": 20, "bssid": "aa:bb:cc:00:11:22", "firmwareVersion": "v0.8.13-esp32", "firmwareHash": "428d3a5", "source": "operator_env"}
    bad = capture_from_env({
        "PHANTOM_CAPTURE_CHANNEL": "abc", "PHANTOM_CAPTURE_BANDWIDTH_MHZ": "30", "PHANTOM_ROUTER_BSSID": "not-a-mac",
        "PHANTOM_FIRMWARE_VERSION": "has space", "PHANTOM_FIRMWARE_HASH": "zzz",
    })
    assert bad["source"] == "not_recorded" and all(v is None for k, v in bad.items() if k != "source")
    for weird in ("nan", "inf", "6.5", ""):
        assert capture_from_env({"PHANTOM_CAPTURE_CHANNEL": weird})["channel"] is None, weird


def test_annotation_is_validated_and_capped() -> None:
    h = build_header("room1", "s1", "empty", 0, 1, GEOMETRY, annotation={"nodeMoved": True, "roomNotEmpty": "yes", "text": "x" * 900})
    assert h["annotation"]["nodeMoved"] is True and h["annotation"]["roomNotEmpty"] is None and len(h["annotation"]["text"]) == 500


def test_dumps_is_compact_and_roundtrips_through_the_loader(tmp_path: Path) -> None:
    from phantom.dataset import load_recording

    header = build_header("room1", "s1", "empty", 0, 1792346161097, GEOMETRY, annotation={"nodeMoved": True})
    path = output_path(tmp_path, "room1", "s1", "empty", 1792346161097)
    path.parent.mkdir(parents=True)
    path.write_text(dumps(header) + "\n" + dumps(frame_record(1792346161104, 1, -40, [1.5, 2.5])) + "\n", encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    assert '": ' not in text and '", "' not in text, "no spaces after separators"
    rec = load_recording([path])
    assert rec.header["annotation"]["nodeMoved"] is True and rec.header["geometryHash"] == GEOMETRY_HASH and rec.report.clean


# ── PS-FIX-29: per-part link summary sidecar (parity vector identical to server/lib/dataset-recorder.test.ts) ─────────────

from scripts.record_dataset import PartNodeStats, build_part_summary, summary_path_for, write_part_summary  # noqa: E402

BASE = 1_700_000_000_000


def parity_frames() -> list[tuple[int, int, int]]:
    """(t, node, rssi): node 1 50 fps -36 then -47 at +20 s; node 2 50 fps then 20 fps; node 3 steady; node 4 only 5 s."""
    out = [(BASE + t, 1, -36 if t < 20_000 else -47) for t in range(0, 30_000, 20)]
    out += [(BASE + t, 2, -27) for t in range(0, 10_000, 20)] + [(BASE + t, 2, -27) for t in range(10_000, 30_000, 50)]
    out += [(BASE + t, 3, -30) for t in range(0, 30_000, 20)] + [(BASE + t, 4, -40) for t in range(0, 5_000, 20)]
    return sorted(out)


def stats_for(frames: list[tuple[int, int, int]]) -> dict[int, PartNodeStats]:
    stats: dict[int, PartNodeStats] = {}
    for t, n, rssi in frames:
        stats.setdefault(n, PartNodeStats()).add(t, rssi)
    return stats


def test_part_summary_parity_vector_matches_the_dashboard_recorder(tmp_path: Path) -> None:
    f = tmp_path / "room1__s1__empty__20261102T000000Z.jsonl"
    s = build_part_summary(f, 1, BASE, BASE, BASE + 30_000, stats_for(parity_frames()))
    n = s["perNode"]
    assert s["type"] == "part_summary" and s["file"] == f.name
    n1 = n["1"]
    assert [n1["frames"], n1["first10s"]["frames"], n1["first10s"]["fps"], n1["first10s"]["rssiMedian"], n1["last10s"]["frames"], n1["last10s"]["fps"],
            n1["last10s"]["rssiMedian"], n1["rssiMedianPart"], n1["rssiDeltaDb"], n1["fpsRatio"], n1["stepFlag"], n1["stepReasons"]] == \
        [1500, 500, 50, -36, 500, 50, -47, -36, -11, 1, True, ["rssi_step"]]
    n2 = n["2"]
    assert [n2["frames"], n2["first10s"]["fps"], n2["last10s"]["frames"], n2["last10s"]["fps"], n2["rssiDeltaDb"], n2["fpsRatio"], n2["stepFlag"], n2["stepReasons"]] == \
        [900, 50, 200, 20, 0, 0.4, True, ["rate_collapse"]]
    assert [n["3"]["stepFlag"], n["3"]["stepReasons"], n["3"]["rssiDeltaDb"], n["3"]["fpsRatio"]] == [False, [], 0, 1]
    assert [n["4"]["shortPart"], n["4"]["stepFlag"], n["4"]["rssiDeltaDb"]] == [True, None, None]


def test_low_first_window_rate_gives_no_collapse_statement() -> None:
    frames = [(BASE + t, 1, -40) for t in range(0, 10_000, 200)] + [(BASE + t, 1, -40) for t in range(10_000, 30_000, 1000)]
    n1 = build_part_summary(Path("f.jsonl"), 1, BASE, BASE, BASE, stats_for(frames))["perNode"]["1"]
    assert n1["fpsRatio"] is None and n1["stepFlag"] is False


def test_summary_path_is_a_sibling_that_the_jsonl_glob_never_matches(tmp_path: Path) -> None:
    f = tmp_path / "room1__s6__empty__20261102T000000Z.jsonl"
    assert summary_path_for(f).name == "room1__s6__empty__20261102T000000Z.summary.json"
    assert summary_path_for(tmp_path / "room1__s6__empty__20261102T000000Z.part2.jsonl").name.endswith("Z.part2.summary.json")
    f.write_text("{}\n", encoding="utf-8")
    write_part_summary(build_part_summary(f, 1, BASE, BASE, BASE, stats_for(parity_frames())), f)
    assert [p.name for p in tmp_path.glob("*.jsonl")] == [f.name]               # the summary is not a dataset file
    assert json.loads(summary_path_for(f).read_text(encoding="utf-8"))["perNode"]["1"]["stepFlag"] is True


def test_summary_write_failure_is_swallowed_and_never_overwrites(tmp_path: Path) -> None:
    f = tmp_path / "room1__s6__empty__20261102T000000Z.jsonl"
    summary_path_for(f).write_text("occupied", encoding="utf-8")
    assert write_part_summary(build_part_summary(f, 1, BASE, BASE, BASE, stats_for(parity_frames())), f) is None
    assert summary_path_for(f).read_text(encoding="utf-8") == "occupied"
    assert write_part_summary({"perNode": {}}, f) is None                         # no frames -> no file
