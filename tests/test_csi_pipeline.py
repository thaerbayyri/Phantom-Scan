"""
Test suite for CSI Filter Pipeline — uses real ESP32 recorded data.

Run: python -m pytest tests/test_csi_pipeline.py -v
"""

import os
import sys
import csv
import math
import pytest
import numpy as np

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from csi_filter_pipeline import (
    HampelFilter,
    DWTDenoiser,
    BackgroundSubtractor,
    KalmanTracker,
    CSIFilterPipeline,
)


# ── Fixtures: load real ESP32 data ──────────────────────────────────

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "recordings")


def _find_recording() -> str:
    """Find the first available real CSI recording CSV."""
    if not os.path.isdir(RECORDINGS_DIR):
        pytest.skip("No recordings/ directory found")
    csvs = sorted(
        [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".csv")],
        reverse=True,
    )
    if not csvs:
        pytest.skip("No CSV recording files found in recordings/")
    return os.path.join(RECORDINGS_DIR, csvs[0])


def _load_samples(max_rows: int = 500):
    """Load real CSI samples from the first available recording."""
    filepath = _find_recording()
    samples = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            try:
                samples.append({
                    "timestamp": float(row["timestamp"]),
                    "h1_re": float(row["h1_re"]),
                    "h1_im": float(row["h1_im"]),
                    "h2_re": float(row["h2_re"]),
                    "h2_im": float(row["h2_im"]),
                    "rssi": float(row["rssi"]),
                })
            except (ValueError, KeyError):
                continue  # Skip malformed rows (integer noise bursts)
    return samples


@pytest.fixture
def real_samples():
    """Fixture providing real ESP32 CSI samples."""
    samples = _load_samples(500)
    assert len(samples) > 50, "Need at least 50 valid samples for testing"
    return samples


@pytest.fixture
def pipeline():
    """Fixture providing a fresh CSIFilterPipeline instance."""
    return CSIFilterPipeline()


# ═══════════════════════════════════════════════════════════════════
#  Test 1: Hampel filter detects and removes hardware outliers
# ═══════════════════════════════════════════════════════════════════

class TestHampelFilter:
    def test_removes_spike_outliers(self):
        """Hampel should replace spike outliers with median."""
        hf = HampelFilter(window_size=7, n_sigma=3.0)
        clean_signal = [0.5] * 10
        # Inject a hardware spike (like the integer noise bursts from ESP32)
        spiked = clean_signal[:5] + [50.0] + clean_signal[5:]

        results = [hf.push(v) for v in spiked]
        # The spike at index 5 should have been replaced (close to 0.5, not 50)
        assert results[10] < 5.0, "Hampel failed to remove outlier spike"

    def test_preserves_clean_signal(self):
        """Hampel should not alter clean signals."""
        hf = HampelFilter(window_size=7, n_sigma=3.0)
        clean = [math.sin(i * 0.1) for i in range(30)]
        results = [hf.push(v) for v in clean]
        # After warm-up, filtered values should be very close to original
        for i in range(10, 30):
            assert abs(results[i] - clean[i]) < 0.5

    def test_with_real_data(self, real_samples):
        """Hampel should not crash on real ESP32 data."""
        hf = HampelFilter()
        for s in real_samples:
            result = hf.push(s["h1_re"])
            assert math.isfinite(result), "Hampel produced non-finite value"


# ═══════════════════════════════════════════════════════════════════
#  Test 2: DWT denoiser preserves signal shape
# ═══════════════════════════════════════════════════════════════════

class TestDWTDenoiser:
    def test_preserves_low_frequency(self):
        """DWT should preserve low-frequency components (human movement)."""
        dwt = DWTDenoiser(wavelet="db4", level=3)
        # Low-frequency sine wave with high-frequency noise
        t = np.linspace(0, 2 * math.pi, 64)
        clean = np.sin(t)
        noisy = clean + np.random.normal(0, 0.3, len(t))

        denoised = dwt.denoise_array(noisy)
        # Denoised should be closer to clean than noisy is
        error_noisy = np.mean((noisy - clean) ** 2)
        error_denoised = np.mean((denoised - clean) ** 2)
        assert error_denoised < error_noisy, "DWT made signal worse, not better"

    def test_online_mode(self, real_samples):
        """DWT online (push-based) should not crash on real data."""
        dwt = DWTDenoiser()
        for s in real_samples[:100]:
            result = dwt.push(s["h1_re"])
            assert math.isfinite(result)


# ═══════════════════════════════════════════════════════════════════
#  Test 3: Background subtraction removes static paths
# ═══════════════════════════════════════════════════════════════════

class TestBackgroundSubtractor:
    def test_removes_constant_background(self):
        """Static signal should converge to near-zero after subtraction."""
        bg = BackgroundSubtractor(alpha=0.1)
        static_re, static_im = 0.5, 0.3

        results = []
        for _ in range(100):
            d_re, d_im, _, _ = bg.process(static_re, static_im, 0.0, 0.0)
            results.append(abs(d_re) + abs(d_im))

        # After convergence, dynamic component should be near zero
        assert results[-1] < 0.01, "Background subtraction did not converge"

    def test_passes_dynamic_signal(self):
        """Moving component should survive background subtraction."""
        bg = BackgroundSubtractor(alpha=0.02)
        # Static + dynamic
        for i in range(200):
            static = 0.5
            dynamic = 0.3 * math.sin(i * 0.2)
            d_re, _, _, _ = bg.process(static + dynamic, 0.0, 0.0, 0.0)

        # At the end, dynamic component should still be present
        last_d_re, _, _, _ = bg.process(0.5 + 0.3, 0.0, 0.0, 0.0)
        assert abs(last_d_re) > 0.01, "Background subtraction killed dynamic signal"


# ═══════════════════════════════════════════════════════════════════
#  Test 4: DBSCAN clustering separates targets from noise
# ═══════════════════════════════════════════════════════════════════

class TestDBSCANClustering:
    def test_pipeline_clustering(self):
        """Pipeline should cluster tight point groups correctly."""
        pipeline = CSIFilterPipeline(dbscan_eps=0.5, dbscan_min_samples=3)

        # Feed samples that should form a coherent cluster
        for i in range(30):
            pipeline.process_sample(
                h1_re=0.5 + np.random.normal(0, 0.01),
                h1_im=0.3 + np.random.normal(0, 0.01),
                h2_re=0.4 + np.random.normal(0, 0.01),
                h2_im=0.25 + np.random.normal(0, 0.01),
                rssi=-45.0 + np.random.normal(0, 1),
            )

        result = pipeline.last_result
        assert result is not None, "Pipeline should produce a result"
        assert result["confidence"] > 0.2, "Should have reasonable confidence"


# ═══════════════════════════════════════════════════════════════════
#  Test 5: Kalman filter position + velocity convergence
# ═══════════════════════════════════════════════════════════════════

class TestKalmanTracker:
    def test_tracks_linear_motion(self):
        """Kalman should converge on position and velocity for linear motion."""
        kf = KalmanTracker(dt=0.05)

        # Simulate linear motion: x = t, z = 0.5t
        for i in range(100):
            t = i * 0.05
            kf.predict()
            kf.update(t, 0.5 * t)

        state = kf.get_state()
        # Velocity should converge near (1.0, 0.5) per second → (0.05, 0.025) per dt
        assert abs(state["vx"] - 1.0) < 0.3, f"vx={state['vx']}, expected ~1.0"
        assert abs(state["vz"] - 0.5) < 0.2, f"vz={state['vz']}, expected ~0.5"

    def test_handles_missing_updates(self):
        """Kalman should coast (predict-only) without updates."""
        kf = KalmanTracker(dt=0.05)
        kf.update(1.0, 2.0)

        # Predict without update — should not crash
        for _ in range(50):
            kf.predict()

        state = kf.get_state()
        assert math.isfinite(state["x"]) and math.isfinite(state["z"])


# ═══════════════════════════════════════════════════════════════════
#  Test 6: Full pipeline end-to-end with real ESP32 data
# ═══════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_processes_real_data_without_crashing(self, real_samples, pipeline):
        """Full pipeline should process all real ESP32 samples without errors."""
        results = []
        for s in real_samples:
            result = pipeline.process_sample(
                h1_re=s["h1_re"],
                h1_im=s["h1_im"],
                h2_re=s["h2_re"],
                h2_im=s["h2_im"],
                rssi=s["rssi"],
                timestamp=s["timestamp"],
            )
            results.append(result)

        assert len(results) == len(real_samples)

        # All results should have finite values
        for i, r in enumerate(results):
            for key in ["x", "z", "r", "theta", "vx", "vz", "speed"]:
                assert math.isfinite(r[key]), f"Result {i} has non-finite {key}={r[key]}"

    def test_output_schema(self, real_samples, pipeline):
        """Pipeline output should contain all required fields."""
        required_keys = {"x", "z", "r", "theta", "vx", "vz", "speed", "angle", "isMoving", "confidence"}

        for s in real_samples[:10]:
            result = pipeline.process_sample(
                s["h1_re"], s["h1_im"], s["h2_re"], s["h2_im"], s["rssi"]
            )
            assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
            assert isinstance(result["isMoving"], bool)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_reset_clears_state(self, pipeline):
        """Pipeline reset should clear all internal state."""
        pipeline.process_sample(0.5, 0.3, 0.4, 0.2, -45.0)
        pipeline.reset()

        assert pipeline.frame_count == 0
        assert pipeline.last_result is None
        assert len(pipeline.point_buffer) == 0
