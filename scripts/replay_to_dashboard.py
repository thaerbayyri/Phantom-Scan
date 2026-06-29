#!/usr/bin/env python3
"""Compatibility wrapper for JSONL replay through the canonical Python runtime."""

import argparse
import os
import sys
from phantom.runtime import PhantomRuntime, RuntimeConfig


RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "recordings")


def find_best_recording():
    """Find the largest recording file for best visualization."""
    if not os.path.isdir(RECORDINGS_DIR):
        print(f"ERROR: No recordings directory at {RECORDINGS_DIR}")
        sys.exit(1)
    
    files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".jsonl")]
    if not files:
        print("ERROR: No JSONL recording files found")
        sys.exit(1)
    
    # Pick the largest file for most data
    files_with_size = [(f, os.path.getsize(os.path.join(RECORDINGS_DIR, f))) for f in files]
    files_with_size.sort(key=lambda x: x[1], reverse=True)
    
    best = files_with_size[0]
    return os.path.join(RECORDINGS_DIR, best[0])


def replay(filepath, speed=1.0):
    """Replay a JSONL recording through the canonical runtime."""
    print(f"\n{'═' * 60}")
    print(f"  PHANTOM SCAN — JSONL Replay")
    print(f"{'═' * 60}")
    print(f"  File:   {os.path.basename(filepath)}")
    print(f"  Speed:  {speed}x")
    print(f"{'═' * 60}\n")
    runtime = PhantomRuntime(RuntimeConfig(output_dir=os.path.join("data", "sessions")))
    runtime.start_session()
    derived = runtime.replay_file(filepath, speed=speed)
    runtime.stop_session()
    print(f"  Derived frames: {len(derived)}")
    if derived:
        print(f"  Final mode:     {derived[-1]['runtime_mode']}")
    print("\n  ✅ Replay complete\n")


def main():
    parser = argparse.ArgumentParser(description="Replay CSI recording to Phantom Scan dashboard")
    parser.add_argument("--file", default=None, help="Path to JSONL recording file")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier (default: 1.0)")
    args = parser.parse_args()

    filepath = args.file or find_best_recording()
    replay(filepath, speed=args.speed)


if __name__ == "__main__":
    main()
