# CSI Phase in Wi-Fi Sensing

How Channel State Information (CSI) phase is used for sensing, and where it is
actually used in this codebase. This is standard OFDM/CSI-sensing theory
mapped onto the concrete implementation in `phantom/dsp.py`,
`server/lib/signal-processing.ts`, and `scripts/rf_validation/phase_sanitizer.py`.

## The core idea

CSI gives a complex number `H(k) = I + jQ` per OFDM subcarrier `k`, per
antenna link. From that you get two things:

- **Amplitude** `|H(k)|` — how much the signal attenuated on that path
- **Phase** `∠H(k) = atan2(Q, I)` — how much the signal's carrier was
  delayed/shifted on that path

Amplitude tells you *something* moved. Phase tells you **how far** and **how
fast**, because phase is directly proportional to path length:

```text
φ = 2π · f_c · τ        (τ = propagation delay = distance / c)
```

A moving target (chest wall breathing, a person walking) continuously
changes the path length, so it continuously changes phase — often by amounts
far smaller than what amplitude can resolve. This is why phase is the
preferred channel for **vital signs** (sub-millimeter chest displacement)
and **fine motion/ranging**, while amplitude is typically used for coarse
**presence/motion** detection.

## Why raw phase is unusable directly

Commodity Wi-Fi radios (the ESP32-S3 nodes in this project included) don't
synchronize TX/RX clocks or lock packet-detection timing, so raw phase is
corrupted by two hardware artifacts before any real motion signal shows up:

1. **SFO (Sampling Frequency Offset)** — clock drift between TX/RX → shows
   up as a **linear phase slope across subcarrier index**
2. **PDD (Packet Detection Delay)** — variable frame-sync timing → shows up
   as a **constant phase offset per packet**

[`scripts/rf_validation/phase_sanitizer.py`](../../scripts/rf_validation/phase_sanitizer.py)
implements the standard fix (Algorithm 3.A from VTP-PS-002): unwrap phase
across subcarriers, fit a line `φ(k) = a·k + b` by least squares, and
subtract it off. The slope `a` is the SFO, the intercept `b` is the PDD, and
what survives is the true motion-induced phase. The module's own synthetic
self-test injects a known sinusoidal breathing phase profile plus known
SFO/PDD and confirms the sanitizer recovers the breathing correlation
(`> 0.90`) while extracting the SFO within `0.01` rad.

The module's docstring notes that `edge_processing.c` (firmware) currently
only does temporal unwrapping, not this cross-subcarrier regression — the
firmware-side path is not yet doing the full sanitization the Python
reference does.

## Where phase is used downstream in this pipeline

Once you have clean phase (or the raw complex `H = re + j·im`, which encodes
both amplitude and phase together), the codebase uses it for three distinct
sensing tasks:

| Use case | File | Mechanism |
|---|---|---|
| **AoA (Angle of Arrival)** | [`server/lib/signal-processing.ts`](../../server/lib/signal-processing.ts) `computeMUSICSpectrum` | Builds a spatial covariance matrix from multi-antenna complex samples; the **phase difference between antennas** for a given angle is the MUSIC steering vector `a(θ) = e^{-j·2π·d·n·sin(θ)}` — pure inter-antenna phase geometry |
| **Ranging / distance** | [`server/lib/signal-processing.ts`](../../server/lib/signal-processing.ts) `PDPRanger` | IFFTs the complex CSI vector into a Power Delay Profile; peak bin position (which depends on phase-derived time-of-flight) → distance in cm |
| **Vital signs (breathing/heart rate)** | [`phantom/dsp.py`](../../phantom/dsp.py) `extract_phases`, `unwrap_phase_series`, `RespirationBandFilter` | `atan2(Q,I)` → unwrap → bandpass-filter 0.1–0.5 Hz to isolate the breathing-rate phase oscillation |
| **1-D on-axis position (two-node)** | [`phantom/dsp.py`](../../phantom/dsp.py) `dual_node_on_axis_position` | Uses **amplitude balance** between nodes, not phase — phase isn't used here since the two ESP32 nodes aren't phase-synchronized to each other |

Note the asymmetry: within a single node's antenna pair, phase differences
are trustworthy (same clock, same packet) and drive AoA/ranging. Across the
two separate ESP32 nodes, there's no shared clock, so
[`dsp.py`](../../phantom/dsp.py) `dual_node_on_axis_position` deliberately
falls back to amplitude balance for cross-node localization rather than
trying to compare phase between nodes.

## Open gap

`edge_processing.c` (firmware) has not been confirmed to implement the
cross-subcarrier SFO/PDD regression that `phase_sanitizer.py` documents as
missing on that path. If board-side phase output is ever relied on directly
(rather than only the host-side Python/TS paths above), that gap should be
closed or explicitly re-verified first.
