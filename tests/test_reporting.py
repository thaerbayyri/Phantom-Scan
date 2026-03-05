"""
Test suite for the Contextual Reporting Module.

Covers:
  - DistanceEstimator: IFFT PDP, parabolic peak, RSSI fusion
  - ActivityClassifier: feature extraction, SVM/rule-based classification
  - SessionReporter: frame accumulation, event detection, report generation

Run: python -m pytest tests/test_reporting.py -v
"""

import os
import sys
import math
import json
import time
import tempfile

import pytest
import numpy as np

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from reporting.distance_estimator import DistanceEstimator
from reporting.activity_classifier import (
    ActivityClassifier,
    compute_acf,
    extract_acf_features,
    extract_motion_features,
)
from reporting.session_reporter import SessionReporter
from reporting.models import (
    ActivityLabel,
    ActivityResult,
    DistanceResult,
    SessionReport,
)


# ═══════════════════════════════════════════════════════════════════
#  Test 1: DistanceEstimator
# ═══════════════════════════════════════════════════════════════════

class TestDistanceEstimator:
    def test_produces_finite_distance(self):
        """Estimator should return finite, positive distance."""
        est = DistanceEstimator()
        result = est.estimate(
            h1_re=0.8, h1_im=0.2, h2_re=0.7, h2_im=-0.3, rssi=-45.0
        )
        assert math.isfinite(result.distance_cm)
        assert result.distance_cm > 0

    def test_distance_changes_with_rssi(self):
        """Closer RSSI (stronger signal) should yield shorter distance."""
        est = DistanceEstimator()
        close = est.estimate(h1_re=0.5, h1_im=0.1, h2_re=0.4, h2_im=0.1, rssi=-30.0)
        far = est.estimate(h1_re=0.5, h1_im=0.1, h2_re=0.4, h2_im=0.1, rssi=-70.0)
        # After smoothing the second estimate should trend larger
        assert far.rssi_distance_m > close.rssi_distance_m

    def test_tof_fields_populated(self):
        """Result should have valid ToF and peak fields."""
        est = DistanceEstimator()
        result = est.estimate(h1_re=0.6, h1_im=0.3, h2_re=0.5, h2_im=-0.2, rssi=-50.0)
        assert result.tof_ns >= 0
        assert result.peak_bin >= 0
        assert 0 <= result.peak_power <= 1.0

    def test_pdp_profile_returned_when_requested(self):
        """PDP profile should be returned when return_pdp=True."""
        est = DistanceEstimator()
        result = est.estimate(
            h1_re=0.5, h1_im=0.2, h2_re=0.4, h2_im=0.1,
            rssi=-50.0, return_pdp=True,
        )
        assert result.pdp_profile is not None
        assert len(result.pdp_profile) == est.n_fft

    def test_pdp_profile_none_by_default(self):
        """PDP profile should be None when not requested."""
        est = DistanceEstimator()
        result = est.estimate(h1_re=0.5, h1_im=0.2, h2_re=0.4, h2_im=0.1, rssi=-50.0)
        assert result.pdp_profile is None

    def test_multiple_samples_smooth(self):
        """Repeated estimates should converge (EMA smoothing)."""
        est = DistanceEstimator(smoothing_alpha=0.5)
        distances = []
        for _ in range(20):
            result = est.estimate(h1_re=0.5, h1_im=0.2, h2_re=0.5, h2_im=0.2, rssi=-50.0)
            distances.append(result.distance_cm)
        # Variance should decrease over time
        first_half_var = np.var(distances[:10])
        second_half_var = np.var(distances[10:])
        assert second_half_var <= first_half_var + 1.0  # Allow small tolerance

    def test_reset_clears_state(self):
        """Reset should clear smoothed state."""
        est = DistanceEstimator()
        est.estimate(h1_re=0.5, h1_im=0.2, h2_re=0.4, h2_im=0.1, rssi=-50.0)
        est.reset()
        assert est._smoothed_distance_cm is None


# ═══════════════════════════════════════════════════════════════════
#  Test 2: Feature Extraction (ACF + Motion)
# ═══════════════════════════════════════════════════════════════════

class TestFeatureExtraction:
    def test_acf_normalized(self):
        """ACF should be normalized: acf[0] = 1.0."""
        signal = np.sin(np.linspace(0, 4 * np.pi, 100))
        acf = compute_acf(signal, max_lag=50)
        assert abs(acf[0] - 1.0) < 1e-6

    def test_acf_detects_periodicity(self):
        """ACF of a periodic signal should show periodicity."""
        sample_rate = 20.0
        t = np.arange(200) / sample_rate
        signal = np.sin(2 * np.pi * 1.5 * t)  # 1.5 Hz
        acf = compute_acf(signal, max_lag=60)
        feats = extract_acf_features(acf, sample_rate)
        assert feats.periodicity_score > 0.3
        assert 0.3 < feats.dominant_period_s < 1.2  # ~0.67s period

    def test_acf_handles_constant_signal(self):
        """ACF of a constant signal should not crash."""
        signal = np.ones(50)
        acf = compute_acf(signal, max_lag=20)
        feats = extract_acf_features(acf)
        assert math.isfinite(feats.periodicity_score)

    def test_motion_features_walking(self):
        """Synthetic walking signal should have gait frequency in range."""
        sample_rate = 20.0
        t = np.arange(100) / sample_rate
        # Simulate walking speed oscillation at ~2 Hz (gait)
        speeds = 1.0 + 0.3 * np.sin(2 * np.pi * 2.0 * t)
        amplitudes = 0.5 + 0.2 * np.sin(2 * np.pi * 2.0 * t)
        feats = extract_motion_features(speeds, amplitudes, sample_rate)
        assert 1.0 <= feats.stride_frequency_hz <= 3.0
        assert feats.avg_speed > 0.5

    def test_motion_features_static(self):
        """Static signal should have near-zero speed features."""
        speeds = np.zeros(50)
        amplitudes = np.ones(50) * 0.01
        feats = extract_motion_features(speeds, amplitudes, 20.0)
        assert feats.avg_speed < 0.01


# ═══════════════════════════════════════════════════════════════════
#  Test 3: ActivityClassifier
# ═══════════════════════════════════════════════════════════════════

class TestActivityClassifier:
    def test_unknown_when_insufficient_data(self):
        """Should return UNKNOWN with < 10 samples."""
        clf = ActivityClassifier()
        for i in range(5):
            clf.push(amplitude=0.5, speed=0.3)
        result = clf.classify()
        assert result.label == ActivityLabel.UNKNOWN

    def test_classifies_walking_pattern(self):
        """Walking pattern should classify as Human - Walking."""
        clf = ActivityClassifier(window_size=100, sample_rate=20.0)
        for i in range(100):
            t = i / 20.0
            # Periodic gait pattern at ~2 Hz
            amp = 0.5 + 0.3 * math.sin(2 * math.pi * 2.0 * t)
            speed = 1.0 + 0.2 * math.sin(2 * math.pi * 2.0 * t)
            clf.push(amplitude=amp, speed=speed)
        result = clf.classify()
        assert result.label in [ActivityLabel.HUMAN_WALKING, ActivityLabel.UNKNOWN]
        assert result.acf_features is not None
        assert result.motion_features is not None

    def test_classifies_sitting_pattern(self):
        """Static pattern should classify as sitting or unknown."""
        clf = ActivityClassifier(window_size=50, sample_rate=20.0)
        for i in range(50):
            clf.push(amplitude=0.01, speed=0.001)
        result = clf.classify()
        assert result.label in [ActivityLabel.HUMAN_SITTING, ActivityLabel.UNKNOWN]

    def test_get_features(self):
        """get_features should return valid dict."""
        clf = ActivityClassifier()
        for i in range(30):
            clf.push(amplitude=0.5 + 0.1 * math.sin(i * 0.2), speed=0.3)
        features = clf.get_features()
        assert "acf" in features
        assert "motion" in features
        assert features["window_size"] == 30

    def test_reset_clears_data(self):
        """Reset should clear all buffers."""
        clf = ActivityClassifier()
        for i in range(20):
            clf.push(amplitude=0.5, speed=0.3)
        clf.reset()
        result = clf.classify()
        assert result.label == ActivityLabel.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
#  Test 4: SessionReporter
# ═══════════════════════════════════════════════════════════════════

class TestSessionReporter:
    def _make_pipeline_result(
        self, x=1.0, z=0.5, speed=0.5, is_moving=True, label="human", ts=None
    ):
        return {
            "x": x, "z": z,
            "speed": speed,
            "isMoving": is_moving,
            "label": label,
            "distanceCm": 200.0,
            "timestamp": ts or time.time(),
        }

    def test_accumulates_frames(self):
        """Reporter should accumulate frames."""
        reporter = SessionReporter()
        reporter.start()
        for i in range(10):
            reporter.add_frame(self._make_pipeline_result(ts=time.time() + i))
        assert reporter._frame_count == 10

    def test_generates_report_with_data(self):
        """Report should have valid structure."""
        reporter = SessionReporter()
        reporter.start()
        for i in range(20):
            dist = DistanceResult(
                distance_cm=200 + i,
                wall_distance_m=5.0,
                tof_ns=10.0,
                peak_bin=5,
                peak_power=0.8,
                rssi_distance_m=2.0,
            )
            reporter.add_frame(
                self._make_pipeline_result(x=1.0 + i * 0.1, ts=time.time() + i),
                distance_result=dist,
            )
        reporter.stop()
        report = reporter.generate_report()
        assert isinstance(report, SessionReport)
        assert report.total_frames == 20
        assert report.spatial_metrics.avg_distance_cm > 0
        assert report.kinematic_data.avg_speed_ms > 0

    def test_detects_motion_events(self):
        """Should detect motion state transitions."""
        reporter = SessionReporter()
        reporter.start()
        # Moving
        for i in range(5):
            reporter.add_frame(
                self._make_pipeline_result(is_moving=True, ts=time.time() + i)
            )
        # Stopped
        for i in range(5):
            reporter.add_frame(
                self._make_pipeline_result(
                    is_moving=False, speed=0.0, ts=time.time() + 5 + i
                )
            )
        events = [e.description for e in reporter._events]
        assert any("started moving" in e for e in events)
        assert any("stopped moving" in e for e in events)

    def test_detects_classification_change(self):
        """Should detect when classification changes."""
        reporter = SessionReporter()
        reporter.start()
        # Human walking
        for i in range(5):
            reporter.add_frame(
                self._make_pipeline_result(label="human", speed=1.0, ts=time.time() + i)
            )
        # Mechanical
        for i in range(5):
            reporter.add_frame(
                self._make_pipeline_result(
                    label="mechanical", speed=0.5, ts=time.time() + 5 + i
                )
            )
        events = [e.description for e in reporter._events]
        assert any("Classification changed" in e for e in events)

    def test_export_json(self):
        """JSON export should create valid file."""
        reporter = SessionReporter()
        reporter.start()
        for i in range(5):
            reporter.add_frame(self._make_pipeline_result(ts=time.time() + i))
        reporter.stop()

        path = os.path.join(tempfile.gettempdir(), "test_report.json")
        reporter.export_json(path)
        assert os.path.exists(path)

        with open(path) as f:
            data = json.load(f)
        assert "session_id" in data
        assert "spatial_metrics" in data
        assert "event_timeline" in data
        os.unlink(path)

    def test_export_pdf_fallback(self):
        """PDF fallback (text) should create a file."""
        reporter = SessionReporter()
        reporter.start()
        for i in range(5):
            reporter.add_frame(self._make_pipeline_result(ts=time.time() + i))
        reporter.stop()

        path = os.path.join(tempfile.gettempdir(), "test_report.pdf")
        reporter.export_pdf(path)
        assert os.path.exists(path)
        os.unlink(path)

    def test_reset_clears_all(self):
        """Reset should clear all session data."""
        reporter = SessionReporter()
        reporter.start()
        for i in range(5):
            reporter.add_frame(self._make_pipeline_result(ts=time.time() + i))
        reporter.reset()
        assert reporter._frame_count == 0
        assert len(reporter._events) == 0
        assert len(reporter._distances) == 0

    def test_auto_starts_on_add_frame(self):
        """Reporter should auto-start when add_frame is called."""
        reporter = SessionReporter()
        reporter.add_frame(self._make_pipeline_result())
        assert reporter._started or reporter._frame_count > 0

    def test_majority_vote_classification(self):
        """Dominant label should win majority vote."""
        reporter = SessionReporter()
        reporter.start()
        # 8 walking, 2 sitting
        for i in range(8):
            reporter.add_frame(
                self._make_pipeline_result(label="human", speed=1.0, ts=time.time() + i)
            )
        for i in range(2):
            reporter.add_frame(
                self._make_pipeline_result(
                    label="human", speed=0.0, is_moving=False, ts=time.time() + 8 + i
                )
            )
        report = reporter.generate_report()
        assert report.target_classification == ActivityLabel.HUMAN_WALKING
