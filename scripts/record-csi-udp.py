#!/usr/bin/env python3
"""Compatibility wrapper around the canonical Phantom JSONL recorder."""

from __future__ import annotations

import argparse
import time

from phantom.ingest import UdpPacketSource
from phantom.protocol import CsiFrameV1, HeartbeatV1
from phantom.recording import JsonlSessionWriter


def main() -> None:
    parser = argparse.ArgumentParser(description="Record ESP32 CSI over UDP into Milestone-1 JSONL")
    parser.add_argument("--port", type=int, default=5005, help="UDP port (default: 5005)")
    parser.add_argument("--duration", type=int, default=300, help="Duration in seconds (default: 300)")
    parser.add_argument("--output", default="data/recordings", help="Output directory")
    args = parser.parse_args()

    writer = JsonlSessionWriter.create(
        output_dir=args.output,
        expected_nodes=[1, 2],
        dsp_config={"pipeline": "raw_record_only"},
        runtime_version="m1-wrapper",
    )
    source = UdpPacketSource(bind_port=args.port)
    print(f"Recording JSONL on UDP :{args.port} for {args.duration}s")
    print(f"Output: {writer.path}")

    count = 0
    start = time.time()
    try:
        while time.time() - start < args.duration:
            for packet in source.packets():
                if isinstance(packet, (CsiFrameV1, HeartbeatV1)):
                    writer.write(packet.to_record())
                    count += 1
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        source.close()
        writer.close(summary={"records": count})

    elapsed = time.time() - start
    print(f"\n=== Recording Complete ===")
    print(f"  Records: {count}")
    print(f"  Duration: {elapsed:.0f}s")
    print(f"  Output: {writer.path}")


if __name__ == "__main__":
    main()
