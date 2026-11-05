"""PS-FIX-28: the measurement reuses the sidecar's own functions (extracted with ast) and slides windows like the sidecar."""
from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="torch not installed")

from scripts.presence_eval import presence_head_norms as ph  # noqa: E402


@pytest.fixture(scope="module")
def code() -> dict:
    return ph.load_sidecar_code(np.zeros(8), np.ones(8))


def test_the_sidecar_functions_are_extracted_from_the_real_source_not_copied(code: dict) -> None:
    assert {"estimate_vitals", "extract_features_8d", "Enc", "DEFAULT_FS"} <= set(code)
    assert code["DEFAULT_FS"] == 20.0
    assert code["extract_features_8d"].__code__.co_filename.startswith("scripts/ai_inference.py")


def test_feature_extraction_gives_eight_finite_standardised_features(code: dict) -> None:
    rng = np.random.default_rng(1)
    amps = 12 + rng.standard_normal((100, 51))
    feats, motion, mean, vitals = code["extract_features_8d"](amps, np.full(100, -40.0), 50.0, None)
    assert feats.shape == (8,) and np.isfinite(feats).all() and mean.shape == (51,) and motion >= 0
    assert set(vitals) == {"breathing", "heart_rate", "reliable"}


def test_the_extracted_encoder_returns_both_the_normalised_and_the_unnormalised_activation(code: dict) -> None:
    net = code["Enc"]().eval()
    z, pre = net(torch.zeros(3, 8))
    assert z.shape == pre.shape == (3, 128)


def test_windows_slide_like_the_sidecar_100_frames_every_point_two_seconds(code: dict) -> None:
    n = 400
    t = np.arange(n) * 20                                    # 50 fps
    amps = np.random.default_rng(2).standard_normal((n, 51)) + 12
    feats, ends = ph.windows_for_node(t, amps, np.full(n, -40.0), code)
    assert feats.shape[1] == 8 and feats.dtype == np.float32
    assert np.all(np.diff(ends) == 200)                      # step = round(fs * 0.2) = 10 frames of 20 ms
    assert ends[0] == t[99]
    f2, e2 = ph.windows_for_node(t[:99], amps[:99], np.full(99, -40.0), code)
    assert f2.shape == (0, 8) and e2.size == 0               # fewer than 100 frames: no window, nothing invented


def test_estimate_fs_follows_the_sidecar_guard() -> None:
    assert ph.estimate_fs(np.arange(0, 1000, 20.0), 20.0) == pytest.approx(50.0)   # 49 intervals over 0.98 s
    assert ph.estimate_fs(np.array([5.0]), 20.0) == 20.0                          # too few samples
    assert ph.estimate_fs(np.array([1000.0, 1000.0]), 20.0) == 20.0               # zero span
    assert ph.estimate_fs(np.arange(0, 100, 1.0) * 1000, 20.0) == pytest.approx(1.0)   # 1 Hz is the lowest accepted rate
    assert ph.estimate_fs(np.arange(0, 100, 1.0) * 2000, 20.0) == 20.0            # 0.5 Hz: below the guard -> default
    assert ph.estimate_fs(np.arange(0, 100, 1.0) * 2.0, 20.0) == 20.0             # 500 Hz: above the guard -> default


def test_quantiles_and_render_handle_an_empty_cell() -> None:
    assert ph.q(np.zeros(0)) == [None, None, None]
    res = {"head": {"weight_norm": 3.0, "bias": 8.0}, "pre_norm_all_windows_q05_q50_q95": [10.0, 20.0, 30.0], "auc_p_vs_empty": {},
           "guard_unit_norm": {"ok": False}, "guard_with_measured_q05_norm": {"ok": True}, "note": "n",
           "cells": {"empty/N1": {"windows": 0, "pre_norm_q05_q50_q95": [None] * 3, "logit_q05_q50_q95": [None] * 3, "p_q05_q50_q95": [None] * 3,
                                  "share_p_gt_0.5": 0.0, "share_p_gt_0.99": 0.0, "l2_normalised_input_logit_min_max": [1.0, 2.0]}}}
    assert "empty/N1" in ph.render(res)
