"""
CSI Filter Pipeline — Advanced signal processing for Wi-Fi CSI-based tracking.

Pipeline: Raw CSI → Hampel → DWT → Phase Sanitize → Background Sub → STFT Classify
          → PDP Range → AoA → DBSCAN → Kalman

Requires: numpy, pywt, scikit-learn
"""

import math
import time
import numpy as np
from typing import Dict, Any, Optional, List, Tuple

try:
    import pywt
    HAS_PYWT = True
except ImportError:
    HAS_PYWT = False

try:
    from sklearn.cluster import DBSCAN as SkDBSCAN
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ═══════════════════════════════════════════════════════════════════
#  Hampel Filter — sliding-window median + MAD outlier rejection
# ═══════════════════════════════════════════════════════════════════

class HampelFilter:
    """
    Detects and replaces outliers using median / MAD (Median Absolute Deviation).
    Useful for removing hardware spikes (e.g., integer noise bursts from ESP32).
    """

    def __init__(self, window_size: int = 7, n_sigma: float = 3.0):
        self.window_size = window_size
        self.n_sigma = n_sigma
        self.buffer: List[float] = []
        self.k = 1.4826  # consistency constant for Gaussian distribution

    def push(self, value: float) -> float:
        """Push a sample and return the filtered value (outlier → median)."""
        self.buffer.append(value)

        if len(self.buffer) < self.window_size:
            return value

        # Keep buffer bounded
        if len(self.buffer) > self.window_size * 3:
            self.buffer = self.buffer[-self.window_size * 2:]

        window = self.buffer[-self.window_size:]
        median = float(np.median(window))
        mad = float(np.median(np.abs(np.array(window) - median)))
        threshold = self.n_sigma * self.k * mad

        if mad > 1e-10 and abs(value - median) > threshold:
            return median  # Replace outlier with median
        return value

    def filter_array(self, data: np.ndarray) -> np.ndarray:
        """Filter an entire array in one pass."""
        result = data.copy()
        half_w = self.window_size // 2

        for i in range(half_w, len(data) - half_w):
            window = data[i - half_w: i + half_w + 1]
            median = np.median(window)
            mad = np.median(np.abs(window - median))
            threshold = self.n_sigma * self.k * mad

            if mad > 1e-10 and abs(data[i] - median) > threshold:
                result[i] = median

        return result

    def reset(self):
        self.buffer.clear()


# ═══════════════════════════════════════════════════════════════════
#  DWT Denoiser — Discrete Wavelet Transform soft-thresholding
# ═══════════════════════════════════════════════════════════════════

class DWTDenoiser:
    """
    Uses pywt (PyWavelets) to decompose, threshold detail coefficients,
    and reconstruct. Preserves low-frequency human movement components
    while removing high-frequency sensor noise.
    """

    def __init__(self, wavelet: str = "db4", level: int = 3):
        self.wavelet = wavelet
        self.level = level
        self.buffer: List[float] = []
        self.min_samples = 2 ** (level + 1)  # Minimum for decomposition

    def push(self, value: float) -> float:
        """Accumulate samples; return denoised version of latest value."""
        self.buffer.append(value)

        if len(self.buffer) < self.min_samples:
            return value

        # Keep bounded buffer
        if len(self.buffer) > self.min_samples * 4:
            self.buffer = self.buffer[-self.min_samples * 2:]

        denoised = self.denoise_array(np.array(self.buffer[-self.min_samples:]))
        return float(denoised[-1])

    def denoise_array(self, data: np.ndarray) -> np.ndarray:
        """Denoise an entire array using DWT + soft thresholding."""
        if not HAS_PYWT:
            return data  # Fallback: no filtering

        if len(data) < self.min_samples:
            return data

        # Decompose
        coeffs = pywt.wavedec(data, self.wavelet, level=self.level)

        # Compute universal threshold (VisuShrink)
        # σ estimated from finest detail coefficients
        detail_coeffs = coeffs[-1]
        sigma = np.median(np.abs(detail_coeffs)) / 0.6745
        threshold = sigma * np.sqrt(2 * np.log(len(data)))

        # Soft-threshold detail coefficients (keep approximation intact)
        denoised_coeffs = [coeffs[0]]  # Keep approximation
        for c in coeffs[1:]:
            denoised_coeffs.append(pywt.threshold(c, threshold, mode="soft"))

        # Reconstruct
        return pywt.waverec(denoised_coeffs, self.wavelet)[:len(data)]

    def reset(self):
        self.buffer.clear()


# ═══════════════════════════════════════════════════════════════════
#  Background Subtractor — EMA-based static path removal
# ═══════════════════════════════════════════════════════════════════

class BackgroundSubtractor:
    """
    Exponential moving average (EMA) subtraction to eliminate
    static multipath (walls, furniture). Only dynamic components pass.
    """

    def __init__(self, alpha: float = 0.02):
        """alpha: smoothing factor. Lower = slower adaptation = better static removal."""
        self.alpha = alpha
        self.bg_h1_re: Optional[float] = None
        self.bg_h1_im: Optional[float] = None
        self.bg_h2_re: Optional[float] = None
        self.bg_h2_im: Optional[float] = None

    def process(
        self,
        h1_re: float, h1_im: float,
        h2_re: float, h2_im: float,
    ) -> Tuple[float, float, float, float]:
        """Returns dynamic (h1_re, h1_im, h2_re, h2_im) after background removal."""
        if self.bg_h1_re is None:
            # Initialize background model
            self.bg_h1_re = h1_re
            self.bg_h1_im = h1_im
            self.bg_h2_re = h2_re
            self.bg_h2_im = h2_im
            return 0.0, 0.0, 0.0, 0.0

        # Update EMA background
        a = self.alpha
        self.bg_h1_re = a * h1_re + (1 - a) * self.bg_h1_re
        self.bg_h1_im = a * h1_im + (1 - a) * self.bg_h1_im
        self.bg_h2_re = a * h2_re + (1 - a) * self.bg_h2_re
        self.bg_h2_im = a * h2_im + (1 - a) * self.bg_h2_im

        # Dynamic = current - background
        return (
            h1_re - self.bg_h1_re,
            h1_im - self.bg_h1_im,
            h2_re - self.bg_h2_re,
            h2_im - self.bg_h2_im,
        )

    def reset(self):
        self.bg_h1_re = None
        self.bg_h1_im = None
        self.bg_h2_re = None
        self.bg_h2_im = None


# ═══════════════════════════════════════════════════════════════════
#  Kalman Filter — constant-velocity model for (x, z, vx, vz)
# ═══════════════════════════════════════════════════════════════════

class KalmanTracker:
    """
    2D constant-velocity Kalman filter.
    State: [x, z, vx, vz]
    Measurement: [x, z]
    """

    def __init__(self, dt: float = 0.05):
        self.dt = dt

        # State [x, z, vx, vz]
        self.x = np.zeros(4)

        # State transition
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1],
        ], dtype=float)

        # Measurement matrix (observe position only)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)

        # Covariance
        self.P = np.eye(4) * 1.0

        # Process noise
        q = 0.05
        self.Q = np.array([
            [q * dt**3 / 3, 0, q * dt**2 / 2, 0],
            [0, q * dt**3 / 3, 0, q * dt**2 / 2],
            [q * dt**2 / 2, 0, q * dt, 0],
            [0, q * dt**2 / 2, 0, q * dt],
        ], dtype=float)

        # Measurement noise
        self.R = np.eye(2) * 0.15

        self.initialized = False

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, pos_x: float, pos_z: float):
        if not self.initialized:
            self.x[0] = pos_x
            self.x[1] = pos_z
            self.initialized = True
            return

        z = np.array([pos_x, pos_z])
        y = z - self.H @ self.x  # Innovation
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    def get_state(self) -> Dict[str, float]:
        return {
            "x": float(self.x[0]),
            "z": float(self.x[1]),
            "vx": float(self.x[2]),
            "vz": float(self.x[3]),
        }

    def reset(self):
        self.x = np.zeros(4)
        self.P = np.eye(4) * 1.0
        self.initialized = False


# ═══════════════════════════════════════════════════════════════════
#  Phase Sanitizer — Linear regression SFO/PCLO removal
# ═══════════════════════════════════════════════════════════════════

class PhaseSanitizer:
    """
    Removes Sampling Frequency Offset (SFO) and Packet-level Clock/Phase
    Offset (PCLO) from CSI phase using linear regression.

    For each sample, the phase across channels (h1, h2) is unwrapped,
    a linear model φ(k) = a·k + b is fit (slope = SFO, intercept = PCLO),
    and the fitted line is subtracted to yield clean phase.
    """

    def __init__(self, buffer_size: int = 30):
        self.buffer_size = buffer_size
        self.phase_buffer: List[List[float]] = []  # [[phase_h1, phase_h2], ...]

    def process(
        self, h1_re: float, h1_im: float, h2_re: float, h2_im: float
    ) -> Tuple[float, float, float, float]:
        """Clean phase via linear regression and return sanitized complex values."""
        phase_h1 = math.atan2(h1_im, h1_re + 1e-10)
        phase_h2 = math.atan2(h2_im, h2_re + 1e-10)
        amp_h1 = math.sqrt(h1_re**2 + h1_im**2)
        amp_h2 = math.sqrt(h2_re**2 + h2_im**2)

        self.phase_buffer.append([phase_h1, phase_h2])
        if len(self.phase_buffer) > self.buffer_size:
            self.phase_buffer = self.phase_buffer[-self.buffer_size:]

        if len(self.phase_buffer) < 5:
            return h1_re, h1_im, h2_re, h2_im

        # Unwrap phases across time
        phases = np.array(self.phase_buffer)
        unwrapped_h1 = np.unwrap(phases[:, 0])
        unwrapped_h2 = np.unwrap(phases[:, 1])

        # Fit linear model to each channel: phase(t) = a*t + b
        t_indices = np.arange(len(unwrapped_h1))
        # H1 fit
        coeffs_h1 = np.polyfit(t_indices, unwrapped_h1, 1)
        clean_phase_h1 = unwrapped_h1[-1] - (coeffs_h1[0] * t_indices[-1] + coeffs_h1[1])
        # H2 fit
        coeffs_h2 = np.polyfit(t_indices, unwrapped_h2, 1)
        clean_phase_h2 = unwrapped_h2[-1] - (coeffs_h2[0] * t_indices[-1] + coeffs_h2[1])

        # Reconstruct complex from cleaned phase + original amplitude
        return (
            amp_h1 * math.cos(clean_phase_h1),
            amp_h1 * math.sin(clean_phase_h1),
            amp_h2 * math.cos(clean_phase_h2),
            amp_h2 * math.sin(clean_phase_h2),
        )

    def reset(self):
        self.phase_buffer.clear()


# ═══════════════════════════════════════════════════════════════════
#  Micro-Doppler Classifier — STFT-based human/machine discrimination
# ═══════════════════════════════════════════════════════════════════

class MicroDopplerClassifier:
    """
    Classifies detected targets as human or mechanical using
    Short-Time Fourier Transform (STFT) of the CSI amplitude envelope.

    Features:
      - Periodicity score: autocorrelation of spectral energy
        (mechanical targets have strong periodic signatures)
      - High-frequency ratio: fraction of energy above 5Hz
        (machines exhibit high-freq vibrations)

    Classification:
      Periodic + high-freq → "mechanical" (humanProb < 0.3)
      Non-periodic + low-freq → "human" (humanProb > 0.7)
    """

    def __init__(self, buffer_size: int = 40, sample_rate: float = 20.0):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.amplitude_buffer: List[float] = []
        self.last_label = "unknown"
        self.last_human_prob = 0.5

    def push(self, amplitude: float) -> Dict[str, Any]:
        """Push CSI amplitude and return classification."""
        self.amplitude_buffer.append(amplitude)
        if len(self.amplitude_buffer) > self.buffer_size * 2:
            self.amplitude_buffer = self.amplitude_buffer[-self.buffer_size:]

        if len(self.amplitude_buffer) < self.buffer_size:
            return {"label": self.last_label, "humanProb": self.last_human_prob}

        window = np.array(self.amplitude_buffer[-self.buffer_size:])

        # Remove DC component
        window = window - np.mean(window)

        # Apply Hanning window
        windowed = window * np.hanning(len(window))

        # FFT
        fft_result = np.fft.rfft(windowed)
        power_spectrum = np.abs(fft_result) ** 2
        freqs = np.fft.rfftfreq(len(windowed), d=1.0 / self.sample_rate)

        total_power = np.sum(power_spectrum[1:]) + 1e-10  # Exclude DC

        # Feature 1: High-frequency ratio (energy above 5Hz / total)
        high_freq_mask = freqs > 5.0
        high_freq_ratio = float(np.sum(power_spectrum[high_freq_mask]) / total_power)

        # Feature 2: Periodicity — autocorrelation peak strength
        autocorr = np.correlate(window, window, mode="full")
        autocorr = autocorr[len(autocorr) // 2:]  # Second half
        autocorr = autocorr / (autocorr[0] + 1e-10)  # Normalize

        # Find first significant peak after lag 0 (skip first 3 samples)
        min_lag = 3
        if len(autocorr) > min_lag + 5:
            peaks_region = autocorr[min_lag:]
            periodicity = float(np.max(peaks_region))
        else:
            periodicity = 0.0

        # Classification logic
        # High periodicity + high freq → mechanical
        # Low periodicity + low freq → human
        mechanical_score = 0.0
        mechanical_score += min(1.0, high_freq_ratio * 3.0) * 0.5  # Up to 0.5
        mechanical_score += min(1.0, periodicity * 1.5) * 0.5       # Up to 0.5

        human_prob = max(0.0, min(1.0, 1.0 - mechanical_score))

        if human_prob > 0.65:
            label = "human"
        elif human_prob < 0.35:
            label = "mechanical"
        else:
            label = "unknown"

        self.last_label = label
        self.last_human_prob = human_prob

        return {
            "label": label,
            "humanProb": round(human_prob, 4),
            "mechanicalProb": round(1.0 - human_prob, 4),
            "periodicity": round(periodicity, 4),
            "highFreqRatio": round(high_freq_ratio, 4),
        }

    def reset(self):
        self.amplitude_buffer.clear()
        self.last_label = "unknown"
        self.last_human_prob = 0.5


# ═══════════════════════════════════════════════════════════════════
#  PDP Ranger — Power Delay Profile super-resolution distance
# ═══════════════════════════════════════════════════════════════════

class PDPRanger:
    """
    Computes Power Delay Profile (PDP) via IFFT of complex CSI data
    to estimate the distance to the moving target and static reflections.

    Uses dual-path (h1, h2) to build a mini-CSI vector, applies IFFT
    to get the channel impulse response, and finds the first significant
    peak → direct path → distance d = c·τ / 2.

    Also identifies later peaks as wall/static reflections.
    """

    SPEED_OF_LIGHT = 3e8  # m/s
    BANDWIDTH = 20e6      # ESP32 Wi-Fi channel bandwidth (20MHz)

    def __init__(self, n_fft: int = 64, peak_threshold: float = 0.3):
        self.n_fft = n_fft
        self.peak_threshold = peak_threshold
        self.csi_buffer: List[np.ndarray] = []  # Complex CSI vectors
        self.buffer_size = 10
        self.last_distance = 2.0
        self.last_wall_distance = 5.0

    def push(
        self,
        h1_re: float, h1_im: float,
        h2_re: float, h2_im: float,
        rssi: float = -50.0,
    ) -> Dict[str, float]:
        """Process CSI sample and return distance estimates."""
        # Build complex CSI vector from dual-path data
        h1 = complex(h1_re, h1_im)
        h2 = complex(h2_re, h2_im)

        # Create a synthetic subcarrier-like vector using h1, h2
        # and their combinations (phase-rotated)
        csi_vec = np.array([
            h1, h2,
            h1 * np.conj(h2),  # Cross-correlation
            h1 + h2,           # Sum beam
        ], dtype=complex)

        self.csi_buffer.append(csi_vec)
        if len(self.csi_buffer) > self.buffer_size:
            self.csi_buffer = self.csi_buffer[-self.buffer_size:]

        # Build averaged CSI matrix for PDP
        if len(self.csi_buffer) < 3:
            # Fall back to RSSI-based distance
            A, n_path = -30.0, 2.5
            r = 10.0 ** ((A - rssi) / (10.0 * n_path))
            r = max(0.5, min(8.0, r))
            return {
                "distanceCm": round(r * 100, 1),
                "wallDistance": round(self.last_wall_distance, 2),
            }

        # Average CSI across recent frames for noise reduction
        avg_csi = np.mean(self.csi_buffer, axis=0)

        # Zero-pad and IFFT → Power Delay Profile
        padded = np.zeros(self.n_fft, dtype=complex)
        padded[:len(avg_csi)] = avg_csi
        impulse = np.fft.ifft(padded)
        pdp = np.abs(impulse) ** 2

        # Normalize PDP
        pdp_max = np.max(pdp)
        if pdp_max > 1e-10:
            pdp_norm = pdp / pdp_max
        else:
            pdp_norm = pdp

        # Time resolution per bin
        # τ_bin = 1 / BW, distance_bin = c / (2 * BW)
        dist_per_bin = self.SPEED_OF_LIGHT / (2 * self.BANDWIDTH * self.n_fft / len(avg_csi))

        # Find peaks above threshold
        peaks = []
        for i in range(1, len(pdp_norm) // 2):  # First half only
            if pdp_norm[i] > self.peak_threshold:
                if pdp_norm[i] > pdp_norm[i - 1] and (
                    i + 1 >= len(pdp_norm) or pdp_norm[i] >= pdp_norm[i + 1]
                ):
                    peaks.append((i, float(pdp_norm[i])))

        if peaks:
            # First peak = direct path (target distance)
            first_peak_bin = peaks[0][0]
            distance_m = max(0.3, min(8.0, first_peak_bin * dist_per_bin))
            self.last_distance = distance_m

            # Look for wall reflection (second significant peak)
            if len(peaks) > 1:
                wall_bin = peaks[-1][0]  # Furthest peak
                wall_dist = wall_bin * dist_per_bin
                self.last_wall_distance = max(distance_m + 0.5, min(10.0, wall_dist))
        else:
            # Fallback to RSSI
            A, n_path = -30.0, 2.5
            r = 10.0 ** ((A - rssi) / (10.0 * n_path))
            self.last_distance = max(0.5, min(8.0, r))

        return {
            "distanceCm": round(self.last_distance * 100, 1),
            "wallDistance": round(self.last_wall_distance, 2),
        }

    def reset(self):
        self.csi_buffer.clear()
        self.last_distance = 2.0
        self.last_wall_distance = 5.0


# ═══════════════════════════════════════════════════════════════════
#  CSI Filter Pipeline — Full end-to-end processing class
# ═══════════════════════════════════════════════════════════════════

class CSIFilterPipeline:
    """
    Complete signal processing pipeline for ESP32 CSI-based human tracking.

    Pipeline stages:
      1. Hampel filter — remove hardware outliers (integer noise bursts)
      2. DWT denoiser — wavelet-based noise floor reduction
      3. Phase sanitization — SFO/PCLO linear regression removal
      4. Background subtraction — remove static multipath (walls/furniture)
      5. Micro-Doppler classification — STFT human vs mechanical
      6. PDP ranging — IFFT super-resolution distance (cm)
      7. AoA estimation — bearing angle from phase difference
      8. DBSCAN clustering — isolate human target from multipath ghosts
      9. Kalman filter — smooth trajectory, estimate velocity vector
    """

    def __init__(
        self,
        hampel_window: int = 7,
        hampel_sigma: float = 3.0,
        dwt_wavelet: str = "db4",
        dwt_level: int = 3,
        bg_alpha: float = 0.02,
        dbscan_eps: float = 0.5,
        dbscan_min_samples: int = 3,
        kalman_dt: float = 0.05,
        stft_buffer: int = 40,
        sample_rate: float = 20.0,
    ):
        # Stage 1: Hampel
        self.hampel_h1_re = HampelFilter(hampel_window, hampel_sigma)
        self.hampel_h1_im = HampelFilter(hampel_window, hampel_sigma)
        self.hampel_h2_re = HampelFilter(hampel_window, hampel_sigma)
        self.hampel_h2_im = HampelFilter(hampel_window, hampel_sigma)

        # Stage 2: DWT
        self.dwt_h1_re = DWTDenoiser(dwt_wavelet, dwt_level)
        self.dwt_h1_im = DWTDenoiser(dwt_wavelet, dwt_level)
        self.dwt_h2_re = DWTDenoiser(dwt_wavelet, dwt_level)
        self.dwt_h2_im = DWTDenoiser(dwt_wavelet, dwt_level)

        # Stage 3: Phase sanitization
        self.phase_sanitizer = PhaseSanitizer()

        # Stage 4: Background subtraction
        self.bg_sub = BackgroundSubtractor(bg_alpha)

        # Stage 5: Micro-Doppler classifier
        self.classifier = MicroDopplerClassifier(stft_buffer, sample_rate)

        # Stage 6: PDP ranger
        self.pdp_ranger = PDPRanger()

        # Stage 8: DBSCAN
        self.dbscan_eps = dbscan_eps
        self.dbscan_min_samples = dbscan_min_samples
        self.point_buffer: List[Dict[str, float]] = []
        self.max_buffer = 30

        # Stage 9: Kalman
        self.kalman = KalmanTracker(kalman_dt)

        # State
        self.frame_count = 0
        self.last_result: Optional[Dict[str, Any]] = None

    def process_sample(
        self,
        h1_re: float, h1_im: float,
        h2_re: float, h2_im: float,
        rssi: float = -50.0,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process a single CSI sample through the full pipeline.

        Returns dict with keys:
            x, z, r, theta, vx, vz, speed, angle, isMoving, confidence,
            label, humanProb, mechanicalProb, distanceCm, wallDistance
        """
        ts = timestamp or time.time()
        self.frame_count += 1

        # ── Stage 1: Hampel outlier removal ──
        h1_re = self.hampel_h1_re.push(h1_re)
        h1_im = self.hampel_h1_im.push(h1_im)
        h2_re = self.hampel_h2_re.push(h2_re)
        h2_im = self.hampel_h2_im.push(h2_im)

        # ── Stage 2: DWT denoising ──
        h1_re = self.dwt_h1_re.push(h1_re)
        h1_im = self.dwt_h1_im.push(h1_im)
        h2_re = self.dwt_h2_re.push(h2_re)
        h2_im = self.dwt_h2_im.push(h2_im)

        # ── Stage 3: Phase sanitization (SFO/PCLO removal) ──
        h1_re, h1_im, h2_re, h2_im = self.phase_sanitizer.process(
            h1_re, h1_im, h2_re, h2_im
        )

        # ── Stage 4: Background subtraction ──
        dh1_re, dh1_im, dh2_re, dh2_im = self.bg_sub.process(h1_re, h1_im, h2_re, h2_im)

        # Dynamic signal amplitude (movement indicator)
        dyn_amp = math.sqrt(dh1_re**2 + dh1_im**2 + dh2_re**2 + dh2_im**2)

        # ── Stage 5: Micro-Doppler classification ──
        classification = self.classifier.push(dyn_amp)

        # ── Stage 6: PDP super-resolution distance ──
        pdp_result = self.pdp_ranger.push(dh1_re, dh1_im, dh2_re, dh2_im, rssi)

        # ── Stage 7: AoA estimation ──
        phase_h1 = math.atan2(dh1_im, dh1_re + 1e-10)
        phase_h2 = math.atan2(dh2_im, dh2_re + 1e-10)
        phase_diff = phase_h1 - phase_h2
        phase_diff = math.atan2(math.sin(phase_diff), math.cos(phase_diff))

        sin_theta = max(-1.0, min(1.0, phase_diff / math.pi))
        theta = math.asin(sin_theta)

        # Use PDP distance instead of RSSI fallback
        r = pdp_result["distanceCm"] / 100.0  # Convert cm → meters
        r = max(0.5, min(8.0, r))

        # Polar → Cartesian
        raw_x = r * math.cos(theta)
        raw_z = r * math.sin(theta)

        # ── Stage 8: DBSCAN clustering ──
        self.point_buffer.append({"x": raw_x, "z": raw_z, "amp": dyn_amp})
        if len(self.point_buffer) > self.max_buffer:
            self.point_buffer = self.point_buffer[-self.max_buffer:]

        centroid_x, centroid_z, confidence = self._cluster_centroid()

        # ── Stage 9: Kalman filter ──
        self.kalman.predict()
        if confidence > 0.3:
            self.kalman.update(centroid_x, centroid_z)

        state = self.kalman.get_state()
        speed = math.sqrt(state["vx"] ** 2 + state["vz"] ** 2)
        is_moving = speed > 0.05 and dyn_amp > 0.01

        # Direction of travel
        if is_moving and speed > 0.02:
            angle = math.atan2(state["vz"], state["vx"])
        elif self.last_result:
            angle = self.last_result["angle"]
        else:
            angle = 0.0

        result = {
            "x": round(state["x"], 4),
            "z": round(state["z"], 4),
            "r": round(math.sqrt(state["x"]**2 + state["z"]**2), 4),
            "theta": round(math.atan2(state["z"], state["x"] + 1e-10), 4),
            "vx": round(state["vx"], 4),
            "vz": round(state["vz"], 4),
            "speed": round(speed, 4),
            "angle": round(angle, 4),
            "isMoving": is_moving,
            "confidence": round(confidence, 4),
            # New fields
            "label": classification["label"],
            "humanProb": classification["humanProb"],
            "mechanicalProb": classification.get("mechanicalProb", round(1.0 - classification["humanProb"], 4)),
            "distanceCm": pdp_result["distanceCm"],
            "wallDistance": pdp_result["wallDistance"],
        }

        self.last_result = result
        return result

    def _cluster_centroid(self) -> Tuple[float, float, float]:
        """Run DBSCAN and return weighted centroid of largest cluster."""
        if len(self.point_buffer) < self.dbscan_min_samples:
            if self.point_buffer:
                p = self.point_buffer[-1]
                return p["x"], p["z"], 0.3
            return 0.0, 0.0, 0.0

        coords = np.array([[p["x"], p["z"]] for p in self.point_buffer])
        amps = np.array([p["amp"] for p in self.point_buffer])

        if HAS_SKLEARN:
            clustering = SkDBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples)
            labels = clustering.fit_predict(coords)
        else:
            # Fallback: treat all as one cluster
            labels = np.zeros(len(coords), dtype=int)

        unique_labels = set(labels)
        unique_labels.discard(-1)

        if not unique_labels:
            # All noise — return latest point
            p = self.point_buffer[-1]
            return p["x"], p["z"], 0.2

        # Find highest-energy cluster
        best_label = -1
        best_energy = -1.0
        for label in unique_labels:
            mask = (labels == label)
            energy = float(amps[mask].sum())
            if energy > best_energy:
                best_energy = energy
                best_label = label

        mask = (labels == best_label)
        cluster_coords = coords[mask]
        cluster_amps = amps[mask]
        total_w = cluster_amps.sum()

        if total_w < 1e-10:
            cx = float(cluster_coords[:, 0].mean())
            cz = float(cluster_coords[:, 1].mean())
        else:
            cx = float(np.average(cluster_coords[:, 0], weights=cluster_amps))
            cz = float(np.average(cluster_coords[:, 1], weights=cluster_amps))

        # Confidence: ratio of cluster size to total points
        confidence = float(mask.sum()) / len(labels)
        return cx, cz, min(1.0, confidence + 0.3)

    def reset(self):
        """Reset all pipeline state."""
        self.hampel_h1_re.reset()
        self.hampel_h1_im.reset()
        self.hampel_h2_re.reset()
        self.hampel_h2_im.reset()
        self.dwt_h1_re.reset()
        self.dwt_h1_im.reset()
        self.dwt_h2_re.reset()
        self.dwt_h2_im.reset()
        self.phase_sanitizer.reset()
        self.bg_sub.reset()
        self.classifier.reset()
        self.pdp_ranger.reset()
        self.kalman.reset()
        self.point_buffer.clear()
        self.frame_count = 0
        self.last_result = None


# ═══════════════════════════════════════════════════════════════════
#  Convenience: process a recorded CSV session
# ═══════════════════════════════════════════════════════════════════

def process_csv_file(filepath: str) -> List[Dict[str, Any]]:
    """Load a recorded CSI session CSV and process through the full pipeline."""
    pipeline = CSIFilterPipeline()
    results = []

    with open(filepath, "r") as f:
        header = f.readline()  # Skip header

        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue

            try:
                ts = float(parts[0])
                h1_re = float(parts[2])
                h1_im = float(parts[3])
                h2_re = float(parts[4])
                h2_im = float(parts[5])
                rssi = float(parts[6])
            except (ValueError, IndexError):
                continue

            result = pipeline.process_sample(h1_re, h1_im, h2_re, h2_im, rssi, ts)
            results.append(result)

    return results
