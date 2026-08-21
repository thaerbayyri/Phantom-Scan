#!/usr/bin/env python3
"""
Phantom Scan — Live-Scan Phase Test Logger (serial capture)

Opens the ESP32 node's USB serial port during a live scan, parses the
periodic "Vitals: ... phase=<rad> rad (sc=<idx>)" line emitted by
process_frame() in firmware/esp32-csi-node/main/edge_processing.c, and
appends each reading to a timestamped CSV log for offline analysis.

This is the device-side counterpart to server/lib/phase-test-logger.ts,
which logs the server's own per-packet phase computed from the raw CSI
UDP stream. The two are independent captures (on-device DSP vs.
host-side dominant-subcarrier phase) useful for cross-checking.

INSTALLATION:
    pip install pyserial

USAGE:
    python scripts/serial_phase_logger.py --port COM7
    python scripts/serial_phase_logger.py --port COM7 --output data/phase-tests/my_test.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from typing import Optional

try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore
except ImportError:
    print("ERROR: pyserial not found. Install with: pip install pyserial")
    sys.exit(1)

# Matches the ESP_LOGI line added in edge_processing.c's process_frame():
#   "Vitals: br=14.2 hr=68.5 motion=0.0123 pres=YES fall=no persons=1
#    frames=1800 phase=3.7421 rad (sc=42)"
VITALS_PHASE_RE = re.compile(
    r"br=(?P<br>-?[\d.]+)\s+hr=(?P<hr>-?[\d.]+)\s+motion=(?P<motion>-?[\d.]+)\s+"
    r"pres=(?P<pres>YES|no)\s+fall=(?P<fall>YES|no)\s+persons=(?P<persons>\d+)\s+"
    r"frames=(?P<frames>\d+)\s+phase=(?P<phase>-?[\d.]+)\s+rad\s+\(sc=(?P<sc>\d+)\)"
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "data", "phase-tests")


def choose_serial_port() -> Optional[str]:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports detected. Make sure the ESP32 node is plugged in.")
        return None

    print("\nAvailable serial ports:")
    for i, p in enumerate(ports, 1):
        desc = f" - {p.description}" if p.description else ""
        print(f"  [{i}] {p.device}{desc}")

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


def parse_phase_line(line: str) -> Optional[dict]:
    match = VITALS_PHASE_RE.search(line)
    if not match:
        return None
    g = match.groupdict()
    return {
        "breathing_bpm": float(g["br"]),
        "heartrate_bpm": float(g["hr"]),
        "motion": float(g["motion"]),
        "presence": g["pres"] == "YES",
        "fall": g["fall"] == "YES",
        "persons": int(g["persons"]),
        "frames": int(g["frames"]),
        "phase_rad": float(g["phase"]),
        "subcarrier_idx": int(g["sc"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Phantom Scan — live-scan phase test logger (serial)")
    parser.add_argument("--port", default=None, help="Serial port (e.g. COM7). Prompted if omitted.")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--output", default=None, help="Output CSV path (default: data/phase-tests/serial-phase_<timestamp>.csv)")
    args = parser.parse_args()

    port = args.port or choose_serial_port()
    if port is None:
        sys.exit(1)

    output_path = args.output
    if output_path is None:
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"serial-phase_{int(time.time())}.csv")
    else:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    print(f"Opening {port} at {args.baud} baud …")
    ser = serial.Serial(port, args.baud, timeout=1)
    print(f"Serial connected. Logging phase readings to: {output_path}")
    print("Press Ctrl+C to stop\n")

    csv_file = open(output_path, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow([
        "timestamp_ms", "subcarrier_idx", "phase_rad",
        "breathing_bpm", "heartrate_bpm", "motion", "presence", "fall", "persons", "frames",
    ])

    readings = 0
    try:
        while True:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue

            reading = parse_phase_line(raw)
            if reading is None:
                continue

            writer.writerow([
                int(time.time() * 1000),
                reading["subcarrier_idx"],
                reading["phase_rad"],
                reading["breathing_bpm"],
                reading["heartrate_bpm"],
                reading["motion"],
                reading["presence"],
                reading["fall"],
                reading["persons"],
                reading["frames"],
            ])
            readings += 1
            if readings % 10 == 0:
                csv_file.flush()
                print(f"  logged {readings} phase readings (last: {reading['phase_rad']:.4f} rad, sc={reading['subcarrier_idx']})")
    except KeyboardInterrupt:
        print(f"\n\nStopped. Logged {readings} phase readings.")
    finally:
        ser.close()
        csv_file.close()
        print(f"Saved: {os.path.abspath(output_path)}")


if __name__ == "__main__":
    main()
