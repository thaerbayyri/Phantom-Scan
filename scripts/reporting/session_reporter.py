"""
SessionReporter — Aggregates tracking data and generates structured reports.

Collects per-frame results from the CSI pipeline, distance estimator,
and activity classifier over a session, then compiles a detailed JSON
or PDF report containing:
  - Target classification (dominant label)
  - Spatial metrics (min/max/avg distance, bounding box)
  - Kinematic data (avg/max speed, total distance traveled)
  - Event timeline (timestamped state changes)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
import csv
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

# Allow running as a standalone subprocess (e.g. spawned by Express)
# without needing to be part of a package
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import (  # type: ignore
        ActivityLabel,
        ActivityResult,
        DistanceResult,
        KinematicData,
        SessionEvent,
        SessionReport,
        SpatialMetrics,
    )
else:
    from .models import (
        ActivityLabel,
        ActivityResult,
        DistanceResult,
        KinematicData,
        SessionEvent,
        SessionReport,
        SpatialMetrics,
    )


# Epoch timestamps above this are milliseconds (seconds would be year ~5138+).
_MS_EPOCH_THRESHOLD = 1e11
# A gap longer than this between frames is a dropout, not continuous movement.
MAX_INTEGRATION_STEP_S = 1.0


def _to_seconds(ts: float) -> float:
    """Normalise an epoch timestamp that may be in ms (server) or s (python) to seconds."""
    ts = float(ts)
    return ts / 1000.0 if ts > _MS_EPOCH_THRESHOLD else ts


class SessionReporter:
    """
    Aggregates CSI processing results over a session and generates reports.

    Usage:
        reporter = SessionReporter()
        reporter.start()

        for sample in stream:
            # ... process sample ...
            reporter.add_frame(pipeline_result, distance_result, activity_result)

        report = reporter.generate_report()
        reporter.export_json("report.json")
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self._started = False
        self._start_time: float = 0.0
        self._end_time: float = 0.0

        # Frame data accumulation
        self._distances: List[float] = []
        self._speeds: List[float] = []
        self._positions_x: List[float] = []
        self._positions_z: List[float] = []
        self._labels: List[ActivityLabel] = []
        self._timestamps: List[float] = []
        self._doppler_shifts: List[float] = []

        # Event timeline
        self._events: List[SessionEvent] = []
        self._last_label: Optional[ActivityLabel] = None
        self._last_moving: Optional[bool] = None
        self._frame_count = 0

    # ─── Session Lifecycle ───────────────────────────────────────

    def start(self) -> None:
        """Start a new session (or restart if already started)."""
        self.reset()
        self._started = True
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop the current session."""
        if self._started:
            self._end_time = time.time()
            self._started = False

    def reset(self) -> None:
        """Clear all session data."""
        self.session_id = str(uuid.uuid4())[:12]
        self._started = False
        self._start_time = 0.0
        self._end_time = 0.0
        self._distances.clear()
        self._speeds.clear()
        self._positions_x.clear()
        self._positions_z.clear()
        self._labels.clear()
        self._timestamps.clear()
        self._doppler_shifts.clear()
        self._events.clear()
        self._last_label = None
        self._last_moving = None
        self._frame_count = 0

    # ─── Data Ingestion ──────────────────────────────────────────

    def add_frame(
        self,
        pipeline_result: Dict[str, Any],
        distance_result: Optional[DistanceResult] = None,
        activity_result: Optional[ActivityResult] = None,
    ) -> None:
        """
        Record a single processed frame.

        Parameters
        ----------
        pipeline_result : dict
            Output from CSIFilterPipeline.process_sample() containing
            x, z, speed, isMoving, label, etc.
        distance_result : DistanceResult, optional
            Output from DistanceEstimator.estimate().
        activity_result : ActivityResult, optional
            Output from ActivityClassifier.classify().
        """
        if not self._started:
            self.start()

        ts = _to_seconds(pipeline_result.get("timestamp", time.time()))
        if "timestamp" in pipeline_result and not self._timestamps:
            # Replayed/recorded frames: the session clock is the DATA clock,
            # not the wall time the reporter happened to be started at.
            self._start_time = ts
        self._timestamps.append(ts)
        self._frame_count += 1

        # Position
        x = pipeline_result.get("x", 0.0)
        z = pipeline_result.get("z", 0.0)
        self._positions_x.append(x)
        self._positions_z.append(z)

        # Speed
        speed = pipeline_result.get("speed", 0.0)
        self._speeds.append(speed)

        # Distance
        if distance_result:
            self._distances.append(distance_result.distance_cm)
        elif "distanceCm" in pipeline_result:
            self._distances.append(pipeline_result["distanceCm"])

        # Activity label
        if activity_result and activity_result.label != ActivityLabel.UNKNOWN:
            label = activity_result.label
        elif "label" in pipeline_result:
            # Map micro-doppler label to activity label
            label = self._map_pipeline_label(
                pipeline_result["label"],
                pipeline_result.get("isMoving", False),
                speed,
            )
        else:
            label = ActivityLabel.UNKNOWN
        self._labels.append(label)

        # Check for motion state transitions
        is_moving = pipeline_result.get("isMoving", False)
        self._detect_motion_event(ts, is_moving)

        # Check for classification changes
        self._detect_label_event(ts, label, distance_result)

        # Check for fall detection
        if label == ActivityLabel.HUMAN_FALLING:
            dist_str = ""
            if distance_result:
                dist_str = f" at {distance_result.distance_cm / 100:.1f} meters"
            self.add_event(ts, f"Object classified as 'Human - Falling'{dist_str}")

    def add_event(self, timestamp: float, description: str) -> None:
        """Manually log a custom event."""
        elapsed = timestamp - self._start_time if self._start_time else 0.0
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        self._events.append(SessionEvent(
            timestamp=timestamp,
            elapsed_s=round(elapsed, 2),
            elapsed_formatted=f"{minutes:02d}:{seconds:02d}",
            description=description,
            distance_cm=(
                self._distances[-1] if self._distances else None
            ),
        ))

    # ─── Report Generation ───────────────────────────────────────

    def generate_report(self) -> SessionReport:
        """
        Compile all accumulated data into a structured SessionReport.

        Returns
        -------
        SessionReport
            Complete session report with classification, metrics, and timeline.
        """
        now = time.time()
        end_time = self._end_time if self._end_time else (self._timestamps[-1] if self._timestamps else now)
        start_time = self._start_time if self._start_time else now
        duration = max(0.0, end_time - start_time)

        # Target classification: majority vote
        target_class, class_conf, class_breakdown = self._compute_classification()

        # Spatial metrics
        spatial = self._compute_spatial_metrics()

        # Kinematic data
        kinematic = self._compute_kinematic_data(duration)

        # Deduplicate events
        unique_events = self._dedupe_events()

        return SessionReport(
            session_id=self.session_id,
            start_time=start_time,
            end_time=end_time,
            duration_s=round(duration, 2),
            total_frames=self._frame_count,
            target_classification=target_class,
            classification_confidence=round(class_conf, 4),
            classification_breakdown=class_breakdown,
            spatial_metrics=spatial,
            kinematic_data=kinematic,
            event_timeline=unique_events,
        )

    def export_json(self, filepath: str) -> str:
        """Export the report as a JSON file. Returns the filepath."""
        report = self.generate_report()
        data = report.model_dump()
        # Convert enums to strings for JSON
        data["target_classification"] = data["target_classification"].value if hasattr(data["target_classification"], "value") else str(data["target_classification"])
        for event in data.get("event_timeline", []):
            if event.get("label") and hasattr(event["label"], "value"):
                event["label"] = event["label"].value

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    def export_pdf(self, filepath: str) -> str:
        """
        Export the report as a PDF file. Returns the filepath.

        Uses reportlab if available; otherwise falls back to a text file.
        """
        report = self.generate_report()

        try:
            return self._export_pdf_reportlab(filepath, report)
        except ImportError:
            # Fallback: write as formatted text with .pdf extension
            return self._export_pdf_text_fallback(filepath, report)

    # ─── Private: Event Detection ────────────────────────────────

    def _detect_motion_event(self, ts: float, is_moving: bool) -> None:
        """Detect motion start/stop transitions."""
        if self._last_moving is None:
            self._last_moving = is_moving
            if is_moving:
                self.add_event(ts, "Object started moving")
            return

        if is_moving and not self._last_moving:
            self.add_event(ts, "Object started moving")
        elif not is_moving and self._last_moving:
            self.add_event(ts, "Object stopped moving")

        self._last_moving = is_moving

    def _detect_label_event(
        self,
        ts: float,
        label: ActivityLabel,
        distance_result: Optional[DistanceResult] = None,
    ) -> None:
        """Detect classification state changes."""
        if label == ActivityLabel.UNKNOWN:
            return

        if self._last_label is not None and label != self._last_label:
            dist_str = ""
            if distance_result:
                dist_str = f" at {distance_result.distance_cm / 100:.1f} meters"
            self.add_event(
                ts,
                f"Classification changed: '{self._last_label.value}' → '{label.value}'{dist_str}",
            )

        self._last_label = label

    @staticmethod
    def _map_pipeline_label(
        label_str: str, is_moving: bool, speed: float
    ) -> ActivityLabel:
        """Map micro-doppler label strings to ActivityLabel enum."""
        if label_str == "human":
            if speed > 0.3:
                return ActivityLabel.HUMAN_WALKING
            elif is_moving:
                return ActivityLabel.HUMAN_WALKING
            else:
                return ActivityLabel.HUMAN_SITTING
        elif label_str == "mechanical":
            return ActivityLabel.NON_HUMAN
        else:
            return ActivityLabel.UNKNOWN

    # ─── Private: Report Computation ─────────────────────────────

    def _compute_classification(self):
        """Majority vote classification from all frame labels."""
        valid_labels = [l for l in self._labels if l != ActivityLabel.UNKNOWN]
        if not valid_labels:
            return ActivityLabel.UNKNOWN, 0.0, {}

        counter = Counter(valid_labels)
        total = len(valid_labels)
        most_common = counter.most_common(1)[0]
        dominant_label = most_common[0]
        confidence = most_common[1] / total

        breakdown = {
            label.value: count for label, count in counter.items()
        }
        return dominant_label, confidence, breakdown

    def _compute_spatial_metrics(self) -> SpatialMetrics:
        """Compute spatial statistics from accumulated distance/position data."""
        if not self._distances:
            return SpatialMetrics(
                min_distance_cm=0.0,
                max_distance_cm=0.0,
                avg_distance_cm=0.0,
            )

        distances = np.array(self._distances)
        positions_x = np.array(self._positions_x) if self._positions_x else np.array([0.0])
        positions_z = np.array(self._positions_z) if self._positions_z else np.array([0.0])

        bbox = {
            "x_min": round(float(np.min(positions_x)), 3),
            "x_max": round(float(np.max(positions_x)), 3),
            "z_min": round(float(np.min(positions_z)), 3),
            "z_max": round(float(np.max(positions_z)), 3),
        }

        return SpatialMetrics(
            min_distance_cm=round(float(np.min(distances)), 1),
            max_distance_cm=round(float(np.max(distances)), 1),
            avg_distance_cm=round(float(np.mean(distances)), 1),
            movement_bbox=bbox,
        )

    def _compute_kinematic_data(self, duration_s: float) -> KinematicData:
        """Compute kinematic statistics from speed data."""
        if not self._speeds:
            return KinematicData(
                avg_speed_ms=0.0,
                max_speed_ms=0.0,
                total_distance_m=0.0,
            )

        speeds = np.array(self._speeds)
        avg_speed = float(np.mean(speeds))
        max_speed = float(np.max(speeds))

        # Total distance: integrate speed over time. Timestamps are already
        # normalised to seconds at ingestion (_to_seconds). A recording gap
        # (node dropout) must not be integrated as continuous travel, so each
        # step is capped at MAX_INTEGRATION_STEP_S.
        if len(self._timestamps) > 1:
            dt_array = np.clip(np.abs(np.diff(self._timestamps)), 0.0, MAX_INTEGRATION_STEP_S)
            total_dist = float(np.sum(speeds[1:len(dt_array) + 1] * dt_array[:len(speeds) - 1]))
        else:
            total_dist = avg_speed * duration_s

        # Doppler shift (proportional to radial speed)
        avg_doppler = 0.0
        if self._doppler_shifts:
            avg_doppler = float(np.mean(self._doppler_shifts))

        return KinematicData(
            avg_speed_ms=round(avg_speed, 4),
            max_speed_ms=round(max_speed, 4),
            total_distance_m=round(total_dist, 3),
            avg_doppler_hz=round(avg_doppler, 2),
        )

    def _dedupe_events(self) -> List[SessionEvent]:
        """Remove duplicate consecutive events with same description."""
        if not self._events:
            return []

        unique = [self._events[0]]
        for event in self._events[1:]:
            if event.description != unique[-1].description:
                unique.append(event)
            elif event.timestamp - unique[-1].timestamp > 2.0:
                # Allow same description if > 2 seconds apart
                unique.append(event)
        return unique

    # ─── Private: PDF Export ─────────────────────────────────────

    def _export_pdf_reportlab(self, filepath: str, report: SessionReport) -> str:
        """Generate PDF using reportlab."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        y = height - 30 * mm

        def write_line(text: str, size: int = 10, bold: bool = False):
            nonlocal y
            font = "Helvetica-Bold" if bold else "Helvetica"
            c.setFont(font, size)
            c.drawString(20 * mm, y, text)
            y -= (size + 4)
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm

        # Title
        write_line("PHANTOM SCAN — SESSION REPORT", 18, bold=True)
        write_line("")
        write_line(f"Session ID: {report.session_id}", 11)
        write_line(f"Duration: {report.duration_s:.1f} seconds  |  Frames: {report.total_frames}", 11)
        write_line("")

        # Classification
        write_line("TARGET CLASSIFICATION", 14, bold=True)
        write_line(f"  Dominant Label: {report.target_classification.value}", 11)
        write_line(f"  Confidence: {report.classification_confidence:.1%}", 11)
        for label, count in report.classification_breakdown.items():
            write_line(f"    {label}: {count} frames", 10)
        write_line("")

        # Spatial
        write_line("SPATIAL METRICS", 14, bold=True)
        sm = report.spatial_metrics
        write_line(f"  Min Distance: {sm.min_distance_cm:.1f} cm", 11)
        write_line(f"  Max Distance: {sm.max_distance_cm:.1f} cm", 11)
        write_line(f"  Avg Distance: {sm.avg_distance_cm:.1f} cm", 11)
        if sm.movement_bbox:
            bb = sm.movement_bbox
            write_line(
                f"  Bounding Box: X=[{bb.get('x_min', 0):.2f}, {bb.get('x_max', 0):.2f}]  "
                f"Z=[{bb.get('z_min', 0):.2f}, {bb.get('z_max', 0):.2f}]", 10
            )
            write_line(
                "  NOT A ROOM POSITION: X is a 1-D on-axis projection onto the "
                "3 m two-node baseline; Z is architecturally fixed at 0 in "
                "fused two-node mode (both node anchors share z=0), not an "
                "independently measured second spatial dimension.", 8
            )
        write_line("")

        # Kinematic
        write_line("KINEMATIC DATA", 14, bold=True)
        kd = report.kinematic_data
        write_line(f"  Avg Speed: {kd.avg_speed_ms:.3f} m/s", 11)
        write_line(f"  Max Speed: {kd.max_speed_ms:.3f} m/s", 11)
        write_line(f"  Total Distance: {kd.total_distance_m:.2f} m", 11)
        write_line("")

        # Timeline
        if report.event_timeline:
            write_line("EVENT TIMELINE", 14, bold=True)
            for evt in report.event_timeline:
                write_line(f"  [{evt.elapsed_formatted}] {evt.description}", 10)

        c.save()
        return filepath

    def _export_pdf_text_fallback(self, filepath: str, report: SessionReport) -> str:
        """Fallback: write formatted text report when reportlab is unavailable."""
        lines = []
        lines.append("=" * 60)
        lines.append("  PHANTOM SCAN — SESSION REPORT")
        lines.append("=" * 60)
        lines.append(f"Session ID:  {report.session_id}")
        lines.append(f"Duration:    {report.duration_s:.1f}s  |  Frames: {report.total_frames}")
        lines.append("")
        lines.append("── TARGET CLASSIFICATION ──")
        lines.append(f"  Label:      {report.target_classification.value}")
        lines.append(f"  Confidence: {report.classification_confidence:.1%}")
        lines.append("")
        lines.append("── SPATIAL METRICS ──")
        sm = report.spatial_metrics
        lines.append(f"  Min Distance: {sm.min_distance_cm:.1f} cm")
        lines.append(f"  Max Distance: {sm.max_distance_cm:.1f} cm")
        lines.append(f"  Avg Distance: {sm.avg_distance_cm:.1f} cm")
        lines.append("")
        lines.append("── KINEMATIC DATA ──")
        kd = report.kinematic_data
        lines.append(f"  Avg Speed: {kd.avg_speed_ms:.3f} m/s")
        lines.append(f"  Max Speed: {kd.max_speed_ms:.3f} m/s")
        lines.append(f"  Total Distance: {kd.total_distance_m:.2f} m")
        lines.append("")
        if report.event_timeline:
            lines.append("── EVENT TIMELINE ──")
            for evt in report.event_timeline:
                lines.append(f"  [{evt.elapsed_formatted}] {evt.description}")
        lines.append("")
        lines.append("=" * 60)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filepath

def compile_case_report(csv_path: str) -> None:
    import os
    print(f"[SessionReporter] Compiling report for {csv_path}")
    if not os.path.exists(csv_path):
        print(f"Error: File not found {csv_path}")
        return
        
    case_name = os.path.basename(csv_path).replace(".csv", "")
    reporter = SessionReporter(session_id=case_name)
    reporter.start()
    
    from scripts.reporting.models import ActivityResult, ActivityLabel
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            try:
                ts = float(row.get("timestamp", 0))
                x = float(row.get("x_disp_m", row.get("x", 0)) or 0.0)
                z = float(row.get("z_disp_m", row.get("z", 0)) or 0.0)
                speed = float(row.get("speed", 0) or 0.0)
                label_str = row.get("label", "unknown")
                distance_cm = float(row.get("distance_cm", 0) or 0.0)
                
                pipeline_res = {
                    "timestamp": ts,
                    "x": x,
                    "z": z,
                    "speed": speed,
                    "isMoving": speed > 0.05,
                    "distanceCm": distance_cm,
                }
                
                try:
                    mapped_label = ActivityLabel(label_str)
                except ValueError:
                    mapped_label = ActivityLabel.UNKNOWN
                    
                activity_res = ActivityResult(
                    label=mapped_label,
                    human_prob=1.0 if "human" in label_str.lower() else 0.0,
                    mechanical_prob=1.0 if "mechanical" in label_str.lower() else 0.0,
                    snr=10.0
                )
                
                reporter.add_frame(pipeline_res, None, activity_res)
            except Exception as e:
                print(f"[SessionReporter] Row error: {e}")
                continue
                
    reporter.stop()
    json_path = csv_path.replace(".csv", ".json")
    reporter.export_json(json_path)
    
    pdf_path = csv_path.replace(".csv", ".pdf")
    reporter.export_pdf(pdf_path)
    
    print(f"[SessionReporter] Report saved to {json_path}")
    print(f"[SessionReporter] PDF Report saved to {pdf_path}")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Ensure scripts/ is importable from the project root
    _project_root = str(Path(__file__).resolve().parent.parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
        
    if len(sys.argv) > 1:
        compile_case_report(sys.argv[1])
    else:
        print("Usage: python session_reporter.py <path_to_csv>")

