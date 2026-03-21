#!/usr/bin/env python3
"""
Phantom Scan — Multi-protocol UDP Parser (ADR-018 & Vitals)

Listens on UDP port 5005 for binary packets from ESP32-S3 nodes.
Parses both 0xC5110001 (Raw CSI) and 0xC5110002 (Tier 2 Vitals/Presence).
"""

import socket
import struct
import argparse
import time

MAGIC_CSI = 0xC5110001
MAGIC_VITALS = 0xC5110002

def parse_csi_packet(data: bytes, addr):
    """Parses ADR-018 Raw CSI Packet."""
    if len(data) < 20:
        return
    
    # Header format: <I B B H I I b b x x
    # I: Magic (4)
    # B: Node ID (1)
    # B: Num Antennas (1)
    # H: Num Subcarriers (2)
    # I: Freq MHz (4)
    # I: Sequence (4)
    # b: RSSI (1)
    # b: Noise (1)
    # 2 bytes reserved
    header = struct.unpack('<IBBHIIbbxx', data[:20])
    magic, node_id, num_ant, num_sub, freq, seq, rssi, noise = header
    
    expected_iq_len = num_ant * num_sub * 2 # 2 bytes per subcarrier (I/Q)
    if len(data) < 20 + expected_iq_len:
        print(f"[WARN] Incomplete CSI packet from {addr}")
        return
        
    print(f"[{time.strftime('%H:%M:%S')}] [CSI] Node {node_id} | Antennas: {num_ant} | Subcarriers: {num_sub} | RSSI: {rssi} dBm")
    # I/Q parsing would follow here based on (data[20:])
    # e.g., struct.unpack(f'<{expected_iq_len}b', data[20:])

def parse_vitals_packet(data: bytes, addr):
    """Parses Tier 2 Vitals Packet."""
    if len(data) < 32:
        return

    # Header format: <I B B H I b B x x f f I x x x x
    # Note: 32 bytes total. Let's strictly follow the ADR-018 Vitals struct:
    # 0: Magic (4)
    # 4: Node ID (1)
    # 5: Flags (1)
    # 6: Breathing rate (2)
    # 8: Heart rate (4)
    # 12: RSSI (1)
    # 13: Num persons (1)
    # 14: Reserved (2)
    # 16: Motion energy (4) -> f32
    # 20: Presence score (4) -> f32
    # 24: Timestamp (4) -> u32
    # 28: Reserved (4)
    
    unpacked = struct.unpack('<IBBH I bBxx f f I 4x', data[:32])
    magic, node_id, flags, breathing_fp, hr_fp, rssi, n_persons, motion_e, presence_score, ts_ms = unpacked
    
    presence = (flags & 0x01) > 0
    fall_flag = (flags & 0x02) > 0
    motion_flag = (flags & 0x04) > 0
    
    breathing_bpm = breathing_fp / 100.0
    heart_bpm = hr_fp / 10000.0
    
    presence_str = "YES" if presence else "NO"
    fall_str = "DETECTED!" if fall_flag else "None"
    
    print(f"[{time.strftime('%H:%M:%S')}] [VITALS] Node {node_id} | Presence: {presence_str} ({presence_score:.2f}) | "
          f"Persons: {n_persons} | BPM: {breathing_bpm:.1f} | HR: {heart_bpm:.1f} | Fall: {fall_str} | RSSI: {rssi}")

def main():
    parser = argparse.ArgumentParser(description="UDP Receiver for ESP32 Firmware")
    parser.add_argument("--port", type=int, default=5005, help="UDP Port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    
    print(f"Listening for UDP packets on {args.host}:{args.port}...")
    
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            if len(data) < 4:
                continue
                
            magic = struct.unpack('<I', data[:4])[0]
            
            if magic == MAGIC_CSI:
                parse_csi_packet(data, addr)
            elif magic == MAGIC_VITALS:
                parse_vitals_packet(data, addr)
            else:
                # Could be Magic 0xC5110004 WASM output
                pass
                
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
