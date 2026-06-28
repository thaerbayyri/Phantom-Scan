# Phantom Scan — RF Validation Protocol: Dual-Target NLOS Detection

> **Document:** VTP-PS-002 — Multi-Target Through-Wall Validation  
> **Classification:** Engineering Test Report  
> **Author:** Senior RF Test Engineer  
> **Revision:** 1.0 — 2026-03-31  
> **Project:** PHANTOM SCAN v1.1  

---

## 1. OBJECTIVE

Verify that the ESP32-S3 CSI collection pipeline (`csi_collector.c` → `edge_processing.c` → `stream_sender.c` → Node.js `signal-processing.ts` → `vitals.ts`) can **spectrally resolve TWO independent human breathing signatures** at distances of 3m and 6m through a 20cm concrete/drywall barrier (NLOS), without mutual interference or spectral leakage between targets.

### 1.1 Pass Criteria

| Metric | Threshold |
|--------|-----------|
| Breathing Rate Accuracy (Target A) | ≤ ±2 BPM vs. ground truth |
| Breathing Rate Accuracy (Target B) | ≤ ±3 BPM vs. ground truth (relaxed for NLOS/far) |
| SNR (Target A, near) | ≥ 10 dB |
| SNR (Target B, far)  | ≥ 5 dB |
| False Positive Ratio  | ≤ 15% |
| Spectral Separation   | Two distinct PSD peaks in 0.1–0.5 Hz with ≥ 3 dB valley |
| Variance Masking Test | Target B variance > 10% of Target A variance |

---

## 2. TEST CONFIGURATION

### 2.1 Node Deployment — Bistatic Array

```
                    ███████████████████████████████████
                    █          20cm WALL              █
                    ███████████████████████████████████
                        │                   │
    TX ─── 2m ────► ██ WALL ██          ██ WALL ██
                        │                   │
                   3m   │              6m   │
                        ▼                   ▼
                   ┌─────────┐         ┌─────────┐
                   │Target A │         │Target B  │
                   │ Seated  │         │ Standing │
                   │ 0.25 Hz │         │ 0.40 Hz  │
                   │ Normal  │         │ Elevated │
                   └─────────┘         └─────────┘
                        │                   │
              ┌────────────┐       ┌─────────────┐
              │   RX-1     │       │   RX-2      │
              │ ESP32-S3 #1│       │ ESP32-S3 #2 │
              │ NodeID=0   │       │ NodeID=1    │
              └────────────┘       └─────────────┘
                    │                       │
                    └───── UDP:5005 ────────┘
                              │
                    ┌────────────────────┐
                    │  Phantom Scan      │
                    │  Node.js Server    │
                    │  (signal-processing│
                    │   + vitals.ts)     │
                    └────────────────────┘
```

### 2.2 Hardware Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **TX ESP32-S3** | 1 unit | `csi_inject_ndp_frame()` @ 20 Hz |
| **RX ESP32-S3** | 2 units | `csi_collector_init()`, NodeID 0/1 |
| **WiFi Channel** | 6 (2.437 GHz) | Fixed, no channel hopping |
| **Bandwidth** | 20 MHz (HT20) | 52 usable subcarriers |
| **TX Power** | 20 dBm (100 mW) | `esp_wifi_set_max_tx_power(80)` |
| **Antenna** | PCB onboard | 2.4 GHz ISM band |
| **LNA** | Default (no external) | See §5.2 for NLOS failure adjustment |
| **Wall Type** | Concrete/drywall, 20 cm | Attenuation ~8–15 dB |
| **ADR-018 Format** | Binary UDP | Magic `0xC5110001` |
| **Edge Tier** | 2 (Full pipeline) | Vital extraction on-device |

### 2.3 Target Specification 

| | Target A | Target B |
|---|----------|----------|
| **Posture** | Seated, stationary | Standing, slight sway |
| **Distance from RX** | 3 meters | 6 meters |
| **Breathing Rate** | ~15 BPM (0.25 Hz) | ~24 BPM (0.40 Hz) |
| **Ground Truth** | Manual count + chest strap | Manual count + chest strap |
| **Expected SNR** | 10–20 dB (near, LOS/NLOS) | 5–12 dB (far, NLOS) |

---

## 3. ALGORITHMIC ANALYSIS TASKS

### 3.A Phase Sanitization — SFO/PDD Removal

**Problem:** The ESP32's ADC introduces Sampling Frequency Offset (SFO) that appears as a linear phase drift across subcarriers, and Packet Detection Delay (PDD) that adds a constant phase offset per frame.

**Solution:** Linear regression on unwrapped phase across subcarrier index `k`:

```
φ_clean(k) = φ_raw(k) - (â·k + b̂)

where â = SFO slope, b̂ = PDD intercept
```

The Python validation script `scripts/rf_validation/phase_sanitizer.py` implements this by:
1. Unwrapping phase across all 52 subcarriers per frame
2. Fitting `numpy.polyfit(k, φ_unwrapped, deg=1)` 
3. Subtracting the fitted line to yield sanitized phase

**Existing Code Gap:** The firmware `edge_processing.c` performs per-subcarrier phase unwrapping (line 602–611) but does **not** apply cross-subcarrier linear regression. The Python script `csi_filter_pipeline.py` has a `PhaseSanitizer` class that does this correctly. The new validation script replicates and enhances this.

### 3.B Top-K Subcarrier Selection for Target B

**Problem:** Not all 52 subcarriers respond equally to Target B (the far, NLOS target). Many subcarriers may be dominated by Target A's stronger reflection.

**Solution:** Use Welford's running variance (already implemented in `edge_processing.c` line 153–165) to rank subcarriers. Then, perform per-subcarrier spectral analysis in the breathing band (0.1–0.5 Hz) to cluster subcarriers by dominant frequency:

- **Group 1** (Target A): Subcarriers whose PSD peaks near 0.25 Hz
- **Group 2** (Target B): Subcarriers whose PSD peaks near 0.40 Hz

The Top-K for Target B are those in Group 2 with highest variance.

### 3.C Spectral Separation via FFT PSD

**Expected Result:**

```
Power Spectral Density
  │
  │    ╱╲               ╱╲
  │   ╱  ╲ Target A    ╱  ╲ Target B
  │  ╱    ╲           ╱    ╲
  │ ╱      ╲    ≥3dB ╱      ╲
  │╱        ╲__valley╱        ╲___
  └──────────────────────────────── Freq (Hz)
  0    0.1   0.25   0.33  0.40   0.5
```

**Pass condition:** Two distinct peaks in the 0.1–0.5 Hz band with ≥ 3 dB valley between them.

### 3.D Variance Mapping — Motion Energy Masking Analysis

**Problem:** Target A at 3m produces much stronger CSI perturbations than Target B at 6m through a wall. The question is whether Target B's breathing signature is being "masked" by Target A's proximity.

**Method:** Compute Welford's variance independently for each target's subcarrier group, then calculate the masking ratio:

```
Masking Ratio = Var(Target_B_group) / Var(Target_A_group)
```

If `Masking Ratio < 0.10` (10%), Target B is critically masked and antenna/filter adjustments are needed (see §5).

---

## 4. DATA LOGGING REQUIREMENTS

### 4.1 Capture Parameters

| Parameter | Value |
|-----------|-------|
| Capture Duration | 120 seconds per test run |
| Output Format | CSV (primary) + ADR-018 Binary (archival) |
| Sample Rate | 20 Hz (firmware default) |
| Total Frames | 2400 per 120s run |
| Subcarriers Logged | 1–52 (all usable HT20 subcarriers) |

### 4.2 CSV Schema

```csv
timestamp_ms,node_id,rssi,channel,subcarrier_count,phase_sc0,...,phase_sc51,amplitude_sc0,...,amplitude_sc51,breathing_bpm,heartrate_bpm,motion_energy,presence_score,n_persons
```

### 4.3 Metrics to Report Per Test Run

| Metric | Computation |
|--------|-------------|
| **SNR_A** | `10*log10(Var(Target_A_subcarriers) / Var(noise_floor_subcarriers))` |
| **SNR_B** | `10*log10(Var(Target_B_subcarriers) / Var(noise_floor_subcarriers))` |
| **BR_A (BPM)** | Peak frequency in 0.1–0.5 Hz band from Target A subcarrier group × 60 |
| **BR_B (BPM)** | Peak frequency in 0.1–0.5 Hz band from Target B subcarrier group × 60 |
| **Error_A** | `|BR_A - Ground_Truth_A|` |
| **Error_B** | `|BR_B - Ground_Truth_B|` |
| **FP Ratio** | `(False presence detections in empty-room baseline) / (Total frames)` |
| **Masking Ratio** | `Var(Group_B) / Var(Group_A)` |

---

## 5. TROUBLESHOOTING DECISION TREE

### 5.1 Only One PSD Peak Found

```
┌─────────────────────────────────────┐
│     Only 1 peak in 0.1–0.5 Hz?     │
└──────────────┬──────────────────────┘
               │
       ┌───────▼───────┐
       │ Peak near 0.25│──YES──► Target B is masked
       │   Hz only?    │         │
       └───────┬───────┘         ▼
               │          ┌───────────────────────┐
              NO          │ ADJUSTMENT ACTIONS:    │
               │          │ 1. Narrow biquad BW:   │
               ▼          │    Change f_hi from    │
       Target A is        │    0.5 to 0.35 Hz to   │
       the one masked     │    isolate Target A    │
       (very unlikely)    │                        │
                          │ 2. Re-position antenna │
                          │    to improve Target B │
                          │    multipath geometry  │
                          │                        │
                          │ 3. Increase Top-K from │
                          │    8 to 16 subcarriers │
                          │    to capture weaker   │
                          │    Target B response   │
                          └───────────────────────┘
```

**Biquad Coefficient Fix (firmware `edge_processing.c`):**

To split the single breathing band into two narrower bands for per-target isolation:

```c
/* BEFORE (single broadband): */
biquad_bandpass_design(&s_bq_breathing, fs, 0.1f, 0.5f);

/* AFTER (dual narrowband for target separation): */
/* Band A: Normal breathing 0.15–0.30 Hz (Target A @ 0.25 Hz) */
biquad_bandpass_design(&s_bq_breathing_a, fs, 0.15f, 0.30f);
/* Band B: Elevated breathing 0.30–0.50 Hz (Target B @ 0.40 Hz) */
biquad_bandpass_design(&s_bq_breathing_b, fs, 0.30f, 0.50f);
```

### 5.2 Signal Lost Through Wall

```
┌─────────────────────────────────────┐
│  SNR_B < 5 dB through wall?        │
└──────────────┬──────────────────────┘
               │
       ┌───────▼───────┐
       │ Check RSSI:   │
       │ < -75 dBm?    │──YES──► PHY Layer adjustments needed
       └───────┬───────┘         │
              NO                 ▼
               │          ┌───────────────────────────┐
               ▼          │ ESP-IDF PHY Adjustments:   │
       Check if wall      │                           │
       attenuation is     │ 1. Max TX power:          │
       > 15 dB and        │    esp_wifi_set_max_tx_   │
       use external       │    power(84); // +21 dBm  │
       antenna            │                           │
                          │ 2. Enable LNA gain:       │
                          │    In sdkconfig:          │
                          │    CONFIG_ESP32S3_        │
                          │    DEFAULT_PHY_TX_POWER=84│
                          │                           │
                          │ 3. Reduce hop/dwell to    │
                          │    maximize ON-channel    │
                          │    time (no hopping)      │
                          │                           │
                          │ 4. External antenna via   │
                          │    U.FL connector if PCB  │
                          │    antenna insufficient   │
                          └───────────────────────────┘
```

---

## 6. EXECUTION PROTOCOL

### Test Run Sequence

| Step | Action | Duration |
|------|--------|----------|
| 1 | Empty room baseline (no targets) | 120s |
| 2 | Target A only (seated, 3m) | 120s |
| 3 | Target B only (standing, 6m) | 120s |
| 4 | Both targets simultaneously | 120s |
| 5 | Both targets, NLOS (wall between TX and targets) | 120s |
| 6 | Post-processing: run `dual_target_analyzer.py` | — |

### Ground Truth Capture

Each test subject wears a respiratory belt or uses a manual breath counter. The observer records timestamps of inhalation peaks to establish a reference BPM.

---

## 7. ASSOCIATED SCRIPTS

| Script | Purpose |
|--------|---------|
| `scripts/rf_validation/phase_sanitizer.py` | SFO/PDD removal via linear regression |
| `scripts/rf_validation/dual_target_analyzer.py` | Full analysis: PSD, variance mapping, SNR, dual-target plotting |
| `scripts/rf_validation/nlos_capture.py` | 120s CSI capture logging to CSV with all 52 subcarrier phases |

---

## 8. REVISION HISTORY

| Rev | Date | Change |
|-----|------|--------|
| 1.0 | 2026-03-31 | Initial dual-target NLOS validation protocol |
