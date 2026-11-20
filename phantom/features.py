"""Window features for the per-room activity classifier (RuView ADR-048 style).

ONE implementation shared by training (scripts/train/) and the AI sidecar
runtime, so there is no train/serve skew. Pure numpy; no torch/sklearn.

Input per node: a window of per-packet amplitude vectors [T, K] (the 51 LLTF
data subcarriers the server and sidecar both use), per-packet RSSI [T], and
the window's frame rate. Output: 15 features —

  temporal (from the per-frame mean amplitude series):
    temporal_variance  mean over subcarriers of the temporal variance
    motion_band_power  0.5–4 Hz spectral power (limbs / walking)
    breath_band_power  0.1–0.5 Hz spectral power
    spectral_power     total 0.1 Hz–0.45·fs power
    dominant_freq_hz   strongest 0.1–4 Hz component (0 if the band is silent)
    change_points      count of abrupt frame-to-frame jumps
    rssi_mean
  shape (from the window-mean amplitude spectrum across subcarriers):
    spec_mean, spec_std, spec_skew, spec_kurt, spec_iqr, spec_entropy,
    spec_max, spec_range      (skew/kurt/entropy are gain-invariant)

Windows too short or flat to analyse return all zeros, never NaN.
"""

from __future__ import annotations

from typing import Iterator

import numpy as np

FEATURE_NAMES: tuple[str, ...] = (
    "temporal_variance",
    "motion_band_power",
    "breath_band_power",
    "spectral_power",
    "dominant_freq_hz",
    "change_points",
    "rssi_mean",
    "spec_mean",
    "spec_std",
    "spec_skew",
    "spec_kurt",
    "spec_iqr",
    "spec_entropy",
    "spec_max",
    "spec_range",
)
NUM_FEATURES = len(FEATURE_NAMES)

MIN_FRAMES = 8
MOTION_BAND = (0.5, 4.0)
BREATH_BAND = (0.1, 0.5)
DOMINANT_MAX_HZ = 4.0
DOMINANT_MIN_HZ = 0.1
# Peak power relative to the squared mean amplitude below which the band is
# treated as silent and dominant_freq_hz is reported as 0.
MIN_RELATIVE_PEAK_POWER = 1e-7
CHANGE_POINT_MULT = 3.0
EPS = 1e-9
# Every window is resampled onto this fixed grid before feature extraction, so the
# features describe the scene and not the packet rate (nodes run 40-67 fps and the
# rate drops when the AP bunches its frames; see
# reports/campaign-2026-11/c2-20261119/RATE-DROP-DIAGNOSIS.md). 30 Hz keeps the
# 4 Hz motion band far below Nyquist and is below the lowest healthy node rate.
RESAMPLE_HZ = 30.0


def _band_power(power: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> float:
    mask = (freqs >= lo) & (freqs < hi)
    return float(power[mask].sum()) if mask.any() else 0.0


def extract_window_features(amps: np.ndarray, rssi: np.ndarray, fs: float) -> np.ndarray:
    amps = np.asarray(amps, dtype=np.float64)
    if amps.ndim != 2 or amps.shape[0] < 2 or amps.shape[1] < 1 or not np.all(np.isfinite(amps)):
        return np.zeros(NUM_FEATURES)
    t = amps.shape[0]

    series = amps.mean(axis=1)
    temporal_variance = float(amps.var(axis=0).mean())

    demeaned = series - series.mean()
    windowed = demeaned * np.hanning(t)
    spectrum = np.fft.rfft(windowed)
    power = (np.abs(spectrum) ** 2) / (t * t)
    freqs = np.fft.rfftfreq(t, d=1.0 / fs) if fs > 0 else np.zeros_like(power)

    motion_power = _band_power(power, freqs, *MOTION_BAND)
    breath_power = _band_power(power, freqs, *BREATH_BAND)
    total_power = _band_power(power, freqs, DOMINANT_MIN_HZ, 0.45 * fs)

    # Dominant frequency: exact DFT evaluated on a fixed 0.1 Hz grid, not the
    # FFT bins — a 1 s window has only 1 Hz bins, which would quantize (and
    # split via leakage) anything between them (RuView csi.rs does the same).
    dom_hi = min(DOMINANT_MAX_HZ, 0.45 * fs)
    dominant = 0.0
    if t >= MIN_FRAMES and fs > 0 and dom_hi > DOMINANT_MIN_HZ:
        grid = np.arange(DOMINANT_MIN_HZ, dom_hi + 1e-9, 0.1)
        phase = np.exp(-2j * np.pi * np.outer(grid, np.arange(t) / fs))
        grid_power = np.abs(phase @ windowed) ** 2 / (t * t)
        peak = int(np.argmax(grid_power))
        # No peak-to-floor gate: on a 1 s window the peak/median ratio of pure
        # noise (p95 ≈ 8) overlaps real tones (≈2–6), so any ratio threshold
        # would be arbitrary. Report the argmax unless the band is silent
        # relative to the signal level; the model weighs it with the power
        # features rather than trusting it alone.
        level = float(series.mean()) ** 2 + EPS
        if grid_power[peak] / level > MIN_RELATIVE_PEAK_POWER:
            dominant = float(grid[peak])

    jumps = np.abs(np.diff(series))
    scale = np.median(jumps) + EPS
    change_points = float(np.count_nonzero(jumps > CHANGE_POINT_MULT * scale + 1e-6)) if t >= MIN_FRAMES else 0.0

    rssi_arr = np.asarray(rssi, dtype=np.float64)
    rssi_mean = float(rssi_arr.mean()) if rssi_arr.size and np.all(np.isfinite(rssi_arr)) else 0.0

    spec = amps.mean(axis=0)
    mean = float(spec.mean())
    std = float(spec.std())
    if std > EPS:
        z = (spec - mean) / std
        skew = float((z**3).mean())
        kurt = float((z**4).mean() - 3.0)
    else:
        skew = kurt = 0.0
    q75, q25 = np.percentile(spec, [75, 25])
    total = float(spec.sum())
    if total > EPS and np.all(spec >= 0):
        p = spec / total
        p = p[p > 0]
        entropy = float(-(p * np.log(p)).sum() / np.log(spec.size)) if spec.size > 1 else 0.0
    else:
        entropy = 0.0

    return np.array(
        [
            temporal_variance,
            motion_power,
            breath_power,
            total_power,
            dominant,
            change_points,
            rssi_mean,
            mean,
            std,
            skew,
            kurt,
            float(q75 - q25),
            entropy,
            float(spec.max()),
            float(spec.max() - spec.min()),
        ]
    )


def _merge_duplicate_times(t_ms: np.ndarray, amps: np.ndarray, rssi: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average packets that share a timestamp (bursty arrival) so the time axis is strictly increasing."""
    uniq, inverse, counts = np.unique(t_ms, return_inverse=True, return_counts=True)
    if uniq.size == t_ms.size:
        return t_ms, amps, rssi
    merged_amps = np.zeros((uniq.size, amps.shape[1]))
    np.add.at(merged_amps, inverse, amps)
    merged_rssi = np.zeros(uniq.size)
    np.add.at(merged_rssi, inverse, rssi)
    return uniq, merged_amps / counts[:, None], merged_rssi / counts


def resampled_window_features(
    t_ms: np.ndarray, amps: np.ndarray, rssi: np.ndarray, target_hz: float = RESAMPLE_HZ
) -> np.ndarray:
    """Features of one window after linear resampling onto a fixed `target_hz` grid over its own time span.

    The single entry point for training and the sidecar, so a 40 fps and a 66 fps window of the same scene give
    the same features. Returns zeros (like extract_window_features) when the window cannot be analysed.
    """
    t_ms = np.asarray(t_ms, dtype=np.float64)
    amps = np.asarray(amps, dtype=np.float64)
    rssi = np.asarray(rssi, dtype=np.float64)
    if t_ms.ndim != 1 or amps.ndim != 2 or amps.shape[0] != t_ms.size or rssi.shape != t_ms.shape or t_ms.size < 2:
        return np.zeros(NUM_FEATURES)
    order = np.argsort(t_ms, kind="stable")
    t_ms, amps, rssi = _merge_duplicate_times(t_ms[order], amps[order], rssi[order])
    span_s = (t_ms[-1] - t_ms[0]) / 1000.0
    n = int(round(span_s * target_hz)) + 1
    if span_s <= 0 or n < 2:
        return np.zeros(NUM_FEATURES)
    grid = np.linspace(t_ms[0], t_ms[-1], n)
    res_amps = np.empty((n, amps.shape[1]))
    for k in range(amps.shape[1]):
        res_amps[:, k] = np.interp(grid, t_ms, amps[:, k])
    res_rssi = np.interp(grid, t_ms, rssi)
    return extract_window_features(res_amps, res_rssi, target_hz)


def sliding_windows(
    t_ms: np.ndarray,
    amps: np.ndarray,
    rssi: np.ndarray,
    window_s: float = 1.0,
    hop_s: float = 0.5,
    min_frames: int = 16,
) -> Iterator[tuple[np.ndarray, float]]:
    """Yield (features, window_end_ms) over one node's time-ordered stream.

    Each window is resampled onto the fixed RESAMPLE_HZ grid from its own
    timestamps, so bursty or dropped packets and node rate changes don't skew
    the features. Windows with fewer than `min_frames` frames (gaps) are skipped.
    """
    t_ms = np.asarray(t_ms, dtype=np.float64)
    if t_ms.size == 0:
        return
    window_ms = window_s * 1000.0
    hop_ms = hop_s * 1000.0
    end = t_ms[0] + window_ms
    last = t_ms[-1]
    while end <= last + 1e-6:
        lo = np.searchsorted(t_ms, end - window_ms, side="left")
        hi = np.searchsorted(t_ms, end, side="right")
        if hi - lo >= min_frames and t_ms[hi - 1] > t_ms[lo]:
            yield resampled_window_features(t_ms[lo:hi], amps[lo:hi], rssi[lo:hi]), float(end)
        end += hop_ms
