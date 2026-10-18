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
    assert header["schema"] == 1
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
