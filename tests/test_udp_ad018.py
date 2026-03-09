import socket
import struct
import time
import random

# ADR-018 Frame Format
# [0..3]   Magic: 0xC5110001 (LE)
# [4]      Node ID
# [5]      Number of antennas
# [6..7]   Number of subcarriers (LE u16)
# [8..11]  Frequency MHz (LE u32)
# [12..15] Sequence number (LE u32)
# [16]     RSSI (i8)
# [17]     Noise floor (i8)
# [18..19] Reserved
# [20..]   I/Q data (raw bytes)

UDP_IP = "127.0.0.1"
UDP_PORT = 5005

print(f"UDP target IP: {UDP_IP}")
print(f"UDP target port: {UDP_PORT}")

sock = socket.socket(socket.AF_INET, socket.socket.SOCK_DGRAM)

num_antennas = 1
num_subcarriers = 10  # Sending 10 just to test parsing

def create_mock_frame(sequence):
    magic = 0xC5110001
    node_id = 1
    freq_mhz = 2412
    rssi = -55
    noise = -90
    
    # Pack Header (20 bytes)
    # < I B B H I I b b x x
    # I = 4, B = 1, B = 1, H = 2, I = 4, I = 4, b = 1, b = 1, x = 1, x = 1 (Total 20)
    header = struct.pack('<IBBHIIbbxx', 
                         magic, 
                         node_id, 
                         num_antennas, 
                         num_subcarriers, 
                         freq_mhz, 
                         sequence, 
                         rssi, 
                         noise)
    
    # Mock IQ data 
    # 1 antenna * 10 subcarriers * 2 bytes = 20 bytes
    iq_data = bytearray()
    for _ in range(num_subcarriers):
        # Generate some synthetic movement
        re = int(random.uniform(-50, 50))
        im = int(random.uniform(-50, 50))
        iq_data.extend(struct.pack('<bb', re, im))
        
    return header + iq_data

print("Starting UDP transmission...")
seq = 0
try:
    while True:
        frame = create_mock_frame(seq)
        sock.sendto(frame, (UDP_IP, UDP_PORT))
        seq += 1
        time.sleep(0.05) # ~20 FPS
except KeyboardInterrupt:
    print("\nStopped.")
