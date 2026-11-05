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
from collections import deque
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file
import websocket

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phantom.protocol import CsiFrameV1, parse_csi_frame  # noqa: E402
from phantom.sidecar import (  # noqa: E402
    FUSION_WINDOW_S,
    PerNodeThrottle,
    fresh_results,
    count_window_from_history,
    fuse_activity,
    fuse_count,
    fuse_embedding_drift,
    activity_from_motion,
    advisory_human_prob,
    credentials_from_env,
    fuse_vitals,
    relative_motion,
    login_url_from_ws_url,
    route_ws_message,
    session_cookie_from_set_cookie,
    window_features_from_history,
)
from phantom.activity_model import ActivityModel  # noqa: E402
from phantom.count_model import CountPredictor  # noqa: E402
from phantom.embedding import (  # noqa: E402
    cosine_drift,
    load_standardizer,
    mean_embedding,
    ruview_scale_features,
    standardize,
)
from phantom.presence_guard import presence_head_check  # noqa: E402
from phantom.subcarriers import NUM_DATA_SUBCARRIERS, lltf_amplitudes  # noqa: E402

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

# Phase-1 bug audit: these were hardcoded, out of step with the TS side's
# UDP_PORT env-var convention (server/lib/udp-server.ts). PY_SIDECAR_PORT/HOST
# match the same env vars the TS forwarder now reads, so both sides move
# together instead of requiring a hand-edit in lockstep.
UDP_PORT = int(os.environ.get("PY_SIDECAR_PORT", "5006"))
UDP_HOST = os.environ.get("PY_SIDECAR_HOST", "127.0.0.1")
WS_URL = os.environ.get("PHANTOM_WS_URL", "ws://127.0.0.1:5000/ws")

MODEL_DIR = os.path.join("ai model and densepose", "model")
EMBED_WEIGHTS = os.path.join(MODEL_DIR, "csi-embed-v2.safetensors")
# The int4 bin carries the encoder's input standardizer (fp16 mean[8], std[8]).
EMBED_STANDARDIZER = os.path.join(MODEL_DIR, "csi-embed-v2-int4.bin")
POSE_WEIGHTS = os.path.join(MODEL_DIR, "pose_v1.safetensors")
PRESENCE_HEAD = os.path.join(MODEL_DIR, "presence-head.json")
NODE_ADAPTERS = {1: os.path.join(MODEL_DIR, "node-1.json"),
                 2: os.path.join(MODEL_DIR, "node-2.json")}

def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


# Opt-in model components. Defaults are OFF because each is unvalidated on
# this hardware/room (see docs and the model README):
#   * pose_v1: ~2.5% PCK@20, never rendered by the dashboard.
#   * presence head: trained against RuView's feature standardization, which
#     is not shipped — its probability is uncalibrated here.
#   * node-1/2 LoRA adapters: trained for someone else's rooms, and none
#     exist for nodes 3/4.
POSE_ENABLED = _env_flag("PHANTOM_AI_POSE")
PRESENCE_HEAD_ENABLED = _env_flag("PHANTOM_AI_PRESENCE_HEAD")
LORA_ENABLED = _env_flag("PHANTOM_AI_LORA")
# Synthetic 56-vectors from WS rawSample scalars, only while UDP is silent.
WS_FALLBACK_ENABLED = _env_flag("PHANTOM_AI_WS_FALLBACK")

# History length for sliding window
HISTORY_LEN = 100

# pose_v1 was trained on 56-subcarrier input; live frames carry 51 LLTF data
# subcarriers, so pose input is resampled (pose is opt-in only).
POSE_INPUT_SUBCARRIERS = 56

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
inference_throttle = PerNodeThrottle()
# node_id -> "udp" | "ws_fallback": a node's history is cleared when its
# source changes so synthetic and real frames are never mixed in one window.
node_sources = {}

# Per-node previous window mean for temporal-delta motion energy.
node_prev_means = {}

# Per-node short history of motion_raw, used only for the activity-state
# heuristic below (trend/ratio detection across inference cycles).
node_motion_history = {}
ACTIVITY_HISTORY_LEN = 6      # ~1.2s of samples at the 5Hz inference throttle
# Longer per-node relative-motion history (~10 s at 5 Hz) that "Calibrate Empty
# Room" reduces to that node's empty-room baseline; node -> baseline (unit-free).
node_motion_long = {}
CALIBRATION_HISTORY_LEN = 50
CALIBRATION_MIN_SAMPLES = 10
node_calibrated_baseline = {}

# csi-embed-v2 empty-room reference: per-node recent embeddings reduced to a
# mean unit vector by "Calibrate Empty Room"; drift from it is advisory only.
node_embed_long = {}
EMBED_HISTORY_LEN = 50
EMBED_MIN_SAMPLES = 10
node_empty_embed = {}
embed_ref_time = None
# Input standardizer for the encoder; replaced by the shipped values on load.
EMBED_MEAN = np.zeros(8)
EMBED_STD = np.ones(8)
embed_loaded = False

# ─── Model Loading ────────────────────────────────────────────────────

print("[AI] Loading models...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[AI] Using device: {device}")

# 1. Embedding model
embed_model = Enc().to(device)
try:
    if os.path.exists(EMBED_WEIGHTS) and os.path.exists(EMBED_STANDARDIZER):
        # strict: a mismatched state dict must not silently leave random weights.
        embed_model.load_state_dict(load_file(EMBED_WEIGHTS), strict=True)
        EMBED_MEAN, EMBED_STD = load_standardizer(EMBED_STANDARDIZER)
        embed_loaded = True
        print("[AI] Loaded csi-embed-v2 weights and standardizer.")
    else:
        print(f"[WARN] Embed weights/standardizer not found in {MODEL_DIR}; embedding disabled")
except Exception as e:
    print(f"[ERROR] Failed to load embed model, embedding disabled: {e}")
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

# 3. Presence head (opt-in: uncalibrated without RuView's standardizer)
presence_head = None
try:
    if not PRESENCE_HEAD_ENABLED:
        print("[AI] Presence head disabled (set PHANTOM_AI_PRESENCE_HEAD=1 to enable; output is uncalibrated).")
    elif os.path.exists(PRESENCE_HEAD):
        candidate_head = PresenceHead(PRESENCE_HEAD)
        # PS-FIX-06: refuse a saturated head (||w|| <= |bias| on unit-norm input answers one class for every input).
        # A refused head leaves presence_prob None, i.e. no advisory presence evidence; it never changes the verdict.
        head_check = presence_head_check(candidate_head.w, candidate_head.b)
        if head_check.ok:
            presence_head = candidate_head
            print(f"[AI] Loaded presence head (||w||={np.linalg.norm(presence_head.w):.2f}, bias={presence_head.b:.2f}).")
        else:
            print(f"[AI] Presence head REFUSED, advisory presence unavailable: {head_check.reason}.")
    else:
        print(f"[WARN] presence-head.json not found at {PRESENCE_HEAD}")
except Exception as e:
    print(f"[ERROR] Failed to load presence head: {e}")

# 4. LoRA node adapters (opt-in: trained for other rooms; none for nodes 3/4)
lora_adapters = {}
if not LORA_ENABLED:
    print("[AI] LoRA room adapters disabled (set PHANTOM_AI_LORA=1 to enable).")
for nid, path in (NODE_ADAPTERS.items() if LORA_ENABLED else ()):
    try:
        if os.path.exists(path):
            lora_adapters[nid] = LoRAAdapter(path)
            print(f"[AI] Loaded LoRA adapter for node {nid} (scaling={lora_adapters[nid].scaling}).")
        else:
            print(f"[WARN] LoRA adapter not found: {path}")
    except Exception as e:
        print(f"[ERROR] Failed to load LoRA adapter {path}: {e}")

# 5. Per-room activity model (trained by scripts/train/train_activity.py from
# labelled recordings of THIS room). Advisory only; absent -> no activity field.
ROOM_ID = os.environ.get("PHANTOM_ROOM_ID", "").strip()
MODELS_ROOT = os.environ.get("PHANTOM_MODELS_ROOT", os.path.join("models", "rooms"))
activity_model = None
if ROOM_ID:
    activity_path = os.path.join(MODELS_ROOT, ROOM_ID, "activity.json")
    try:
        if os.path.exists(activity_path):
            activity_model = ActivityModel.load(activity_path)
            print(f"[AI] Loaded room activity model for '{ROOM_ID}' "
                  f"(balanced acc {activity_model.meta.get('metrics', {}).get('model_balanced_accuracy', 'n/a')}).")
        else:
            print(f"[AI] No activity model at {activity_path} — run scripts/train/train_activity.py after recording.")
    except Exception as e:
        print(f"[ERROR] Failed to load activity model {activity_path}: {e}")
else:
    print("[AI] PHANTOM_ROOM_ID not set — per-room activity model disabled.")

# 6. Per-room people-count CNN (scripts/train/train_count.py). Advisory only.
COUNT_MIN_CONFIDENCE = float(os.environ.get("PHANTOM_AI_COUNT_MIN_CONF", "0.6"))
count_predictor = None
if ROOM_ID:
    count_dir = os.path.join(MODELS_ROOT, ROOM_ID)
    try:
        if os.path.exists(os.path.join(count_dir, "count.json")):
            count_predictor = CountPredictor.load(count_dir)
            print(f"[AI] Loaded room count model for '{ROOM_ID}' (classes={count_predictor.classes}, "
                  f"T={count_predictor.temperature:.2f}).")
        else:
            print(f"[AI] No count model in {count_dir} — run scripts/train/train_count.py after recording.")
    except Exception as e:
        print(f"[ERROR] Failed to load count model from {count_dir}: {e}")

# ─── Vitals (breathing / heart rate) from CSI ──────────────────────────

def estimate_vitals(mags_history, fs):
    """Estimate respiration (RPM) and heart rate (BPM) from the CSI amplitude
    time-series via band-pass + dominant-frequency detection.

    Returns (respiration_rpm, heart_bpm, reliable); rates are None when no
    band peak exists — never a fabricated "typical" fallback value."""
    mags = np.asarray(mags_history, dtype=np.float64)   # [T, subcarriers]
    T = mags.shape[0]
    if T < 32 or fs <= 0:
        return None, None, False

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

    resp_rpm = float(rf * 60.0) if rf else None
    heart_bpm = float(hf * 60.0) if hf else None

    # Reliable when both bands carry meaningful energy relative to the noise floor.
    noise = float(np.median(spec) + 1e-9)
    reliable = bool(rf and hf and rp > 3 * noise and hp > 3 * noise)
    return resp_rpm, heart_bpm, reliable

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

    rssi_mean = float(np.mean(rssi_history))

    # Map onto the 0-1 scale csi-embed-v2 was trained on, then apply its shipped
    # per-feature standardizer. Dims 4-6 (phase variance, person count, fall)
    # were constant in training and have no Phantom source, so they are masked
    # to 0 rather than divided by a vanishing std. The old per-vector z-score
    # across the 8 features destroyed absolute magnitudes and is gone.
    raw_features = ruview_scale_features(presence, motion, breathing, heart_rate, rssi_mean)
    features_std = standardize(raw_features, EMBED_MEAN, EMBED_STD)

    vitals = {"breathing": breathing, "heart_rate": heart_rate, "reliable": vitals_reliable}
    return features_std, motion, current_window_mean, vitals

def classify_activity(node_id, motion_raw):
    """Motion-energy-only activity heuristic. Advisory, not pose-derived.

    "rapid_change" means an abrupt jump in CSI motion energy relative to this
    node's recent baseline — it is NOT a validated fall-detection signal. The
    same signature equally fits sitting down, leaving the sensing field, or a
    reflector (door/curtain) moving, and 1-antenna CSI cannot discriminate
    those cases. Callers must not present it as a fall/injury claim."""
    hist = node_motion_history.setdefault(node_id, deque(maxlen=ACTIVITY_HISTORY_LEN))
    recent = list(hist)
    hist.append(motion_raw)
    node_motion_long.setdefault(node_id, deque(maxlen=CALIBRATION_HISTORY_LEN)).append(motion_raw)
    # `motion_raw` here is UNIT-FREE relative motion (see relative_motion). It
    # is judged against this node's calibrated empty-room level; until the
    # operator runs "Calibrate Empty Room" the answer is "unknown".
    return activity_from_motion(motion_raw, node_calibrated_baseline.get(node_id), recent)

def _resample_subcarriers(mags, n_out):
    """Linearly resample a [T, n_in] amplitude history to [T, n_out]."""
    n_in = mags.shape[1]
    if n_in == n_out:
        return mags
    x_in = np.linspace(0.0, 1.0, n_in)
    x_out = np.linspace(0.0, 1.0, n_out)
    return np.stack([np.interp(x_out, x_in, row) for row in mags])


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

    # ── Pose (opt-in) ── [B, 56, T]
    coords_raw = None
    if POSE_ENABLED:
        pose_input = _resample_subcarriers(np.array(mags_hist), POSE_INPUT_SUBCARRIERS)
        mags_tensor = torch.tensor(pose_input.T).float().unsqueeze(0).to(device)
        with torch.no_grad():
            coords_raw = pose_model(mags_tensor).cpu().numpy()[0]   # [34]

    # ── Embedding + LoRA + presence head ──
    features_8d, motion_raw, current_mean, vitals = extract_features_8d(
        mags_hist, rssi_hist, fs, prev_mean)
    z = pre = None
    if embed_loaded:
        feat_tensor = torch.tensor(features_8d).float().unsqueeze(0).to(device)
        with torch.no_grad():
            z_t, pre_t = embed_model(feat_tensor)
        z = z_t.cpu().numpy()[0]
        pre = pre_t.cpu().numpy()[0]

    # Room adaptation on the un-normalized activation.
    adapter = lora_adapters.get(node_id) if pre is not None else None
    pre_adapted = adapter.apply(pre) if adapter is not None else pre

    presence_prob = (
        presence_head.predict(pre_adapted) if presence_head is not None and pre_adapted is not None else None
    )

    # Advisory drift of this node's embedding from its empty-room reference
    # (set by "Calibrate Empty Room"); None until calibrated.
    embedding_drift = None
    if z is not None:
        node_embed_long.setdefault(node_id, deque(maxlen=EMBED_HISTORY_LEN)).append(z)
        reference = node_empty_embed.get(node_id)
        if reference is not None:
            embedding_drift = cosine_drift(z, reference)

    # ── Classification ──
    # ADVISORY ONLY: this AI presence/human verdict is displayed alongside the
    # deterministic pipeline's decision — it can never originate or flip the
    # dashboard's target presence (server/lib owns that). Without an enabled
    # presence head there is no model presence evidence at all (the old
    # fallback thresholded a cross-feature z-score, which is meaningless).
    present = presence_prob > 0.5 if presence_prob is not None else None
    # Moving perturbation (>0.005 temporal delta) reads as human; a present
    # but statically-perturbing reflector reads as mechanical.
    mags_arr = np.asarray(mags_hist, dtype=np.float64)
    motion_rel = relative_motion(
        float(np.mean(np.abs(np.diff(mags_arr, axis=0)))) if len(mags_arr) > 1 else 0.0,
        float(mags_arr.mean()),
    )
    activity_state = classify_activity(node_id, motion_rel)
    label = "unknown"
    if present:
        label = "human" if activity_state in ("walking", "rapid_change") else "mechanical"

    activity_feats = None
    if activity_model is not None:
        activity_feats = window_features_from_history(
            mags_hist, rssi_hist, timestamps, activity_model.window_s)

    count_window = None
    if count_predictor is not None:
        count_window = count_window_from_history(mags_hist, timestamps)

    return {
        "count_window": count_window,
        "activity_feats": activity_feats,
        "node_id": node_id,
        "coords": coords_raw,           # [34] (x, z) pairs
        "motion_raw": motion_raw,
        "motion_rel": motion_rel,
        "baseline_rel": node_calibrated_baseline.get(node_id),
        "presence_prob": presence_prob,
        "present": present,
        "label": label,
        "activity_state": activity_state,
        "vitals": vitals,
        "current_mean": current_mean,
        "embedding": z,
        "embedding_drift": embedding_drift,
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
        fresh = fresh_results(node_results, now, FUSION_WINDOW_S)

    if not fresh:
        return

    results = list(fresh.values())

    # Identity is advisory only. The deterministic runtime owns human/non-human verdicts.
    labels = [r["label"] for r in results if r["present"]]
    advisory_label = "human" if "human" in labels else ("mechanical" if labels else "unknown")
    label = "unknown"
    motion = max(r["motion_raw"] for r in results)
    pp = [r["presence_prob"] for r in results if r["presence_prob"] is not None]
    presence_prob = max(pp) if pp else None

    vitals = fuse_vitals([r["vitals"] for r in results])

    human_prob = max(
        advisory_human_prob(r["activity_state"], r["motion_rel"], r["baseline_rel"]) for r in results
    )
    if advisory_label == "human" and presence_prob is not None:
        human_prob = max(human_prob, presence_prob)

    # Fused activity tag: motion-energy heuristic only (see classify_activity
    # docstring). Without a presence model the heuristic still reports the
    # strongest per-node motion state; "unknown" only when a presence model
    # says nothing is present.
    activity_states = [r["activity_state"] for r in results]
    if all(s == "unknown" for s in activity_states) or (
        presence_prob is not None and not any(r["present"] for r in results)
    ):
        activity_state = "unknown"
    elif "rapid_change" in activity_states:
        activity_state = "rapid_change"
    elif "walking" in activity_states:
        activity_state = "walking"
    else:
        activity_state = "stationary"

    identity = {
        "label": label,
        "humanProb": human_prob,
        "mechanicalProb": 1.0 - human_prob,
        "periodicity": vitals.respiration_rpm or 0.0,
        "presenceProb": presence_prob,
        "presenceCalibrated": False,
        "advisoryLabel": advisory_label,
        "activityState": activity_state,
        "nodesFused": sorted(int(r["node_id"]) for r in results),
    }
    room_activity = fuse_activity(
        activity_model,
        {int(r["node_id"]): r["activity_feats"] for r in results if r.get("activity_feats") is not None},
        ROOM_ID,
    )
    if room_activity:
        identity.update(room_activity)
    room_count = fuse_count(
        count_predictor,
        {int(r["node_id"]): r["count_window"] for r in results if r.get("count_window") is not None},
        ROOM_ID,
        COUNT_MIN_CONFIDENCE,
    )
    if room_count:
        identity.update(room_count)
    room_embedding = fuse_embedding_drift(
        {int(r["node_id"]): r["embedding_drift"] for r in results if r.get("embedding_drift") is not None},
        None if embed_ref_time is None else now - embed_ref_time,
        ROOM_ID,
    )
    if room_embedding:
        identity.update(room_embedding)

    if not (ws_connected and ws is not None):
        return
    try:
        if POSE_ENABLED and all(r["coords"] is not None for r in results):
            # Output-level fusion: average per-node keypoints (pose is opt-in;
            # the dashboard never renders it — see canPresentVolumetricTarget).
            coords = np.mean([r["coords"] for r in results], axis=0)
            ws.send(json.dumps({
                "type": "poseFrame",
                "data": {"timestamp": int(now * 1000), "keypoints": _coords_to_keypoints(coords)},
            }))
        ws.send(json.dumps({"type": "targetIdentity", "data": identity}))
        ws.send(json.dumps({
            "type": "vitalSigns",
            "data": {
                "heartRateBpm": vitals.heart_bpm,
                "respirationRateRpm": vitals.respiration_rpm,
                "vitalsReliable": vitals.reliable,
            },
        }))
        pp_str = f"{presence_prob:.2f}" if presence_prob is not None else "n/a"
        print(f"[AI] Fused nodes={identity['nodesFused']} advisory_label={advisory_label} "
              f"activity={activity_state} presence={pp_str} motion={motion:.4f} "
              f"vitals_reliable={vitals.reliable}")
    except Exception as e:
        print(f"[WS] Send error: {e}")

# ─── Inference Throttler ───────────────────────────────────────────────

def trigger_inference(node_id, mags_hist, rssi_hist, timestamps):
    # Max 5 Hz PER NODE (was one global 5 Hz budget shared by all nodes).
    if not inference_throttle.should_run(node_id, time.time()):
        return

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

def _append_and_maybe_infer(node_id, mags, rssi, timestamp, is_real, source="udp"):
    """Shared buffer-append + inference-trigger used by all data paths.

    `source` keeps real UDP frames and synthetic WS-fallback vectors from ever
    sharing one window: a source switch clears that node's history."""
    if is_real:
        real_nodes.add(node_id)
    with lock:
        if node_sources.get(node_id) != source:
            node_sources[node_id] = source
            node_histories.pop(node_id, None)
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

def parse_csi_packet(data: bytes):
    """Parse a forwarded ADR-018 v1 datagram (32-byte header) into the
    sidecar's sample dict, or None.

    The previous parser read the 20-byte LEGACY layout from v1 packets: node
    id came from the schema-version byte (every node collapsed to "node 1")
    and the subcarrier count from unrelated bytes, so nearly every real packet
    was dropped and the sidecar ran on synthetic WS vectors only. Uses the
    same v1 parser as the Python runtime and the same LLTF data-subcarrier
    selection / imaginary-first order as the TS ingest."""
    frame = parse_csi_frame(data)
    if not isinstance(frame, CsiFrameV1):
        return None
    try:
        mags = lltf_amplitudes(frame.iq_bytes, frame.n_subcarriers)
    except ValueError:
        return None
    return {"node_id": frame.node_id, "mags": mags, "rssi": frame.rssi_dbm, "timestamp": time.time() * 1000}

# ─── Baseline calibration ("Calibrate Empty Room") ─────────────────────

def _run_calibration():
    """Reset the rolling motion baseline classify_activity() compares
    against, to the room's condition at the moment this is called.

    This does NOT retrain any model weight (embedding/pose/presence-head/
    LoRA all stay exactly as loaded from disk) — it only clears the short
    per-node history so the next sample becomes its own baseline, one
    reasonable to run while standing in an empty room so ambient noise
    (fan, HVAC) captured right now stops reading as "walking"/"rapid_change"
    afterward."""
    global embed_ref_time
    calibrated = []
    for node_id, long_hist in list(node_motion_long.items()):
        if len(long_hist) >= CALIBRATION_MIN_SAMPLES:
            node_calibrated_baseline[node_id] = float(np.median(list(long_hist)))
            calibrated.append(node_id)
    # Embedding reference: the room as it is right now, per node.
    embed_calibrated = []
    for node_id, embeds in list(node_embed_long.items()):
        if len(embeds) >= EMBED_MIN_SAMPLES:
            reference = mean_embedding(list(embeds))
            if reference is not None:
                node_empty_embed[node_id] = reference
                embed_calibrated.append(node_id)
    if embed_calibrated:
        embed_ref_time = time.time()
        print(f"[AI] Captured empty-room embedding reference for nodes={embed_calibrated}")
    for hist in node_motion_history.values():
        hist.clear()
    levels = {n: round(node_calibrated_baseline[n], 4) for n in calibrated}
    print(f"[AI] Calibrated empty-room motion level for nodes={calibrated}: {levels}")
    if ws_connected and ws is not None:
        try:
            ws.send(json.dumps({
                "type": "calibrationAck",
                "data": {"nodes": calibrated, "t": time.time()},
            }))
        except Exception as e:
            print(f"[WS] calibrationAck send error: {e}")

# ─── WebSocket Client ──────────────────────────────────────────────────

def on_message(ws_conn, message):
    # rawSample is ignored unless PHANTOM_AI_WS_FALLBACK=1 AND UDP is silent:
    # the server already forwards the real packet over UDP, and appending a
    # synthetic vector for the same frame double-ingested every node.
    try:
        msg = json.loads(message)
        action = route_ws_message(
            msg,
            ws_fallback_enabled=WS_FALLBACK_ENABLED,
            seconds_since_udp=time.time() - last_udp_time,
        )
        if action == "calibrate":
            _run_calibration()
            return
        if action != "fallback_sample":
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

        # Synthesize per-subcarrier magnitudes from the dominant complex
        # numbers (fallback only — NOT real CSI, so flagged is_real=False).
        mag1 = math.sqrt(h1["re"] ** 2 + h1["im"] ** 2)
        mag2 = math.sqrt(h2["re"] ** 2 + h2["im"] ** 2) if h2 else mag1
        mags = np.zeros(NUM_DATA_SUBCARRIERS)
        for i in range(NUM_DATA_SUBCARRIERS):
            fade = 1.0 + 0.3 * math.sin(i * 0.15)
            mags[i] = (mag1 * 0.7 + mag2 * 0.3) * fade + np.random.normal(0, 0.05)
            mags[i] = max(0.01, mags[i])

        _append_and_maybe_infer(node_id, mags, rssi, timestamp, is_real=False, source="ws_fallback")
    except Exception as e:
        print(f"[WS] message handling error: {e}")

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

def _login_for_session_cookie():
    """Log in to the dashboard and return 'phantom.sid=…', or None.

    The dashboard WebSocket answers 401 to unauthenticated clients, so without
    PHANTOM_AI_USERNAME / PHANTOM_AI_PASSWORD the sidecar can never deliver
    advisories. The password is read from the environment only and is never
    printed."""
    creds = credentials_from_env(os.environ)
    if creds is None:
        print("[WS] No PHANTOM_AI_USERNAME/PHANTOM_AI_PASSWORD set — dashboard login required, "
              "connection will be rejected (401).")
        return None
    import urllib.request
    request = urllib.request.Request(
        login_url_from_ws_url(WS_URL),
        data=json.dumps({"username": creds.username, "password": creds.password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            cookie = session_cookie_from_set_cookie(response.headers.get_all("Set-Cookie") or [])
    except Exception as e:
        print(f"[WS] Login failed for user '{creds.username}': {e}")
        return None
    if cookie is None:
        print("[WS] Login succeeded but no session cookie was returned.")
    else:
        print(f"[WS] Logged in as '{creds.username}'.")
    return cookie

def run_ws_client():
    global ws, ws_connected
    while True:
        try:
            cookie = _login_for_session_cookie()
            ws = websocket.WebSocketApp(
                WS_URL,
                header=[f"Cookie: {cookie}"] if cookie else None,
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

        mags = np.zeros(NUM_DATA_SUBCARRIERS)
        for i in range(NUM_DATA_SUBCARRIERS):
            static_part = 0.8 + 0.05 * math.sin(i * 0.2)
            moving_phase = 2 * math.pi * math.sin(theta) * depth * 0.3 + t * 0.5
            fade = 1.0 + 0.3 * math.sin(i * 0.15)
            dynamic_part = max(0.05, 0.4 - depth * 0.04) * fade * (
                1 + 0.4 * math.sin(moving_phase + resp + hr + i * 0.1))
            mags[i] = abs(static_part + dynamic_part) + np.random.normal(0, 0.01)
        rssi = -55 + depth * -2 + np.random.uniform(-2, 2)

        _append_and_maybe_infer(SYNTH_NODE_ID, mags, rssi, time.time() * 1000, is_real=False, source="synthetic")

# ─── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=run_ws_client, daemon=True).start()
    if os.environ.get("PHANTOM_AI_SYNTHETIC", "").lower() in {"1", "true", "yes"}:
        threading.Thread(target=run_synthetic_feed, daemon=True).start()
    try:
        run_udp_receiver()
    except KeyboardInterrupt:
        print("\n[AI] Exiting...")
