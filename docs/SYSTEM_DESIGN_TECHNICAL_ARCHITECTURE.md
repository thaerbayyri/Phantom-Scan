> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# PHANTOM SCAN — System Design & Technical Architecture Report

**Document Classification:** Internal Engineering Reference  
**Revision:** 2.0  
**Date:** 2026-03-26  
**Authors:** Systems Architecture Division  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Hardware Architecture & Deployment](#2-hardware-architecture--deployment)
3. [Software Stack & Processing Tiers](#3-software-stack--processing-tiers)
4. [Algorithmic Deep-Dive](#4-algorithmic-deep-dive)
5. [Edge Intelligence (WASM) & Storage](#5-edge-intelligence-wasm--storage)
6. [Visualization & UI](#6-visualization--ui)
7. [Security & Privacy](#7-security--privacy)
8. [Appendix — Specification Summary](#8-appendix--specification-summary)

---

## 1. Executive Summary

### 1.1 Project Mission

PHANTOM SCAN transforms ambient 802.11 Wi-Fi radiation into a **privacy-first, camera-free human sensing grid**. The platform performs non-contact, non-line-of-sight (NLOS) perception of human presence, pose, and physiology by analyzing sub-wavelength perturbations in the Channel State Information (CSI) of commodity wireless signals.

The system is designed for **fixed-position, infrastructure-embedded deployment** — mounted within walls, ceilings, or structural enclosures — to provide continuous environmental awareness without optical sensors, wearable devices, or active radar transmissions.

### 1.2 Core Capabilities

| Capability | Methodology | Performance Target |
|---|---|---|
| Through-Wall Pose Reconstruction | Multistatic CSI fusion → DensePose skeleton mapping | < 30 mm spatial jitter |
| Respiration Rate Monitoring | Phase-unwrapped IIR bandpass (0.1–0.5 Hz) + autocorrelation | ± 1 BRM accuracy |
| Cardiac Rate Estimation | Phase-unwrapped IIR bandpass (0.8–2.0 Hz) + zero-crossing | ± 2 BPM accuracy |
| Fall Detection | Abrupt variance spike detection with adaptive thresholding | < 200 ms latency |
| Occupancy Counting | Spatial variance clustering across subcarrier groups | ≥ 95% accuracy (1–4 persons) |

### 1.3 Design Principles

1. **Passive Sensing** — The system emits no probing signals; it operates exclusively on ambient Wi-Fi traffic.
2. **Privacy by Design** — No image, video, or payload data is captured. All PII (MAC addresses) is hashed in-memory via SHA-256 before any persistence.
3. **Edge-First Processing** — Critical DSP occurs on-node to minimise network bandwidth and central-server dependency.

---

## 2. Hardware Architecture & Deployment

### 2.1 System-on-Chip Specification

The sensing node is built on the **Espressif ESP32-S3** (Dual-core Xtensa LX7 @ 240 MHz).

| Parameter | Specification |
|---|---|
| **SoC** | ESP32-S3-WROOM-1 / 1U |
| **CPU** | Dual-core Xtensa LX7, 240 MHz |
| **SRAM** | 512 KB internal |
| **PSRAM** | 8 MB octal SPI (PSRAM-enabled modules) |
| **Wi-Fi** | 802.11 b/g/n, 2.4 GHz, HT20/HT40 |
| **CSI Extraction** | 52 subcarriers (HT20) / 114 subcarriers (HT40), per-antenna I/Q |
| **USB** | Native USB-OTG (CDC/JTAG) |
| **GPIO** | 45 programmable pins |

#### Core Affinity Model

The firmware enforces a strict dual-core partitioning strategy to prevent priority inversion and ensure deterministic CSI capture timing:

| Core | Designation | Responsibilities |
|---|---|---|
| **Core 0** | RF Core | Wi-Fi driver, promiscuous mode callback, raw CSI DMA ingestion, UDP frame transmission |
| **Core 1** | DSP Core | Phase unwrapping, IIR filtering, Welford variance, top-K subcarrier selection, WASM runtime |

Inter-core communication is achieved via lock-free ring buffers (`xRingBuffer`) allocated in PSRAM, avoiding mutex contention on the critical capture path.

### 2.2 Multistatic Mesh Deployment

PHANTOM SCAN employs a **multistatic receiver mesh** in which 3–6 ESP32-S3 nodes are deployed per monitored room. Each node independently captures CSI from a shared set of ambient access points (APs), and the backend fuses the multi-perspective observations to resolve 3D spatial position.

#### Deployment Topology

```
┌─────────────────────────────────────────────────────┐
│                    MONITORED ROOM                    │
│                                                      │
│   [N1]────────────────────────────────────────[N2]   │
│    │          ·  ·  ·  TARGET  ·  ·  ·          │   │
│    │              (Human Subject)                │   │
│    │                                             │   │
│   [N3]────────────────────────────────────────[N4]   │
│                                                      │
│                       [N5] (ceiling)                 │
│                       [N6] (ceiling)                 │
└─────────────────────────────────────────────────────┘
        │              │              │
        └──── UDP 5005 ┴── UDP 5005 ──┘
                       │
              ┌────────▼────────┐
              │  FUSION SERVER  │
              │  (Node.js/TS)   │
              └─────────────────┘
```

| Parameter | Specification |
|---|---|
| Nodes per room | 3–6 (minimum 3 for 3D triangulation) |
| Node placement | Corners + ceiling for maximal angular diversity |
| Synchronisation | NTP-aligned timestamps (± 2 ms inter-node skew) |
| Spatial jitter | < 30 mm RMS after Kalman fusion |
| Coverage volume | Up to 8 m × 8 m × 3 m per room |

#### Geometric Dilution of Precision (GDOP)

Node placement is optimised to minimise GDOP — the ratio of position-estimation error to measurement error. Corner-plus-ceiling placement yields a GDOP factor of **1.2–1.8**, ensuring that millimetre-level CSI phase accuracy translates to centimetre-level pose accuracy.

### 2.3 Antenna Strategy

Standard PCB antennas on ESP32-S3 modules provide omnidirectional coverage but suffer from insufficient gain for through-wall (NLOS) operation. PHANTOM SCAN specifies **external high-gain directional antennas** for deployment scenarios requiring material penetration.

| Antenna Type | Gain | Beamwidth | Use Case |
|---|---|---|---|
| PCB Trace (stock) | 2 dBi | 360° (omni) | Line-of-sight, same-room sensing |
| Patch Antenna | 6–8 dBi | ~70° H / ~60° V | Through single drywall partition |
| Yagi-Uda (5-element) | 10–12 dBi | ~45° H / ~40° V | Through concrete / double-wall penetration |
| Sector Panel | 8–10 dBi | ~120° H / ~60° V | Wide-area corridor monitoring |

**Material Attenuation Budget:**

| Material | Typical Loss (2.4 GHz) | Maximum Penetrable Layers |
|---|---|---|
| Drywall (12 mm) | 2–3 dB | 3–4 layers |
| Plywood (18 mm) | 3–4 dB | 2–3 layers |
| Concrete block (200 mm) | 10–15 dB | 1 layer (with Yagi) |
| Brick (110 mm) | 5–8 dB | 2 layers |
| Glass (6 mm) | 2–3 dB | 4+ layers |

Antenna selection is determined during site survey by measuring the **received CSI SNR** at each node after wall attenuation; the minimum operational threshold is defined as SNR ≥ 15 dB across the top-K subcarriers.

---

## 3. Software Stack & Processing Tiers

### 3.1 Firmware Layer

| Component | Specification |
|---|---|
| Framework | ESP-IDF v5.2 (FreeRTOS SMP) |
| Wi-Fi Mode | Promiscuous (monitor) mode with CSI callback registration |
| Packet Format | ADR-018 binary frame (proprietary) |
| Transport | UDP unicast to ingestion server, port 5005 |
| OTA Updates | HTTPS pull with Ed25519 signature verification |

#### ADR-018 Frame Structure

```
┌────────┬────────┬──────┬───────┬──────────┬────────────────────┐
│ Magic  │ SeqNo  │ RSSI │ Noise │ Antenna  │ I/Q Subcarrier     │
│ 4B     │ 2B     │ 1B   │ 1B   │ Mask 1B  │ Array (N×2×2B)     │
├────────┼────────┼──────┼───────┼──────────┼────────────────────┤
│ 0xCAFE │ uint16 │ int8 │ int8  │ bitmask  │ int16[N][2]        │
│ BABE   │        │ dBm  │ dBm   │          │ (I, Q per carrier) │
└────────┴────────┴──────┴───────┴──────────┴────────────────────┘
```

Where `N` = 52 (HT20 mode) or 114 (HT40 mode).

### 3.2 Processing Tier Model

The signal processing pipeline is decomposed into four tiers of ascending abstraction, each with well-defined input/output contracts:

```
┌──────────────────────────────────────────────────────────────────┐
│                     PROCESSING TIER MODEL                        │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │  TIER 0  │──▶│  TIER 1  │──▶│  TIER 2  │──▶│   TIER 3     │ │
│  │  Raw     │   │  DSP     │   │  Vitals  │   │   WASM Edge  │ │
│  │  Capture │   │  Stats   │   │  Extract │   │   Inference  │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

| Tier | Name | Location | Inputs | Outputs | Latency Budget |
|---|---|---|---|---|---|
| **0** | Raw Capture | ESP32 Core 0 | 802.11 PHY frames | ADR-018 binary datagrams | < 1 ms |
| **1** | DSP Statistics | ESP32 Core 1 | Raw I/Q arrays | Phase-unwrapped, filtered subcarrier streams; running variance; top-K selection | < 5 ms |
| **2** | Vitals Extraction | Server (Node.js) | Filtered streams from all nodes | Respiration rate (BRM), cardiac rate (BPM), motion energy index | < 20 ms |
| **3** | WASM Edge Inference | Server / ESP32 PSRAM | Tier 2 features | Pose keypoints, fall alerts, occupancy count, DensePose mesh | < 50 ms |

### 3.3 Server Architecture

| Component | Technology | Role |
|---|---|---|
| Ingestion Server | Node.js / TypeScript, `dgram` | UDP listener on port 5005; ADR-018 binary parsing |
| Signal Processor | TypeScript DSP module | MUSIC AoA, PDP ranging, Hampel filtering, EMA background subtraction |
| WebSocket Server | `ws` library, port 5000 | Real-time frame broadcast to dashboard clients at 20 Hz |
| REST API | Express.js | System control endpoints, session management, interface enumeration |
| Persistence | CSV / SQLite | Session recording to `data/sessions/` for offline analysis and audit |

---

## 4. Algorithmic Deep-Dive

This section provides the mathematical foundation, functional purpose, and implementation logic for each core algorithm in the PHANTOM SCAN signal processing pipeline.

---

### 4.A — CSI Phase Unwrapping

#### Functional Purpose

Raw CSI phase values extracted from the ESP32 Wi-Fi driver are wrapped within the interval $[-\pi, +\pi]$ due to the inherent modular arithmetic of IQ-to-angle conversion. This wrapping introduces artificial $2\pi$ discontinuities that corrupt downstream filtering and vital-sign extraction. Phase unwrapping applies a **linear phase correction model** to remove these discontinuities and produce a continuous, monotonic phase stream suitable for motion analysis.

#### Mathematical Definition

Given raw phase measurements $\phi[k]$ across $K$ subcarriers for a single CSI frame, the unwrapped phase $\hat{\phi}[k]$ is computed as:

$$
\hat{\phi}[k] = \phi[k] - \left( a \cdot k + b \right)
$$

Where the linear correction coefficients are derived via least-squares regression over the subcarrier index:

$$
a = \frac{K \sum_{k} k \cdot \phi[k] - \left(\sum_{k} k\right)\left(\sum_{k} \phi[k]\right)}{K \sum_{k} k^2 - \left(\sum_{k} k\right)^2}
$$

$$
b = \frac{1}{K} \left( \sum_{k} \phi[k] - a \sum_{k} k \right)
$$

This removes the linear component (caused by symbol timing offset and carrier frequency offset), leaving only the **residual phase** that encodes environmental motion.

#### Implementation Logic

```
PROCEDURE PhaseUnwrap(iq_array[K][2]):
    FOR k = 0 TO K-1:
        φ[k] = atan2(iq_array[k][Q], iq_array[k][I])
    END FOR
    
    // Least-squares linear fit
    sum_k  = K*(K-1)/2
    sum_k2 = K*(K-1)*(2K-1)/6
    sum_φ  = Σ φ[k]
    sum_kφ = Σ k·φ[k]
    
    a = (K·sum_kφ - sum_k·sum_φ) / (K·sum_k2 - sum_k²)
    b = (sum_φ - a·sum_k) / K
    
    FOR k = 0 TO K-1:
        φ_unwrapped[k] = φ[k] - (a·k + b)
    END FOR
    
    RETURN φ_unwrapped
```

| Parameter | Value |
|---|---|
| Input | Raw I/Q array, $K = 52$ (HT20) or $K = 114$ (HT40) |
| Output | Unwrapped phase vector $\hat{\phi}[k]$ |
| Complexity | $O(K)$ per frame |
| Execution tier | Tier 1 (ESP32 Core 1) |

---

### 4.B — Biquad IIR Filtering (Dual-Stage)

#### Functional Purpose

Human vital signs produce extremely subtle periodic phase perturbations superimposed on a background of environmental noise, body sway, and hardware drift. To isolate these micro-movements, PHANTOM SCAN employs two cascaded **second-order IIR (biquad) bandpass filters** — one tuned to the respiration band and one tuned to the cardiac band — applied independently to the unwrapped phase stream of each selected subcarrier.

#### Mathematical Definition

The transfer function of a second-order (biquad) IIR section in the $z$-domain is:

$$
H(z) = \frac{b_0 + b_1 z^{-1} + b_2 z^{-2}}{1 + a_1 z^{-1} + a_2 z^{-2}}
$$

The difference equation (Direct Form I) for real-time computation:

$$
y[n] = b_0 \cdot x[n] + b_1 \cdot x[n\!-\!1] + b_2 \cdot x[n\!-\!2] - a_1 \cdot y[n\!-\!1] - a_2 \cdot y[n\!-\!2]
$$

Filter design is performed via the **bilinear transform** of an analog Butterworth prototype:

$$
s = \frac{2}{T} \cdot \frac{1 - z^{-1}}{1 + z^{-1}}
$$

Where $T = 1/f_s$ is the sampling period.

#### Dual-Stage Band Specification

| Stage | Band | $f_{low}$ (Hz) | $f_{high}$ (Hz) | Physiological Target | Order |
|---|---|---|---|---|---|
| **Respiration** | Bandpass | 0.1 | 0.5 | Chest wall displacement (12–30 BRM) | 2nd (biquad) |
| **Cardiac** | Bandpass | 0.8 | 2.0 | Heart wall micro-motion (48–120 BPM) | 2nd (biquad) |

#### Implementation Logic

```
STRUCTURE BiquadState:
    b0, b1, b2    : float  // Numerator coefficients
    a1, a2        : float  // Denominator coefficients
    x1, x2        : float  // Input delay line  (init 0)
    y1, y2        : float  // Output delay line (init 0)

FUNCTION biquad_process(state, x_in) -> float:
    y_out = state.b0 * x_in
          + state.b1 * state.x1
          + state.b2 * state.x2
          - state.a1 * state.y1
          - state.a2 * state.y2
    
    // Shift delay line
    state.x2 = state.x1
    state.x1 = x_in
    state.y2 = state.y1
    state.y1 = y_out
    
    RETURN y_out

// Per-frame processing for each selected subcarrier:
resp_sample = biquad_process(respiration_filter, φ_unwrapped[k])
card_sample = biquad_process(cardiac_filter,     φ_unwrapped[k])
```

| Parameter | Value |
|---|---|
| Sampling rate $f_s$ | 20 Hz (nominal CSI frame rate) |
| Coefficient precision | IEEE 754 single-precision float |
| Memory per filter | 7 floats (28 bytes) |
| Execution tier | Tier 1 (ESP32 Core 1) |

---

### 4.C — Welford's Method for Running Variance

#### Functional Purpose

Motion detection in PHANTOM SCAN relies on quantifying the **temporal energy** of subcarrier phase fluctuations. A high variance indicates dynamic scattering (human motion), while a low variance indicates a static channel. Welford's online algorithm computes the sample mean and variance **incrementally** — processing one observation at a time — without requiring storage of historical samples, making it ideal for memory-constrained embedded systems.

#### Mathematical Definition

Given a stream of observations $x_1, x_2, \ldots, x_n$, Welford's method maintains three accumulators:

**Count:**

$$
n \leftarrow n + 1
$$

**Running mean:**

$$
\bar{x}_n = \bar{x}_{n-1} + \frac{x_n - \bar{x}_{n-1}}{n}
$$

**Running sum of squared differences (M₂):**

$$
M_{2,n} = M_{2,n-1} + (x_n - \bar{x}_{n-1})(x_n - \bar{x}_n)
$$

**Sample variance:**

$$
\sigma_n^2 = \frac{M_{2,n}}{n - 1}, \quad n \geq 2
$$

This formulation is **numerically stable** — unlike the naive two-pass formula — because it avoids catastrophic cancellation when the mean is large relative to the variance.

#### Implementation Logic

```
STRUCTURE WelfordAccumulator:
    count : uint32 = 0
    mean  : float  = 0.0
    M2    : float  = 0.0

FUNCTION welford_update(acc, new_value):
    acc.count += 1
    delta      = new_value - acc.mean
    acc.mean  += delta / acc.count
    delta2     = new_value - acc.mean
    acc.M2    += delta * delta2

FUNCTION welford_variance(acc) -> float:
    IF acc.count < 2:
        RETURN 0.0
    RETURN acc.M2 / (acc.count - 1)

FUNCTION welford_reset(acc):
    acc.count = 0
    acc.mean  = 0.0
    acc.M2    = 0.0
```

| Parameter | Value |
|---|---|
| Memory per subcarrier | 12 bytes (1 × uint32, 2 × float) |
| Reset interval | Every 300 frames (15 seconds at 20 Hz) |
| Execution tier | Tier 1 (ESP32 Core 1) |

---

### 4.D — Top-K Subcarrier Selection (Variance-Based)

#### Functional Purpose

Not all subcarriers carry equal motion information. Some subcarriers experience deep frequency-selective fading or hardware-induced noise floors that corrupt downstream analysis. The **Top-K selection algorithm** dynamically identifies the $K$ subcarriers exhibiting the highest **phase variance** — a proxy for motion sensitivity — and routes only those subcarriers to the vital-sign extraction pipeline. This maximises the effective signal-to-noise ratio (SNR) while reducing computational load.

#### Mathematical Definition

Let $\sigma_k^2$ denote the running phase variance (computed via Welford's method) for subcarrier index $k$, where $k \in \{0, 1, \ldots, N\!-\!1\}$ and $N$ is the total subcarrier count.

The Top-K set $\mathcal{S}$ is defined as:

$$
\mathcal{S} = \underset{|\mathcal{S}| = K}{\arg\max} \sum_{k \in \mathcal{S}} \sigma_k^2
$$

Equivalently, $\mathcal{S}$ contains the indices of the $K$ largest elements of the variance vector $\boldsymbol{\sigma}^2 = [\sigma_0^2, \sigma_1^2, \ldots, \sigma_{N-1}^2]$.

A **minimum variance threshold** $\tau$ is applied to exclude subcarriers below the noise floor:

$$
\mathcal{S}' = \{ k \in \mathcal{S} \mid \sigma_k^2 \geq \tau \}
$$

#### Implementation Logic

```
CONSTANT K = 8           // Number of subcarriers to select
CONSTANT τ = 0.001       // Minimum variance threshold

FUNCTION select_top_k(variance_array[N]) -> index_set:
    // Partial sort: O(N + K·log K)
    candidates = []
    FOR k = 0 TO N-1:
        IF variance_array[k] >= τ:
            candidates.append((k, variance_array[k]))
    END FOR
    
    // Sort descending by variance
    partial_sort(candidates, K, descending=true)
    
    RETURN candidates[0 : K].indices
```

| Parameter | Value |
|---|---|
| Total subcarriers $N$ | 52 (HT20) / 114 (HT40) |
| Selected subset $K$ | 8 (configurable, 6–12 range) |
| Variance threshold $\tau$ | 0.001 (auto-calibrated via noise floor) |
| Selection refresh interval | Every 300 frames (15 seconds) |
| Execution tier | Tier 1 (ESP32 Core 1) → Tier 2 (Server) |

---

### 4.E — Zero-Crossing & Autocorrelation (BPM Extraction)

#### Functional Purpose

After bandpass filtering, the vital-sign signal approximates a quasi-sinusoidal waveform whose fundamental frequency corresponds to the respiration or cardiac rate. Two complementary time-domain methods are employed to extract the period: **zero-crossing detection** for fast, low-cost estimation, and **autocorrelation** for noise-robust refinement.

#### Mathematical Definition

**Zero-Crossing Rate:**

Given a filtered signal $y[n]$ over a window of $W$ samples, a zero-crossing occurs when $y[n] \cdot y[n\!-\!1] < 0$. The number of zero-crossings $Z$ yields the estimated frequency:

$$
f_{zc} = \frac{Z}{2 \cdot W / f_s} \quad \text{Hz}
$$

Converting to beats/breaths per minute:

$$
\text{BPM} = f_{zc} \times 60
$$

**Autocorrelation Function:**

The normalised autocorrelation of $y[n]$ at lag $\ell$ is:

$$
R[\ell] = \frac{\sum_{n=0}^{W-\ell-1} y[n] \cdot y[n + \ell]}{\sum_{n=0}^{W-1} y[n]^2}
$$

The fundamental period $T_0$ is estimated as the lag of the **first prominent peak** in $R[\ell]$ beyond the origin:

$$
T_0 = \underset{\ell \in [\ell_{\min}, \ell_{\max}]}{\arg\max} \; R[\ell]
$$

$$
\text{BPM} = \frac{60 \cdot f_s}{T_0}
$$

Where $\ell_{\min}$ and $\ell_{\max}$ define the physiological search bounds:

| Vital Sign | $\ell_{\min}$ | $\ell_{\max}$ | Rate Range |
|---|---|---|---|
| Respiration | 40 samples | 200 samples | 6–30 BRM |
| Cardiac | 10 samples | 25 samples | 48–120 BPM |

#### Implementation Logic

```
FUNCTION extract_bpm(signal[W], fs, l_min, l_max) -> float:
    // --- Method 1: Zero-Crossing ---
    zero_crossings = 0
    FOR n = 1 TO W-1:
        IF signal[n] * signal[n-1] < 0:
            zero_crossings += 1
    END FOR
    f_zc = zero_crossings / (2.0 * W / fs)
    bpm_zc = f_zc * 60.0
    
    // --- Method 2: Autocorrelation (refinement) ---
    R = ARRAY[l_max + 1] initialized to 0.0
    energy = SUM(signal[n]² for n in 0..W-1)
    
    FOR lag = l_min TO l_max:
        FOR n = 0 TO W - lag - 1:
            R[lag] += signal[n] * signal[n + lag]
        END FOR
        R[lag] /= energy
    END FOR
    
    T0 = argmax(R[l_min .. l_max])
    bpm_ac = 60.0 * fs / T0
    
    // Fuse: prefer autocorrelation if peak confidence > 0.6
    IF R[T0] > 0.6:
        RETURN bpm_ac
    ELSE:
        RETURN bpm_zc
```

| Parameter | Value |
|---|---|
| Window size $W$ | 200 samples (10 seconds at 20 Hz) |
| Output update rate | Every 100 samples (5-second sliding advance) |
| Execution tier | Tier 2 (Server, Node.js) |

---

### 4.F — Adaptive Thresholding (Nuisance Filtering)

#### Functional Purpose

Static objects (furniture, walls, HVAC reflections) and periodic environmental disturbances (oscillating fans, automated doors) contribute a **background variance floor** that can trigger false-positive motion alerts. The adaptive thresholding algorithm maintains a **60-second sliding window** of ambient variance measurements to continuously calibrate the noise floor, dynamically adjusting the detection threshold to the current environment.

#### Mathematical Definition

Let $E[t]$ denote the aggregate motion energy at time $t$, computed as the mean variance across the Top-K subcarriers:

$$
E[t] = \frac{1}{K} \sum_{k \in \mathcal{S}} \sigma_k^2[t]
$$

The adaptive threshold $\Theta[t]$ is computed from the statistics of a sliding window of duration $T_w = 60$ seconds (1200 samples at 20 Hz):

**Sliding-window mean:**

$$
\mu_E[t] = \frac{1}{T_w f_s} \sum_{i=t-T_w f_s}^{t} E[i]
$$

**Sliding-window standard deviation:**

$$
\sigma_E[t] = \sqrt{\frac{1}{T_w f_s - 1} \sum_{i=t-T_w f_s}^{t} \left(E[i] - \mu_E[t]\right)^2}
$$

**Adaptive threshold:**

$$
\Theta[t] = \mu_E[t] + \alpha \cdot \sigma_E[t]
$$

Where $\alpha$ is a sensitivity multiplier (default $\alpha = 3.0$, corresponding to a 99.7% confidence bound under Gaussian assumptions).

**Detection decision:**

$$
\text{Motion Detected}[t] = 
\begin{cases}
\text{TRUE} & \text{if } E[t] > \Theta[t] \\
\text{FALSE} & \text{otherwise}
\end{cases}
$$

#### Implementation Logic

```
CONSTANT WINDOW_SIZE = 1200    // 60 seconds × 20 Hz
CONSTANT ALPHA       = 3.0     // Sensitivity multiplier

STRUCTURE AdaptiveThreshold:
    ring_buffer[WINDOW_SIZE] : float
    write_index              : uint16 = 0
    welford                  : WelfordAccumulator  // reused from §4.C

FUNCTION update_threshold(state, energy_value) -> (threshold, is_motion):
    // Evict oldest sample if buffer is full
    IF state.write_index >= WINDOW_SIZE:
        // Use circular buffer; Welford must be periodically
        // recomputed or maintained with a remove operation.
        recompute_welford(state)
    END IF
    
    state.ring_buffer[state.write_index % WINDOW_SIZE] = energy_value
    state.write_index += 1
    
    welford_update(state.welford, energy_value)
    
    μ = state.welford.mean
    σ = sqrt(welford_variance(state.welford))
    
    threshold = μ + ALPHA * σ
    is_motion = (energy_value > threshold)
    
    RETURN (threshold, is_motion)
```

| Parameter | Value |
|---|---|
| Sliding window $T_w$ | 60 seconds |
| Buffer size | 1200 samples |
| Sensitivity $\alpha$ | 3.0 (configurable 2.0–5.0) |
| Cold-start period | First 60 seconds (threshold = ∞, no alerts) |
| Execution tier | Tier 2 (Server, Node.js) |

---

## 5. Edge Intelligence (WASM) & Storage

### 5.1 WebAssembly Runtime

Tier 3 inference modules are compiled to **WebAssembly (WASM)** and executed within a sandboxed runtime on the server (or optionally on ESP32-S3 with PSRAM). This architecture enables **hot-swappable logic** — new detection models can be deployed without firmware reflash or server restart.

#### RVF (RuVector Format) Module Containers

| Field | Size | Description |
|---|---|---|
| Magic | 4 bytes | `0x52564600` ("RVF\0") |
| Version | 2 bytes | Container format version |
| Module ID | 16 bytes | UUID v4 of the logic module |
| Timestamp | 8 bytes | Unix epoch of build time |
| WASM Size | 4 bytes | Size of the WASM binary payload |
| WASM Binary | Variable | Compiled WebAssembly bytecode |
| Ed25519 Signature | 64 bytes | Cryptographic signature over all preceding fields |

Every RVF container is **signed** with an Ed25519 keypair. The runtime verifies the signature before instantiation, preventing execution of tampered or unauthorised modules.

### 5.2 Memory Isolation

Each WASM module executes within a **160 KB PSRAM arena** (configurable up to 512 KB) with strict bounds checking:

| Resource | Limit per Module |
|---|---|
| Linear memory | 160 KB (10 × 64 KB pages) |
| Stack depth | 8 KB |
| Execution time | 50 ms hard timeout per invocation |
| Host function calls | Whitelisted API surface only |

Multiple modules may execute concurrently in separate arena slots, enabling parallel inference (e.g., fall detection + occupancy counting).

### 5.3 Session Storage

| Storage Layer | Format | Retention | Purpose |
|---|---|---|---|
| Hot buffer | In-memory ring buffer | 60 seconds | Real-time dashboard feed |
| Session archive | CSV (gzip compressed) | 30 days | Offline analysis, regulatory audit |
| Event log | JSON lines | 90 days | Triggered alerts (fall, entry, exit) |
| Model registry | SQLite | Indefinite | RVF module catalogue and deployment history |

---

## 6. Visualization & UI

### 6.1 Dashboard Architecture

The PHANTOM SCAN dashboard is a **React** single-page application featuring real-time 3D scene rendering via **Three.js** (React Three Fiber).

| Component | Technology | Refresh Rate |
|---|---|---|
| 3D Pose Viewer | Three.js / React Three Fiber | 20 Hz (WebSocket) |
| Vital Signs Monitor | Recharts (line graphs) | 20 Hz |
| Radar / AoA Display | Three.js (radial scene with cardinal labels) | 20 Hz |
| Doppler Spectrogram | Plotly.js (heatmap) | 5 Hz |
| System Control Panel | React + Express REST | On-demand |
| Diagnostic Terminal | SSE (Server-Sent Events) stream | Real-time |

### 6.2 3D Pose Reconstruction (DensePose)

The fused 3D position data from the multistatic mesh is mapped onto a **DensePose** skeleton model within the Three.js scene:

```
Multistatic CSI (N nodes)
        │
        ▼
  ┌─────────────┐
  │ Kalman Fuser │  ──▶  (x, y, z) centroid ± 30 mm
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │ WASM Pose   │  ──▶  17 skeletal keypoints
  │ Estimator   │
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │ Three.js    │  ──▶  Real-time 3D mesh render
  │ DensePose   │
  └─────────────┘
```

### 6.3 WebSocket Protocol

All real-time data is delivered to the dashboard via a WebSocket connection on port 5000, with the following message channels:

| Channel | Payload | Rate |
|---|---|---|
| `csiFrame` | Raw subcarrier amplitude/phase arrays | 20 Hz |
| `vitalSigns` | `{ bpm, brm, confidence, timestamp }` | 20 Hz |
| `isarFrame` | AoA spectrum peaks, distance estimates | 20 Hz |
| `poseFrame` | 17-keypoint skeleton coordinates | 10 Hz |
| `alertEvent` | Fall detection, zone entry/exit | Event-driven |

---

## 7. Security & Privacy

### 7.1 Privacy-by-Design: Optical Comparison

| Dimension | Camera / LIDAR | PHANTOM SCAN (CSI) |
|---|---|---|
| **PII capture** | Face, body, clothing, skin tone | None — RF reflection only |
| **Payload data** | Full video stream | No payload; PHY-layer telemetry only |
| **Consent visibility** | Subject aware of camera | Passive; no emitted signal |
| **GDPR Art. 9 (biometric)** | Likely classified as biometric | Not classified as biometric data |
| **Data breach impact** | Catastrophic (imagery leak) | Minimal (anonymous variance data) |

### 7.2 Data Integrity & Module Security

| Mechanism | Algorithm | Purpose |
|---|---|---|
| MAC address hashing | SHA-256 (in-memory, pre-persist) | GDPR compliance; PII never written to disk |
| RVF module signing | Ed25519 (Curve25519) | Prevent execution of tampered WASM modules |
| OTA firmware signing | Ed25519 (same keypair or separate) | Prevent malicious firmware injection |
| Transport encryption | TLS 1.3 (server ↔ dashboard) | Protect data in transit |
| Session file integrity | HMAC-SHA256 per CSV row | Detect tampering in archived session data |

### 7.3 Secure Task Execution

The server exposes a **whitelisted command spawner** (`child_process.spawn` with `shell: false`) for administrative tasks (monitor mode toggle, interface reboot). This design:

- Prevents shell injection by construction (no shell interpolation).
- Limits executable commands to a static whitelist.
- Logs all invocations with timestamps and originator identity.

---

## 8. Appendix — Specification Summary

### A. System Performance Targets

| Metric | Target | Measurement Condition |
|---|---|---|
| CSI frame rate | 20 Hz | Single AP, HT20, 1 node |
| End-to-end latency (Tier 0 → Dashboard) | < 80 ms | Local network, 1 node |
| Spatial jitter (3D pose) | < 30 mm RMS | 4-node mesh, Kalman fused |
| Respiration rate accuracy | ± 1 BRM | Stationary subject, 1 m range |
| Cardiac rate accuracy | ± 2 BPM | Stationary subject, 1 m range |
| Fall detection latency | < 200 ms | From impact to alert event |
| Maximum through-wall range | 8 m | Yagi antenna, single drywall |
| Occupancy counting accuracy | ≥ 95% | 1–4 persons, 4-node mesh |

### B. Bill of Materials (per Node)

| Component | Part Number / Description | Quantity | Unit Cost (USD) |
|---|---|---|---|
| ESP32-S3-DevKitC-1 | Espressif dev board, 8 MB PSRAM | 1 | ~$8 |
| Yagi antenna (2.4 GHz, 10 dBi) | 5-element, SMA connector | 1 | ~$12 |
| SMA pigtail cable | U.FL to SMA, 15 cm | 1 | ~$3 |
| USB-C cable | Data + power, 1 m | 1 | ~$3 |
| 3D-printed enclosure | ABS/PETG, vented | 1 | ~$2 |
| **Total per node** | | | **~$28** |

### C. Glossary

| Abbreviation | Definition |
|---|---|
| ADR-018 | Application Data Record format 018 (proprietary CSI frame) |
| AoA | Angle of Arrival |
| BPM | Beats Per Minute (cardiac) |
| BRM | Breaths Per Minute (respiration) |
| CSI | Channel State Information |
| DensePose | Dense human pose estimation (body surface mapping) |
| DSP | Digital Signal Processing |
| GDOP | Geometric Dilution of Precision |
| HT20 / HT40 | High Throughput 20 MHz / 40 MHz channel bandwidth |
| IIR | Infinite Impulse Response (filter) |
| MUSIC | MUltiple SIgnal Classification (AoA algorithm) |
| NLOS | Non-Line-of-Sight |
| PDP | Power Delay Profile |
| PSRAM | Pseudo-Static Random Access Memory |
| RVF | RuVector Format (WASM module container) |
| SNR | Signal-to-Noise Ratio |
| WASM | WebAssembly |

---

*End of Document — PHANTOM SCAN System Design & Technical Architecture Report v2.0*
