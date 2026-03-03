"""
CSI Filter Pipeline — Advanced signal processing for Wi-Fi CSI-based tracking.

Pipeline: Raw CSI → Hampel → DWT → Background Subtraction → AoA/ToF → DBSCAN → Kalman

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
#  CSI Filter Pipeline — Full end-to-end processing class
# ═══════════════════════════════════════════════════════════════════

class CSIFilterPipeline:
    """
    Complete signal processing pipeline for ESP32 CSI-based human tracking.

    Pipeline stages:
      1. Hampel filter — remove hardware outliers (integer noise bursts)
      2. DWT denoiser — wavelet-based noise floor reduction
      3. Background subtraction — remove static multipath (walls/furniture)
      4. AoA + ToF estimation — bearing angle + RSSI-based distance
      5. DBSCAN clustering — isolate human target from multipath ghosts
      6. Kalman filter — smooth trajectory, estimate velocity vector
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

        # Stage 3: Background subtraction
        self.bg_sub = BackgroundSubtractor(bg_alpha)

        # Stage 5: DBSCAN
        self.dbscan_eps = dbscan_eps
        self.dbscan_min_samples = dbscan_min_samples
        self.point_buffer: List[Dict[str, float]] = []
        self.max_buffer = 30

        # Stage 6: Kalman
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
            x, z, r, theta, vx, vz, speed, angle, isMoving, confidence
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

        # ── Stage 3: Background subtraction ──
        dh1_re, dh1_im, dh2_re, dh2_im = self.bg_sub.process(h1_re, h1_im, h2_re, h2_im)

        # ── Stage 4: AoA + ToF estimation ──
        # AoA from phase difference
        phase_h1 = math.atan2(dh1_im, dh1_re + 1e-10)
        phase_h2 = math.atan2(dh2_im, dh2_re + 1e-10)
        phase_diff = phase_h1 - phase_h2
        phase_diff = math.atan2(math.sin(phase_diff), math.cos(phase_diff))

        sin_theta = max(-1.0, min(1.0, phase_diff / math.pi))
        theta = math.asin(sin_theta)

        # Distance from RSSI (free-space path loss)
        A = -30.0   # RSSI at 1m (calibration)
        n = 2.5     # Path loss exponent (indoor)
        r = 10.0 ** ((A - rssi) / (10.0 * n))
        r = max(0.5, min(8.0, r))

        # Polar → Cartesian
        raw_x = r * math.cos(theta)
        raw_z = r * math.sin(theta)

        # Dynamic signal amplitude (movement indicator)
        dyn_amp = math.sqrt(dh1_re**2 + dh1_im**2 + dh2_re**2 + dh2_im**2)

        # ── Stage 5: DBSCAN clustering ──
        self.point_buffer.append({"x": raw_x, "z": raw_z, "amp": dyn_amp})
        if len(self.point_buffer) > self.max_buffer:
            self.point_buffer = self.point_buffer[-self.max_buffer:]

        centroid_x, centroid_z, confidence = self._cluster_centroid()

        # ── Stage 6: Kalman filter ──
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
        self.bg_sub.reset()
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
