#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  PHANTOM SCAN — Network Link Validation Test Suite (VTP-NL-001)        ║
║  ESP32-S3 (Station) ↔ Ground Control Station (PC Receiver)            ║
║                                                                        ║
║  Protocol:  UDP/5005 (ADR-018 Binary Frame Format)                     ║
║  Target:    100 Hz PPS, <1% packet loss, <10ms jitter                  ║
║                                                                        ║
║  Tests:                                                                ║
║    A. THROUGHPUT AUDIT    — Measures Packets Per Second reaching GCS    ║
║    B. LATENCY JITTER      — Delta-T distribution & sleep interference  ║
║    C. BINARY INTEGRITY    — ADR-018 header vs payload consistency      ║
║    D. DISTANCE DROP-OFF   — RSSI degradation & CSI phase corruption    ║
║                                                                        ║
║  Usage:                                                                ║
║    python tests/network_link_validation.py --mode full                 ║
║    python tests/network_link_validation.py --mode throughput           ║
║    python tests/network_link_validation.py --mode jitter               ║
║    python tests/network_link_validation.py --mode integrity            ║
║    python tests/network_link_validation.py --mode dropoff              ║
║    python tests/network_link_validation.py --mode emitter              ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import socket
import struct
import time
import random
import threading
import argparse
import statistics
import math
import json
import os
import sys
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════
# ADR-018 Protocol Constants
# ═══════════════════════════════════════════════════════════════════════

MAGIC_CSI         = 0xC5110001
MAGIC_VITALS      = 0xC5110002
HEADER_SIZE       = 20
HEADER_FORMAT     = '<IBBHIIbbxx'   # 20 bytes total
UDP_PORT          = 5005
UDP_HOST          = '0.0.0.0'

# Test parameters
TARGET_PPS        = 100             # Target packets per second
PPS_PASS_THRESH   = 95              # Minimum acceptable PPS
MAX_LOSS_PCT      = 1.0             # Maximum acceptable packet loss %
MAX_JITTER_MS     = 10.0            # Maximum acceptable jitter in ms
NUM_SUBCARRIERS   = 52              # ADR-018 standard: 52 subcarriers (HT20)
NUM_ANTENNAS      = 1               # ESP32-S3 single antenna CSI
IQ_BYTES_PER_SUB  = 2               # 1 byte I + 1 byte Q per subcarrier


# ═══════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ADR018Packet:
    """Parsed ADR-018 CSI packet."""
    magic: int = 0
    node_id: int = 0
    num_antennas: int = 0
    num_subcarriers: int = 0
    freq_mhz: int = 0
    sequence: int = 0
    rssi: int = 0
    noise_floor: int = 0
    iq_data: bytes = b''
    recv_timestamp: float = 0.0
    raw_length: int = 0
    is_valid: bool = False
    error: str = ''


@dataclass
class ThroughputResult:
    """Results from throughput audit."""
    duration_sec: float = 0.0
    total_packets: int = 0
    avg_pps: float = 0.0
    min_pps: float = 0.0
    max_pps: float = 0.0
    pps_history: List[float] = field(default_factory=list)
    packets_lost: int = 0
    loss_percentage: float = 0.0
    pass_status: bool = False
    bottleneck: str = ''


@dataclass
class JitterResult:
    """Results from latency jitter analysis."""
    total_packets: int = 0
    avg_delta_ms: float = 0.0
    min_delta_ms: float = 0.0
    max_delta_ms: float = 0.0
    stddev_delta_ms: float = 0.0
    p95_delta_ms: float = 0.0
    p99_delta_ms: float = 0.0
    jitter_violations: int = 0
    jitter_violation_pct: float = 0.0
    sleep_interference_detected: bool = False
    pass_status: bool = False
    delta_histogram: Dict[str, int] = field(default_factory=dict)


@dataclass
class IntegrityResult:
    """Results from binary integrity check."""
    total_packets: int = 0
    valid_packets: int = 0
    malformed_packets: int = 0
    malformed_details: List[str] = field(default_factory=list)
    magic_errors: int = 0
    length_errors: int = 0
    subcarrier_errors: int = 0
    pass_status: bool = False


@dataclass
class DropOffResult:
    """Results from distance drop-off simulation."""
    rssi_levels: List[int] = field(default_factory=list)
    pps_per_rssi: Dict[int, float] = field(default_factory=dict)
    phase_std_per_rssi: Dict[int, float] = field(default_factory=dict)
    fft_viable_per_rssi: Dict[int, bool] = field(default_factory=dict)
    critical_rssi: int = 0  # RSSI where FFT extraction fails
    pass_status: bool = False


# ═══════════════════════════════════════════════════════════════════════
# Packet Parser
# ═══════════════════════════════════════════════════════════════════════

def parse_adr018_packet(data: bytes, recv_time: float) -> ADR018Packet:
    """Parse a raw UDP datagram into ADR018Packet structure."""
    pkt = ADR018Packet(recv_timestamp=recv_time, raw_length=len(data))

    if len(data) < HEADER_SIZE:
        pkt.error = f'Runt packet: {len(data)} bytes < {HEADER_SIZE} header'
        return pkt

    try:
        header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        pkt.magic = header[0]
        pkt.node_id = header[1]
        pkt.num_antennas = header[2]
        pkt.num_subcarriers = header[3]
        pkt.freq_mhz = header[4]
        pkt.sequence = header[5]
        pkt.rssi = header[6]
        pkt.noise_floor = header[7]
    except struct.error as e:
        pkt.error = f'Header unpack failed: {e}'
        return pkt

    if pkt.magic != MAGIC_CSI:
        pkt.error = f'Magic 0x{pkt.magic:08X} != expected 0x{MAGIC_CSI:08X}'
        return pkt

    expected_iq = pkt.num_antennas * pkt.num_subcarriers * IQ_BYTES_PER_SUB
    actual_iq = len(data) - HEADER_SIZE

    if actual_iq < expected_iq:
        pkt.error = (f'Payload truncated: got {actual_iq} bytes, '
                     f'expected {expected_iq} '
                     f'({pkt.num_antennas}ant × {pkt.num_subcarriers}sub × {IQ_BYTES_PER_SUB}B)')
        return pkt

    pkt.iq_data = data[HEADER_SIZE:HEADER_SIZE + expected_iq]
    pkt.is_valid = True
    return pkt


# ═══════════════════════════════════════════════════════════════════════
# Test A: Throughput Audit
# ═══════════════════════════════════════════════════════════════════════

class ThroughputAudit:
    """
    Measures Packets Per Second (PPS) reaching the Python backend.
    If PPS < 95, identifies bottleneck (Serial buffer vs WiFi radio).
    """

    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT,
                 duration_sec: int = 30):
        self.host = host
        self.port = port
        self.duration_sec = duration_sec
        self.packets: List[ADR018Packet] = []
        self._stop = threading.Event()

    def run(self) -> ThroughputResult:
        result = ThroughputResult()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))

        print(f'\n{"═" * 70}')
        print(f'  TEST A: THROUGHPUT AUDIT')
        print(f'  Listening on {self.host}:{self.port} for {self.duration_sec}s')
        print(f'  Target: ≥{PPS_PASS_THRESH} PPS (100 Hz stream)')
        print(f'{"═" * 70}')

        pps_buckets = []
        bucket_start = time.monotonic()
        bucket_count = 0
        test_start = time.monotonic()
        sequences_seen = set()

        try:
            while (time.monotonic() - test_start) < self.duration_sec:
                try:
                    data, addr = sock.recvfrom(65535)
                    recv_time = time.monotonic()
                    pkt = parse_adr018_packet(data, recv_time)

                    if pkt.is_valid:
                        self.packets.append(pkt)
                        sequences_seen.add(pkt.sequence)
                        bucket_count += 1

                    # 1-second PPS bucket
                    elapsed = time.monotonic() - bucket_start
                    if elapsed >= 1.0:
                        pps = bucket_count / elapsed
                        pps_buckets.append(pps)
                        bar = '█' * int(pps) + '░' * max(0, TARGET_PPS - int(pps))
                        status = '✓' if pps >= PPS_PASS_THRESH else '✗'
                        print(f'  [{status}] PPS: {pps:6.1f} | {bar[:50]}')
                        bucket_count = 0
                        bucket_start = time.monotonic()

                except socket.timeout:
                    elapsed = time.monotonic() - bucket_start
                    if elapsed >= 1.0:
                        pps_buckets.append(bucket_count / elapsed)
                        print(f'  [✗] PPS: {bucket_count / elapsed:6.1f} (timeout in bucket)')
                        bucket_count = 0
                        bucket_start = time.monotonic()

        except KeyboardInterrupt:
            print('\n  [!] Test interrupted by user')
        finally:
            sock.close()

        # Calculate results
        total_time = time.monotonic() - test_start
        result.duration_sec = total_time
        result.total_packets = len(self.packets)
        result.pps_history = pps_buckets

        if pps_buckets:
            result.avg_pps = statistics.mean(pps_buckets)
            result.min_pps = min(pps_buckets)
            result.max_pps = max(pps_buckets)

        # Packet loss calculation from sequence numbers
        if sequences_seen:
            min_seq = min(sequences_seen)
            max_seq = max(sequences_seen)
            expected_packets = max_seq - min_seq + 1
            result.packets_lost = expected_packets - len(sequences_seen)
            if expected_packets > 0:
                result.loss_percentage = (result.packets_lost / expected_packets) * 100.0

        result.pass_status = (result.avg_pps >= PPS_PASS_THRESH and
                              result.loss_percentage <= MAX_LOSS_PCT)

        # Bottleneck identification
        if result.avg_pps < PPS_PASS_THRESH:
            if result.max_pps >= PPS_PASS_THRESH:
                result.bottleneck = ('INTERMITTENT: WiFi radio contention or sleep mode. '
                                     'PPS drops during radio re-transmissions. '
                                     'Recommend: Disable WiFi power save (WIFI_PS_NONE)')
            elif result.avg_pps < 50:
                result.bottleneck = ('SERIAL BUFFER: ESP32 UART/USB buffer overflow or '
                                     'CSI callback rate-limited too aggressively. '
                                     'Recommend: Decrease CSI_MIN_SEND_INTERVAL_US')
            else:
                result.bottleneck = ('WIFI RADIO: 2.4GHz congestion or channel overlap. '
                                     'Recommend: Switch to least-congested channel (1, 6, or 11)')

        self._print_result(result)
        return result

    def _print_result(self, r: ThroughputResult):
        status = '✅ PASS' if r.pass_status else '❌ FAIL'
        print(f'\n  ── Result: {status} ──')
        print(f'  Duration:     {r.duration_sec:.1f}s')
        print(f'  Total Pkts:   {r.total_packets}')
        print(f'  Avg PPS:      {r.avg_pps:.1f} (target: ≥{PPS_PASS_THRESH})')
        print(f'  Min/Max PPS:  {r.min_pps:.1f} / {r.max_pps:.1f}')
        print(f'  Packet Loss:  {r.packets_lost} ({r.loss_percentage:.2f}%)')
        if r.bottleneck:
            print(f'  Bottleneck:   {r.bottleneck}')


# ═══════════════════════════════════════════════════════════════════════
# Test B: Latency Jitter Analysis
# ═══════════════════════════════════════════════════════════════════════

class JitterAnalysis:
    """
    Calculates Delta-T between incoming packets.
    If jitter > 10ms, analyzes if ESP32 WiFi sleep mode is interfering.
    """

    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT,
                 duration_sec: int = 30):
        self.host = host
        self.port = port
        self.duration_sec = duration_sec

    def run(self) -> JitterResult:
        result = JitterResult()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))

        print(f'\n{"═" * 70}')
        print(f'  TEST B: LATENCY JITTER ANALYSIS')
        print(f'  Listening on {self.host}:{self.port} for {self.duration_sec}s')
        print(f'  Target: Jitter < {MAX_JITTER_MS}ms (P99)')
        print(f'{"═" * 70}')

        timestamps = []
        test_start = time.monotonic()

        try:
            while (time.monotonic() - test_start) < self.duration_sec:
                try:
                    data, addr = sock.recvfrom(65535)
                    recv_time = time.monotonic()

                    if len(data) >= HEADER_SIZE:
                        magic = struct.unpack('<I', data[:4])[0]
                        if magic == MAGIC_CSI:
                            timestamps.append(recv_time)

                except socket.timeout:
                    continue

        except KeyboardInterrupt:
            print('\n  [!] Test interrupted by user')
        finally:
            sock.close()

        if len(timestamps) < 2:
            print('  [!] Insufficient packets for jitter analysis')
            return result

        # Calculate inter-packet deltas
        deltas_ms = []
        for i in range(1, len(timestamps)):
            dt = (timestamps[i] - timestamps[i - 1]) * 1000.0
            deltas_ms.append(dt)

        result.total_packets = len(timestamps)
        result.avg_delta_ms = statistics.mean(deltas_ms)
        result.min_delta_ms = min(deltas_ms)
        result.max_delta_ms = max(deltas_ms)
        result.stddev_delta_ms = statistics.stdev(deltas_ms) if len(deltas_ms) > 1 else 0.0

        sorted_deltas = sorted(deltas_ms)
        idx_95 = int(len(sorted_deltas) * 0.95)
        idx_99 = int(len(sorted_deltas) * 0.99)
        result.p95_delta_ms = sorted_deltas[idx_95] if idx_95 < len(sorted_deltas) else sorted_deltas[-1]
        result.p99_delta_ms = sorted_deltas[idx_99] if idx_99 < len(sorted_deltas) else sorted_deltas[-1]

        # Count jitter violations
        result.jitter_violations = sum(1 for d in deltas_ms if d > MAX_JITTER_MS)
        result.jitter_violation_pct = (result.jitter_violations / len(deltas_ms)) * 100.0

        # Build histogram
        buckets = {'0-2ms': 0, '2-5ms': 0, '5-10ms': 0, '10-20ms': 0,
                   '20-50ms': 0, '50-100ms': 0, '100ms+': 0}
        for d in deltas_ms:
            if d < 2:
                buckets['0-2ms'] += 1
            elif d < 5:
                buckets['2-5ms'] += 1
            elif d < 10:
                buckets['5-10ms'] += 1
            elif d < 20:
                buckets['10-20ms'] += 1
            elif d < 50:
                buckets['20-50ms'] += 1
            elif d < 100:
                buckets['50-100ms'] += 1
            else:
                buckets['100ms+'] += 1
        result.delta_histogram = buckets

        # WiFi Sleep Mode Interference Detection
        # If we see periodic large gaps (>50ms) with regular spacing (~100ms),
        # this indicates DTIM beacon-driven wakeups from modem sleep.
        large_gaps = [d for d in deltas_ms if d > 50.0]
        if len(large_gaps) > 3:
            gap_intervals = []
            gap_indices = [i for i, d in enumerate(deltas_ms) if d > 50.0]
            for j in range(1, len(gap_indices)):
                gap_intervals.append(gap_indices[j] - gap_indices[j - 1])
            if gap_intervals:
                gap_cv = (statistics.stdev(gap_intervals) / statistics.mean(gap_intervals)
                          if len(gap_intervals) > 1 else 0.0)
                # Low coefficient of variation = periodic = sleep mode
                if gap_cv < 0.5:
                    result.sleep_interference_detected = True

        result.pass_status = result.p99_delta_ms <= MAX_JITTER_MS

        self._print_result(result)
        return result

    def _print_result(self, r: JitterResult):
        status = '✅ PASS' if r.pass_status else '❌ FAIL'
        print(f'\n  ── Result: {status} ──')
        print(f'  Packets:      {r.total_packets}')
        print(f'  Avg Δt:       {r.avg_delta_ms:.2f}ms')
        print(f'  Min/Max Δt:   {r.min_delta_ms:.2f} / {r.max_delta_ms:.2f}ms')
        print(f'  Std Dev:      {r.stddev_delta_ms:.2f}ms')
        print(f'  P95 Δt:       {r.p95_delta_ms:.2f}ms')
        print(f'  P99 Δt:       {r.p99_delta_ms:.2f}ms')
        print(f'  Violations:   {r.jitter_violations} ({r.jitter_violation_pct:.1f}%)')
        print(f'  Sleep Mode:   {"⚠ DETECTED" if r.sleep_interference_detected else "None"}')
        print(f'\n  Delta Histogram:')
        total = sum(r.delta_histogram.values())
        for bucket, count in r.delta_histogram.items():
            pct = (count / total * 100) if total > 0 else 0
            bar = '█' * int(pct / 2)
            print(f'    {bucket:>10}: {count:5d} ({pct:5.1f}%) {bar}')


# ═══════════════════════════════════════════════════════════════════════
# Test C: Binary Integrity Check
# ═══════════════════════════════════════════════════════════════════════

class BinaryIntegrityCheck:
    """
    Checks for malformed packets where ADR-018 header
    doesn't match payload length.
    """

    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT,
                 duration_sec: int = 20):
        self.host = host
        self.port = port
        self.duration_sec = duration_sec

    def run(self) -> IntegrityResult:
        result = IntegrityResult()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))

        print(f'\n{"═" * 70}')
        print(f'  TEST C: BINARY INTEGRITY CHECK')
        print(f'  Listening on {self.host}:{self.port} for {self.duration_sec}s')
        print(f'  Validating ADR-018 header ↔ payload consistency')
        print(f'{"═" * 70}')

        test_start = time.monotonic()
        last_sequence = -1

        try:
            while (time.monotonic() - test_start) < self.duration_sec:
                try:
                    data, addr = sock.recvfrom(65535)
                    recv_time = time.monotonic()
                    result.total_packets += 1

                    pkt = parse_adr018_packet(data, recv_time)

                    if not pkt.is_valid:
                        result.malformed_packets += 1

                        if pkt.magic != MAGIC_CSI and pkt.magic != 0:
                            result.magic_errors += 1
                            if len(result.malformed_details) < 20:
                                result.malformed_details.append(
                                    f'[#{result.total_packets}] Bad magic: 0x{pkt.magic:08X}')

                        elif 'Payload truncated' in pkt.error:
                            result.length_errors += 1
                            if len(result.malformed_details) < 20:
                                result.malformed_details.append(
                                    f'[#{result.total_packets}] {pkt.error}')
                        else:
                            if len(result.malformed_details) < 20:
                                result.malformed_details.append(
                                    f'[#{result.total_packets}] {pkt.error}')
                        continue

                    result.valid_packets += 1

                    # Additional validation
                    if pkt.num_subcarriers not in (0, 26, 52, 56, 64, 114, 128, 242, 256):
                        result.subcarrier_errors += 1
                        if len(result.malformed_details) < 20:
                            result.malformed_details.append(
                                f'[#{result.total_packets}] Unusual subcarrier count: {pkt.num_subcarriers}')

                    # Sequence gap detection
                    if last_sequence >= 0 and pkt.sequence != last_sequence + 1:
                        gap = pkt.sequence - last_sequence
                        if gap > 1 and len(result.malformed_details) < 20:
                            result.malformed_details.append(
                                f'[#{result.total_packets}] Sequence gap: {last_sequence} → {pkt.sequence} (lost {gap - 1})')
                    last_sequence = pkt.sequence

                    # Periodic status
                    if result.total_packets % 500 == 0:
                        pct = (result.valid_packets / result.total_packets * 100)
                        print(f'  Checked {result.total_packets} packets — {pct:.1f}% valid')

                except socket.timeout:
                    continue

        except KeyboardInterrupt:
            print('\n  [!] Test interrupted by user')
        finally:
            sock.close()

        result.pass_status = (result.total_packets > 0 and
                              result.malformed_packets / max(1, result.total_packets) < 0.01)

        self._print_result(result)
        return result

    def _print_result(self, r: IntegrityResult):
        status = '✅ PASS' if r.pass_status else '❌ FAIL'
        print(f'\n  ── Result: {status} ──')
        print(f'  Total Packets:     {r.total_packets}')
        print(f'  Valid:             {r.valid_packets}')
        print(f'  Malformed:         {r.malformed_packets}')
        print(f'    Magic errors:    {r.magic_errors}')
        print(f'    Length errors:   {r.length_errors}')
        print(f'    Subcarrier errs: {r.subcarrier_errors}')
        if r.malformed_details:
            print(f'\n  Malformed Packet Details (first {len(r.malformed_details)}):')
            for d in r.malformed_details:
                print(f'    {d}')


# ═══════════════════════════════════════════════════════════════════════
# Test D: Distance Drop-Off (RSSI Degradation Simulation)
# ═══════════════════════════════════════════════════════════════════════

class DistanceDropOff:
    """
    Simulates RSSI degradation from -30dBm to -80dBm and identifies
    the point where CSI phase data becomes too corrupted for FFT.
    """

    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT):
        self.host = host
        self.port = port

    def run(self) -> DropOffResult:
        result = DropOffResult()

        print(f'\n{"═" * 70}')
        print(f'  TEST D: DISTANCE DROP-OFF (RSSI Degradation Simulation)')
        print(f'  Simulating RSSI: -30 dBm → -80 dBm')
        print(f'  Analyzing CSI phase coherence at each level')
        print(f'{"═" * 70}')

        rssi_levels = list(range(-30, -85, -5))  # -30, -35, ..., -80
        result.rssi_levels = rssi_levels

        for rssi in rssi_levels:
            print(f'\n  ── RSSI = {rssi} dBm ──')

            # Generate synthetic CSI packets at this RSSI level
            packets = self._generate_rssi_simulation(rssi, count=500)
            pps, phase_std, fft_viable = self._analyze_packets(packets, rssi)

            result.pps_per_rssi[rssi] = pps
            result.phase_std_per_rssi[rssi] = phase_std
            result.fft_viable_per_rssi[rssi] = fft_viable

            fft_str = '✓ VIABLE' if fft_viable else '✗ CORRUPTED'
            print(f'    PPS:        {pps:.1f}')
            print(f'    Phase σ:    {phase_std:.4f} rad')
            print(f'    FFT:        {fft_str}')

        # Find critical RSSI where FFT fails
        for rssi in rssi_levels:
            if not result.fft_viable_per_rssi.get(rssi, True):
                result.critical_rssi = rssi
                break

        result.pass_status = result.critical_rssi <= -70  # FFT should work to at least -70dBm

        self._print_result(result)
        return result

    def _generate_rssi_simulation(self, rssi: int, count: int = 500) -> List[ADR018Packet]:
        """Generate synthetic ADR-018 packets with noise proportional to RSSI."""
        packets = []

        # SNR model: lower RSSI → higher noise → more phase corruption
        # Typical noise floor is ~-90 dBm
        noise_floor = -90
        snr_db = rssi - noise_floor  # e.g., -30 - (-90) = 60 dB
        snr_linear = 10 ** (snr_db / 20.0)

        for seq in range(count):
            iq_data = bytearray()
            for sub in range(NUM_SUBCARRIERS):
                # Base signal: clean CSI tone
                phase = 2.0 * math.pi * sub / NUM_SUBCARRIERS
                amplitude = max(1, int(30 * (snr_linear / 1000.0)))
                amplitude = min(amplitude, 127)

                # Add Gaussian noise inversely proportional to SNR
                noise_power = max(0.5, 127.0 / snr_linear)
                re = int(amplitude * math.cos(phase) + random.gauss(0, noise_power))
                im = int(amplitude * math.sin(phase) + random.gauss(0, noise_power))

                # Clamp to int8 range
                re = max(-128, min(127, re))
                im = max(-128, min(127, im))
                iq_data.extend(struct.pack('<bb', re, im))

            # Build ADR-018 frame
            header = struct.pack(HEADER_FORMAT,
                                 MAGIC_CSI, 1, NUM_ANTENNAS, NUM_SUBCARRIERS,
                                 2412, seq, rssi, noise_floor)

            pkt = ADR018Packet(
                magic=MAGIC_CSI, node_id=1, num_antennas=NUM_ANTENNAS,
                num_subcarriers=NUM_SUBCARRIERS, freq_mhz=2412,
                sequence=seq, rssi=rssi, noise_floor=noise_floor,
                iq_data=bytes(iq_data),
                recv_timestamp=time.monotonic() + seq * 0.01,
                raw_length=HEADER_SIZE + len(iq_data),
                is_valid=True
            )
            packets.append(pkt)

        return packets

    def _analyze_packets(self, packets: List[ADR018Packet], rssi: int) -> Tuple[float, float, bool]:
        """Analyze CSI phase coherence for FFT viability."""
        if not packets:
            return 0.0, float('inf'), False

        # Effective PPS: model drop-off with distance
        # At -30 dBm → 100%, at -80 dBm → ~50% due to retransmissions
        drop_factor = max(0.3, 1.0 - ((abs(rssi) - 30) / 80.0))
        effective_pps = TARGET_PPS * drop_factor

        # Extract phase across packets for each subcarrier
        phase_stds = []
        for sub_idx in range(min(NUM_SUBCARRIERS, 10)):  # Sample 10 subcarriers
            phases = []
            for pkt in packets:
                offset = sub_idx * 2
                if offset + 1 < len(pkt.iq_data):
                    re = struct.unpack('<b', pkt.iq_data[offset:offset+1])[0]
                    im = struct.unpack('<b', pkt.iq_data[offset+1:offset+2])[0]
                    if re != 0 or im != 0:
                        phases.append(math.atan2(im, re))

            if len(phases) > 2:
                # Circular standard deviation for phase
                sin_sum = sum(math.sin(p) for p in phases)
                cos_sum = sum(math.cos(p) for p in phases)
                r_mean = math.sqrt(sin_sum**2 + cos_sum**2) / len(phases)
                circ_std = math.sqrt(-2.0 * math.log(max(1e-10, r_mean)))
                phase_stds.append(circ_std)

        avg_phase_std = statistics.mean(phase_stds) if phase_stds else float('inf')

        # FFT viability: phase std < π/4 (~0.785 rad)
        # Below this threshold, CSI phase data is too noisy for reliable FFT
        fft_threshold = math.pi / 4
        fft_viable = avg_phase_std < fft_threshold

        return effective_pps, avg_phase_std, fft_viable

    def _print_result(self, r: DropOffResult):
        status = '✅ PASS' if r.pass_status else '❌ FAIL'
        print(f'\n  ── Result: {status} ──')
        print(f'  Critical RSSI:  {r.critical_rssi} dBm (FFT fails beyond this)')
        print(f'\n  RSSI Drop-Off Table:')
        print(f'  {"RSSI":>6} | {"PPS":>6} | {"Phase σ":>10} | {"FFT":>10}')
        print(f'  {"─" * 6}─┼─{"─" * 6}─┼─{"─" * 10}─┼─{"─" * 10}')
        for rssi in r.rssi_levels:
            pps = r.pps_per_rssi.get(rssi, 0)
            phase = r.phase_std_per_rssi.get(rssi, 0)
            fft = '✓ VIABLE' if r.fft_viable_per_rssi.get(rssi, False) else '✗ CORRUPT'
            print(f'  {rssi:>4}dBm | {pps:>6.1f} | {phase:>8.4f}rad | {fft:>10}')


# ═══════════════════════════════════════════════════════════════════════
# Emitter: High-Fidelity ADR-018 Packet Generator (100 Hz)
# ═══════════════════════════════════════════════════════════════════════

class ADR018Emitter:
    """
    Generates and transmits synthetic ADR-018 packets at 100Hz
    for testing the receiver pipeline without ESP32 hardware.
    """

    def __init__(self, target_ip: str = '127.0.0.1', target_port: int = UDP_PORT,
                 rate_hz: int = 100, duration_sec: int = 30,
                 simulate_interference: bool = False):
        self.target_ip = target_ip
        self.target_port = target_port
        self.rate_hz = rate_hz
        self.duration_sec = duration_sec
        self.simulate_interference = simulate_interference
        self.sequence = 0

    def create_packet(self, rssi: int = -45) -> bytes:
        """Create a valid ADR-018 binary frame."""
        header = struct.pack(HEADER_FORMAT,
                             MAGIC_CSI,
                             1,                    # node_id
                             NUM_ANTENNAS,
                             NUM_SUBCARRIERS,
                             2412,                 # freq_mhz (channel 1)
                             self.sequence,
                             rssi,
                             -90)                  # noise_floor

        # Generate synthetic I/Q data (52 subcarriers × 2 bytes)
        iq_data = bytearray()
        t = time.monotonic()
        for sub in range(NUM_SUBCARRIERS):
            phase = 2.0 * math.pi * sub / NUM_SUBCARRIERS + 0.1 * math.sin(2 * math.pi * t)
            amplitude = 30
            re = int(amplitude * math.cos(phase) + random.gauss(0, 3))
            im = int(amplitude * math.sin(phase) + random.gauss(0, 3))
            re = max(-128, min(127, re))
            im = max(-128, min(127, im))
            iq_data.extend(struct.pack('<bb', re, im))

        self.sequence += 1
        return header + bytes(iq_data)

    def run(self):
        """Transmit packets at target rate."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        print(f'\n{"═" * 70}')
        print(f'  ADR-018 PACKET EMITTER')
        print(f'  Target: {self.target_ip}:{self.target_port}')
        print(f'  Rate: {self.rate_hz} Hz | Duration: {self.duration_sec}s')
        print(f'  Interference: {"ON" if self.simulate_interference else "OFF"}')
        print(f'{"═" * 70}')

        interval = 1.0 / self.rate_hz
        start = time.monotonic()
        sent = 0
        dropped = 0

        try:
            while (time.monotonic() - start) < self.duration_sec:
                loop_start = time.monotonic()

                # Simulate UAV flight interference
                rssi = -45
                if self.simulate_interference:
                    # Simulate RSSI fluctuations during flight
                    flight_time = time.monotonic() - start
                    rssi = int(-35 + -25 * math.sin(flight_time * 0.5) +
                               random.gauss(0, 5))
                    rssi = max(-80, min(-20, rssi))

                    # Simulate occasional packet drops during maneuvers
                    if random.random() < 0.02:  # 2% drop rate during interference
                        dropped += 1
                        self.sequence += 1  # Increment seq to create gap
                        time.sleep(interval)
                        continue

                pkt = self.create_packet(rssi=rssi)
                sock.sendto(pkt, (self.target_ip, self.target_port))
                sent += 1

                if sent % (self.rate_hz * 5) == 0:
                    elapsed = time.monotonic() - start
                    actual_pps = sent / elapsed if elapsed > 0 else 0
                    print(f'  TX: {sent} pkts | {actual_pps:.1f} PPS | RSSI: {rssi}dBm')

                # Precision sleep to maintain target rate
                elapsed = time.monotonic() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print('\n  [!] Emitter stopped by user')
        finally:
            sock.close()

        total_time = time.monotonic() - start
        print(f'\n  ── Emitter Summary ──')
        print(f'  Sent:     {sent} packets in {total_time:.1f}s')
        print(f'  Avg PPS:  {sent / total_time:.1f}')
        print(f'  Dropped:  {dropped} (simulated interference)')


# ═══════════════════════════════════════════════════════════════════════
# Link Optimization Report Generator
# ═══════════════════════════════════════════════════════════════════════

def generate_report(throughput: Optional[ThroughputResult],
                    jitter: Optional[JitterResult],
                    integrity: Optional[IntegrityResult],
                    dropoff: Optional[DropOffResult],
                    output_path: str):
    """Generate the Link Optimization Report in Markdown."""

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    report = f"""# 🛰️ Phantom Scan — Link Optimization Report
## ESP32-S3 ↔ Ground Control Station UDP Data Link Validation

**Generated:** {timestamp}
**Protocol:** UDP/5005 (ADR-018 Binary Frame Format)
**Target Spec:** 100 Hz, <1% packet loss, <10ms jitter (P99)

---

## Executive Summary

| Test | Status | Key Metric |
|------|--------|------------|
"""

    if throughput:
        status = '✅ PASS' if throughput.pass_status else '❌ FAIL'
        report += f'| A. Throughput Audit | {status} | Avg PPS: {throughput.avg_pps:.1f} |\n'

    if jitter:
        status = '✅ PASS' if jitter.pass_status else '❌ FAIL'
        report += f'| B. Latency Jitter | {status} | P99 Δt: {jitter.p99_delta_ms:.2f}ms |\n'

    if integrity:
        status = '✅ PASS' if integrity.pass_status else '❌ FAIL'
        pct = (integrity.valid_packets / max(1, integrity.total_packets)) * 100
        report += f'| C. Binary Integrity | {status} | Valid: {pct:.1f}% |\n'

    if dropoff:
        status = '✅ PASS' if dropoff.pass_status else '❌ FAIL'
        report += f'| D. Distance Drop-Off | {status} | Critical RSSI: {dropoff.critical_rssi}dBm |\n'

    report += '\n---\n\n'

    # Detailed sections
    if throughput:
        report += f"""## A. Throughput Audit

- **Duration:** {throughput.duration_sec:.1f}s
- **Total Packets:** {throughput.total_packets}
- **Average PPS:** {throughput.avg_pps:.1f} (target: ≥{PPS_PASS_THRESH})
- **Min/Max PPS:** {throughput.min_pps:.1f} / {throughput.max_pps:.1f}
- **Packet Loss:** {throughput.packets_lost} ({throughput.loss_percentage:.2f}%)
"""
        if throughput.bottleneck:
            report += f'- **Bottleneck:** {throughput.bottleneck}\n'
        report += '\n---\n\n'

    if jitter:
        report += f"""## B. Latency Jitter

- **Packets Analyzed:** {jitter.total_packets}
- **Avg Δt:** {jitter.avg_delta_ms:.2f}ms
- **Std Dev:** {jitter.stddev_delta_ms:.2f}ms
- **P95 Δt:** {jitter.p95_delta_ms:.2f}ms
- **P99 Δt:** {jitter.p99_delta_ms:.2f}ms
- **Jitter Violations (>{MAX_JITTER_MS}ms):** {jitter.jitter_violations} ({jitter.jitter_violation_pct:.1f}%)
- **WiFi Sleep Interference:** {'⚠ DETECTED' if jitter.sleep_interference_detected else 'Not detected'}

### Delta-T Histogram

| Bucket | Count | Percentage |
|--------|-------|------------|
"""
        for bucket, count in jitter.delta_histogram.items():
            total = sum(jitter.delta_histogram.values())
            pct = (count / total * 100) if total > 0 else 0
            report += f'| {bucket} | {count} | {pct:.1f}% |\n'
        report += '\n---\n\n'

    if integrity:
        report += f"""## C. Binary Integrity

- **Total Packets:** {integrity.total_packets}
- **Valid Packets:** {integrity.valid_packets}
- **Malformed Packets:** {integrity.malformed_packets}
  - Magic Errors: {integrity.magic_errors}
  - Length Errors: {integrity.length_errors}
  - Subcarrier Errors: {integrity.subcarrier_errors}
"""
        if integrity.malformed_details:
            report += '\n### Malformed Packet Log\n```\n'
            for d in integrity.malformed_details:
                report += f'{d}\n'
            report += '```\n'
        report += '\n---\n\n'

    if dropoff:
        report += f"""## D. Distance Drop-Off

- **Critical RSSI:** {dropoff.critical_rssi} dBm (FFT extraction fails beyond this)

### RSSI vs FFT Viability

| RSSI (dBm) | Effective PPS | Phase σ (rad) | FFT Status |
|------------|---------------|---------------|------------|
"""
        for rssi in dropoff.rssi_levels:
            pps = dropoff.pps_per_rssi.get(rssi, 0)
            phase = dropoff.phase_std_per_rssi.get(rssi, 0)
            fft = '✓ Viable' if dropoff.fft_viable_per_rssi.get(rssi, False) else '✗ Corrupted'
            report += f'| {rssi} | {pps:.1f} | {phase:.4f} | {fft} |\n'
        report += '\n---\n\n'

    # Optimization recommendations
    report += """## 🔧 Optimization Recommendations

### 1. WiFi Channel Selection
Auto-switch to least congested channel among 1, 6, 11.
See: `firmware/esp32-csi-node/main/channel_optimizer.c`

### 2. Circular Buffer (ESP32 C++)
Lock-free ring buffer prevents data drops during radio re-transmissions.
See: `firmware/esp32-csi-node/main/csi_ringbuffer.h`

### 3. AsyncUDP Implementation
Non-blocking UDP prevents WiFi stack from blocking CSI sensing core.
See: `firmware/esp32-csi-node/main/async_udp_sender.c`

### 4. Power Management Fix
Disable WiFi modem sleep during active sensing to eliminate DTIM-beacon jitter gaps.
Set: `esp_wifi_set_ps(WIFI_PS_NONE)` during burst windows.

---
*Report generated by Phantom Scan Network Link Validation Suite (VTP-NL-001)*
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f'\n  📄 Report saved: {output_path}')


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Phantom Scan — Network Link Validation Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tests:
  full        Run all 4 tests sequentially
  throughput  Test A: Throughput audit (PPS measurement)
  jitter      Test B: Latency jitter analysis
  integrity   Test C: Binary integrity check
  dropoff     Test D: Distance drop-off simulation
  emitter     Run the ADR-018 packet emitter (for testing without hardware)
        """
    )
    parser.add_argument('--mode', default='full',
                        choices=['full', 'throughput', 'jitter', 'integrity',
                                 'dropoff', 'emitter'],
                        help='Test mode to run')
    parser.add_argument('--host', default='0.0.0.0', help='UDP listen host')
    parser.add_argument('--port', type=int, default=UDP_PORT, help='UDP port')
    parser.add_argument('--duration', type=int, default=30,
                        help='Test duration in seconds')
    parser.add_argument('--target-ip', default='127.0.0.1',
                        help='Emitter target IP')
    parser.add_argument('--rate', type=int, default=100,
                        help='Emitter packet rate in Hz')
    parser.add_argument('--interference', action='store_true',
                        help='Simulate UAV flight interference in emitter')
    parser.add_argument('--report', default=None,
                        help='Output path for the Link Optimization Report')
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  PHANTOM SCAN — Network Link Validation Suite (VTP-NL-001)         ║
║  ESP32-S3 ↔ GCS UDP Data Link Validation                          ║
║  {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^66}  ║
╚══════════════════════════════════════════════════════════════════════╝""")

    if args.mode == 'emitter':
        emitter = ADR018Emitter(
            target_ip=args.target_ip, target_port=args.port,
            rate_hz=args.rate, duration_sec=args.duration,
            simulate_interference=args.interference)
        emitter.run()
        return

    throughput_result = None
    jitter_result = None
    integrity_result = None
    dropoff_result = None

    if args.mode in ('full', 'throughput'):
        audit = ThroughputAudit(args.host, args.port, args.duration)
        throughput_result = audit.run()

    if args.mode in ('full', 'jitter'):
        jitter = JitterAnalysis(args.host, args.port, args.duration)
        jitter_result = jitter.run()

    if args.mode in ('full', 'integrity'):
        integrity = BinaryIntegrityCheck(args.host, args.port, args.duration)
        integrity_result = integrity.run()

    if args.mode in ('full', 'dropoff'):
        dropoff = DistanceDropOff(args.host, args.port)
        dropoff_result = dropoff.run()

    # Generate report
    report_path = args.report or os.path.join(
        os.path.dirname(__file__), '..', 'docs', 'LINK_OPTIMIZATION_REPORT.md')
    generate_report(throughput_result, jitter_result, integrity_result,
                    dropoff_result, report_path)

    # Final summary
    all_pass = True
    for r in [throughput_result, jitter_result, integrity_result, dropoff_result]:
        if r and not r.pass_status:
            all_pass = False

    if all_pass:
        print('\n  ✅ ALL TESTS PASSED — Link meets operational requirements')
    else:
        print('\n  ❌ SOME TESTS FAILED — Review report for remediation steps')

    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
