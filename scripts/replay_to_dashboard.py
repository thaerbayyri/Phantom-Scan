#!/usr/bin/env python3
"""
Phantom Scan — CSI Recording Replay to Dashboard

Replays real ESP32 CSI recordings through the live dashboard
for full pipeline visualization (3D point cloud, AoA, Doppler, vitals).

Usage:
    python scripts/replay_to_dashboard.py
    python scripts/replay_to_dashboard.py --speed 2.0        # 2x speed
    python scripts/replay_to_dashboard.py --file recordings/csi_session_2026-03-09T19-00-21-092Z.csv
"""

import argparse
import csv
import json
import os
import sys
import time
import threading

try:
    import websocket  # websocket-client
    HAS_WS = True
except ImportError:
    HAS_WS = False

try:
    import urllib.request
except ImportError:
    pass

SERVER_URL = "http://localhost:5000"
WS_URL = "ws://localhost:5000/ws"
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "recordings")


def load_recording(filepath, max_rows=5000):
    """Load CSI samples from a recording CSV."""
    samples = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            try:
                samples.append({
                    "timestamp": float(row["timestamp"]),
                    "h1": {"re": float(row["h1_re"]), "im": float(row["h1_im"])},
                    "h2": {"re": float(row["h2_re"]), "im": float(row["h2_im"])},
                    "rssi": float(row["rssi"]),
                })
            except (ValueError, KeyError):
                continue
    return samples


def find_best_recording():
    """Find the largest recording file for best visualization."""
    if not os.path.isdir(RECORDINGS_DIR):
        print(f"ERROR: No recordings directory at {RECORDINGS_DIR}")
        sys.exit(1)
    
    csvs = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".csv")]
    if not csvs:
        print("ERROR: No CSV recording files found")
        sys.exit(1)
    
    # Pick the largest file for most data
    csvs_with_size = [(f, os.path.getsize(os.path.join(RECORDINGS_DIR, f))) for f in csvs]
    csvs_with_size.sort(key=lambda x: x[1], reverse=True)
    
    best = csvs_with_size[0]
    return os.path.join(RECORDINGS_DIR, best[0])


def send_ws_message(ws_conn, msg_type, data=None):
    """Send a WebSocket message."""
    ws_conn.send(json.dumps({"type": msg_type, "data": data}))


def send_sample_rest(sample, server_url):
    """Send a single CSI sample via REST API."""
    req = urllib.request.Request(
        f"{server_url}/api/csi/ingest",
        data=json.dumps(sample).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=2)
        return resp.status == 200
    except Exception:
        return False


def send_batch_rest(samples, server_url):
    """Send a batch of CSI samples via REST API."""
    req = urllib.request.Request(
        f"{server_url}/api/csi/ingest/batch",
        data=json.dumps({"samples": samples}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def replay(filepath, speed=1.0, batch_size=5, server_url=SERVER_URL, ws_url=WS_URL):
    """Replay a recording file to the dashboard."""
    
    print(f"\n{'═' * 60}")
    print(f"  PHANTOM SCAN — CSI Recording Replay")
    print(f"{'═' * 60}")
    print(f"  File:   {os.path.basename(filepath)}")
    print(f"  Speed:  {speed}x")
    print(f"  Server: {server_url}")
    print(f"{'═' * 60}\n")

    # Load samples
    print("  Loading recording...", end="", flush=True)
    samples = load_recording(filepath)
    print(f" {len(samples)} samples loaded")

    if len(samples) < 10:
        print("  ERROR: Not enough samples in recording")
        return

    # Check server
    print("  Checking server...", end="", flush=True)
    try:
        resp = urllib.request.urlopen(f"{server_url}/api/health", timeout=2)
        if resp.status != 200:
            print(" FAILED")
            print("  ERROR: Server not healthy")
            return
        print(" OK")
    except Exception as e:
        print(f" FAILED ({e})")
        print("  ERROR: Cannot reach server. Is 'npm run dev' running?")
        return

    # Connect via WebSocket to control processing
    ws_conn = None
    if HAS_WS:
        print("  Connecting WebSocket...", end="", flush=True)
        try:
            ws_conn = websocket.create_connection(ws_url, timeout=5)
            print(" OK")
        except Exception as e:
            print(f" FAILED ({e})")
            print("  Will use REST-only mode (no processing start via WS)")

    # Start processing via WebSocket
    if ws_conn:
        print("  Starting processing pipeline...", end="", flush=True)
        send_ws_message(ws_conn, "startProcessing", {"customName": f"Replay: {os.path.basename(filepath)}"})
        time.sleep(0.5)
        print(" OK")
    else:
        print("  ⚠  WebSocket not available — start processing manually from the dashboard")

    # Calculate timing
    if len(samples) > 1:
        ts_start = samples[0]["timestamp"]
        ts_end = samples[-1]["timestamp"]
        total_duration = (ts_end - ts_start) / 1000  # ms → seconds
    else:
        total_duration = 1.0

    replay_duration = total_duration / speed
    interval = replay_duration / len(samples) if len(samples) > 0 else 0.05
    
    # Clamp interval to reasonable bounds
    interval = max(0.01, min(interval, 0.2))

    print(f"\n  ▶ Replaying {len(samples)} samples over ~{replay_duration:.1f}s ({speed}x speed)")
    print(f"    Interval: {interval*1000:.0f}ms per sample ({1/interval:.0f} samples/sec)")
    print(f"    Original duration: {total_duration:.1f}s")
    print(f"\n  {'─' * 56}")
    print(f"  Open http://localhost:5000 to see the visualization!")
    print(f"  {'─' * 56}\n")

    sent = 0
    errors = 0
    start_time = time.time()
    batch_buf = []

    try:
        for i, sample in enumerate(samples):
            # Update timestamp to current time for live processing
            sample["timestamp"] = time.time() * 1000

            batch_buf.append(sample)

            if len(batch_buf) >= batch_size:
                if send_batch_rest(batch_buf, server_url):
                    sent += len(batch_buf)
                else:
                    errors += len(batch_buf)
                batch_buf = []

            # Progress indicator
            if (i + 1) % 50 == 0 or i == len(samples) - 1:
                elapsed = time.time() - start_time
                pct = ((i + 1) / len(samples)) * 100
                pps = sent / elapsed if elapsed > 0 else 0
                bar_len = 30
                filled = int(bar_len * (i + 1) / len(samples))
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r  [{bar}] {pct:5.1f}% | {sent:>5} sent | {pps:>5.1f} sps | {errors} err", end="", flush=True)

            time.sleep(interval)

        # Flush remaining batch
        if batch_buf:
            if send_batch_rest(batch_buf, server_url):
                sent += len(batch_buf)
            else:
                errors += len(batch_buf)

    except KeyboardInterrupt:
        print("\n\n  [Interrupted by user]")

    total_elapsed = time.time() - start_time
    print(f"\n\n  {'═' * 56}")
    print(f"  REPLAY COMPLETE")
    print(f"  {'═' * 56}")
    print(f"  Samples sent:    {sent}")
    print(f"  Errors:          {errors}")
    print(f"  Duration:        {total_elapsed:.1f}s")
    print(f"  Avg rate:        {sent/total_elapsed:.1f} samples/sec")
    print()

    # Wait a bit for processing to finish, then stop
    if ws_conn:
        time.sleep(2)
        print("  Stopping processing pipeline...", end="", flush=True)
        send_ws_message(ws_conn, "stopProcessing")
        time.sleep(1)
        ws_conn.close()
        print(" OK")

    print("\n  ✅ Done! Check the dashboard at http://localhost:5000\n")


def main():
    parser = argparse.ArgumentParser(description="Replay CSI recording to Phantom Scan dashboard")
    parser.add_argument("--file", default=None, help="Path to CSV recording file")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier (default: 1.0)")
    parser.add_argument("--batch-size", type=int, default=5, dest="batch_size",
                        help="Samples per REST request (default: 5)")
    parser.add_argument("--server", default=SERVER_URL, help="Dashboard server URL")
    args = parser.parse_args()

    server = args.server
    ws = server.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

    filepath = args.file or find_best_recording()
    replay(filepath, speed=args.speed, batch_size=args.batch_size, server_url=server, ws_url=ws)


if __name__ == "__main__":
    main()
