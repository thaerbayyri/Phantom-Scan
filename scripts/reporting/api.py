"""
Phantom Scan — Reporting API (FastAPI)

Runs alongside the main Express dashboard on a separate port (8001).
Provides endpoints for generating session reports, classifying activity,
and estimating distance from CSI data.

Usage:
    python -m scripts.reporting.api
    # or: uvicorn scripts.reporting.api:app --port 8001
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Optional

# Ensure scripts/ is importable
_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .distance_estimator import DistanceEstimator
from .activity_classifier import ActivityClassifier
from .session_reporter import SessionReporter
from .models import (
    ActivityLabel,
    ActivityResult,
    CSISampleInput,
    DistanceResult,
    ReportRequest,
    SessionReport,
)


# ─── App Setup ───────────────────────────────────────────────────────

app = FastAPI(
    title="Phantom Scan — Reporting API",
    description=(
        "Contextual Reporting Module for Wi-Fi CSI-based sensing. "
        "Provides distance estimation, activity classification, "
        "and session report generation."
    ),
    version="1.0.0",
)

# CORS for React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Singleton Instances ─────────────────────────────────────────────

_distance_estimator = DistanceEstimator()
_activity_classifier = ActivityClassifier()
_session_reporter = SessionReporter()
_last_report_path: Optional[str] = None


# ─── Input Models ────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    """Request body for on-demand classification."""
    amplitudes: list[float] = Field(..., description="CSI amplitude window")
    speeds: list[float] = Field(default_factory=list, description="Speed history")
    sample_rate: float = 20.0


class IngestAndReportRequest(BaseModel):
    """Request body for ingesting a sample and adding to session."""
    sample: CSISampleInput
    pipeline_result: Optional[dict] = None


# ─── Endpoints ───────────────────────────────────────────────────────

@app.post("/api/report/generate", response_model=SessionReport)
async def generate_report(request: ReportRequest = ReportRequest()):
    """
    Generate and return the current session report as JSON.

    This compiles all data accumulated via /api/report/ingest or
    add_frame() calls into a structured summary.
    """
    if _session_reporter._frame_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No session data available. Ingest samples first or connect to the dashboard.",
        )

    report = _session_reporter.generate_report()

    # Also save as file for download
    global _last_report_path
    _last_report_path = os.path.join(tempfile.gettempdir(), f"phantom_report_{report.session_id}.json")
    _session_reporter.export_json(_last_report_path)

    if request.format == "pdf":
        pdf_path = _last_report_path.replace(".json", ".pdf")
        _session_reporter.export_pdf(pdf_path)
        _last_report_path = pdf_path

    return report


@app.get("/api/report/download")
async def download_report():
    """Download the last generated report file (JSON or PDF)."""
    if not _last_report_path or not os.path.exists(_last_report_path):
        raise HTTPException(status_code=404, detail="No report generated yet. Call /api/report/generate first.")

    media_type = "application/pdf" if _last_report_path.endswith(".pdf") else "application/json"
    return FileResponse(
        _last_report_path,
        media_type=media_type,
        filename=os.path.basename(_last_report_path),
    )


@app.get("/api/report/status")
async def report_status():
    """Get current session status (frame count, duration, etc.)."""
    reporter = _session_reporter
    duration = 0.0
    if reporter._start_time:
        duration = time.time() - reporter._start_time

    return {
        "session_id": reporter.session_id,
        "frame_count": reporter._frame_count,
        "duration_s": round(duration, 2),
        "is_active": reporter._started,
        "event_count": len(reporter._events),
        "last_label": (
            reporter._last_label.value if reporter._last_label else None
        ),
    }


@app.get("/api/report/events")
async def get_events():
    """Get the event timeline for the current session."""
    events = _session_reporter._dedupe_events()
    return {
        "events": [e.model_dump() for e in events],
        "total": len(events),
    }


@app.post("/api/classify", response_model=ActivityResult)
async def classify_activity(request: ClassifyRequest):
    """
    Classify activity from a CSI amplitude window.

    Accepts a window of amplitude values and optional speed history,
    runs feature extraction + classification, and returns the result.
    """
    classifier = ActivityClassifier(
        window_size=len(request.amplitudes),
        sample_rate=request.sample_rate,
    )

    for i, amp in enumerate(request.amplitudes):
        speed = request.speeds[i] if i < len(request.speeds) else 0.0
        classifier.push(amplitude=amp, speed=speed)

    return classifier.classify()


@app.post("/api/distance", response_model=DistanceResult)
async def estimate_distance(sample: CSISampleInput):
    """
    Estimate distance from a single CSI sample.

    Uses IFFT Power Delay Profile for Time-of-Flight estimation,
    fused with RSSI log-distance model.
    """
    result = _distance_estimator.estimate(
        h1_re=sample.h1.re,
        h1_im=sample.h1.im,
        h2_re=sample.h2.re,
        h2_im=sample.h2.im,
        rssi=sample.rssi,
        return_pdp=False,
    )
    return result


@app.post("/api/report/ingest")
async def ingest_sample(request: IngestAndReportRequest):
    """
    Ingest a CSI sample into the reporting session.

    Runs distance estimation and activity classification,
    then adds the frame to the session reporter.
    """
    sample = request.sample

    # Distance estimation
    distance = _distance_estimator.estimate(
        h1_re=sample.h1.re,
        h1_im=sample.h1.im,
        h2_re=sample.h2.re,
        h2_im=sample.h2.im,
        rssi=sample.rssi,
    )

    # Push to activity classifier
    amp = (sample.h1.re**2 + sample.h1.im**2 + sample.h2.re**2 + sample.h2.im**2) ** 0.5
    speed = 0.0
    if request.pipeline_result:
        speed = request.pipeline_result.get("speed", 0.0)
    _activity_classifier.push(amplitude=amp, speed=speed, timestamp=sample.timestamp)

    # Classify
    activity = _activity_classifier.classify()

    # Build pipeline result (from provided or synthesized)
    pipeline_result = request.pipeline_result or {
        "x": 0.0,
        "z": 0.0,
        "speed": speed,
        "isMoving": speed > 0.05,
        "label": "unknown",
        "distanceCm": distance.distance_cm,
        "timestamp": sample.timestamp,
    }

    _session_reporter.add_frame(pipeline_result, distance, activity)

    return {
        "success": True,
        "frame_count": _session_reporter._frame_count,
        "distance_cm": distance.distance_cm,
        "activity_label": activity.label.value,
    }


@app.post("/api/report/reset")
async def reset_session():
    """Reset all session data and start fresh."""
    _distance_estimator.reset()
    _activity_classifier.reset()
    _session_reporter.reset()
    return {"success": True, "message": "Session reset"}


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  Phantom Scan — Reporting API")
    print("  http://localhost:8001/docs for interactive API docs")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8001)
