"""
Pydantic data models for the Contextual Reporting Module.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    class _FieldSpec:
        def __init__(self, default=None, default_factory=None):
            self.default = default
            self.default_factory = default_factory

        def resolve(self):
            if self.default_factory is not None:
                return self.default_factory()
            return self.default

    def Field(default=None, default_factory=None, **_kwargs):
        if default_factory is not None:
            return _FieldSpec(default=default, default_factory=default_factory)
        return default

    class BaseModel:
        def __init__(self, **data):
            annotations = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for name in annotations:
                if name in data:
                    value = data[name]
                else:
                    default = getattr(self.__class__, name, None)
                    value = default.resolve() if isinstance(default, _FieldSpec) else default
                setattr(self, name, value)

        def model_dump(self):
            result = {}
            annotations = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for name in annotations:
                value = getattr(self, name)
                if isinstance(value, BaseModel):
                    result[name] = value.model_dump()
                elif isinstance(value, list):
                    result[name] = [item.model_dump() if isinstance(item, BaseModel) else item for item in value]
                else:
                    result[name] = value
            return result


# ─── Enums ───────────────────────────────────────────────────────────

class ActivityLabel(str, Enum):
    HUMAN_WALKING = "Human - Walking"
    HUMAN_FALLING = "Human - Falling"
    HUMAN_SITTING = "Human - Sitting"
    NON_HUMAN = "Non-Human/Pet"
    UNKNOWN = "Unknown"


# ─── Input Models ────────────────────────────────────────────────────

class ComplexPair(BaseModel):
    re: float
    im: float


class CSISampleInput(BaseModel):
    timestamp: float
    h1: ComplexPair
    h2: ComplexPair
    rssi: float = -50.0
    subcarrier_index: int = 0


class ReportRequest(BaseModel):
    """Parameters for report generation."""
    format: str = Field("json", description="Output format: 'json' or 'pdf'")
    include_pdp_raw: bool = Field(False, description="Include raw PDP arrays in report")
    include_feature_vectors: bool = Field(False, description="Include raw feature vectors")


# ─── Result Models ───────────────────────────────────────────────────

class DistanceResult(BaseModel):
    distance_cm: float = Field(..., description="Estimated distance in centimeters")
    wall_distance_m: float = Field(..., description="First wall reflection distance in meters")
    tof_ns: float = Field(..., description="Time-of-Flight in nanoseconds")
    peak_bin: int = Field(..., description="PDP peak bin index")
    peak_power: float = Field(..., description="PDP peak power (normalized)")
    rssi_distance_m: float = Field(..., description="RSSI log-distance estimate in meters")
    pdp_profile: Optional[List[float]] = Field(
        None, description="Raw PDP magnitude profile (optional)"
    )


class ACFFeatures(BaseModel):
    periodicity_score: float = Field(..., description="Autocorrelation periodicity (0-1)")
    dominant_period_s: float = Field(..., description="Dominant period in seconds")
    decay_rate: float = Field(..., description="ACF envelope decay rate")


class MotionFeatures(BaseModel):
    avg_speed: float
    speed_variance: float
    amplitude_variance: float
    stride_frequency_hz: float = Field(0.0, description="Detected gait stride frequency")
    regularity_index: float = Field(0.0, description="Gait regularity (0-1)")


class ActivityResult(BaseModel):
    label: ActivityLabel = ActivityLabel.UNKNOWN
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    probabilities: dict = Field(
        default_factory=dict,
        description="Per-class probabilities",
    )
    acf_features: Optional[ACFFeatures] = None
    motion_features: Optional[MotionFeatures] = None
    classifier_used: str = Field("svm", description="'lstm_densenet' or 'svm'")


# ─── Session Event ───────────────────────────────────────────────────

class SessionEvent(BaseModel):
    timestamp: float
    elapsed_s: float = Field(..., description="Seconds since session start")
    elapsed_formatted: str = Field("", description="Formatted MM:SS string")
    description: str
    label: Optional[ActivityLabel] = None
    distance_cm: Optional[float] = None


# ─── Session Report ──────────────────────────────────────────────────

class SpatialMetrics(BaseModel):
    min_distance_cm: float
    max_distance_cm: float
    avg_distance_cm: float
    movement_bbox: dict = Field(
        default_factory=dict,
        description="Bounding box: {x_min, x_max, z_min, z_max}",
    )


class KinematicData(BaseModel):
    avg_speed_ms: float = Field(..., description="Average speed in m/s")
    max_speed_ms: float = Field(..., description="Maximum speed in m/s")
    total_distance_m: float = Field(
        ..., description="Total distance traveled in meters"
    )
    avg_doppler_hz: float = Field(0.0, description="Average Doppler shift in Hz")


class SessionReport(BaseModel):
    """Full session report compiled by SessionReporter."""

    # Metadata
    session_id: str
    start_time: float
    end_time: float
    duration_s: float
    total_frames: int

    # Core analysis
    target_classification: ActivityLabel
    classification_confidence: float
    classification_breakdown: dict = Field(
        default_factory=dict,
        description="Per-label frame counts",
    )

    # Metrics
    spatial_metrics: SpatialMetrics
    kinematic_data: KinematicData

    # Timeline
    event_timeline: List[SessionEvent] = Field(default_factory=list)

    # Optional raw data
    feature_summary: Optional[dict] = None
