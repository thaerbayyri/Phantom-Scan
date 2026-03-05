"""
DistanceEstimator — IFFT-based Time-of-Flight distance estimation.

Uses the Power Delay Profile (PDP) derived from an Inverse Fast Fourier
Transform of CSI frequency-domain data to estimate absolute target distance.

    Distance = (ToF × C) / 2

where C = speed of light (3 × 10⁸ m/s).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from .models import DistanceResult


# ─── Constants ───────────────────────────────────────────────────────

SPEED_OF_LIGHT = 3e8          # m/s
ESP32_BANDWIDTH_HZ = 20e6    # 20 MHz HT20 channel bandwidth
SUBCARRIER_SPACING_HZ = 312.5e3  # 802.11n subcarrier spacing
ESP32_NUM_SUBCARRIERS = 64   # Number of subcarriers for 20 MHz channel

# RSSI log-distance model parameters (calibrated for ESP32 at 2.4 GHz)
RSSI_REF = -40.0             # RSSI at 1 meter reference distance
PATH_LOSS_EXPONENT = 2.7     # Indoor path-loss exponent


class DistanceEstimator:
    """
    Estimates target distance using IFFT Power Delay Profile (PDP).

    The estimator transforms dual-channel CSI data (h1, h2) from the
    frequency domain to the time domain via IFFT, producing a PDP.
    The peak in the PDP corresponds to the dominant reflection path.

    Parameters
    ----------
    n_fft : int
        FFT size for zero-padded IFFT (higher = finer resolution).
    peak_threshold : float
        Minimum normalized peak power to consider valid (0-1).
    max_distance_m : float
        Maximum credible distance in meters (clamps output).
    smoothing_alpha : float
        EMA smoothing factor for distance output (0 = no smoothing).
    """

    def __init__(
        self,
        n_fft: int = 128,
        peak_threshold: float = 0.25,
        max_distance_m: float = 15.0,
        smoothing_alpha: float = 0.3,
    ):
        self.n_fft = n_fft
        self.peak_threshold = peak_threshold
        self.max_distance_m = max_distance_m
        self.smoothing_alpha = smoothing_alpha

        # State
        self._smoothed_distance_cm: Optional[float] = None
        self._smoothed_wall_m: Optional[float] = None
        self._csi_buffer: List[np.ndarray] = []
        self._max_buffer = 64

        # Pre-compute the Hanning window
        self._window = np.hanning(ESP32_NUM_SUBCARRIERS)

        # Delay-to-distance conversion factor
        # Each IFFT bin corresponds to: 1 / (n_fft * subcarrier_spacing) seconds
        self._bin_duration_s = 1.0 / (self.n_fft * SUBCARRIER_SPACING_HZ)

    # ─── Public API ──────────────────────────────────────────────

    def estimate(
        self,
        h1_re: float,
        h1_im: float,
        h2_re: float,
        h2_im: float,
        rssi: float = -50.0,
        return_pdp: bool = False,
    ) -> DistanceResult:
        """
        Estimate distance from a single CSI sample.

        Parameters
        ----------
        h1_re, h1_im : float
            Complex channel estimate for antenna/path 1.
        h2_re, h2_im : float
            Complex channel estimate for antenna/path 2.
        rssi : float
            Received Signal Strength Indicator (dBm).
        return_pdp : bool
            If True, include the raw PDP profile in the result.

        Returns
        -------
        DistanceResult
            Distance estimate with supporting metadata.
        """
        # Build CSI frequency vector from dual-channel data
        csi_vector = self._build_csi_vector(h1_re, h1_im, h2_re, h2_im)

        # Buffer for multi-sample averaging
        self._csi_buffer.append(csi_vector)
        if len(self._csi_buffer) > self._max_buffer:
            self._csi_buffer = self._csi_buffer[-self._max_buffer:]

        # Compute PDP via IFFT
        pdp_magnitude = self._compute_pdp(csi_vector)

        # Find the dynamic reflection peak (skip bin 0 = DC / direct path)
        peak_bin, peak_power = self._find_dynamic_peak(pdp_magnitude)

        # Convert peak bin to Time-of-Flight
        tof_s = peak_bin * self._bin_duration_s
        tof_ns = tof_s * 1e9

        # Distance = (ToF × C) / 2  (round-trip)
        pdp_distance_m = (tof_s * SPEED_OF_LIGHT) / 2.0

        # RSSI fallback distance
        rssi_distance_m = self._rssi_to_meters(rssi)

        # Fuse PDP and RSSI estimates
        if peak_power >= self.peak_threshold:
            # PDP peak is strong — trust it, blend with RSSI
            fused_m = 0.7 * pdp_distance_m + 0.3 * rssi_distance_m
        else:
            # Weak PDP — fall back more heavily to RSSI
            fused_m = 0.3 * pdp_distance_m + 0.7 * rssi_distance_m

        fused_m = max(0.1, min(self.max_distance_m, fused_m))
        fused_cm = fused_m * 100.0

        # Wall distance: second peak in PDP (first strong static reflection)
        wall_m = self._estimate_wall_distance(pdp_magnitude, peak_bin)

        # EMA smoothing
        if self._smoothed_distance_cm is None:
            self._smoothed_distance_cm = fused_cm
            self._smoothed_wall_m = wall_m
        else:
            a = self.smoothing_alpha
            self._smoothed_distance_cm = a * fused_cm + (1 - a) * self._smoothed_distance_cm
            self._smoothed_wall_m = a * wall_m + (1 - a) * self._smoothed_wall_m

        return DistanceResult(
            distance_cm=round(self._smoothed_distance_cm, 1),
            wall_distance_m=round(self._smoothed_wall_m, 2),
            tof_ns=round(tof_ns, 3),
            peak_bin=int(peak_bin),
            peak_power=round(float(peak_power), 4),
            rssi_distance_m=round(rssi_distance_m, 2),
            pdp_profile=[round(float(v), 6) for v in pdp_magnitude] if return_pdp else None,
        )

    def reset(self) -> None:
        """Clear all internal state."""
        self._smoothed_distance_cm = None
        self._smoothed_wall_m = None
        self._csi_buffer.clear()

    # ─── Private Methods ─────────────────────────────────────────

    def _build_csi_vector(
        self, h1_re: float, h1_im: float, h2_re: float, h2_im: float
    ) -> np.ndarray:
        """
        Build a CSI frequency vector from dual-channel complex data.

        With only 2 antenna paths we simulate a short frequency vector.
        The dual-path phase difference carries ranging information.
        """
        h1 = complex(h1_re, h1_im)
        h2 = complex(h2_re, h2_im)

        # Build a synthetic subcarrier array using the two paths
        # Interpolate phase and amplitude across virtual subcarriers
        n_sub = ESP32_NUM_SUBCARRIERS
        csi = np.zeros(n_sub, dtype=complex)

        mag1, mag2 = abs(h1), abs(h2)
        phase1, phase2 = np.angle(h1), np.angle(h2)
        phase_diff = phase1 - phase2

        for k in range(n_sub):
            # Linear interpolation across subcarriers
            t = k / (n_sub - 1)
            mag = mag1 * (1 - t) + mag2 * t
            phase = phase1 + t * phase_diff
            csi[k] = mag * np.exp(1j * phase)

        return csi

    def _compute_pdp(self, csi_vector: np.ndarray) -> np.ndarray:
        """
        Compute Power Delay Profile via windowed IFFT.

        Steps:
        1. Apply Hanning window to reduce spectral leakage
        2. Zero-pad to n_fft points for interpolation
        3. IFFT to get time-domain impulse response
        4. Take magnitude squared for power profile
        """
        # Apply Hanning window
        windowed = csi_vector * self._window[:len(csi_vector)]

        # Zero-pad to n_fft
        padded = np.zeros(self.n_fft, dtype=complex)
        padded[:len(windowed)] = windowed

        # IFFT → time domain
        impulse_response = np.fft.ifft(padded)

        # Power Delay Profile = |h(τ)|²
        pdp = np.abs(impulse_response) ** 2

        # Normalize
        pdp_max = np.max(pdp)
        if pdp_max > 1e-12:
            pdp = pdp / pdp_max

        return pdp

    def _find_dynamic_peak(
        self, pdp: np.ndarray, skip_bins: int = 2
    ) -> Tuple[float, float]:
        """
        Find the strongest peak in the PDP (skipping DC/near-zero bins).

        Uses parabolic interpolation for sub-bin resolution.
        """
        half = len(pdp) // 2  # Only use first half (positive delays)
        search_region = pdp[skip_bins:half]

        if len(search_region) == 0:
            return 0.0, 0.0

        raw_peak_idx = int(np.argmax(search_region))
        peak_power = float(search_region[raw_peak_idx])

        # Map back to full PDP index
        peak_bin = raw_peak_idx + skip_bins

        # Parabolic interpolation for sub-bin accuracy
        if 0 < raw_peak_idx < len(search_region) - 1:
            left = search_region[raw_peak_idx - 1]
            center = search_region[raw_peak_idx]
            right = search_region[raw_peak_idx + 1]
            offset = self._parabolic_peak(left, center, right)
            peak_bin += offset

        return float(peak_bin), peak_power

    def _estimate_wall_distance(
        self, pdp: np.ndarray, target_peak_bin: int
    ) -> float:
        """
        Estimate first wall reflection distance from secondary PDP peaks.
        """
        half = len(pdp) // 2
        exclusion_zone = max(3, int(target_peak_bin * 0.5))

        # Search for peaks outside the exclusion zone around the target
        best_bin = 0
        best_power = 0.0

        for i in range(2, half):
            if abs(i - target_peak_bin) < exclusion_zone:
                continue
            if pdp[i] > best_power:
                best_power = pdp[i]
                best_bin = i

        if best_power < 0.1:
            return 5.0  # Default wall distance

        tof_s = best_bin * self._bin_duration_s
        wall_m = (tof_s * SPEED_OF_LIGHT) / 2.0
        return max(0.5, min(20.0, wall_m))

    @staticmethod
    def _parabolic_peak(left: float, center: float, right: float) -> float:
        """Parabolic interpolation for sub-bin peak refinement."""
        denom = 2.0 * (2.0 * center - left - right)
        if abs(denom) < 1e-10:
            return 0.0
        return (left - right) / denom

    @staticmethod
    def _rssi_to_meters(rssi: float) -> float:
        """RSSI log-distance path-loss model (calibrated for ESP32 @ 2.4 GHz)."""
        if rssi >= RSSI_REF:
            return 0.5
        exponent = (RSSI_REF - rssi) / (10.0 * PATH_LOSS_EXPONENT)
        distance = 10.0 ** exponent
        return max(0.1, min(30.0, distance))
