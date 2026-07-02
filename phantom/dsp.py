from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from typing import Iterable

import numpy as np

from .protocol import CsiFrameV1, iq_pairs_from_bytes


def extract_amplitudes(iq_bytes: bytes) -> np.ndarray:
    pairs = iq_pairs_from_bytes(iq_bytes)
    if not pairs:
        return np.array([], dtype=float)
    arr = np.asarray(pairs, dtype=float)
    return np.sqrt(np.sum(np.square(arr), axis=1))


def extract_phases(iq_bytes: bytes) -> np.ndarray:
    pairs = iq_pairs_from_bytes(iq_bytes)
    if not pairs:
        return np.array([], dtype=float)
    arr = np.asarray(pairs, dtype=float)
    return np.arctan2(arr[:, 1], arr[:, 0])


def unwrap_phase_series(phases: np.ndarray) -> np.ndarray:
    if phases.size == 0:
        return phases
    return np.unwrap(phases)


@dataclass(slots=True)
class StaticClutterSuppressor:
    alpha: float = 0.05
    baseline: np.ndarray | None = None

    def update(self, amplitudes: np.ndarray) -> np.ndarray:
        if self.baseline is None or self.baseline.shape != amplitudes.shape:
            self.baseline = amplitudes.astype(float, copy=True)
            return np.zeros_like(amplitudes, dtype=float)
        self.baseline = (1.0 - self.alpha) * self.baseline + self.alpha * amplitudes
        return amplitudes - self.baseline


@dataclass(slots=True)
class HampelFilter:
    window_size: int = 7
    n_sigma: float = 3.0
    _buffer: deque[float] = field(init=False, repr=False)
    _k: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._buffer = deque(maxlen=max(self.window_size * 3, self.window_size))
        self._k = 1.4826

    def push(self, value: float) -> float:
        self._buffer.append(value)
        if len(self._buffer) < self.window_size:
            return value
        window = np.asarray(list(self._buffer)[-self.window_size :], dtype=float)
        median = float(np.median(window))
        mad = float(np.median(np.abs(window - median)))
        if mad <= 1e-12:
            return value
        threshold = self.n_sigma * self._k * mad
        return median if abs(value - median) > threshold else value

    def reset(self) -> None:
        self._buffer.clear()


@dataclass(slots=True)
class RespirationBandFilter:
    sample_rate_hz: float = 20.0
    low_hz: float = 0.1
    high_hz: float = 0.5
    window_size: int = 128
    _buffer: deque[float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._buffer = deque(maxlen=self.window_size)

    def push(self, value: float) -> float:
        self._buffer.append(value)
        if len(self._buffer) < 8:
            return value
        arr = np.asarray(self._buffer, dtype=float)
        arr = arr - np.mean(arr)
        spectrum = np.fft.rfft(arr)
        freqs = np.fft.rfftfreq(arr.size, d=1.0 / self.sample_rate_hz)
        mask = (freqs >= self.low_hz) & (freqs <= self.high_hz)
        filtered = np.zeros_like(spectrum)
        filtered[mask] = spectrum[mask]
        result = np.fft.irfft(filtered, n=arr.size)
        return float(result[-1])

    def reset(self) -> None:
        self._buffer.clear()


def motion_energy(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return 0.0
    centered = arr - np.mean(arr)
    return float(np.mean(np.square(centered)))


def cross_node_correlation(left: np.ndarray, right: np.ndarray) -> float:
    if left.size == 0 or right.size == 0:
        return 0.0
    n = min(left.size, right.size)
    left = left[:n]
    right = right[:n]
    left_std = float(np.std(left))
    right_std = float(np.std(right))
    if left_std <= 1e-12 or right_std <= 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def dual_node_on_axis_position(
    left_amplitude: float,
    right_amplitude: float,
    baseline_m: float = 5.0,
) -> dict[str, float | str]:
    total = max(0.0, left_amplitude) + max(0.0, right_amplitude)
    balance = 0.5 if total <= 1e-12 else max(0.0, right_amplitude) / total
    x_m = baseline_m * balance
    return {
        "x_m": float(x_m),
        "balance": float(balance),
        "baseline_m": float(baseline_m),
        "dimensionality": "1D-on-axis",
    }


def deterministic_human_gate(
    motion_present: bool,
    respiration_periodic: bool,
    cardiac_energy_present: bool = False,
) -> bool:
    return bool(motion_present and respiration_periodic and (cardiac_energy_present or respiration_periodic))


@dataclass(slots=True)
class NodeDspPipeline:
    clutter_alpha: float = 0.05
    hampel_window: int = 7
    sample_rate_hz: float = 20.0
    _clutter: StaticClutterSuppressor = field(init=False, repr=False)
    _hampel: HampelFilter = field(init=False, repr=False)
    _resp: RespirationBandFilter = field(init=False, repr=False)
    _history: deque[float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._clutter = StaticClutterSuppressor(alpha=self.clutter_alpha)
        self._hampel = HampelFilter(window_size=self.hampel_window)
        self._resp = RespirationBandFilter(sample_rate_hz=self.sample_rate_hz)
        self._history = deque(maxlen=128)

    def process(self, frame: CsiFrameV1) -> dict[str, float | int | bool]:
        amplitudes = extract_amplitudes(frame.iq_bytes)
        phases = unwrap_phase_series(extract_phases(frame.iq_bytes))
        dynamic = self._clutter.update(amplitudes)
        mean_dynamic = float(np.mean(dynamic)) if dynamic.size else 0.0
        filtered = self._hampel.push(mean_dynamic)
        resp_value = self._resp.push(filtered)
        self._history.append(filtered)
        energy = motion_energy(self._history)
        return {
            "node_id": frame.node_id,
            "seq": frame.seq,
            "mean_amplitude": float(np.mean(amplitudes)) if amplitudes.size else 0.0,
            "mean_phase": float(np.mean(phases)) if phases.size else 0.0,
            "dynamic_mean": filtered,
            "respiration_signal": resp_value,
            "motion_energy": energy,
            "sample_count": len(self._history),
            "is_motion": energy > 0.01,
        }
