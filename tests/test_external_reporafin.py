"""Converter for the third-party reporafin ESP32 CSV dataset (empty / stationary / moving)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phantom.external.reporafin import LABEL_MAP, load_reporafin_csv, load_reporafin_dataset

HEADER = "Packet_Count," + ",".join(f"Sub_{i}" for i in range(64)) + "\n"


def _row(count: int, value: int) -> str:
    return f"{count}," + ",".join(str(value if 6 <= i < 59 else 0) for i in range(64)) + "\n"


def _write(path: Path, rows: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


def test_parses_rows_into_one_node_stream_at_the_assumed_100_hz(tmp_path: Path) -> None:
    path = _write(tmp_path / "room1_quiet" / "moving_trail.csv", [_row(155, 20), _row(156, 21), _row(158, 22)])

    rec = load_reporafin_csv(path)

    stream = rec.nodes[1]
    assert rec.label == "walking"
    assert rec.day == "room1_quiet"
    assert stream.t_ms.tolist() == [0.0, 10.0, 30.0]  # packet-counter gaps become time gaps
    assert stream.amps.shape == (3, 52)  # fixed set: subcarriers 6-58 without the DC carrier 32
    assert np.all(stream.rssi == 0.0)


def test_skips_corrupted_rows(tmp_path: Path) -> None:
    path = _write(tmp_path / "room2_quiet" / "empty_trail.csv", [_row(1, 5), "2,abc,\n", _row(3, 6)])

    rec = load_reporafin_csv(path)

    assert rec.label == "empty"
    assert rec.nodes[1].t_ms.tolist() == [0.0, 20.0]


def test_maps_states_to_project_labels() -> None:
    assert LABEL_MAP == {"empty": "empty", "stationary": "still", "moving": "walking"}


def test_unknown_state_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path / "room1_quiet" / "jumping_trail.csv", [_row(1, 5), _row(2, 6)])
    with pytest.raises(ValueError, match="unknown state"):
        load_reporafin_csv(path)


def test_loads_every_csv_under_the_dataset_folder(tmp_path: Path) -> None:
    for room in ("room1_quiet", "room2_quiet"):
        for state in ("empty", "stationary", "moving"):
            _write(tmp_path / room / f"{state}_trail.csv", [_row(1, 5), _row(2, 6)])

    recs = load_reporafin_dataset(tmp_path)

    assert len(recs) == 6
    assert {r.day for r in recs} == {"room1_quiet", "room2_quiet"}
