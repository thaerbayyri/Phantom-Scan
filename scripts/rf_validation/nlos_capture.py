"""
Phantom Scan Project — RF Validation: NLOS Capture Logger
Brief: Captures 120 seconds of full-spectrum CSI data (all 52 subcarrier phases
       and amplitudes) from two ESP32 receiver nodes via UDP and logs to CSV.

This is the data acquisition script for VTP-PS-002 (RF Validation Protocol).

Architecture:
    ESP32-S3 TX → [NDP frames @ 20 Hz] → Wall → Target A/B
    ESP32-S3 RX #0 (NodeID=0) → UDP:5005 → This Script → CSV Log
    ESP32-S3 RX #1 (NodeID=1) → UDP:5005 → This Script → CSV Log

The script listens for ADR-018 binary packets (magic 0xC5110001) on UDP port 5005,
parses the full I/Q payload into per-subcarrier phase and amplitude values,
and writes a comprehensive CSV log suitable for offline dual-target analysis.

Usage:
    python nlos_capture.py --duration 120 --output test_run_001.csv
    python nlos_capture.py --duration 120 --output test_run_001.csv --port 5005

Output CSV columns:
    timestamp_ms, node_id, rssi, channel, n_subcarriers,
    phase_sc0..phase_sc51, amplitude_sc0..amplitude_sc51
"""

import argparse         # Command-line argument parsing
import csv              # CSV file writing
import math             # atan2 for phase extraction
import os               # File path operations
import socket           # UDP socket for receiving ESP32 data
import struct           # Binary struct unpacking for ADR-018 header
import sys              # System exit codes
import time             # Timing and timestamps


# ══════════════════════════════════════════════════════════════════
# ADR-018 Binary Protocol Constants
# These must match csi_collector.h definitions exactly
# ══════════════════════════════════════════════════════════════════

# ADR-018 magic number (little-endian) — identifies valid CSI packets
ADR018_MAGIC = 0xC5110001

# ADR-018 header size in bytes (20 bytes fixed header)
ADR018_HEADER_SIZE = 20

# Maximum expected subcarriers (HT20 = 52, HT40 = 114)
MAX_SUBCARRIERS = 128

# UDP receive buffer size (must accommodate header + worst-case I/Q payload)
UDP_BUFFER_SIZE = 4096


def parse_adr018_packet(data: bytes) -> dict:
    """
    Parse an ADR-018 binary CSI packet from the ESP32 firmware.

    ADR-018 Header Layout (20 bytes):
        Offset  Type     Field
        0       u32 LE   Magic (0xC5110001)
        4       u8       Node ID
        5       u8       Number of antennas
        6       u16 LE   Number of subcarriers
        8       u32 LE   Frequency (MHz)
        12      u32 LE   Sequence number
        16      i8       RSSI (dBm)
        17      i8       Noise floor (dBm)
        18      u8       Channel number
        19      u8       Reserved

    Payload: n_antennas * n_subcarriers * 2 bytes (int8 I, int8 Q pairs)

    Args:
        data: Raw UDP packet bytes.

    Returns:
        Parsed dict with node_id, rssi, channel, n_subcarriers,
        phases (list of float in radians), amplitudes (list of float).
        Returns None if packet is invalid.
    """
    # Validate minimum packet length against ADR-018 header size
    if len(data) < ADR018_HEADER_SIZE:
        return None

    # Parse the 20-byte ADR-018 header using struct.unpack
    # '<' = little-endian, 'I' = uint32, 'B' = uint8, 'H' = uint16, 'b' = int8
    magic = struct.unpack_from('<I', data, 0)[0]

    # Verify ADR-018 magic number — reject non-CSI packets silently
    if magic != ADR018_MAGIC:
        return None

    # Extract header fields
    node_id = struct.unpack_from('B', data, 4)[0]        # ESP32 node identifier
    n_antennas = struct.unpack_from('B', data, 5)[0]      # Number of TX/RX antennas
    n_subcarriers = struct.unpack_from('<H', data, 6)[0]  # Subcarrier count
    # freq_mhz = struct.unpack_from('<I', data, 8)[0]     # Not needed for logging
    # seq_num = struct.unpack_from('<I', data, 12)[0]      # Not needed for logging
    rssi = struct.unpack_from('b', data, 16)[0]           # RSSI in dBm (signed)
    # noise_floor = struct.unpack_from('b', data, 17)[0]   # Not needed for logging
    channel = struct.unpack_from('B', data, 18)[0]        # WiFi channel number

    # Validate subcarrier count is within expected range
    if n_subcarriers == 0 or n_subcarriers > MAX_SUBCARRIERS:
        return None

    # Validate antenna count
    if n_antennas == 0:
        return None

    # Extract I/Q payload starting after the 20-byte header
    iq_data = data[ADR018_HEADER_SIZE:]

    # Calculate expected I/Q payload size: n_antennas * n_subcarriers * 2 bytes
    expected_iq_bytes = n_antennas * n_subcarriers * 2

    # Validate we have enough I/Q data
    if len(iq_data) < expected_iq_bytes:
        return None

    # Extract per-subcarrier phase (radians) and amplitude from I/Q pairs
    # We use antenna 0 (primary) for the phase/amplitude extraction
    phases = []       # Phase = atan2(Q, I) in radians
    amplitudes = []   # Amplitude = sqrt(I^2 + Q^2)

    for sc in range(n_subcarriers):
        # Calculate byte offset for this subcarrier on antenna 0
        offset = sc * 2  # Each subcarrier is 2 bytes (I, Q)

        # Extract I and Q as signed 8-bit integers
        i_val = struct.unpack_from('b', iq_data, offset)[0]  # In-phase component
        q_val = struct.unpack_from('b', iq_data, offset + 1)[0]  # Quadrature component

        # Compute phase using atan2(Q, I) — provides full [-π, π] range
        phase = math.atan2(q_val, i_val)
        phases.append(phase)

        # Compute amplitude as Euclidean magnitude of I/Q vector
        amplitude = math.sqrt(i_val * i_val + q_val * q_val)
        amplitudes.append(amplitude)

    return {
        'node_id': node_id,
        'rssi': rssi,
        'channel': channel,
        'n_subcarriers': n_subcarriers,
        'phases': phases,          # List of float, length = n_subcarriers
        'amplitudes': amplitudes,  # List of float, length = n_subcarriers
    }


def run_capture(duration_s: int, output_path: str, udp_port: int = 5005):
    """
    Run a timed CSI capture session, logging all received packets to CSV.

    Opens a UDP socket on the specified port, receives ADR-018 packets
    from ESP32 nodes, parses them, and writes full subcarrier data to CSV.
    Automatically stops after the specified duration.

    Args:
        duration_s: Capture duration in seconds (e.g., 120 for the standard test run).
        output_path: Path to the output CSV file.
        udp_port: UDP port to listen on (default 5005, matching firmware config).
    """
    # Create UDP socket for receiving ESP32 CSI packets
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind to all interfaces on the specified port
    sock.bind(('0.0.0.0', udp_port))

    # Set socket timeout to 1 second so we can check elapsed time periodically
    sock.settimeout(1.0)

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  Phantom Scan — NLOS Capture Logger          ║")
    print(f"╠══════════════════════════════════════════════╣")
    print(f"║  Duration:    {duration_s:>6d} seconds                ║")
    print(f"║  Output:      {os.path.basename(output_path):<30s} ║")
    print(f"║  UDP Port:    {udp_port:>6d}                        ║")
    print(f"╚══════════════════════════════════════════════╝")
    print(f"\nListening for ADR-018 packets on UDP:{udp_port}...")
    print("Press Ctrl+C to abort early.\n")

    # Build CSV header with columns for all 52 subcarrier phases and amplitudes
    # This produces: timestamp_ms, node_id, rssi, channel, n_subcarriers,
    #                phase_sc0, phase_sc1, ..., phase_sc51,
    #                amplitude_sc0, amplitude_sc1, ..., amplitude_sc51
    max_sc = 52  # Standard HT20 subcarrier count
    csv_header = ['timestamp_ms', 'node_id', 'rssi', 'channel', 'n_subcarriers']
    csv_header += [f'phase_sc{i}' for i in range(max_sc)]      # 52 phase columns
    csv_header += [f'amplitude_sc{i}' for i in range(max_sc)]  # 52 amplitude columns

    # Open CSV file and begin capture loop
    packet_count = 0     # Total valid packets received
    start_time = time.time()  # Capture start timestamp

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)  # Write CSV header row

        try:
            while True:
                # Check if capture duration has elapsed
                elapsed = time.time() - start_time
                if elapsed >= duration_s:
                    print(f"\n✅ Capture complete: {duration_s}s elapsed.")
                    break

                try:
                    # Attempt to receive a UDP packet (1s timeout)
                    data, addr = sock.recvfrom(UDP_BUFFER_SIZE)
                except socket.timeout:
                    # No packet received within timeout — print progress and continue
                    remaining = duration_s - int(elapsed)
                    print(f"  Waiting for data... ({remaining}s remaining)", end='\r')
                    continue

                # Parse the received packet as ADR-018 binary format
                parsed = parse_adr018_packet(data)
                if parsed is None:
                    continue  # Invalid packet — silently skip

                # Build CSV row: timestamp + metadata + padded phase/amplitude arrays
                timestamp_ms = int(time.time() * 1000)  # Current time in milliseconds

                # Pad phases and amplitudes to exactly max_sc columns
                # (if fewer subcarriers received, pad with 0.0)
                phases_padded = parsed['phases'][:max_sc]
                phases_padded += [0.0] * (max_sc - len(phases_padded))

                amplitudes_padded = parsed['amplitudes'][:max_sc]
                amplitudes_padded += [0.0] * (max_sc - len(amplitudes_padded))

                # Construct the full CSV row
                row = [
                    timestamp_ms,
                    parsed['node_id'],
                    parsed['rssi'],
                    parsed['channel'],
                    parsed['n_subcarriers'],
                ] + [f'{p:.6f}' for p in phases_padded] + \
                    [f'{a:.4f}' for a in amplitudes_padded]

                writer.writerow(row)
                packet_count += 1

                # Progress reporting every 100 packets
                if packet_count % 100 == 0:
                    remaining = duration_s - int(elapsed)
                    print(f"  Captured {packet_count} packets | "
                          f"Node {parsed['node_id']} | "
                          f"RSSI {parsed['rssi']} dBm | "
                          f"{remaining}s remaining   ", end='\r')

        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n⚠️  Capture aborted by user after {elapsed:.1f}s.")

    # Close the UDP socket
    sock.close()

    # Print summary
    print(f"\n{'═' * 50}")
    print(f"Capture Summary:")
    print(f"  Total packets:  {packet_count}")
    print(f"  Duration:       {time.time() - start_time:.1f}s")
    print(f"  Output file:    {os.path.abspath(output_path)}")
    print(f"  File size:      {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"{'═' * 50}")

    return packet_count


# ════════════════════════════════════════════════════════════════
# CLI Entry Point
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phantom Scan — NLOS CSI Capture Logger (VTP-PS-002)"
    )
    # Capture duration in seconds — default 120s per test protocol
    parser.add_argument(
        '--duration', type=int, default=120,
        help='Capture duration in seconds (default: 120)'
    )
    # Output CSV file path
    parser.add_argument(
        '--output', type=str,
        default=f'nlos_capture_{int(time.time())}.csv',
        help='Output CSV file path'
    )
    # UDP port — must match firmware stream_sender target port
    parser.add_argument(
        '--port', type=int, default=5005,
        help='UDP listening port (default: 5005)'
    )

    args = parser.parse_args()

    # Run the capture session
    count = run_capture(
        duration_s=args.duration,
        output_path=args.output,
        udp_port=args.port
    )

    # Exit with error code if no packets were captured
    sys.exit(0 if count > 0 else 1)
