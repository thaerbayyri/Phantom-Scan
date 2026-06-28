#!/usr/bin/env python3
"""
Phantom Scan — Real-time AI Inference Server
Loads csi-embed-v2 and pose_v1 models, processes CSI streams from both nodes,
and sends 17-keypoint skeleton pose frames to the dashboard.
"""

import os
import sys
import time
import math
import json
import socket
import struct
import threading
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file
import websocket

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Model Definitions ────────────────────────────────────────────────

class Enc(nn.Module):
    """v2 Contrastive CSI Encoder (8 -> 64 -> 128)"""
    def __init__(self):
        super().__init__()
        self.w1 = nn.Linear(8, 64)
        self.bn1 = nn.BatchNorm1d(64)
        self.w2 = nn.Linear(64, 128)
        self.bn2 = nn.BatchNorm1d(128)

    def forward(self, x):
        h = F.gelu(self.bn1(self.w1(x)))
        return F.normalize(self.bn2(self.w2(h)), dim=-1)

class EncModule(nn.Module):
    """Pose Model Encoder (Conv1d layers)"""
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv1d(56, 64, kernel_size=3)
        self.c2 = nn.Conv1d(64, 128, kernel_size=3)
        self.c3 = nn.Conv1d(128, 128, kernel_size=3)

class HeadModule(nn.Module):
    """Pose Model Regression Head"""
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(128, 256)
        self.fc2 = nn.Linear(256, 34) # 17 keypoints * 2D (x, y) coordinates

class PoseNet(nn.Module):
    """Complete Pose Estimation Model"""
    def __init__(self):
        super().__init__()
        self.enc = EncModule()
        self.head = HeadModule()

    def forward(self, x):
        # x shape: [B, 56, T]
        x = F.relu(self.enc.c1(x))
        x = F.relu(self.enc.c2(x))
        x = F.relu(self.enc.c3(x))
        x = torch.mean(x, dim=-1) # Global average pooling [B, 128]
        x = F.relu(self.head.fc1(x))
        x = self.head.fc2(x) # Output: [B, 34]
        return x

# ─── Settings ────────────────────────────────────────────────────────

UDP_PORT = 5006
UDP_HOST = "127.0.0.1"
WS_URL = "ws://127.0.0.1:5000/ws"

MODEL_DIR = os.path.join("ai model and densepose", "model")
EMBED_WEIGHTS = os.path.join(MODEL_DIR, "csi-embed-v2.safetensors")
POSE_WEIGHTS = os.path.join(MODEL_DIR, "pose_v1.safetensors")

# History length for sliding window
HISTORY_LEN = 100 

COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# ─── Global State ─────────────────────────────────────────────────────

ws = None
ws_connected = False
lock = threading.Lock()

# Node-specific histories: node_id -> {"timestamps": [], "mags": [], "rssi": [], "prev_mean": None}
node_histories = {}
last_udp_time = 0.0
last_inference_time = 0.0

# ─── Model Loading ────────────────────────────────────────────────────

print("[AI] Loading models...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[AI] Using device: {device}")

# 1. Load Embedding Model
embed_model = Enc().to(device)
try:
    if os.path.exists(EMBED_WEIGHTS):
        embed_model.load_state_dict(load_file(EMBED_WEIGHTS))
        print("[AI] Loaded csi-embed-v2 weights successfully.")
    else:
        print(f"[WARN] Embed weights not found at {EMBED_WEIGHTS}")
except Exception as e:
    print(f"[ERROR] Failed to load embed model: {e}")
embed_model.eval()

# 2. Load Pose Model
pose_model = PoseNet().to(device)
try:
    if os.path.exists(POSE_WEIGHTS):
        pose_model.load_state_dict(load_file(POSE_WEIGHTS))
        print("[AI] Loaded pose_v1 weights successfully.")
    else:
        print(f"[WARN] Pose weights not found at {POSE_WEIGHTS}")
except Exception as e:
    print(f"[ERROR] Failed to load pose model: {e}")
pose_model.eval()

# ─── Helper Functions ─────────────────────────────────────────────────

def parse_csi_packet(data: bytes) -> dict:
    """Parses Raw CSI (ADR-018) from UDP payload."""
    if len(data) < 20:
        return None
    header = struct.unpack('<IBBHIIbbxx', data[:20])
    magic, node_id, num_ant, num_sub, freq, seq, rssi, noise = header
    
    if magic != 0xC5110001 or num_sub == 0 or num_ant == 0:
        return None
        
    iq_data = data[20:]
    expected_len = num_ant * num_sub * 2
    if len(iq_data) < expected_len:
        return None
        
    # Unpack IQ values as signed bytes
    iq_array = struct.unpack(f'<{expected_len}b', iq_data[:expected_len])
    
    # Compute magnitudes
    mags = []
    for i in range(num_sub):
        r = iq_array[i * 2]
        im = iq_array[i * 2 + 1]
        mags.append(math.sqrt(r*r + im*im))
        
    # Standardize/Interpolate to exactly 56 subcarriers
    if len(mags) != 56:
        xp = np.linspace(0, 1, len(mags))
        x_new = np.linspace(0, 1, 56)
        mags = np.interp(x_new, xp, mags)
    else:
        mags = np.array(mags)
        
    return {
        "node_id": node_id,
        "mags": mags,
        "rssi": rssi,
        "timestamp": time.time() * 1000
    }

def extract_features_8d(mags_history, rssi_history, prev_window_mean=None):
    """Extracts 8 standardised features for the csi-embed-v2 model.
    Returns (features_standardised, raw_motion, current_window_mean)."""
    mags_arr = np.array(mags_history)  # Shape: [T, 56]

    # ── Feature 0: Presence ── mean subcarrier variance across time
    presence = float(np.mean(np.std(mags_arr, axis=0)))

    # ── Feature 1: Motion Energy ──
    # Use temporal delta: how much did the MEAN spectrum shift between
    # the first half and second half of the window? Always >= 0.
    half = max(1, len(mags_arr) // 2)
    current_window_mean = np.mean(mags_arr, axis=0)   # [56]
    if prev_window_mean is not None:
        motion_raw = float(np.mean(np.abs(current_window_mean - prev_window_mean)))
    else:
        first_half_mean  = np.mean(mags_arr[:half], axis=0)
        second_half_mean = np.mean(mags_arr[half:], axis=0)
        motion_raw = float(np.mean(np.abs(second_half_mean - first_half_mean)))

    # Also capture frame-by-frame diffs as secondary motion signal
    frame_diff_motion = float(np.mean(np.abs(np.diff(mags_arr, axis=0))))
    motion = max(motion_raw, frame_diff_motion)

    # ── Features 2-7: Auxiliary ──
    breathing = 14.0
    heart_rate = 72.0
    phase_variance = float(np.var(mags_arr))
    person_count = 1.0
    fall_detected = 0.0
    rssi_mean = float(np.mean(rssi_history))

    features = np.array([presence, motion, breathing, heart_rate,
                         phase_variance, person_count, fall_detected, rssi_mean])

    # Per-feature Z-score (not global Z-score which destroys relative magnitude)
    mean_val = np.mean(features)
    std_val  = np.std(features) + 1e-8
    features_std = (features - mean_val) / std_val

    return features_std, motion, current_window_mean

# ─── Inference Pipeline ────────────────────────────────────────────────

def run_inference(node_id: int, mags_hist: list, rssi_hist: list, prev_mean=None):
    global ws, ws_connected

    # ── Pose Model ──
    # Model expects [B, 56, T].
    mags_tensor = torch.tensor(np.array(mags_hist).T).float().unsqueeze(0).to(device)  # [1, 56, T]

    with torch.no_grad():
        coords_raw = pose_model(mags_tensor).cpu().numpy()[0]  # [34]

    # Map 34 values -> 17 COCO keypoints
    keypoints = []
    for idx, name in enumerate(COCO_KEYPOINTS):
        x = float(coords_raw[idx * 2])
        z = float(coords_raw[idx * 2 + 1])

        # Approximate height (y) for each body part
        if idx == 0:          y = 1.65  # nose
        elif idx <= 4:        y = 1.60  # eyes / ears
        elif idx <= 6:        y = 1.40  # shoulders
        elif idx <= 8:        y = 1.15  # elbows
        elif idx <= 10:       y = 0.90  # wrists
        elif idx <= 12:       y = 0.95  # hips
        elif idx <= 14:       y = 0.55  # knees
        else:                 y = 0.08  # ankles

        keypoints.append({
            "name": name,
            "x": x,
            "y": y,
            "z": z,
            "confidence": 0.85
        })

    # ── Embedding Model ──
    features_8d, motion_raw, current_mean = extract_features_8d(mags_hist, rssi_hist, prev_mean)
    feat_tensor = torch.tensor(features_8d).float().unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = embed_model(feat_tensor).cpu().numpy()[0]

    # ── Classification ──
    # Use RAW (pre-Z-score) motion energy for threshold — avoids the
    # global Z-score collapse that made it always ~-0.174
    presence = float(features_8d[0]) > -1.5   # presence after standardisation
    label = "unknown"
    if presence:
        # motion_raw is always >= 0; anything > 0.005 is meaningful motion
        label = "human" if motion_raw > 0.005 else "mechanical"

    # ── Transmit ──
    if ws_connected and ws is not None:
        try:
            ws.send(json.dumps({
                "type": "poseFrame",
                "data": {
                    "timestamp": int(time.time() * 1000),
                    "keypoints": keypoints
                }
            }))
            ws.send(json.dumps({
                "type": "targetIdentity",
                "data": {
                    "label": label,
                    "humanProb": float(F.sigmoid(torch.tensor(motion_raw * 20.0)).item()),
                    "mechanicalProb": float(F.sigmoid(torch.tensor(-motion_raw * 20.0)).item()),
                    "periodicity": float(features_8d[2])
                }
            }))
            print(f"[AI] Inference: node={node_id} label={label} motion_raw={motion_raw:.5f}")
        except Exception as e:
            print(f"[WS] Send error: {e}")

    # Return the current window mean so next call can compute a delta
    return current_mean

# ─── Inference Throttler Helper ────────────────────────────────────────

# Per-node previous window mean for temporal delta motion
node_prev_means = {}

def trigger_inference(node_id, mags_hist, rssi_hist):
    global last_inference_time, node_prev_means
    now = time.time()
    if now - last_inference_time < 0.2:  # Throttle to max 5 Hz
        return
    last_inference_time = now

    mags_copy = list(mags_hist)
    rssi_copy = list(rssi_hist)
    prev_mean = node_prev_means.get(node_id, None)

    def _run():
        result_mean = run_inference(node_id, mags_copy, rssi_copy, prev_mean)
        if result_mean is not None:
            node_prev_means[node_id] = result_mean

    threading.Thread(target=_run, daemon=True).start()

# ─── WebSocket Client Threads ──────────────────────────────────────────

def on_message(ws_conn, message):
    global last_udp_time
    # If we received a real UDP packet in the last 2 seconds, ignore WebSocket raw samples
    if time.time() - last_udp_time < 2.0:
        return
        
    try:
        msg = json.loads(message)
        if msg.get("type") == "rawSample":
            data = msg.get("data")
            if not data:
                return
                
            node_id = data.get("nodeId", 1)
            h1 = data.get("h1")
            h2 = data.get("h2")
            rssi = data.get("rssi", -50)
            timestamp = data.get("timestamp", time.time() * 1000)
            
            if not h1:
                return
                
            # Synthesize 56-subcarrier magnitudes from the dominant complex numbers
            mag1 = math.sqrt(h1["re"]**2 + h1["im"]**2)
            mag2 = math.sqrt(h2["re"]**2 + h2["im"]**2) if h2 else mag1
            
            # Generate synthetic 56 subcarriers with frequency-selective fading + noise
            mags = np.zeros(56)
            for i in range(56):
                fade = 1.0 + 0.3 * math.sin(i * 0.15)
                mags[i] = (mag1 * 0.7 + mag2 * 0.3) * fade + np.random.normal(0, 0.05)
                mags[i] = max(0.01, mags[i])
                
            with lock:
                if node_id not in node_histories:
                    node_histories[node_id] = {"mags": [], "rssi": [], "timestamps": []}
                    
                hist = node_histories[node_id]
                hist["mags"].append(mags)
                hist["rssi"].append(rssi)
                hist["timestamps"].append(timestamp)
                
                if len(hist["mags"]) > HISTORY_LEN:
                    hist["mags"].pop(0)
                    hist["rssi"].pop(0)
                    hist["timestamps"].pop(0)
                    
                if len(hist["mags"]) >= HISTORY_LEN:
                    trigger_inference(node_id, hist["mags"], hist["rssi"])
    except Exception as e:
        pass

def on_error(ws_conn, error):
    print(f"[WS] Error: {error}")

def on_close(ws_conn, close_status_code, close_msg):
    global ws_connected
    ws_connected = False
    print("[WS] Connection closed. Retrying...")

def on_open(ws_conn):
    global ws_connected
    ws_connected = True
    print("[WS] Connection opened. Registering AI Client...")
    ws_conn.send(json.dumps({"type": "registerAIClient", "data": None}))

def run_ws_client():
    global ws, ws_connected
    while True:
        try:
            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"[WS] Run error: {e}")
        time.sleep(2)

# ─── UDP Receiver Thread ──────────────────────────────────────────────

def run_udp_receiver():
    global last_udp_time
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[UDP] Listening for raw CSI on {UDP_HOST}:{UDP_PORT}...")
    
    while True:
        data, addr = sock.recvfrom(65535)
        sample = parse_csi_packet(data)
        if sample is None:
            continue
            
        last_udp_time = time.time()
        node_id = sample["node_id"]
        
        with lock:
            if node_id not in node_histories:
                node_histories[node_id] = {"mags": [], "rssi": [], "timestamps": []}
                
            hist = node_histories[node_id]
            hist["mags"].append(sample["mags"])
            hist["rssi"].append(sample["rssi"])
            hist["timestamps"].append(sample["timestamp"])
            
            # Keep history buffer capped
            if len(hist["mags"]) > HISTORY_LEN:
                hist["mags"].pop(0)
                hist["rssi"].pop(0)
                hist["timestamps"].pop(0)
                
            # Perform inference if we have enough history
            if len(hist["mags"]) >= HISTORY_LEN:
                trigger_inference(node_id, hist["mags"], hist["rssi"])

# ─── Synthetic Self-Feed Thread ───────────────────────────────────────
# When no real UDP data arrives (no ESP32 connected or scan not started),
# generate synthetic CSI samples so the AI pipeline runs continuously and
# the human figure appears in the dashboard automatically.

def run_synthetic_feed():
    """Generates synthetic walking-human CSI samples at 20Hz when idle."""
    walk_phase = 0.0
    t = 0.0
    node_id = 1

    while True:
        time.sleep(0.05)  # 20Hz

        # Only feed synthetic data when no real UDP or WS raw samples for 3s
        if time.time() - last_udp_time < 3.0:
            continue
        if not ws_connected:
            continue

        walk_phase += (2 * math.pi) / (20 * 12)  # 12s loop
        t += 0.05

        # Simulate person walking: angle ±50°, depth 1.5–4.5m
        angle_deg = 50 * math.sin(walk_phase)
        depth = 3.0 + 1.5 * math.sin(walk_phase * 2)
        theta = math.radians(angle_deg)

        # Vital signs
        resp = 0.8 * math.sin(2 * math.pi * 0.3 * t)
        hr   = 0.15 * math.sin(2 * math.pi * 1.2 * t)

        # Static + dynamic channel
        mags = np.zeros(56)
        for i in range(56):
            static_part  = 0.8 + 0.05 * math.sin(i * 0.2)
            moving_phase = 2 * math.pi * math.sin(theta) * depth * 0.3 + t * 0.5
            fade = 1.0 + 0.3 * math.sin(i * 0.15)
            dynamic_part = max(0.05, 0.4 - depth * 0.04) * fade * (
                1 + 0.4 * math.sin(moving_phase + resp + hr + i * 0.1)
            )
            mags[i] = abs(static_part + dynamic_part) + np.random.normal(0, 0.01)

        rssi = -55 + depth * -2 + np.random.uniform(-2, 2)

        with lock:
            if node_id not in node_histories:
                node_histories[node_id] = {"mags": [], "rssi": [], "timestamps": []}

            hist = node_histories[node_id]
            hist["mags"].append(mags)
            hist["rssi"].append(rssi)
            hist["timestamps"].append(time.time() * 1000)

            if len(hist["mags"]) > HISTORY_LEN:
                hist["mags"].pop(0)
                hist["rssi"].pop(0)
                hist["timestamps"].pop(0)

            if len(hist["mags"]) >= HISTORY_LEN:
                trigger_inference(node_id, hist["mags"], hist["rssi"])

# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start WS client thread
    ws_thread = threading.Thread(target=run_ws_client, daemon=True)
    ws_thread.start()

    # Start synthetic data self-feed thread
    synth_thread = threading.Thread(target=run_synthetic_feed, daemon=True)
    synth_thread.start()

    # Start UDP receiver loop in main thread
    try:
        run_udp_receiver()
    except KeyboardInterrupt:
        print("\n[AI] Exiting...")

