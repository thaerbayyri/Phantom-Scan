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

# Node-specific histories: node_id -> {"timestamps": [], "mags": [], "rssi": []}
node_histories = {}
last_udp_time = 0.0

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

def extract_features_8d(mags_history, rssi_history):
    """Extracts 8 standardized features for the csi-embed-v2 model."""
    mags_arr = np.array(mags_history) # Shape: [T, 56]
    
    # Presence: mean subcarrier standard deviation
    presence = float(np.mean(np.std(mags_arr, axis=0)))
    
    # Motion: average step-by-step diff of magnitudes
    motion = float(np.mean(np.abs(np.diff(mags_arr, axis=0))))
    
    # Vitals mock extraction (simplification for raw inputs)
    breathing = 14.0 # default baseline BPM
    heart_rate = 72.0 # default baseline BPM
    phase_variance = float(np.var(mags_arr)) # simple variance proxy
    person_count = 1.0
    fall_detected = 0.0
    rssi_mean = float(np.mean(rssi_history))
    
    features = [presence, motion, breathing, heart_rate, phase_variance, person_count, fall_detected, rssi_mean]
    
    # Z-score standardization baseline
    features = np.array(features)
    mean_val = np.mean(features)
    std_val = np.std(features) + 1e-8
    features_standardized = (features - mean_val) / std_val
    
    return features_standardized

# ─── Inference Pipeline ────────────────────────────────────────────────

def run_inference(node_id: int, mags_hist: list, rssi_hist: list):
    global ws, ws_connected
    
    # Prepare input for Pose model
    # Model expects [B, 56, T].
    # mags_hist is length T, containing 56-dim arrays -> reshape to [56, T]
    mags_tensor = torch.tensor(np.array(mags_hist).T).float().unsqueeze(0).to(device) # Shape [1, 56, 100]
    
    # Run Pose Model
    with torch.no_grad():
        coords_raw = pose_model(mags_tensor).cpu().numpy()[0] # Shape [34]
    
    # Map 34 output values to 17 COCO 3D/2D keypoints
    keypoints = []
    for idx, name in enumerate(COCO_KEYPOINTS):
        x = float(coords_raw[idx * 2])
        z = float(coords_raw[idx * 2 + 1]) # we treat second dim as horizontal depth (z)
        
        # Approximate standard height (y) based on joint height rules
        # Nose starts at ~1.65m, ankles at 0m.
        y = 1.65 - (idx * 0.1) 
        if idx >= 11: # hips/knees/ankles lower down
            y = 0.8 - (idx - 11) * 0.25
        y = max(0.05, y)
        
        keypoints.append({
            "name": name,
            "x": x,
            "y": y,
            "z": z,
            "confidence": 0.8
        })
        
    # Run Embedding Model
    features_8d = extract_features_8d(mags_hist, rssi_hist)
    feat_tensor = torch.tensor(features_8d).float().unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = embed_model(feat_tensor).cpu().numpy()[0]
        
    # Compute downstream values
    presence = float(features_8d[0]) > 0.05
    motion_energy = float(features_8d[1])
    
    label = "unknown"
    if presence:
        label = "human" if motion_energy > 0.1 else "mechanical"
        
    # Send frames via WebSocket
    if ws_connected and ws is not None:
        try:
            # 1. Pose Frame
            ws.send(json.dumps({
                "type": "poseFrame",
                "data": {
                    "timestamp": int(time.time() * 1000),
                    "keypoints": keypoints
                }
            }))
            
            # 2. Target Identity Update
            ws.send(json.dumps({
                "type": "targetIdentity",
                "data": {
                    "label": label,
                    "humanProb": float(F.sigmoid(torch.tensor(motion_energy)).item()),
                    "mechanicalProb": float(F.sigmoid(torch.tensor(1.0 - motion_energy)).item()),
                    "periodicity": float(features_8d[2])
                }
            }))
            print(f"[AI] Inference run completed for node {node_id}: label={label}, motion={motion_energy:.3f}")
        except Exception as e:
            print(f"[WS] Send error: {e}")

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
                    mags_copy = list(hist["mags"])
                    rssi_copy = list(hist["rssi"])
                    threading.Thread(
                        target=run_inference,
                        args=(node_id, mags_copy, rssi_copy),
                        daemon=True
                    ).start()
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
                # Trigger inference in a background thread to prevent blocking receiver
                mags_copy = list(hist["mags"])
                rssi_copy = list(hist["rssi"])
                threading.Thread(
                    target=run_inference,
                    args=(node_id, mags_copy, rssi_copy),
                    daemon=True
                ).start()

# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start WS client thread
    ws_thread = threading.Thread(target=run_ws_client, daemon=True)
    ws_thread.start()
    
    # Start UDP receiver loop in main thread
    try:
        run_udp_receiver()
    except KeyboardInterrupt:
        print("\n[AI] Exiting...")
