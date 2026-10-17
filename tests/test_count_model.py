from pathlib import Path

import numpy as np
import pytest
import torch

from phantom.activity_train import TrainingRefused
from phantom.count_model import (
    NUM_SUBCARRIERS,
    WINDOW_FRAMES,
    CountNet,
    CountPredictor,
    count_to_class,
    expected_calibration_error,
    prepare_window,
    softmax,
    temperature_scale,
)
from phantom.count_train import build_count_windows, train_count
from phantom.dataset import NodeStream, Recording

FS = 40.0


def test_prepare_window_is_channel_major_and_rejects_time_channel_swaps():
    win = np.random.default_rng(0).normal(10, 1, size=(WINDOW_FRAMES, NUM_SUBCARRIERS))
    out = prepare_window(win)
    assert out.shape == (NUM_SUBCARRIERS, WINDOW_FRAMES), "network input must be [subcarriers, time]"
    # Channel 5 of the output is subcarrier 5's time series (deviation from its mean).
    expected = (win[:, 5] - win[:, 5].mean()) / win.mean()
    assert np.allclose(out[5], expected, atol=1e-6)
    with pytest.raises(ValueError, match="time-major"):
        prepare_window(win.T)  # the transposed (RuView-style) layout must be refused


def test_prepare_window_is_gain_invariant_and_applies_the_stored_scale():
    win = np.random.default_rng(1).normal(10, 1, size=(WINDOW_FRAMES, NUM_SUBCARRIERS))
    assert np.allclose(prepare_window(win), prepare_window(win * 7.0), atol=1e-6)
    assert np.allclose(prepare_window(win, scale=0.5), prepare_window(win, scale=1.0) / 0.5, atol=1e-6)
    with pytest.raises(ValueError):
        prepare_window(win, scale=0.0)


def test_countnet_output_shape():
    net = CountNet(num_classes=3)
    assert net(torch.zeros(4, NUM_SUBCARRIERS, WINDOW_FRAMES)).shape == (4, 3)


def test_temperature_scaling_reduces_calibration_error_of_an_overconfident_model():
    rng = np.random.default_rng(0)
    n = 4000
    y = rng.integers(0, 3, size=n)
    logits = rng.normal(0, 1, size=(n, 3))
    wrong = rng.random(n) < 0.4  # 60% accurate...
    logits[np.arange(n), np.where(wrong, (y + 1) % 3, y)] += 8.0  # ...but very confident
    t = temperature_scale(logits, y)
    assert t > 1.5
    assert expected_calibration_error(softmax(logits, t), y) < 0.5 * expected_calibration_error(softmax(logits), y)


def test_count_to_class_caps_at_two_or_more():
    assert [count_to_class(c) for c in (0, 1, 2, 3, 8)] == [0, 1, 2, 2, 2]


def _recording(count: int, idx: int, half: str, seconds: float = 20.0, seed: int | None = None) -> Recording:
    """Same temporal variance for every class; the fluctuating subcarrier HALF differs."""
    streams = {}
    for node in (1, 2):
        rng = np.random.default_rng((idx * 31 + node) if seed is None else seed + node)
        n = int(seconds * FS)
        base = 10.0 + np.sin(np.linspace(0, 3 * np.pi, NUM_SUBCARRIERS))
        wave = np.sin(2 * np.pi * rng.uniform(0.8, 1.6) * np.arange(n) / FS)[:, None]
        mask = np.zeros(NUM_SUBCARRIERS)
        if half == "low":
            mask[: NUM_SUBCARRIERS // 2] = 1.0
        else:
            mask[NUM_SUBCARRIERS // 2 :] = 1.0
        amps = base[None, :] + 1.2 * wave * mask[None, :] + rng.normal(0, 0.05, size=(n, NUM_SUBCARRIERS))
        streams[node] = NodeStream(t_ms=np.arange(n) * (1000.0 / FS), amps=amps, rssi=np.full(n, -45.0))
    return Recording(
        recording_id=f"room__s1__x__2026090{idx % 9 + 1}T0{idx:05d}Z",
        room_id="room",
        subject_id="s1",
        label="walking",
        count=count,
        day="",
        nodes=streams,
    )


def _separable():
    # count 1 -> low-half subcarriers fluctuate; count 2 -> high half. Equal variance.
    return [_recording(1 if i % 2 == 0 else 2, i, "low" if i % 2 == 0 else "high") for i in range(8)]


def test_build_count_windows_shapes_and_recording_ids():
    windows, y, rec_ids = build_count_windows(_separable())
    assert windows.shape[1:] == (WINDOW_FRAMES, NUM_SUBCARRIERS)
    assert len(windows) == len(y) == len(rec_ids) and set(y.tolist()) == {1, 2}


def test_trains_calibrates_exports_and_reloads(tmp_path: Path):
    report = train_count(_separable(), tmp_path, epochs=12, n_permutations=3)
    m = report["metrics"]
    assert m["model_balanced_accuracy"] > m["majority_balanced_accuracy"] + 0.2
    assert m["model_balanced_accuracy"] > m["heuristic_balanced_accuracy"]
    assert report["exported"] is True

    predictor = CountPredictor.load(tmp_path)
    rec_low = _recording(1, 40, "low", seed=999)
    rec_high = _recording(2, 41, "high", seed=999)
    for rec, expected in ((rec_low, 1), (rec_high, 2)):
        wins = {n: s.amps[:WINDOW_FRAMES] for n, s in rec.nodes.items()}
        count, confidence, _ = predictor.predict_fused(wins)
        assert count == expected and 0.5 <= confidence <= 1.0


def test_refuses_to_export_when_labels_carry_no_signal(tmp_path: Path):
    # Byte-identical signal under every label.
    recs = [_recording(1 if i % 2 == 0 else 2, i, "low", seed=5) for i in range(8)]
    with pytest.raises(TrainingRefused):
        train_count(recs, tmp_path, epochs=8, n_permutations=3)
    assert not (tmp_path / "count.safetensors").exists()


def test_refuses_with_a_single_count_class(tmp_path: Path):
    recs = [_recording(1, i, "low") for i in range(4)]
    with pytest.raises(TrainingRefused, match="at least 2 count classes"):
        train_count(recs, tmp_path, epochs=2, n_permutations=1)
