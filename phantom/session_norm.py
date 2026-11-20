"""Session-relative window features: express each window against the same session's empty-room baseline.

Absolute CSI levels (variance, band power, amplitude) change more between sessions (channel noise, node rate, AGC,
day) than between activities; see reports/external-2026-11/REPORAFIN-FEATURE-TEST.md. Dividing scale-type features
by the median of an empty-room calibration period of the same session, and subtracting it from RSSI, keeps the
activity contrast and removes the session level. Shape features (skew, kurtosis, entropy, dominant frequency) are
already scale-free and stay as they are. The calibration period must be separate from evaluated data (use
``split_baseline``), as the dashboard's empty-room calibration is.
"""
from __future__ import annotations

import numpy as np

from phantom.features import FEATURE_NAMES

RATIO_FEATURES: tuple[str, ...] = (
    "temporal_variance",
    "motion_band_power",
    "breath_band_power",
    "spectral_power",
    "change_points",
    "spec_mean",
    "spec_std",
    "spec_iqr",
    "spec_max",
    "spec_range",
)
SHIFT_FEATURES: tuple[str, ...] = ("rssi_mean",)
EPS = 1e-9

_IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}
_RATIO = np.array([_IDX[n] for n in RATIO_FEATURES])
_SHIFT = np.array([_IDX[n] for n in SHIFT_FEATURES])


def relative_to_baseline(x: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    """New array: ratio features / baseline median, shift features - baseline median, others unchanged."""
    x = np.asarray(x, dtype=np.float64)
    ref = np.median(np.asarray(baseline, dtype=np.float64), axis=0)
    out = x.copy()
    out[:, _RATIO] = x[:, _RATIO] / np.maximum(np.abs(ref[_RATIO]), EPS)
    out[:, _SHIFT] = x[:, _SHIFT] - ref[_SHIFT]
    return out


def split_baseline(windows: np.ndarray, fraction: float = 0.3) -> tuple[np.ndarray, np.ndarray]:
    """(calibration windows, remaining windows): the first `fraction` of an empty recording calibrates."""
    windows = np.asarray(windows)
    n = max(1, int(round(len(windows) * fraction)))
    return windows[:n], windows[n:]
