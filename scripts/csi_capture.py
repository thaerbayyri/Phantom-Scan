#!/usr/bin/env python3
from __future__ import annotations
"""
Phantom Scan — ESP32-S3 CSI Capture Script

Reads real-time CSI data from an ESP32-S3 over serial (USB)
and streams it to the Phantom Scan dashboard.

INSTALLATION:
    pip install requests pyserial

USAGE:
    python csi_capture.py --server http://localhost:5000
"""

import argparse
import csv
import os
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── ESP-Centric Coordinate Mapping ───────────────────────────────
# DEPRECATED: The legacy global-state calculate_relative_position() has been
# replaced by the CSIFilterPipeline class in csi_filter_pipeline.py.
# It provides Hampel filtering, DWT denoising, DBSCAN clustering, and Kalman
# tracking with proper encapsulated state. Import and use:
#
#   from csi_filter_pipeline import CSIFilterPipeline
#   pipeline = CSIFilterPipeline()
#   result = pipeline.process_sample(h1_re, h1_im, h2_re, h2_im, rssi)



class CSISample:
    """Represents a single CSI sample with two channel estimates."""

    def __init__(
        self,
        h1_re: float,
        h1_im: float,
        h2_re: float,
        h2_im: float,
        timestamp: Optional[float] = None,
        rssi: Optional[float] = None,
    ):
        self.timestamp = timestamp or time.time() * 1000
        self.h1 = {"re": h1_re, "im": h1_im}
        self.h2 = {"re": h2_re, "im": h2_im}
        self.rssi = rssi

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "h1": self.h1,
            "h2": self.h2,
        }
        if self.rssi is not None:
            result["rssi"] = self.rssi
        return result


def _require_requests():
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError("requests library not found. Install with: pip install requests") from exc
    return requests


def _require_serial():
    try:
        import serial  # type: ignore
        import serial.tools.list_ports  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyserial library not found. Install with: pip install pyserial") from exc
    return serial


# ── Serial port helpers ──────────────────────────────────────────────


def list_serial_ports() -> List[Any]:
    """Return list of serial port info objects."""
    serial = _require_serial()
    return list(serial.tools.list_ports.comports())


def choose_serial_port() -> Optional[str]:
    """Show available COM ports and let the user pick one."""
    ports = list_serial_ports()
    if not ports:
        print("No serial ports detected. Make sure your ESP32-S3 is plugged in.")
        return None

    print("\nAvailable serial ports:")
    for i, p in enumerate(ports, 1):
        desc = f" - {p.description}" if p.description else ""
        hwid = f"  [{p.hwid}]" if p.hwid else ""
        print(f"  [{i}] {p.device}{desc}{hwid}")

    while True:
        try:
            choice = input(f"\nSelect port (1-{len(ports)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                return ports[idx].device
            print(f"Please enter a number between 1 and {len(ports)}")
        except (ValueError, EOFError):
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None


# ── ESP32-S3 CSI parser ──────────────────────────────────────────────


def parse_csi_line(line: str) -> Optional[CSISample]:
    """
    Parse one line of ESP32-S3 CSI output.

    Supports two formats:
      1. Raw CSV:   timestamp,rssi,I1,Q1,I2,Q2,...
      2. ESP-CSI:   CSI_DATA,type,role,mac,rssi,...,[space-separated I/Q]

    We take the first two complex pairs as h1 and h2.
    """
    if not line or line.startswith("#"):
        return None

    try:
        parts = line.split(",")

        # ── Format 2: ESP-CSI firmware with CSI_DATA prefix ──
        if "CSI_DATA" in line:
            raw_data = parts[-1].replace("[", "").replace("]", "").split()
            data_ints = [int(x) for x in raw_data if x]
            rssi = -50
            if len(parts) > 4 and parts[4].lstrip("-").isdigit():
                rssi = int(parts[4])

        # ── Format 1: Raw CSV — timestamp,rssi,I1,Q1,I2,Q2,... ──
        else:
            # Need at least: timestamp, rssi, I1, Q1, I2, Q2 = 6 fields
            if len(parts) < 6:
                return None
            # First field should look like a timestamp (float)
            try:
                float(parts[0])
            except ValueError:
                return None
            rssi = int(parts[1])
            data_ints = [int(x) for x in parts[2:] if x.strip().lstrip("-").isdigit()]

        # Build complex pairs (I, Q)
        complex_pairs = []
        for i in range(0, len(data_ints) - 1, 2):
            complex_pairs.append({"re": data_ints[i], "im": data_ints[i + 1]})

        if len(complex_pairs) < 2:
            return None

        return CSISample(
            h1_re=complex_pairs[0]["re"],
            h1_im=complex_pairs[0]["im"],
            h2_re=complex_pairs[1]["re"],
            h2_im=complex_pairs[1]["im"],
            timestamp=int(time.time() * 1000),
            rssi=rssi,
        )
    except Exception as e:
        print(f"Parse error: {e}")
        return None


# ── Network helpers ──────────────────────────────────────────────────


def check_server(url: str, session) -> bool:
    try:
        r = session.get(f"{url}/api/health", timeout=5)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def check_processing_status(url: str, session) -> bool:
    try:
        r = session.get(f"{url}/api/status", timeout=2)
        if r.status_code == 200:
            return r.json().get("isProcessing", True)
        return True
    except requests.exceptions.RequestException:
        return True

def send_sample(url: str, sample: CSISample, session) -> Tuple[bool, bool]:
    try:
        r = session.post(f"{url}/api/csi/ingest", json=sample.to_dict(), timeout=1)
        if r.status_code == 200:
            data = r.json()
            return True, data.get("isProcessing", True)
        return False, True
    except requests.exceptions.RequestException as e:
        print(f"Send error: {e}")
        return False, True


def send_batch(url: str, samples: List[CSISample], session) -> bool:
    try:
        r = session.post(
            f"{url}/api/csi/ingest/batch",
            json={"samples": [s.to_dict() for s in samples]},
            timeout=2,
        )
        return r.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Batch send error: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Phantom Scan — ESP32-S3 CSI Capture")
    parser.add_argument(
        "--server",
        default="http://localhost:5000",
        help="Dashboard server URL (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port (auto-detected if not specified)",
    )
    parser.add_argument(
        "--baud", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--esp32",
        action="store_true",
        default=True,
        help="(default, kept for backward compatibility)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        dest="batch_size",
        help="Samples per HTTP request (default: 1)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Save captured CSI data locally to CSV",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV file path (default: csi_recording_<timestamp>.csv)",
    )

    args = parser.parse_args()

    # ── Connect to dashboard ──
    requests = _require_requests()
    serial = _require_serial()
    session = requests.Session()
    print(f"Connecting to dashboard: {args.server}")
    if not check_server(args.server, session):
        print("ERROR: Cannot reach dashboard server. Is it running?")
        sys.exit(1)
    print("Dashboard connected ✓")

    # ── Pick serial port ──
    port = args.port
    if port is None:
        port = choose_serial_port()
        if port is None:
            sys.exit(1)

    print(f"Opening {port} at {args.baud} baud …")
    ser = serial.Serial(port, args.baud, timeout=1)
    print(f"Serial connected ✓\n")
    print("Waiting for CSI_DATA lines from ESP32-S3 …")
    print("Press Ctrl+C to stop\n")

    # ── Optional local recording ──
    csv_file = None
    csv_writer = None
    if args.record:
        output_path = args.output or f"csi_recording_{int(time.time())}.csv"
        csv_file = open(output_path, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            ["timestamp", "subcarrier_index", "h1_re", "h1_im", "h2_re", "h2_im", "rssi"]
        )
        print(f"Recording to: {os.path.abspath(output_path)}")

    samples_sent = 0
    errors = 0
    batch_buf: List[CSISample] = []

    try:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            sample = parse_csi_line(line)
            if sample is None:
                continue

            # Record locally if enabled
            if csv_writer is not None:
                csv_writer.writerow([
                    sample.timestamp,
                    0,  # subcarrier index
                    sample.h1["re"],
                    sample.h1["im"],
                    sample.h2["re"],
                    sample.h2["im"],
                    sample.rssi if sample.rssi is not None else "",
                ])
                # Flush every 100 samples
                if samples_sent > 0 and samples_sent % 100 == 0 and csv_file:
                    csv_file.flush()

            if args.batch_size > 1:
                # Batch logic pending update for isProcessing, skipping for now as default is 1
                batch_buf.append(sample)
                if len(batch_buf) >= args.batch_size:
                    if send_batch(args.server, batch_buf, session):
                        samples_sent += len(batch_buf)
                    else:
                        errors += 1
                    batch_buf = []
            else:
                success, should_process = send_sample(args.server, sample, session)
                if success:
                    samples_sent += 1
                else:
                    errors += 1
                
                if not should_process:
                    print("\n🛑 Capture PAUSED (Dashboard stopped processing)")
                    print("   Draining serial buffer...", end="", flush=True)
                    while not should_process:
                        # Drain serial buffer to prevent overflow
                        if ser.in_waiting:
                            ser.read(ser.in_waiting)
                        
                        time.sleep(0.5)
                        should_process = check_processing_status(args.server, session)
                        print(".", end="", flush=True)
                    print("\n▶️ Capture RESUMED\n")

            if samples_sent > 0 and samples_sent % 100 == 0:
                print(f"  Sent: {samples_sent}  |  Errors: {errors}")

    except KeyboardInterrupt:
        print(f"\n\nStopped. Sent {samples_sent} samples, {errors} errors.")
    finally:
        ser.close()
        if csv_file:
            csv_file.close()
            print(f"Recording saved: {os.path.abspath(csv_file.name)}")


if __name__ == "__main__":
    main()
