"""Converter for the third-party ESP32-S3 HAR dataset (imPiglet/esp32s3-csi-har-2025, CC BY 4.0)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phantom.external.esp32s3_har import LABEL_MAP, load_har_csv, load_har_dataset

HEADER = (
    "type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,"
    "noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,len,first_word,data\n"
)


def _row(i: int, ts_us: int, rssi: int, iq: list[int]) -> str:
    data = "[" + ",".join(str(v) for v in iq) + "]"
    return f'CSI_DATA,{i},1a:00:00:00:00:00,{rssi},11,1,0,1,1,1,0,0,0,0,-95,0,11,2,{ts_us},0,47,0,{len(iq)},0,"{data}"\n'


def _write(path: Path, rows: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


def test_parses_iq_into_amplitudes_with_real_timestamps_and_rssi(tmp_path: Path) -> None:
    iq = [3, 4, 0, 0, 6, 8]  # imaginary first: |3j+4| = 5, 0, |6j+8| = 10
    path = _write(tmp_path / "data" / "walking3.csv", [_row(1, 1_000_000, -35, iq), _row(2, 1_050_000, -36, iq)])

    rec = load_har_csv(path)

    s = rec.nodes[1]
    assert rec.label == "walking"
    assert s.t_ms.tolist() == [0.0, 50.0]
    assert s.rssi.tolist() == [-35.0, -36.0]
    np.testing.assert_allclose(s.amps[0], [5.0, 0.0, 10.0])


def test_postures_map_to_still() -> None:
    assert LABEL_MAP == {"sitting": "still", "standing": "still", "lying": "still", "walking": "walking"}


def test_skips_malformed_rows_and_refuses_unknown_labels(tmp_path: Path) -> None:
    good = _row(1, 0, -40, [1, 1])
    path = _write(tmp_path / "data" / "lying1.csv", [good, 'CSI_DATA,2,x,-40,11,1,0,1,1,1,0,0,0,0,-95,0,11,2,10,0,47,0,2,0,"[1"\n', _row(3, 20_000, -41, [1, 1])])
    assert len(load_har_csv(path).nodes[1].t_ms) == 2
    bad = _write(tmp_path / "data" / "jumping1.csv", [good, good])
    with pytest.raises(ValueError, match="unknown label"):
        load_har_csv(bad)


def test_loads_every_csv(tmp_path: Path) -> None:
    for name in ("sitting1", "walking1"):
        _write(tmp_path / "data" / f"{name}.csv", [_row(1, 0, -40, [1, 1]), _row(2, 50_000, -40, [1, 1])])
    assert [r.label for r in load_har_dataset(tmp_path)] == ["still", "walking"]
