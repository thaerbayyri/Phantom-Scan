"""
ActivityClassifier — Feature extraction + dual-path classification.

Paths:
  1. LSTM-DenseNet (PyTorch) — when torch is available and weights are loaded
  2. SVM fallback (scikit-learn) — lightweight, always available

Extracts features from the Autocorrelation Function (ACF) of the CSI
amplitude signal and motion-induced energy (speed, variance, gait).

Output labels:
  - "Human - Walking"
  - "Human - Falling"
  - "Human - Sitting"
  - "Non-Human/Pet"

POST-SESSION only: session_reporter.py runs this over a finished recording to
label the target's activity; the live moving/still decision is made in
server/lib (MotionGate + fusion), not here.
"""

from __future__ import annotations

import math
import time
import warnings
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np

from .models import ACFFeatures, ActivityLabel, ActivityResult, MotionFeatures


# ─── Constants ───────────────────────────────────────────────────────

LABELS = [
    ActivityLabel.HUMAN_WALKING,
    ActivityLabel.HUMAN_FALLING,
    ActivityLabel.HUMAN_SITTING,
    ActivityLabel.NON_HUMAN,
]

DEFAULT_WINDOW_SIZE = 100     # Samples in classification window
DEFAULT_SAMPLE_RATE = 20.0    # Hz
HUMAN_STRIDE_HZ_RANGE = (0.5, 3.0)  # Typical human gait frequency range


# ─── PyTorch LSTM-DenseNet ───────────────────────────────────────────

_TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    pass


if _TORCH_AVAILABLE:
    class _DenseBlock(nn.Module):
        """Dense block with skip connections (DenseNet-style)."""

        def __init__(self, in_features: int, growth_rate: int = 32, num_layers: int = 3):
            super().__init__()
            self.layers = nn.ModuleList()
            for i in range(num_layers):
                self.layers.append(nn.Sequential(
                    nn.Linear(in_features + i * growth_rate, growth_rate),
                    nn.BatchNorm1d(growth_rate),
                    nn.ReLU(inplace=True),
                    nn.Dropout(0.2),
                ))
            self.out_features = in_features + num_layers * growth_rate

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            features = [x]
            for layer in self.layers:
                out = layer(torch.cat(features, dim=1))
                features.append(out)
            return torch.cat(features, dim=1)

    class LSTMDenseNet(nn.Module):
        """
        LSTM encoder + DenseNet classifier for CSI activity recognition.

        Architecture:
          - 2-layer bidirectional LSTM (encodes temporal patterns)
          - DenseNet-style dense block (captures feature interactions)
          - Softmax classification head
        """

        def __init__(
            self,
            input_size: int = 1,
            hidden_size: int = 64,
            num_lstm_layers: int = 2,
            dense_growth_rate: int = 32,
            dense_num_layers: int = 3,
            num_classes: int = 4,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_lstm_layers,
                batch_first=True,
                bidirectional=True,
                dropout=0.3,
            )
            lstm_out_size = hidden_size * 2  # Bidirectional

            self.dense_block = _DenseBlock(
                lstm_out_size, dense_growth_rate, dense_num_layers
            )

            self.classifier = nn.Sequential(
                nn.Linear(self.dense_block.out_features, 64),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(64, num_classes),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x: (batch, seq_len, input_size)
            lstm_out, _ = self.lstm(x)
            # Take the last time step
            last_hidden = lstm_out[:, -1, :]
            dense_out = self.dense_block(last_hidden)
            logits = self.classifier(dense_out)
            return logits


# ─── SVM Fallback ────────────────────────────────────────────────────

_SKLEARN_AVAILABLE = False
try:
    from sklearn.svm import SVC
    from sklearn.preprocessing import StandardScaler
    _SKLEARN_AVAILABLE = True
except ImportError:
    pass


# ─── Feature Extraction ─────────────────────────────────────────────

def compute_acf(signal: np.ndarray, max_lag: int = 50) -> np.ndarray:
    """
    Compute the normalized Autocorrelation Function (ACF).

    Parameters
    ----------
    signal : np.ndarray
        1D input signal.
    max_lag : int
        Maximum lag to compute.

    Returns
    -------
    np.ndarray
        Normalized ACF values for lags 0..max_lag.
    """
    n = len(signal)
    if n < 2:
        return np.ones(1)

    signal = signal - np.mean(signal)
    var = np.var(signal)
    if var < 1e-12:
        return np.zeros(min(max_lag + 1, n))

    max_lag = min(max_lag, n - 1)
    acf = np.correlate(signal, signal, mode="full")
    acf = acf[n - 1: n + max_lag]  # Positive lags only
    acf = acf / acf[0]             # Normalize
    return acf


def extract_acf_features(
    acf: np.ndarray, sample_rate: float = 20.0
) -> ACFFeatures:
    """Extract periodicity, dominant period, and decay rate from ACF."""
    if len(acf) < 5:
        return ACFFeatures(
            periodicity_score=0.0, dominant_period_s=0.0, decay_rate=0.0
        )

    # Periodicity: find the first peak after the initial decay
    # Look for zero crossings then subsequent peaks
    peaks = []
    for i in range(2, len(acf) - 1):
        if acf[i] > acf[i - 1] and acf[i] > acf[i + 1] and acf[i] > 0.1:
            peaks.append((i, acf[i]))

    if peaks:
        dominant_lag = peaks[0][0]
        periodicity_score = float(peaks[0][1])
        dominant_period_s = dominant_lag / sample_rate
    else:
        periodicity_score = 0.0
        dominant_period_s = 0.0

    # Decay rate: fit exponential to ACF envelope
    positive_acf = acf[acf > 0.01]
    if len(positive_acf) > 3:
        log_acf = np.log(positive_acf + 1e-10)
        x = np.arange(len(log_acf))
        # Linear regression on log domain
        if len(x) > 1:
            slope = (log_acf[-1] - log_acf[0]) / (len(log_acf) - 1)
            decay_rate = -float(slope)
        else:
            decay_rate = 0.0
    else:
        decay_rate = 0.0

    return ACFFeatures(
        periodicity_score=max(0.0, min(1.0, periodicity_score)),
        dominant_period_s=max(0.0, dominant_period_s),
        decay_rate=max(0.0, decay_rate),
    )


def extract_motion_features(
    speeds: np.ndarray,
    amplitudes: np.ndarray,
    sample_rate: float = 20.0,
) -> MotionFeatures:
    """Extract kinematic and gait features from speed/amplitude history."""
    avg_speed = float(np.mean(speeds)) if len(speeds) > 0 else 0.0
    speed_var = float(np.var(speeds)) if len(speeds) > 0 else 0.0
    amp_var = float(np.var(amplitudes)) if len(amplitudes) > 0 else 0.0

    # Gait detection via FFT of speed signal
    stride_freq = 0.0
    regularity = 0.0

    if len(speeds) >= 20:
        speed_centered = speeds - np.mean(speeds)
        fft_mag = np.abs(np.fft.rfft(speed_centered))
        freqs = np.fft.rfftfreq(len(speed_centered), d=1.0 / sample_rate)

        # Search for peaks in human gait range (0.5 - 3.0 Hz)
        mask = (freqs >= HUMAN_STRIDE_HZ_RANGE[0]) & (freqs <= HUMAN_STRIDE_HZ_RANGE[1])
        if np.any(mask):
            gait_fft = fft_mag[mask]
            gait_freqs = freqs[mask]
            peak_idx = int(np.argmax(gait_fft))
            stride_freq = float(gait_freqs[peak_idx])

            # Regularity = peak power / total power in gait band
            total_power = float(np.sum(gait_fft))
            if total_power > 1e-10:
                regularity = float(gait_fft[peak_idx]) / total_power

    return MotionFeatures(
        avg_speed=round(avg_speed, 4),
        speed_variance=round(speed_var, 6),
        amplitude_variance=round(amp_var, 6),
        stride_frequency_hz=round(stride_freq, 3),
        regularity_index=round(min(1.0, regularity), 4),
    )


# ─── ActivityClassifier ─────────────────────────────────────────────

class ActivityClassifier:
    """
    Classifies target activity from CSI amplitude and motion data.

    Dual-path architecture:
      1. LSTM-DenseNet (PyTorch) — if torch available and model loaded
      2. SVM fallback — feature-based, always available

    Usage:
        classifier = ActivityClassifier()
        classifier.push(amplitude=0.5, speed=0.3, timestamp=time.time())
        result = classifier.classify()
    """

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
        model_path: Optional[str] = None,
    ):
        self.window_size = window_size
        self.sample_rate = sample_rate

        # Data buffers
        self._amplitudes: deque = deque(maxlen=window_size)
        self._speeds: deque = deque(maxlen=window_size)
        self._timestamps: deque = deque(maxlen=window_size)

        # LSTM-DenseNet (attempt to load)
        self._lstm_model: Optional[object] = None
        self._use_lstm = False

        if _TORCH_AVAILABLE and model_path:
            self._load_lstm_model(model_path)

        # SVM fallback
        self._svm_model: Optional[object] = None
        self._svm_scaler: Optional[object] = None
        self._init_svm()

    def push(
        self,
        amplitude: float,
        speed: float = 0.0,
        timestamp: Optional[float] = None,
    ) -> None:
        """Accumulate a data point for classification."""
        self._amplitudes.append(amplitude)
        self._speeds.append(speed)
        self._timestamps.append(timestamp or time.time())

    def classify(self) -> ActivityResult:
        """
        Run classification on the current data window.

        Returns
        -------
        ActivityResult
            Label, confidence, probabilities, and extracted features.
        """
        if len(self._amplitudes) < 10:
            return ActivityResult(
                label=ActivityLabel.UNKNOWN,
                confidence=0.0,
                classifier_used="none",
            )

        # Extract features
        amplitudes = np.array(self._amplitudes)
        speeds = np.array(self._speeds)

        acf = compute_acf(amplitudes, max_lag=min(50, len(amplitudes) // 2))
        acf_feats = extract_acf_features(acf, self.sample_rate)
        motion_feats = extract_motion_features(speeds, amplitudes, self.sample_rate)

        # Try LSTM-DenseNet first
        if self._use_lstm and self._lstm_model is not None:
            label, confidence, probs = self._classify_lstm(amplitudes)
            classifier_used = "lstm_densenet"
        else:
            label, confidence, probs = self._classify_svm(
                acf_feats, motion_feats, amplitudes
            )
            classifier_used = "svm"

        return ActivityResult(
            label=label,
            confidence=round(confidence, 4),
            probabilities=probs,
            acf_features=acf_feats,
            motion_features=motion_feats,
            classifier_used=classifier_used,
        )

    def get_features(self) -> Dict:
        """Return the current extracted feature vector as a dict."""
        amplitudes = np.array(self._amplitudes)
        speeds = np.array(self._speeds)

        acf = compute_acf(amplitudes, max_lag=min(50, len(amplitudes) // 2))
        acf_feats = extract_acf_features(acf, self.sample_rate)
        motion_feats = extract_motion_features(speeds, amplitudes, self.sample_rate)

        return {
            "acf": acf_feats.model_dump(),
            "motion": motion_feats.model_dump(),
            "window_size": len(self._amplitudes),
        }

    def reset(self) -> None:
        """Clear all internal state."""
        self._amplitudes.clear()
        self._speeds.clear()
        self._timestamps.clear()

    # ─── LSTM-DenseNet Path ──────────────────────────────────────

    def _load_lstm_model(self, model_path: str) -> None:
        """Load pretrained LSTM-DenseNet weights."""
        if not _TORCH_AVAILABLE:
            return

        try:
            self._lstm_model = LSTMDenseNet(
                input_size=1,
                hidden_size=64,
                num_lstm_layers=2,
                num_classes=len(LABELS),
            )
            state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
            self._lstm_model.load_state_dict(state_dict)
            self._lstm_model.eval()
            self._use_lstm = True
        except Exception as e:
            warnings.warn(f"Failed to load LSTM model: {e}. Falling back to SVM.")
            self._lstm_model = None
            self._use_lstm = False

    def _classify_lstm(
        self, amplitudes: np.ndarray
    ) -> Tuple[ActivityLabel, float, Dict]:
        """Run inference through the LSTM-DenseNet model."""
        if not _TORCH_AVAILABLE or self._lstm_model is None:
            return ActivityLabel.UNKNOWN, 0.0, {}

        # Prepare input: (1, seq_len, 1)
        x = torch.FloatTensor(amplitudes).unsqueeze(0).unsqueeze(-1)

        with torch.no_grad():
            logits = self._lstm_model(x)
            probs = torch.softmax(logits, dim=1).squeeze().numpy()

        pred_idx = int(np.argmax(probs))
        label = LABELS[pred_idx]
        confidence = float(probs[pred_idx])

        prob_dict = {
            lbl.value: round(float(probs[i]), 4)
            for i, lbl in enumerate(LABELS)
        }

        return label, confidence, prob_dict

    # ─── SVM Path ────────────────────────────────────────────────

    def _init_svm(self) -> None:
        """Initialize SVM with default heuristic rules (no training data)."""
        if not _SKLEARN_AVAILABLE:
            self._svm_model = None
            return

        # We create an SVM but since we don't have labeled data yet,
        # we use a rule-based classifier that mimics SVM behavior.
        # When labeled data is available, call retrain_svm(X, y).
        self._svm_model = None
        self._svm_scaler = StandardScaler() if _SKLEARN_AVAILABLE else None

    def retrain_svm(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Retrain the SVM classifier with labeled feature data.

        Parameters
        ----------
        X : np.ndarray
            Feature matrix (n_samples, n_features).
        y : np.ndarray
            Label indices (0-3 corresponding to LABELS).
        """
        if not _SKLEARN_AVAILABLE:
            warnings.warn("scikit-learn not available. Cannot train SVM.")
            return

        self._svm_scaler = StandardScaler()
        X_scaled = self._svm_scaler.fit_transform(X)
        self._svm_model = SVC(kernel="rbf", probability=True, C=10.0, gamma="scale")
        self._svm_model.fit(X_scaled, y)

    def _classify_svm(
        self,
        acf_feats: ACFFeatures,
        motion_feats: MotionFeatures,
        amplitudes: np.ndarray,
    ) -> Tuple[ActivityLabel, float, Dict]:
        """
        Classify using SVM if trained, else use rule-based heuristics.
        """
        # Build feature vector
        feature_vec = np.array([
            acf_feats.periodicity_score,
            acf_feats.dominant_period_s,
            acf_feats.decay_rate,
            motion_feats.avg_speed,
            motion_feats.speed_variance,
            motion_feats.amplitude_variance,
            motion_feats.stride_frequency_hz,
            motion_feats.regularity_index,
        ]).reshape(1, -1)

        # If SVM is trained, use it
        if self._svm_model is not None and self._svm_scaler is not None:
            try:
                X_scaled = self._svm_scaler.transform(feature_vec)
                probs = self._svm_model.predict_proba(X_scaled)[0]
                pred_idx = int(np.argmax(probs))

                prob_dict = {
                    lbl.value: round(float(probs[i]), 4)
                    for i, lbl in enumerate(LABELS)
                }
                return LABELS[pred_idx], float(probs[pred_idx]), prob_dict
            except Exception:
                pass  # Fall through to rules

        # Rule-based heuristic classifier (fallback when no trained model)
        return self._rule_based_classify(acf_feats, motion_feats, amplitudes)

    def _rule_based_classify(
        self,
        acf_feats: ACFFeatures,
        motion_feats: MotionFeatures,
        amplitudes: np.ndarray,
    ) -> Tuple[ActivityLabel, float, Dict]:
        """
        Rule-based activity classification using extracted features.

        Heuristics:
        - Walking: high periodicity (gait), moderate speed, gait frequency ~1-2 Hz
        - Falling: sudden amplitude spike then drop, high speed variance
        - Sitting: low speed, low amplitude variance, no periodicity
        - Non-Human: no gait periodicity, irregular speed pattern
        """
        scores = {label: 0.0 for label in LABELS}

        avg_speed = motion_feats.avg_speed
        speed_var = motion_feats.speed_variance
        amp_var = motion_feats.amplitude_variance
        periodicity = acf_feats.periodicity_score
        stride_f = motion_feats.stride_frequency_hz
        regularity = motion_feats.regularity_index

        # ── Walking indicators ──
        if periodicity > 0.3 and HUMAN_STRIDE_HZ_RANGE[0] <= stride_f <= HUMAN_STRIDE_HZ_RANGE[1]:
            scores[ActivityLabel.HUMAN_WALKING] += 0.4
        if regularity > 0.3:
            scores[ActivityLabel.HUMAN_WALKING] += 0.2
        if 0.3 <= avg_speed <= 2.0:
            scores[ActivityLabel.HUMAN_WALKING] += 0.2

        # ── Falling indicators ──
        if speed_var > 0.5 and amp_var > 0.1:
            scores[ActivityLabel.HUMAN_FALLING] += 0.3
        # Check for sudden amplitude spike
        if len(amplitudes) > 20:
            recent = amplitudes[-10:]
            earlier = amplitudes[-20:-10]
            ratio = np.max(recent) / (np.mean(earlier) + 1e-10)
            if ratio > 5.0:
                scores[ActivityLabel.HUMAN_FALLING] += 0.4

        # ── Sitting indicators ──
        if avg_speed < 0.1:
            scores[ActivityLabel.HUMAN_SITTING] += 0.3
        if amp_var < 0.01:
            scores[ActivityLabel.HUMAN_SITTING] += 0.2
        if periodicity < 0.1:
            scores[ActivityLabel.HUMAN_SITTING] += 0.1

        # ── Non-Human indicators ──
        if periodicity < 0.15 and avg_speed > 0.05 and regularity < 0.15:
            scores[ActivityLabel.NON_HUMAN] += 0.3
        if stride_f > HUMAN_STRIDE_HZ_RANGE[1] or (stride_f > 0 and stride_f < HUMAN_STRIDE_HZ_RANGE[0]):
            scores[ActivityLabel.NON_HUMAN] += 0.2

        # Normalize to probabilities
        total = sum(scores.values())
        if total < 1e-10:
            # No strong signals — default to unknown
            return ActivityLabel.UNKNOWN, 0.0, {}

        probs = {label: score / total for label, score in scores.items()}
        best_label = max(probs, key=probs.get)  # type: ignore
        confidence = probs[best_label]

        prob_dict = {label.value: round(p, 4) for label, p in probs.items()}
        return best_label, round(confidence, 4), prob_dict
