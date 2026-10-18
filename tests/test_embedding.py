"""csi-embed-v2 input mapping and empty-room drift (phantom.embedding)."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from phantom.embedding import (
    MASKED_DIMS,
    STD_FLOOR,
    cosine_drift,
    load_standardizer,
    mean_embedding,
    ruview_scale_features,
    standardize,
)
from phantom.sidecar import fuse_embedding_drift

REAL_BIN = Path(__file__).resolve().parents[1] / "ai model and densepose" / "model" / "csi-embed-v2-int4.bin"


def _write_standardizer(path: Path, mean: list[float], std: list[float]) -> None:
    payload = np.asarray(mean + std, dtype="<f2").tobytes() + b"\x00" * 64
    path.write_bytes(payload)


def test_load_standardizer_reads_fp16_mean_then_std(tmp_path: Path) -> None:
    mean = [0.5, 0.5, 0.8, 0.7, 1.0, 1.0, 0.0, 0.6]
    std = [0.3, 0.3, 0.2, 0.1, 1e-6, 1e-6, 1e-6, 0.1]
    _write_standardizer(tmp_path / "enc.bin", mean, std)

    got_mean, got_std = load_standardizer(tmp_path / "enc.bin")

    assert np.allclose(got_mean, mean, atol=1e-3)
    assert np.allclose(got_std[[0, 1, 2, 3, 7]], np.asarray(std)[[0, 1, 2, 3, 7]], atol=1e-3)


def test_load_standardizer_rejects_truncated_file(tmp_path: Path) -> None:
    (tmp_path / "short.bin").write_bytes(b"\x00" * 10)
    with pytest.raises(ValueError):
        load_standardizer(tmp_path / "short.bin")


@pytest.mark.skipif(not REAL_BIN.exists(), reason="RuView weights not present")
def test_shipped_standardizer_matches_documented_values() -> None:
    mean, std = load_standardizer(REAL_BIN)
    assert mean.shape == (8,) and std.shape == (8,)
    assert mean[2] == pytest.approx(0.7998, abs=1e-3)
    assert std[7] == pytest.approx(0.1170, abs=1e-3)


def test_ruview_scale_features_uses_firmware_scaling() -> None:
    feats = ruview_scale_features(presence=5.0, motion=2.0, breathing_bpm=15.0, heart_bpm=60.0, rssi_dbm=-50.0)

    assert feats.shape == (8,)
    assert feats[0] == pytest.approx(0.5)      # presence / 10
    assert feats[1] == pytest.approx(0.2)      # motion / 10
    assert feats[2] == pytest.approx(0.5)      # breathing / 30
    assert feats[3] == pytest.approx(0.5)      # heart / 120
    assert feats[7] == pytest.approx(0.5)      # (rssi + 100) / 100


def test_ruview_scale_features_clamps_and_zeroes_missing_vitals() -> None:
    feats = ruview_scale_features(presence=99.0, motion=-3.0, breathing_bpm=None, heart_bpm=None, rssi_dbm=-200.0)

    assert feats[0] == 1.0
    assert feats[1] == 0.0
    assert feats[2] == 0.0 and feats[3] == 0.0
    assert feats[7] == 0.0
    assert all(feats[d] == 0.0 for d in MASKED_DIMS)


def test_standardize_cannot_explode_on_constant_training_dims() -> None:
    mean = np.array([0.5, 0.5, 0.8, 0.7, 1.0, 1.0, 0.0, 0.6])
    std = np.array([0.3, 0.3, 0.2, 0.1, 1e-6, 1e-6, 1e-6, 0.1])
    raw = np.array([0.5, 0.5, 0.8, 0.7, 0.25, 0.25, 1.0, 0.6])  # dims 4-6 differ from training

    out = standardize(raw, mean, std)

    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) < 50
    assert all(out[d] == 0.0 for d in MASKED_DIMS)


def test_standardize_applies_floor_to_small_std() -> None:
    mean = np.zeros(8)
    std = np.full(8, 1e-9)
    raw = np.full(8, STD_FLOOR)

    out = standardize(raw, mean, std)

    assert out[0] == pytest.approx(1.0)


def test_mean_embedding_is_unit_norm_and_empty_input_is_none() -> None:
    zs = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
    ref = mean_embedding(zs)
    assert ref is not None
    assert np.linalg.norm(ref) == pytest.approx(1.0)
    assert mean_embedding([]) is None


def test_cosine_drift_zero_for_identical_two_for_opposite() -> None:
    a = np.array([1.0, 0.0])
    assert cosine_drift(a, a) == pytest.approx(0.0, abs=1e-9)
    assert cosine_drift(a, -a) == pytest.approx(2.0)
    assert cosine_drift(a, np.array([0.0, 1.0])) == pytest.approx(1.0)


def test_cosine_drift_never_negative_from_rounding() -> None:
    a = np.array([0.1, 0.2, 0.3]) / np.linalg.norm([0.1, 0.2, 0.3])
    assert cosine_drift(a, a) >= 0.0


def test_fuse_embedding_drift_reports_max_with_provenance() -> None:
    out = fuse_embedding_drift({1: 0.05, 3: 0.20}, ref_age_s=12.4, room_id="room1")

    assert out is not None
    assert out["embeddingDrift"] == pytest.approx(0.20)
    assert out["embeddingRefAgeS"] == pytest.approx(12.4)
    assert out["embeddingModelId"] == "csi-embed-v2"
    assert out["roomId"] == "room1"


def test_fuse_embedding_drift_none_without_nodes() -> None:
    assert fuse_embedding_drift({}, ref_age_s=1.0, room_id="room1") is None


def test_struct_layout_sanity() -> None:
    # 8 fp16 means + 8 fp16 stds = 32 bytes, the layout load_standardizer relies on.
    assert struct.calcsize("<16e") == 32
