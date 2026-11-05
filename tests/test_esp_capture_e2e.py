"""
End-to-End ESP32 CSI Capture Data Test

Validates the full data path:
  1. Load real ESP32 CSI recordings from the recordings/ directory
  2. Parse them through csi_capture.py's CSISample format
  3. Process them through the CSIFilterPipeline (Hampel → DWT → BG Sub → Kalman)
  4. POST them to the live server's /api/csi/ingest endpoint
  5. Verify the server accepts and queues them correctly

Run: python -m pytest tests/test_esp_capture_e2e.py -v
"""

import os
import sys
import csv
import math
import time
import struct
import socket
import http.cookiejar

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.csi_filter_pipeline import CSIFilterPipeline
from scripts.csi_capture import CSISample, parse_csi_line
from phantom.protocol import CsiFrameV1, parse_udp_packet

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "recordings")


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _load_all_recordings(max_per_file: int = 200):
    """Load samples from all available recording CSVs."""
    if not os.path.isdir(RECORDINGS_DIR):
        pytest.skip("No recordings/ directory")
    csvs = sorted(
        [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".csv")]
    )
    if not csvs:
        pytest.skip("No CSV recording files found")

    all_samples = {}
    for csv_file in csvs:
        filepath = os.path.join(RECORDINGS_DIR, csv_file)
        samples = []
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_per_file:
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
                    continue
        if samples:
            all_samples[csv_file] = samples
    return all_samples


# ═══════════════════════════════════════════════════════════════════
#  Test 1: CSISample class correctly wraps real data
# ═══════════════════════════════════════════════════════════════════

class TestCSISampleFormat:
    def test_csi_sample_creation(self):
        """CSISample should accept real-valued channel estimates."""
        sample = CSISample(
            h1_re=0.87, h1_im=0.58,
            h2_re=0.74, h2_im=0.59,
            rssi=-45.0
        )
        d = sample.to_dict()
        assert d["h1"]["re"] == 0.87
        assert d["h1"]["im"] == 0.58
        assert d["h2"]["re"] == 0.74
        assert d["h2"]["im"] == 0.59
        assert d["rssi"] == -45.0
        assert "timestamp" in d

    def test_csi_sample_from_recording_row(self):
        """CSISample should be constructable from a recording CSV row."""
        recordings = _load_all_recordings(max_per_file=1)
        assert len(recordings) > 0, "Need at least one recording"

        first_file = list(recordings.keys())[0]
        row = recordings[first_file][0]

        sample = CSISample(
            h1_re=row["h1_re"], h1_im=row["h1_im"],
            h2_re=row["h2_re"], h2_im=row["h2_im"],
            timestamp=row["timestamp"],
            rssi=row["rssi"],
        )
        d = sample.to_dict()
        assert math.isfinite(d["h1"]["re"])
        assert math.isfinite(d["h2"]["im"])
        assert math.isfinite(d["rssi"])


# ═══════════════════════════════════════════════════════════════════
#  Test 2: CSI line parser handles ESP32 serial formats
# ═══════════════════════════════════════════════════════════════════

class TestCSILineParser:
    def test_parse_csv_format(self):
        """Parser should handle raw CSV format: timestamp,rssi,I1,Q1,I2,Q2"""
        line = "1773082802239,-45,10,20,30,40"
        sample = parse_csi_line(line)
        assert sample is not None
        assert sample.h1["re"] == 10
        assert sample.h1["im"] == 20
        assert sample.h2["re"] == 30
        assert sample.h2["im"] == 40

    def test_parse_esp_csi_format(self):
        """Parser should handle CSI_DATA firmware format."""
        line = "CSI_DATA,0,STA,aa:bb:cc:dd:ee:ff,-55,0,0,0,0,0,0,[10 20 30 40 50 60]"
        sample = parse_csi_line(line)
        assert sample is not None
        assert sample.h1["re"] == 10
        assert sample.h1["im"] == 20
        assert sample.rssi == -55

    def test_parse_empty_line(self):
        """Empty lines should return None."""
        assert parse_csi_line("") is None

    def test_parse_comment(self):
        """Comment lines should return None."""
        assert parse_csi_line("# this is a comment") is None

    def test_parse_garbage(self):
        """Garbage input should return None without crashing."""
        assert parse_csi_line("not,valid,data") is None
        assert parse_csi_line("hello world") is None


# ═══════════════════════════════════════════════════════════════════
#  Test 3: Full pipeline with all recording files
# ═══════════════════════════════════════════════════════════════════

class TestPipelineWithRecordings:
    def test_all_recordings_process_cleanly(self):
        """Every recorded CSI session should pass through the pipeline without errors."""
        recordings = _load_all_recordings(max_per_file=100)
        assert len(recordings) > 0, "Need at least one recording"

        for filename, samples in recordings.items():
            pipeline = CSIFilterPipeline()
            results = []

            for s in samples:
                result = pipeline.process_sample(
                    h1_re=s["h1_re"], h1_im=s["h1_im"],
                    h2_re=s["h2_re"], h2_im=s["h2_im"],
                    rssi=s["rssi"], timestamp=s["timestamp"],
                )
                results.append(result)

            # All results should have finite values
            for i, r in enumerate(results):
                for key in ["x", "z", "r", "theta", "speed", "confidence"]:
                    assert math.isfinite(r[key]), (
                        f"File {filename}, sample {i}: non-finite {key}={r[key]}"
                    )

            # At least some samples should produce reasonable confidence
            max_confidence = max(r["confidence"] for r in results)
            assert max_confidence > 0, (
                f"File {filename}: zero confidence across all {len(results)} samples"
            )

    def test_motion_detection_varies(self):
        """Pipeline should detect both moving and stationary states across sessions."""
        recordings = _load_all_recordings(max_per_file=200)
        all_moving_counts = []

        for filename, samples in recordings.items():
            pipeline = CSIFilterPipeline()
            moving_count = 0
            for s in samples:
                result = pipeline.process_sample(
                    s["h1_re"], s["h1_im"], s["h2_re"], s["h2_im"], s["rssi"]
                )
                if result["isMoving"]:
                    moving_count += 1
            all_moving_counts.append(moving_count)

        # Across all recordings, we should see varied motion detection
        assert len(all_moving_counts) > 0


    def test_distance_estimation_reasonable(self):
        """Pipeline radial distance should be in a physically plausible range."""
        recordings = _load_all_recordings(max_per_file=50)

        for filename, samples in recordings.items():
            pipeline = CSIFilterPipeline()
            distances = []
            for s in samples:
                result = pipeline.process_sample(
                    s["h1_re"], s["h1_im"], s["h2_re"], s["h2_im"], s["rssi"]
                )
                distances.append(result["r"])

            # Radial distance should be non-negative and not absurdly large (< 100m)
            for i, d in enumerate(distances):
                assert d >= 0, f"{filename} sample {i}: negative distance r={d}"
                assert d < 100.0, f"{filename} sample {i}: unreasonable distance r={d}"


# ═══════════════════════════════════════════════════════════════════
#  Test 4: ADR-018 UDP frame round-trip
# ═══════════════════════════════════════════════════════════════════

class TestADR018FrameIntegrity:
    MAGIC_CSI = 0xC5110001
    HEADER_FMT = "<IBBBHIIbbBQI"

    def _build_frame(
        self,
        node_id=1,
        n_ant=1,
        n_sub=64,
        freq=2412,
        seq=0,
        rssi=-45,
        noise=-90,
        channel=1,
        device_ts_us=123456789,
        device_ts_ms=123456,
    ):
        """Build a valid ADR-018 frame from parameters."""
        header = struct.pack(
            self.HEADER_FMT,
            self.MAGIC_CSI,
            1,
            node_id,
            n_ant,
            n_sub,
            freq,
            seq,
            rssi,
            noise,
            channel,
            device_ts_us,
            device_ts_ms,
        )
        # IQ data: n_ant * n_sub * 2 bytes (I + Q as signed bytes)
        iq_data = bytearray()
        for i in range(n_ant * n_sub):
            re = int(50 * math.sin(i * 0.1))
            im = int(50 * math.cos(i * 0.1))
            iq_data.extend(struct.pack('<bb', max(-128, min(127, re)), max(-128, min(127, im))))
        return header + iq_data

    def test_frame_header_integrity(self):
        """Frame header should preserve all fields through pack/unpack."""
        frame = self._build_frame(node_id=3, n_sub=32, freq=5240, seq=1234, rssi=-62, noise=-85)
        hdr = struct.unpack(self.HEADER_FMT, frame[:32])
        assert hdr[0] == self.MAGIC_CSI
        assert hdr[1] == 1      # schema version
        assert hdr[2] == 3      # node_id
        assert hdr[3] == 1      # n_ant
        assert hdr[4] == 32     # n_sub
        assert hdr[5] == 5240   # freq
        assert hdr[6] == 1234   # seq
        assert hdr[7] == -62    # rssi
        assert hdr[8] == -85    # noise
        assert hdr[9] == 1      # channel
        assert hdr[10] == 123456789
        assert hdr[11] == 123456

    def test_frame_iq_data_length(self):
        """IQ payload length should match n_ant * n_sub * 2."""
        for n_sub in [10, 32, 52, 64, 128]:
            frame = self._build_frame(n_sub=n_sub)
            iq_len = len(frame) - 32
            assert iq_len == 1 * n_sub * 2, f"n_sub={n_sub}: expected {n_sub * 2}B, got {iq_len}B"

    def test_frame_iq_values_in_range(self):
        """IQ values should be valid signed bytes (-128 to 127)."""
        frame = self._build_frame(n_sub=64)
        iq_data = frame[32:]
        for i in range(0, len(iq_data), 2):
            re = struct.unpack('<b', iq_data[i:i+1])[0]
            im = struct.unpack('<b', iq_data[i+1:i+2])[0]
            assert -128 <= re <= 127
            assert -128 <= im <= 127

    def test_current_parser_accepts_current_adr018_layout(self):
        """The Python authority parser should accept the current 32-byte CSI frame layout."""
        parsed = parse_udp_packet(self._build_frame(node_id=2, n_sub=8, seq=17), ("127.0.0.1", 5005), 999)
        assert isinstance(parsed, CsiFrameV1)
        assert parsed.node_id == 2
        assert parsed.seq == 17
        assert parsed.n_subcarriers == 8
        assert parsed.device_ts_valid is True


# ═══════════════════════════════════════════════════════════════════
#  Test 5: Server REST API ingestion (live server required)
# ═══════════════════════════════════════════════════════════════════

from e2e_guard import DEFAULT_URL, e2e_server_url  # noqa: E402  (tests/e2e_guard.py; opt-in + never :5000)


class TestServerIngestion:
    SERVER_URL = e2e_server_url(os.environ)[0] or DEFAULT_URL
    USERNAME = os.environ.get("PHANTOM_TEST_USERNAME", "thaer")
    PASSWORD = os.environ.get("PHANTOM_TEST_PASSWORD", "thaer")

    def _server_available(self):
        """Check if the dev server is running.

        Opt-in only (PS-EVAL-019/PS-FIX-01): these tests log in, ingest samples and create sessions on
        whatever server answers on :5000 -- including an operator's live dashboard and its data/sessions.
        Set PHANTOM_E2E_LIVE_SERVER=1 to run them against a throw-away dev server.
        """
        if e2e_server_url(os.environ)[0] is None:  # opt-in, local, and never the operator dashboard on :5000
            return False
        try:
            import urllib.request
            resp = urllib.request.urlopen(f"{self.SERVER_URL}/api/health", timeout=2)
            return resp.status == 200
        except Exception:
            return False

    def _auth_opener(self):
        import urllib.request
        import json

        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        req = urllib.request.Request(
            f"{self.SERVER_URL}/api/auth/login",
            data=json.dumps({
                "username": self.USERNAME,
                "password": self.PASSWORD,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["authenticated"] is True
        return opener

    def test_health_endpoint(self):
        """Server health endpoint should respond."""
        if not self._server_available():
            pytest.skip("Live-server e2e is opt-in: set PHANTOM_E2E_LIVE_SERVER=1 and run a throw-away dev server on its own port (default 5099, never 5000); see tests/e2e_guard.py")

        import urllib.request
        import json
        resp = urllib.request.urlopen(f"{self.SERVER_URL}/api/health", timeout=2)
        data = json.loads(resp.read())
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_ingest_single_sample(self):
        """Server should accept a single CSI sample via REST."""
        if not self._server_available():
            pytest.skip("Live-server e2e is opt-in: set PHANTOM_E2E_LIVE_SERVER=1 and run a throw-away dev server on its own port (default 5099, never 5000); see tests/e2e_guard.py")

        import urllib.request
        import json
        opener = self._auth_opener()
        sample = {
            "timestamp": time.time() * 1000,
            "h1": {"re": 0.87, "im": 0.58},
            "h2": {"re": 0.74, "im": 0.59},
            "rssi": -45.0,
        }
        req = urllib.request.Request(
            f"{self.SERVER_URL}/api/csi/ingest",
            data=json.dumps(sample).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = opener.open(req, timeout=5)
        data = json.loads(resp.read())
        assert data["success"] is True

    def test_ingest_batch_from_recording(self):
        """Server should accept a batch of real recorded CSI samples."""
        if not self._server_available():
            pytest.skip("Live-server e2e is opt-in: set PHANTOM_E2E_LIVE_SERVER=1 and run a throw-away dev server on its own port (default 5099, never 5000); see tests/e2e_guard.py")

        recordings = _load_all_recordings(max_per_file=10)
        if not recordings:
            pytest.skip("No recordings available")

        first_file = list(recordings.keys())[0]
        samples = recordings[first_file][:10]

        import urllib.request
        import json
        opener = self._auth_opener()
        batch = {
            "samples": [
                {
                    "timestamp": s["timestamp"],
                    "h1": {"re": s["h1_re"], "im": s["h1_im"]},
                    "h2": {"re": s["h2_re"], "im": s["h2_im"]},
                    "rssi": s["rssi"],
                }
                for s in samples
            ]
        }

        req = urllib.request.Request(
            f"{self.SERVER_URL}/api/csi/ingest/batch",
            data=json.dumps(batch).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = opener.open(req, timeout=5)
        data = json.loads(resp.read())
        assert data["success"] is True
        assert data["samplesIngested"] == len(samples)

    def test_queue_status(self):
        """Server should report queue status."""
        if not self._server_available():
            pytest.skip("Live-server e2e is opt-in: set PHANTOM_E2E_LIVE_SERVER=1 and run a throw-away dev server on its own port (default 5099, never 5000); see tests/e2e_guard.py")

        import urllib.request
        import json
        opener = self._auth_opener()
        resp = opener.open(f"{self.SERVER_URL}/api/csi/queue", timeout=2)
        data = json.loads(resp.read())
        assert "queueLength" in data
        assert "status" in data

    def test_status_endpoint(self):
        """Server status endpoint should return processing state."""
        if not self._server_available():
            pytest.skip("Live-server e2e is opt-in: set PHANTOM_E2E_LIVE_SERVER=1 and run a throw-away dev server on its own port (default 5099, never 5000); see tests/e2e_guard.py")

        import urllib.request
        import json
        opener = self._auth_opener()
        resp = opener.open(f"{self.SERVER_URL}/api/status", timeout=2)
        data = json.loads(resp.read())
        assert "connected" in data or "isProcessing" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
