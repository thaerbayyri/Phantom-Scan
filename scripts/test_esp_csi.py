#!/usr/bin/env python3
"""
Phantom Scan — Quick ESP32-S3 CSI Connection Test

Tests two things:
  1. SERIAL: Can we read boot logs from the ESP32 on COM5?
  2. UDP:    Is the ESP32 sending ADR-018 CSI packets to port 5005?

Usage:
    python scripts/test_esp_csi.py                  # Run both tests
    python scripts/test_esp_csi.py --test serial     # Serial only
    python scripts/test_esp_csi.py --test udp        # UDP listener only
    python scripts/test_esp_csi.py --test monitor     # Serial monitor (live log view)
"""

import argparse
import socket
import struct
import sys
import time
from datetime import datetime


# ── ADR-018 Constants ────────────────────────────────────────────────
MAGIC_CSI    = 0xC5110001
MAGIC_VITALS = 0xED6E5C01
HEADER_SIZE  = 20
HEADER_FMT   = '<IBBHIIBB2x'   # 20 bytes


def test_serial(port: str = "COM5", baud: int = 115200, duration: int = 10):
    """Read ESP32 serial output for <duration> seconds and report what we see."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        return False

    print(f"\n{'═' * 60}")
    print(f"  TEST 1: SERIAL MONITOR — {port} @ {baud} baud")
    print(f"  Listening for {duration}s …")
    print(f"{'═' * 60}\n")

    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"  ❌ Cannot open {port}: {e}")
        print(f"     Is the ESP32 plugged in? Is another program using {port}?")
        return False

    print(f"  ✓ Opened {port}")
    line_count = 0
    csi_lines = 0
    wifi_connected = False
    ip_address = None
    start = time.time()

    try:
        while (time.time() - start) < duration:
            raw = ser.readline()
            if not raw:
                continue

            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                continue

            if not line:
                continue

            line_count += 1

            # Detect key events
            if "Got IP:" in line:
                wifi_connected = True
                # Try to extract IP
                idx = line.find("Got IP:")
                if idx >= 0:
                    ip_address = line[idx + 7:].strip()

            if "CSI cb" in line or "CSI_DATA" in line:
                csi_lines += 1

            # Print every line (live monitor)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{ts}] {line}")

    except KeyboardInterrupt:
        print("\n  [Interrupted]")
    finally:
        ser.close()

    # Summary
    print(f"\n{'─' * 60}")
    print(f"  SERIAL SUMMARY ({duration}s)")
    print(f"{'─' * 60}")
    print(f"  Total lines received:    {line_count}")
    print(f"  CSI callback logs:       {csi_lines}")
    print(f"  WiFi connected:          {'✅ YES' if wifi_connected else '❌ NO'}")
    if ip_address:
        print(f"  ESP32 IP address:        {ip_address}")
    print()

    if line_count == 0:
        print("  ⚠  No serial output. Possible causes:")
        print("     • ESP32 is not powered / not flashed")
        print("     • Wrong COM port (check Device Manager)")
        print("     • Wrong baud rate (try 460800 or 921600)")
        return False

    if not wifi_connected:
        print("  ⚠  WiFi not connected. Check your SSID/password in nvs_config.c")
        print("     Check the NVS-provisioned SSID/target_ip (see firmware/esp32-csi-node/PROVISIONING.md)")

    return line_count > 0


def test_udp(host: str = "0.0.0.0", port: int = 5005, duration: int = 15):
    """Listen for ADR-018 CSI packets on UDP."""
    print(f"\n{'═' * 60}")
    print(f"  TEST 2: UDP CSI LISTENER — {host}:{port}")
    print(f"  Waiting for ADR-018 packets for {duration}s …")
    print(f"  (ESP32 must be connected to WiFi and sending to this PC)")
    print(f"{'═' * 60}\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
    sock.settimeout(2.0)

    try:
        sock.bind((host, port))
    except OSError as e:
        print(f"  ❌ Cannot bind to port {port}: {e}")
        print(f"     Is another program using port {port}? (dashboard server?)")
        return False

    print(f"  ✓ Listening on UDP port {port}")

    total_packets = 0
    valid_csi = 0
    valid_vitals = 0
    invalid = 0
    first_packet_time = None
    last_rssi = None
    last_channel = None
    sources = set()
    start = time.time()

    try:
        while (time.time() - start) < duration:
            try:
                data, addr = sock.recvfrom(65535)
                recv_time = time.time()
                total_packets += 1

                if first_packet_time is None:
                    first_packet_time = recv_time
                    wait_time = recv_time - start
                    print(f"  ✓ First packet after {wait_time:.1f}s from {addr[0]}:{addr[1]}")

                sources.add(addr[0])

                if len(data) < HEADER_SIZE:
                    invalid += 1
                    continue

                magic = struct.unpack('<I', data[:4])[0]

                if magic == MAGIC_CSI:
                    valid_csi += 1
                    hdr = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
                    node_id = hdr[1]
                    n_ant = hdr[2]
                    n_sub = hdr[3]
                    freq = hdr[4]
                    seq = hdr[5]
                    rssi = struct.unpack('b', struct.pack('B', hdr[6]))[0]
                    noise = struct.unpack('b', struct.pack('B', hdr[7]))[0]
                    last_rssi = rssi
                    iq_len = len(data) - HEADER_SIZE

                    # Derive channel from freq
                    if 2412 <= freq <= 2484:
                        last_channel = (freq - 2412) // 5 + 1
                    elif freq > 5000:
                        last_channel = (freq - 5000) // 5

                    if valid_csi <= 5 or valid_csi % 100 == 0:
                        print(f"  [CSI #{valid_csi:>5}] node={node_id} "
                              f"ant={n_ant} sub={n_sub} ch={last_channel} "
                              f"rssi={rssi}dBm seq={seq} iq={iq_len}B")

                elif magic == MAGIC_VITALS:
                    valid_vitals += 1
                    if valid_vitals <= 3:
                        print(f"  [VITALS #{valid_vitals}] Edge vitals packet ({len(data)}B)")

                else:
                    invalid += 1
                    if invalid <= 3:
                        print(f"  [?] Unknown magic: 0x{magic:08X} ({len(data)}B)")

            except socket.timeout:
                elapsed = time.time() - start
                if total_packets == 0:
                    print(f"  … waiting ({elapsed:.0f}s / {duration}s)")

    except KeyboardInterrupt:
        print("\n  [Interrupted]")
    finally:
        sock.close()

    # Calculate PPS
    elapsed = time.time() - start
    pps = valid_csi / elapsed if elapsed > 0 else 0

    # Summary
    print(f"\n{'─' * 60}")
    print(f"  UDP SUMMARY ({elapsed:.1f}s)")
    print(f"{'─' * 60}")
    print(f"  Total UDP packets:       {total_packets}")
    print(f"  Valid CSI (ADR-018):      {valid_csi}")
    print(f"  Valid Vitals:            {valid_vitals}")
    print(f"  Invalid/Unknown:         {invalid}")
    print(f"  Average PPS:             {pps:.1f} packets/sec")
    print(f"  Sources:                 {', '.join(sources) if sources else 'none'}")
    if last_rssi is not None:
        print(f"  Last RSSI:               {last_rssi} dBm")
    if last_channel is not None:
        print(f"  Last Channel:            {last_channel}")
    print()

    if total_packets == 0:
        print("  ⚠  No UDP packets received. Checklist:")
        print("     1. Is ESP32 connected to the NVS-provisioned WiFi network?")
        print("     2. Is target_ip set to THIS PC's IP (192.168.1.155)?")
        print("     3. Is Windows Firewall blocking UDP port 5005?")
        print("        → Run: New-NetFirewallRule -DisplayName 'Phantom CSI' "
              "-Direction Inbound -Protocol UDP -LocalPort 5005 -Action Allow")
        print("     4. Are both devices on the same subnet?")
        return False

    if valid_csi > 0:
        print(f"  ✅ CSI data is flowing! ({pps:.1f} PPS)")
    return valid_csi > 0


def test_serial_monitor(port: str = "COM5", baud: int = 115200):
    """Continuous serial monitor — like idf.py monitor, runs until Ctrl+C."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        return

    print(f"\n{'═' * 60}")
    print(f"  SERIAL MONITOR — {port} @ {baud}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'═' * 60}\n")

    try:
        ser = serial.Serial(port, baud, timeout=0.1)
    except Exception as e:
        print(f"  ❌ Cannot open {port}: {e}")
        return

    try:
        while True:
            raw = ser.readline()
            if raw:
                try:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{ts}] {line}")
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
    finally:
        ser.close()


def main():
    parser = argparse.ArgumentParser(description="Phantom Scan — ESP32 CSI Connection Test")
    parser.add_argument("--test", choices=["serial", "udp", "both", "monitor"],
                        default="both", help="Which test to run (default: both)")
    parser.add_argument("--port", default="COM5", help="Serial port (default: COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--duration", type=int, default=15, help="Test duration in seconds (default: 15)")
    parser.add_argument("--udp-port", type=int, default=5005, dest="udp_port",
                        help="UDP port to listen on (default: 5005)")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  PHANTOM SCAN — ESP32-S3 CSI Connection Test            ║")
    print("╚══════════════════════════════════════════════════════════╝")

    results = {}

    if args.test == "monitor":
        test_serial_monitor(args.port, args.baud)
        return

    if args.test in ("serial", "both"):
        results["serial"] = test_serial(args.port, args.baud, args.duration)

    if args.test in ("udp", "both"):
        results["udp"] = test_udp("0.0.0.0", args.udp_port, args.duration)

    # Final verdict
    print(f"\n{'═' * 60}")
    print(f"  FINAL VERDICT")
    print(f"{'═' * 60}")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name.upper():>10}: {status}")

    all_pass = all(results.values())
    if all_pass:
        print(f"\n  🎉 All tests passed! CSI pipeline is operational.")
        print(f"     You can now run the full dashboard: npm run dev")
    else:
        print(f"\n  ⚠  Some tests failed. Check the details above.")
    print()


if __name__ == "__main__":
    main()
