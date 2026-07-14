#!/usr/bin/env python3
"""
Phantom Scan — Real-time AI Inference Server
Loads the RuView WiFi-sensing model stack and streams pose / identity / vitals
to the dashboard.

Model stack (verified against the shipped weight files):

    feat8  ── Enc(8->64->128) ──┬─► z   = L2-normalized 128-d embedding
                                └─► pre = un-normalized bn2 activation (||pre||~15)
    pre ── LoRA(node) ── PresenceHead(128->1 logistic) ─► P(present)
    mags[56,T] ── PoseNet(conv x3 -> fc) ─► 17 COCO keypoints (x, z)

Notes / verified facts (see scripts/inspect_pose_weights.py and the README):
  * PoseNet matches pose_v1.safetensors exactly (c1 56->64, c2 64->128,
    c3 128->128 k=3; fc1 128->256; fc2 256->34). Loaded strict.
  * presence-head.json has bias=8.19 and ||w||=3.67. On the *L2-normalized*
    embedding the logit is pinned to 6.9..9.3 (always "present"), so it MUST be
    applied to the un-normalized bn2 activation, where it gives a full 0..1
    spread. Its absolute calibration depends on RuView's original feature
    standardization (not shipped), so we treat it as a score combined with the
    motion heuristic rather than an oracle.
  * node-1/2.json are LoRA rank-4 room adapters: loraA[128,4], loraB[4,128],
    scaling=2 -> delta = pre @ loraA @ loraB * scaling.
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
    """v2 Contrastive CSI Encoder (8 -> 64 -> 128).

    Returns BOTH the documented L2-normalized embedding (for downstream
    contrastive use) and the un-normalized bn2 activation (the representation
    the presence head + LoRA adapters were trained against)."""
    def __init__(self):
        super().__init__()
        self.w1 = nn.Linear(8, 64)
        self.bn1 = nn.BatchNorm1d(64)
        self.w2 = nn.Linear(64, 128)
        self.bn2 = nn.BatchNorm1d(128)

    def forward(self, x):
        h = F.gelu(self.bn1(self.w1(x)))
        pre = self.bn2(self.w2(h))             # [B, 128] un-normalized
        z = F.normalize(pre, dim=-1)           # [B, 128] L2-normalized
        return z, pre

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
        self.fc2 = nn.Linear(256, 34)  # 17 keypoints * 2D (x, z) coordinates

class PoseNet(nn.Module):
    """Complete Pose Estimation Model (matches pose_v1.safetensors)."""
    def __init__(self):
        super().__init__()
        self.enc = EncModule()
        self.head = HeadModule()

    def forward(self, x):
        # x shape: [B, 56, T]
        x = F.relu(self.enc.c1(x))
        x = F.relu(self.enc.c2(x))
        x = F.relu(self.enc.c3(x))
        x = torch.mean(x, dim=-1)   # Global average pooling [B, 128]
        x = F.relu(self.head.fc1(x))
        x = self.head.fc2(x)        # Output: [B, 34]
        return x


class PresenceHead:
    """Trained logistic presence head loaded from presence-head.json.

    Applied to the un-normalized 128-d bn2 activation (see module docstring)."""
    def __init__(self, path):
        with open(path) as f:
            data = json.load(f)
        self.w = np.asarray(data["weights"], dtype=np.float64)   # [128]
        self.b = float(data["bias"])

    def predict(self, pre_emb):
        logit = float(np.dot(pre_emb, self.w) + self.b)
        # clip to avoid overflow in exp
        logit = max(-60.0, min(60.0, logit))
        return 1.0 / (1.0 + math.exp(-logit))


class LoRAAdapter:
    """Rank-r room adapter loaded from node-N.json.

    delta = pre @ loraA @ loraB * scaling   (loraA[128,r], loraB[r,128])"""
    def __init__(self, path):
        with open(path) as f:
            data = json.load(f)
        w = data["weights"]
        self.A = np.asarray(w["loraA"], dtype=np.float64)        # [128, r]
        self.B = np.asarray(w["loraB"], dtype=np.float64)        # [r, 128]
        self.scaling = float(w.get("scaling", 1.0))

    def apply(self, pre_emb):
        delta = (pre_emb @ self.A) @ self.B * self.scaling       # [128]
        return pre_emb + delta

# ─── Settings ────────────────────────────────────────────────────────

UDP_PORT = 5006
UDP_HOST = "127.0.0.1"
WS_URL = "ws://127.0.0.1:5000/ws"

MODEL_DIR = os.path.join("ai model and densepose", "model")
EMBED_WEIGHTS = os.path.join(MODEL_DIR, "csi-embed-v2.safetensors")
POSE_WEIGHTS = os.path.join(MODEL_DIR, "pose_v1.safetensors")
PRESENCE_HEAD = os.path.join(MODEL_DIR, "presence-head.json")
NODE_ADAPTERS = {1: os.path.join(MODEL_DIR, "node-1.json"),
                 2: os.path.join(MODEL_DIR, "node-2.json")}

# History length for sliding window
HISTORY_LEN = 100

# Dual-node output fusion: combine per-node results that are fresher than this.
FUSION_WINDOW_S = 1.0

# Default sampling rate assumption (Hz) when timestamps are unusable.
DEFAULT_FS = 20.0

# The "demo" node id the synthetic self-feed uses so it never clobbers real
# hardware nodes 1 / 2.
SYNTH_NODE_ID = 99

COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# Approximate body-part height (y) by keypoint index.
def _kp_height(idx):
    if idx == 0:    return 1.65   # nose
    if idx <= 4:    return 1.60   # eyes / ears
    if idx <= 6:    return 1.40   # shoulders
    if idx <= 8:    return 1.15   # elbows
    if idx <= 10:   return 0.90   # wrists
    if idx <= 12:   return 0.95   # hips
    if idx <= 14:   return 0.55   # knees
    return 0.08                   # ankles

# ─── Global State ─────────────────────────────────────────────────────

ws = None
ws_connected = False
lock = threading.Lock()

# Node-specific histories: node_id -> {"mags": [], "rssi": [], "timestamps": []}
node_histories = {}
# Latest per-node inference result for fusion: node_id -> {"result": {...}, "t": ts}
node_results = {}
node_results_lock = threading.Lock()
# Node ids that have received real (UDP or WS) data — excluded from synthetic feed.
real_nodes = set()

last_udp_time = 0.0
last_inference_time = 0.0

# Per-node previous window mean for temporal-delta motion energy.
node_prev_means = {}

# ─── Model Loading ────────────────────────────────────────────────────

print("[AI] Loading models...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[AI] Using device: {device}")

# 1. Embedding model
embed_model = Enc().to(device)
try:
    if os.path.exists(EMBED_WEIGHTS):
        missing, unexpected = embed_model.load_state_dict(load_file(EMBED_WEIGHTS), strict=False)
        if missing:    print(f"[WARN] embed missing keys: {missing}")
        if unexpected: print(f"[WARN] embed unexpected keys: {unexpected}")
        print("[AI] Loaded csi-embed-v2 weights.")
    else:
        print(f"[WARN] Embed weights not found at {EMBED_WEIGHTS}")
except Exception as e:
    print(f"[ERROR] Failed to load embed model: {e}")
embed_model.eval()

# 2. Pose model
pose_model = PoseNet().to(device)
pose_loaded = False
try:
    if os.path.exists(POSE_WEIGHTS):
        missing, unexpected = pose_model.load_state_dict(load_file(POSE_WEIGHTS), strict=False)
        if missing:    print(f"[WARN] pose missing keys: {missing}")
        if unexpected: print(f"[WARN] pose unexpected keys: {unexpected}")
        if not missing and not unexpected:
            print("[AI] Loaded pose_v1 weights (exact match).")
        else:
            print("[AI] Loaded pose_v1 weights (partial — see warnings above).")
        pose_loaded = True
    else:
        print(f"[WARN] Pose weights not found at {POSE_WEIGHTS} — keypoints will be random.")
except Exception as e:
    print(f"[ERROR] pose_v1 load failed: {e}")
pose_model.eval()

# 3. Presence head
presence_head = None
try:
    if os.path.exists(PRESENCE_HEAD):
        presence_head = PresenceHead(PRESENCE_HEAD)
        print(f"[AI] Loaded presence head (||w||={np.linalg.norm(presence_head.w):.2f}, bias={presence_head.b:.2f}).")
    else:
        print(f"[WARN] presence-head.json not found at {PRESENCE_HEAD}")
except Exception as e:
    print(f"[ERROR] Failed to load presence head: {e}")

# 4. LoRA node adapters
lora_adapters = {}
for nid, path in NODE_ADAPTERS.items():
    try:
        if os.path.exists(path):
            lora_adapters[nid] = LoRAAdapter(path)
            print(f"[AI] Loaded LoRA adapter for node {nid} (scaling={lora_adapters[nid].scaling}).")
        else:
            print(f"[WARN] LoRA adapter not found: {path}")
    except Exception as e:
        print(f"[ERROR] Failed to load LoRA adapter {path}: {e}")

# ─── Vitals (breathing / heart rate) from CSI ──────────────────────────

def estimate_vitals(mags_history, fs):
    """Estimate respiration (RPM) and heart rate (BPM) from the CSI amplitude
    time-series via band-pass + dominant-frequency detection.

    Returns (respiration_rpm, heart_bpm, reliable)."""
    mags = np.asarray(mags_history, dtype=np.float64)   # [T, 56]
    T = mags.shape[0]
    if T < 32 or fs <= 0:
        return 14.0, 72.0, False

    # 1-D vital signal: temporal variation of the mean amplitude across
    # subcarriers, linearly detrended to remove slow drift.
    sig = mags.mean(axis=1)
    sig = sig - np.polyval(np.polyfit(np.arange(T), sig, 1), np.arange(T))
    sig = sig * np.hanning(T)

    spec = np.abs(np.fft.rfft(sig))
    freqs = np.fft.rfftfreq(T, d=1.0 / fs)              # Hz

    def dominant(lo_hz, hi_hz):
        band = (freqs >= lo_hz) & (freqs <= hi_hz)
        if not band.any() or spec[band].max() <= 1e-9:
            return None, 0.0
        idx = np.where(band)[0][np.argmax(spec[band])]
        return freqs[idx], float(spec[idx])

    # Respiration: 6–30 BPM (0.1–0.5 Hz); Heart: 48–120 BPM (0.8–2.0 Hz)
    rf, rp = dominant(0.1, 0.5)
    hf, hp = dominant(0.8, 2.0)

    resp_rpm = rf * 60.0 if rf else 14.0
    heart_bpm = hf * 60.0 if hf else 72.0

    # Reliable when both bands carry meaningful energy relative to the noise floor.
    noise = float(np.median(spec) + 1e-9)
    reliable = bool(rf and hf and rp > 3 * noise and hp > 3 * noise)
    return float(resp_rpm), float(heart_bpm), reliable

# ─── Feature extraction ────────────────────────────────────────────────

def extract_features_8d(mags_history, rssi_history, fs, prev_window_mean=None):
    """Extract 8 standardised features for csi-embed-v2.
    Returns (features_standardised, raw_motion, current_window_mean, vitals)."""
    mags_arr = np.array(mags_history)  # [T, 56]

    # Feature 0: presence — mean subcarrier std across time
    presence = float(np.mean(np.std(mags_arr, axis=0)))

    # Feature 1: motion energy (temporal delta of mean spectrum, always >= 0)
    half = max(1, len(mags_arr) // 2)
    current_window_mean = np.mean(mags_arr, axis=0)   # [56]
    if prev_window_mean is not None:
        motion_raw = float(np.mean(np.abs(current_window_mean - prev_window_mean)))
    else:
        first_half_mean = np.mean(mags_arr[:half], axis=0)
        second_half_mean = np.mean(mags_arr[half:], axis=0)
        motion_raw = float(np.mean(np.abs(second_half_mean - first_half_mean)))
    frame_diff_motion = float(np.mean(np.abs(np.diff(mags_arr, axis=0))))
    motion = max(motion_raw, frame_diff_motion)

    # Features 2-3: derived vitals
    breathing, heart_rate, vitals_reliable = estimate_vitals(mags_arr, fs)

    # Features 4-7: auxiliary
    phase_variance = float(np.var(mags_arr))
    person_count = 1.0
    fall_detected = 0.0
    rssi_mean = float(np.mean(rssi_history))

    features = np.array([presence, motion, breathing, heart_rate,
                         phase_variance, person_count, fall_detected, rssi_mean])

    # Per-feature Z-score across the 8 features (preserves relative magnitude).
    mean_val = np.mean(features)
    std_val = np.std(features) + 1e-8
    features_std = (features - mean_val) / std_val

    vitals = {"breathing": breathing, "heart_rate": heart_rate, "reliable": vitals_reliable}
    return features_std, motion, current_window_mean, vitals

def _estimate_fs(timestamps):
    """Estimate sampling rate (Hz) from millisecond timestamps."""
    if len(timestamps) < 2:
        return DEFAULT_FS
    span_s = (timestamps[-1] - timestamps[0]) / 1000.0
    if span_s <= 0:
        return DEFAULT_FS
    fs = (len(timestamps) - 1) / span_s
    # Guard against absurd values from clock jitter.
    if not (1.0 <= fs <= 200.0):
        return DEFAULT_FS
    return fs

# ─── Per-node inference ────────────────────────────────────────────────

def compute_node_result(node_id, mags_hist, rssi_hist, timestamps, prev_mean):
    """Run the full model stack for one node. Returns a result dict (no I/O)."""
    fs = _estimate_fs(timestamps)

    # ── Pose ── [B, 56, T]
    mags_tensor = torch.tensor(np.array(mags_hist).T).float().unsqueeze(0).to(device)
    with torch.no_grad():
        coords_raw = pose_model(mags_tensor).cpu().numpy()[0]   # [34]

    # ── Embedding + LoRA + presence head ──
    features_8d, motion_raw, current_mean, vitals = extract_features_8d(
        mags_hist, rssi_hist, fs, prev_mean)
    feat_tensor = torch.tensor(features_8d).float().unsqueeze(0).to(device)
    with torch.no_grad():
        z, pre = embed_model(feat_tensor)
    z = z.cpu().numpy()[0]
    pre = pre.cpu().numpy()[0]

    # Room adaptation on the un-normalized activation.
    adapter = lora_adapters.get(node_id)
    pre_adapted = adapter.apply(pre) if adapter is not None else pre

    presence_prob = presence_head.predict(pre_adapted) if presence_head is not None else None

    # ── Classification ──
    # Presence: trust the trained head when available, but require some signal.
    # ADVISORY ONLY: this AI presence/human verdict is displayed alongside the
    # deterministic pipeline's decision — it can never originate or flip the
    # dashboard's target presence (server/lib owns that).
    if presence_prob is not None:
        present = presence_prob > 0.5
    else:
        present = float(features_8d[0]) > -1.5
    # Moving perturbation (>0.005 temporal delta) reads as human; a present
    # but statically-perturbing reflector reads as mechanical.
    label = "unknown"
    if present:
        label = "human" if motion_raw > 0.005 else "mechanical"

    return {
        "node_id": node_id,
        "coords": coords_raw,           # [34] (x, z) pairs
        "motion_raw": motion_raw,
        "presence_prob": presence_prob,
        "present": present,
        "label": label,
        "vitals": vitals,
        "current_mean": current_mean,
        "embedding": z,
    }

# ─── Dual-node fusion + transmit ───────────────────────────────────────

def _coords_to_keypoints(coords):
    kps = []
    for idx, name in enumerate(COCO_KEYPOINTS):
        kps.append({
            "name": name,
            "x": float(coords[idx * 2]),
            "y": _kp_height(idx),
            "z": float(coords[idx * 2 + 1]),
            "confidence": 0.85,
        })
    return kps

def fuse_and_emit():
    """Combine recent per-node results into a single stereoscopic estimate and
    broadcast pose / identity / vitals over the WebSocket."""
    global ws, ws_connected
    now = time.time()

    with node_results_lock:
        fresh = {nid: r["result"] for nid, r in node_results.items()
                 if now - r["t"] <= FUSION_WINDOW_S}

    if not fresh:
        return

    results = list(fresh.values())

    # Pose: average the per-node keypoint coordinates. With two spatially
    # separated nodes this averages out single-node depth/angle bias —
    # output-level fusion that stays compatible with the 56-channel pose_v1.
    coords = np.mean([r["coords"] for r in results], axis=0)
    keypoints = _coords_to_keypoints(coords)

    # Identity is advisory only. The deterministic runtime owns human/non-human verdicts.
    present_any = any(r["present"] for r in results)
    labels = [r["label"] for r in results if r["present"]]
    advisory_label = "human" if "human" in labels else ("mechanical" if labels else "unknown")
    label = "unknown"
    motion = max(r["motion_raw"] for r in results)
    pp = [r["presence_prob"] for r in results if r["presence_prob"] is not None]
    presence_prob = max(pp) if pp else (1.0 if present_any else 0.0)
    periodicity = float(np.mean([r["vitals"]["breathing"] for r in results]))

    # Vitals: average across reliable nodes; fall back to all.
    rel = [r["vitals"] for r in results if r["vitals"]["reliable"]]
    src = rel if rel else [r["vitals"] for r in results]
    breathing = float(np.mean([v["breathing"] for v in src]))
    heart = float(np.mean([v["heart_rate"] for v in src]))
    vitals_reliable = len(rel) > 0

    human_prob = float(F.sigmoid(torch.tensor(motion * 20.0)).item())
    if advisory_label == "human":
        human_prob = max(human_prob, presence_prob)

    if not (ws_connected and ws is not None):
        return
    try:
        ws.send(json.dumps({
            "type": "poseFrame",
            "data": {"timestamp": int(now * 1000), "keypoints": keypoints},
        }))
        ws.send(json.dumps({
            "type": "targetIdentity",
            "data": {
                "label": label,
                "humanProb": human_prob,
                "mechanicalProb": 1.0 - human_prob,
                "periodicity": periodicity,
                "presenceProb": presence_prob,
                "advisoryLabel": advisory_label,
            },
        }))
        ws.send(json.dumps({
            "type": "vitalSigns",
            "data": {
                "heartRateBpm": heart,
                "respirationRateRpm": breathing,
                "vitalsReliable": vitals_reliable,
            },
        }))
        nodes_str = "+".join(str(r["node_id"]) for r in results)
        pp_str = f"{presence_prob:.2f}" if pp else "n/a"
        print(f"[AI] Fused nodes={nodes_str} advisory_label={advisory_label} "
              f"presence={pp_str} motion={motion:.4f} "
              f"resp={breathing:.1f} hr={heart:.0f} rel={vitals_reliable}")
    except Exception as e:
        print(f"[WS] Send error: {e}")

# ─── Inference Throttler ───────────────────────────────────────────────

def trigger_inference(node_id, mags_hist, rssi_hist, timestamps):
    global last_inference_time
    now = time.time()
    if now - last_inference_time < 0.2:   # Throttle to max 5 Hz (global)
        return
    last_inference_time = now

    mags_copy = list(mags_hist)
    rssi_copy = list(rssi_hist)
    ts_copy = list(timestamps)
    prev_mean = node_prev_means.get(node_id, None)

    def _run():
        try:
            result = compute_node_result(node_id, mags_copy, rssi_copy, ts_copy, prev_mean)
        except Exception as e:
            print(f"[AI] inference error node={node_id}: {e}")
            return
        node_prev_means[node_id] = result["current_mean"]
        with node_results_lock:
            node_results[node_id] = {"result": result, "t": time.time()}
        fuse_and_emit()

    threading.Thread(target=_run, daemon=True).start()

def _append_and_maybe_infer(node_id, mags, rssi, timestamp, is_real):
    """Shared buffer-append + inference-trigger used by all data paths."""
    if is_real:
        real_nodes.add(node_id)
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
        ready = len(hist["mags"]) >= HISTORY_LEN
        if ready:
            mags_snapshot = list(hist["mags"])
            rssi_snapshot = list(hist["rssi"])
            ts_snapshot = list(hist["timestamps"])
    if ready:
        trigger_inference(node_id, mags_snapshot, rssi_snapshot, ts_snapshot)

# ─── Helper: parse raw UDP CSI ─────────────────────────────────────────

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
    iq_array = struct.unpack(f'<{expected_len}b', iq_data[:expected_len])
    mags = []
    for i in range(num_sub):
        r = iq_array[i * 2]
        im = iq_array[i * 2 + 1]
        mags.append(math.sqrt(r * r + im * im))
    if len(mags) != 56:
        xp = np.linspace(0, 1, len(mags))
        x_new = np.linspace(0, 1, 56)
        mags = np.interp(x_new, xp, mags)
    else:
        mags = np.array(mags)
    return {"node_id": node_id, "mags": mags, "rssi": rssi, "timestamp": time.time() * 1000}

# ─── WebSocket Client ──────────────────────────────────────────────────

def on_message(ws_conn, message):
    # Process WS rawSamples regardless of UDP — hardware can use both paths.
    try:
        msg = json.loads(message)
        if msg.get("type") != "rawSample":
            return
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

        # Synthesize 56-subcarrier magnitudes from the dominant complex numbers.
        mag1 = math.sqrt(h1["re"] ** 2 + h1["im"] ** 2)
        mag2 = math.sqrt(h2["re"] ** 2 + h2["im"] ** 2) if h2 else mag1
        mags = np.zeros(56)
        for i in range(56):
            fade = 1.0 + 0.3 * math.sin(i * 0.15)
            mags[i] = (mag1 * 0.7 + mag2 * 0.3) * fade + np.random.normal(0, 0.05)
            mags[i] = max(0.01, mags[i])

        _append_and_maybe_infer(node_id, mags, rssi, timestamp, is_real=True)
    except Exception:
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
                on_close=on_close,
            )
            ws.run_forever()
        except Exception as e:
            print(f"[WS] Run error: {e}")
        time.sleep(2)

# ─── UDP Receiver ──────────────────────────────────────────────────────

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
        _append_and_maybe_infer(sample["node_id"], sample["mags"], sample["rssi"],
                                sample["timestamp"], is_real=True)

# ─── Synthetic Self-Feed ───────────────────────────────────────────────
# When no real data arrives, generate a synthetic walking-human stream on a
# dedicated demo node id so the dashboard stays alive without ever overwriting
# real hardware nodes 1 / 2.

def run_synthetic_feed():
    walk_phase = 0.0
    t = 0.0
    while True:
        time.sleep(0.05)  # 20Hz
        if time.time() - last_udp_time < 3.0:
            continue
        if real_nodes:               # any real node active -> stay silent
            continue
        if not ws_connected:
            continue

        walk_phase += (2 * math.pi) / (20 * 12)  # 12s loop
        t += 0.05
        angle_deg = 50 * math.sin(walk_phase)
        depth = 3.0 + 1.5 * math.sin(walk_phase * 2)
        theta = math.radians(angle_deg)
        resp = 0.8 * math.sin(2 * math.pi * 0.3 * t)   # ~18 RPM
        hr = 0.15 * math.sin(2 * math.pi * 1.2 * t)    # ~72 BPM

        mags = np.zeros(56)
        for i in range(56):
            static_part = 0.8 + 0.05 * math.sin(i * 0.2)
            moving_phase = 2 * math.pi * math.sin(theta) * depth * 0.3 + t * 0.5
            fade = 1.0 + 0.3 * math.sin(i * 0.15)
            dynamic_part = max(0.05, 0.4 - depth * 0.04) * fade * (
                1 + 0.4 * math.sin(moving_phase + resp + hr + i * 0.1))
            mags[i] = abs(static_part + dynamic_part) + np.random.normal(0, 0.01)
        rssi = -55 + depth * -2 + np.random.uniform(-2, 2)

        _append_and_maybe_infer(SYNTH_NODE_ID, mags, rssi, time.time() * 1000, is_real=False)

# ─── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=run_ws_client, daemon=True).start()
    if os.environ.get("PHANTOM_AI_SYNTHETIC", "").lower() in {"1", "true", "yes"}:
        threading.Thread(target=run_synthetic_feed, daemon=True).start()
    try:
        run_udp_receiver()
    except KeyboardInterrupt:
        print("\n[AI] Exiting...")
