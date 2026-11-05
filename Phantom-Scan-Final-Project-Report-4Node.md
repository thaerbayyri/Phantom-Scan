# Phantom Scan — Final Project Report (4-Node Edition)

**Revision note:** This report supersedes the earlier two-node edition of the Phantom Scan final project report. The live system has since been extended from a fixed two-node, one-dimensional rig to a **1–4 node deployment with an auto-selected fusion mode**, primary deployment **four nodes, one per room corner**, producing a genuine **two-dimensional** room-centroid position instead of a projection onto a single axis. This edition also adds a physics/mathematics primer chapter (Chapter 2A) explaining amplitude, phase, OFDM subcarriers, the CSI I/Q model, the MUSIC algorithm, and Fresnel-zone motion coupling — the conceptual foundation the implementation chapters build on — and is explicit about which parts of that theory the live system actually implements versus which remain conceptual/replay-only.

---

## Table of Contents

**CHAPTER 1 INTRODUCTION**
1.1 Introduction · 1.2 Background · 1.3 Problem Statement · 1.4 Limitations · 1.5 Project Objectives · 1.6 Project Solution Overview · 1.7 Project Scope · 1.8 Project Feasibility

**CHAPTER 2 LITERATURE REVIEW**
2.1 Introduction · 2.2 Review of Existing Systems · 2.3 Comparison of Existing Solutions

**CHAPTER 2A PHYSICAL AND MATHEMATICAL FOUNDATIONS OF CSI SENSING** *(new)*
2A.1 Introduction · 2A.2 Amplitude — Wave Strength · 2A.3 Phase — Wave Timing · 2A.4 Carrier, Channel, and Subcarrier · 2A.5 From Wi-Fi to CSI: The I/Q Model · 2A.6 The Fresnel-Zone Model of Human Obstruction · 2A.7 Angle-of-Arrival and the MUSIC Algorithm · 2A.8 From Theory to a Position Estimate — Two Paths · 2A.9 The Cheat-Sheet Pipeline vs. Phantom Scan's Live Pipeline

**CHAPTER 3 METHODOLOGY AND WORK PLAN**
3.1 Introduction · 3.2 System Development Methodology · 3.3 Requirement Gathering Techniques · 3.4 Project Plan · 3.5 Development of Tools and Technologies

**CHAPTER 4 SYSTEM SPECIFICATION**
4.1 Introduction · 4.2 Non-Functional Requirements · 4.3 Functional Requirements

**CHAPTER 5 SYSTEM DESIGN**
5.1 Introduction · 5.2 System Architecture Design · 5.3 Module Interaction Design · 5.4 Database and Data Design · 5.5 User Interface Design

**CHAPTER 6 SYSTEM IMPLEMENTATION**
6.1 Introduction · 6.2 Implementation Overview · 6.3 Implementation Details · 6.4 Component Integration and Workflow · 6.5 Implementation Testing Support · 6.6 Summary

**CHAPTER 7 RESULTS AND DISCUSSION**
7.1 Introduction · 7.2 Data Collection and Research · 7.3 System Testing and User Feedback · 7.4 Discussion

**CHAPTER 8 RECOMMENDATIONS AND CONCLUSION**
8.1 Introduction · 8.2 Conclusion · 8.3 Limitations and Recommendations for Future Work

**REFERENCES**

**APPENDICES** A–I

---

# CHAPTER 1 INTRODUCTION

## 1.1 Introduction

Phantom Scan is an academic and engineering project that investigates how Wi-Fi Channel State Information (CSI) can be used to detect a moving human, estimate that person's position within a room, and present the result truthfully on a live operator dashboard — all without cameras, microphones, or wearable devices. In its current verified state, the system supports **one to four ESP32-S3 microcontroller nodes**, with the **primary live deployment being four nodes, one placed at each corner of the monitored room**. Each node captures CSI from ordinary 2.4 GHz Wi-Fi traffic and streams binary measurement frames over UDP to a laptop host, where a Node/TypeScript runtime performs deterministic signal processing, fuses the live node perspectives into a single target estimate, smooths that estimate with a two-dimensional Kalman filter, and publishes the result to a React dashboard over WebSocket [12].

The core physical insight behind the project is unchanged from its earliest design and remains true at any node count: a human body moving through a radio field perturbs the multipath propagation between transmitter and receiver. Wi-Fi CSI exposes this perturbation at the granularity of individual OFDM subcarriers — when a person walks near a sensing node, the per-subcarrier amplitude of the received channel estimate fluctuates measurably over time, while an empty room produces a comparatively stable channel [6]. What has changed is the geometry the fusion math exploits: with exactly two nodes live, the system still projects the target onto the one-dimensional line between them (as the original rig did); with three or four nodes live, it computes a genuine two-dimensional, perturbation-weighted centroid across every active anchor, because a person's position can now be triangulated against more than one baseline.

The topic remains practically relevant for the same reason it always was: many safety, monitoring, and assistive scenarios need privacy-preserving situational awareness, and radio-frequency sensing observes only propagation changes rather than faces, appearance, or scenes [1].

## 1.2 Background

Research over the past decade has shown that commodity wireless hardware can support contactless sensing tasks ranging from through-wall motion detection [1] to activity recognition [6] and dense human pose estimation [8]. The arrival of CSI extraction support on the low-cost Espressif ESP32 family changed the economics of the field: a complete sensing node now costs roughly the price of a development board rather than laboratory radio equipment [7].

Phantom Scan builds directly on this evolution, and has grown along the axis that ESP32-class hardware actually permits: **node count**, not per-node antenna count. Each ESP32-S3 node remains single-antenna, so the project cannot do multi-antenna spatial Angle-of-Arrival (AoA) the way SpotFi-class systems do [5]; instead it scales the number of independent single-antenna observation points from two to four, turning a 1-D on-axis projection into a genuine 2-D room-centroid estimate without changing the underlying per-node physics. On the host, detection still follows the two-receiver "balance" approach analyzed in the project's RuView study [15], generalized to N receivers: each node independently measures how strongly the channel is being perturbed, and the relative perturbation across all active nodes places the moving person within the room.

An important part of the project's history is scope correction, and it still holds at four nodes: earlier project documents explored drone-mounted sensing, GPS/IMU integration, and large multistatic meshes. Those directions remain explicitly historical — the active repository targets a ground-based, fixed multi-node deployment, and an automated invariant test still fails the build if flight-control concepts re-enter the runtime code [12], [19].

## 1.3 Problem Statement

The problem Phantom Scan addresses is unchanged in kind and has become more demanding in degree: design a low-cost, privacy-first sensing system that can detect and localize a moving human using commodity Wi-Fi hardware, while remaining technically honest about uncertainty, degraded states, and hardware limitations — now across a dynamic set of 1–4 live nodes rather than a fixed pair. A sensing dashboard that paints a target when no live evidence exists is worse than no dashboard at all, and that discipline now has to hold across three distinct fusion modes instead of one.

The problem is therefore still dual. First, an engineering problem: capture CSI reliably on up to four independent embedded nodes, transport it without identity confusion (each node must be distinguishable from the other three, not just from "the other one"), and turn per-subcarrier amplitude fluctuations from a variable number of live nodes into a stable position and motion estimate. Second, a truthfulness problem: guarantee at the architecture level that an empty room shows no target *at any live node count*, that a mode transition (e.g., four nodes dropping to three, or three dropping to two) never silently fabricates or hides a real detection, and that stale data clears instead of ghosting.

## 1.4 Limitations

- **Fusion is not RF multilateration at any node count.** With exactly two nodes live, the target is still placed on the 1-D line between them (as in the original rig). With three or four nodes live, `fuseNodeTargets` computes a perturbation-weighted centroid over the active anchors — a genuine 2-D estimate, but still a proxy derived from relative signal perturbation, not true time-of-flight or phase-based ranging [12], [15].
- Each node still uses a single antenna, so classical multi-antenna Angle-of-Arrival techniques run only on synthetic or replay inputs, never on the live path, at any node count [12].
- The detection gate threshold (`PHANTOM_MOTION_THRESHOLD`, default **0.6**) was set from a single 60 s empty-room recording on the original two-node rig (provisional). **A currently open, actively investigated issue**: repeated real four-node empty-room recordings taken in September 2026 show persistent false-positive presence detection, with the per-node motion metric pinned at its saturation ceiling on roughly half of all ticks — meaning existing four-node recordings are too *censored* (clamped) to safely re-derive the threshold as-is. An unclamped `raw_perturbation_n1..n4` export was added specifically to unblock this diagnosis; the leading unconfirmed hypothesis is RF self-interference among four same-channel, same-AP nodes each self-pinging at ~50 Hz, as an alternative to a genuinely elevated real noise floor.
- Headline live metrics — detection rate, false-positive rate, and localization error — are defined in measurement protocols but not yet populated from repeated four-node live campaigns [20], [21], and the false-positive investigation above means the four-node false-positive rate is *known to be unresolved*, not merely unmeasured.
- Two people in the sensing area still blend into a single fused estimate at any node count; multi-target separation remains out of scope [20].
- A **known historical defect**, since fixed, is worth recording for engineering-process honesty: an earlier revision of the two-node fusion branch, exercised only against the fixed pair {N1, N2}, silently produced a false "no target" state whenever exactly two *other* nodes (e.g., N3+N4) were the ones actually live, because the fusion call still read node 1/2's motion windows regardless of which two nodes `resolveLiveNodeMode()` had identified as active. The current code path resolves this generically — `computeFusedTarget` reads `activeHardwareNodeIds()` and fuses whichever two node IDs are actually live — but this is flagged here because it demonstrates the class of bug the project's own honesty testing exists to catch, and because it is exactly the kind of regression a future geometry or ID-mapping change could reintroduce.

## 1.5 Project Objectives

1. To design and implement a working Wi-Fi CSI capture and transport pipeline using **one to four** ESP32-S3 nodes streaming binary frames over UDP to a laptop host, with no build-time flag needed to change node count.
2. To implement a deterministic human-motion detector based on per-subcarrier amplitude turbulence, with an explicit empty-room gate so that a quiet room produces no target at any live node count.
3. To fuse the live node perspectives into a position estimate that is one-dimensional with exactly two nodes and genuinely two-dimensional with three or four, including per-node distance and approaching/receding/stable trend readouts, and to smooth that estimate with a dedicated 2-D Kalman filter.
4. To build a real-time dashboard that visually distinguishes truthful live targets, degraded node states (1, 2, or 3-of-4 live), stale data, and empty-room silence, scaling its node-beacon rendering to however many nodes are actually configured.
5. To protect the live data path against node identity spoofing and unauthorized access, across up to four independently pinned node identities sharing one UDP port.
6. To document and test the system so that every technical claim — including the still-open four-node calibration issue — maps to a source file, an automated test, or a recorded verification artifact, rather than being silently smoothed over as the node count grew.

## 1.6 Project Solution Overview

The implemented solution is organized into the same five cooperating layers as the original design, generalized to N nodes [12]. Layer A is the ESP32-S3 firmware, unchanged in kind across 1–4 boards: it captures CSI in promiscuous mode, keeps the channel busy with a self-ping mechanism, and streams rate-limited binary frames — each node distinguished only by its own provisioned `node_id` (1–4), never by inter-node coordination (the nodes never talk to each other). Layer B is the host ingest: a Node/TypeScript UDP server that owns port 5005 for **all** live nodes simultaneously, validates packet families by magic number, and source-pins up to four node identities independently. Layer C is the deterministic DSP core: a sliding-window per-subcarrier turbulence metric per node (now computed for however many nodes are live), a motion gate, and a fusion stage that automatically selects between the two-node balance projection and the N-node weighted centroid. Layer D is an optional, advisory AI sidecar, unchanged — disabled by default and unable to override the deterministic result. Layer E is the API and UI layer: an authenticated WebSocket stream feeding a React/Three.js operator dashboard that renders however many node beacons are actually live, plus recording, replay, and reporting tools.

The single most consequential architectural addition since the two-node edition is the **fused-position Kalman filter** (`server/lib/fused-position-kalman.ts`): both fusion modes now feed a shared, natively 2-D constant-velocity Kalman filter before their output reaches the dashboard, because recomputing the fused position from scratch every ~50 ms tick with zero history produced a visibly jittery marker — a problem the original two-node system also had but that becomes more noticeable once the target can move in two true dimensions rather than sliding along one fixed axis.

A parallel Python package continues to provide replay of recorded sessions, protocol parsing, and reference DSP implementations. It remains the test harness and tooling path; the Node/TypeScript runtime is still the single authoritative live ingest in normal operation, and the Python live-authority path is now explicitly *retired* rather than merely discouraged — it refuses to bind unless an operator sets an explicit compatibility override, which must never be set while the dashboard is running [12].

## 1.7 Project Scope

### Project Scope Covered

- One-to-four-node ESP32-S3 CSI capture, ADR-018 binary framing, and UDP transport to a laptop host, with automatic fusion-mode selection (`single_node` → `fused_two_node` → `fused_room`) and no manual mode switch.
- Live human-motion detection, empty-room gating, and fusion that scales from a 1-D on-axis projection (2 nodes) to a genuine 2-D weighted centroid (3–4 nodes), including 2-D Kalman-smoothed position, distance, and trend estimation.
- Authenticated live dashboard with radar-style scenes scaling to up to four node beacons, per-node telemetry, temporal spectral views, and honest state labeling across all three fusion modes.
- Per-session CSV recording with a JSON session index, deterministic replay, threshold calibration tooling, and automated regression testing (256 TypeScript + 91 Python tests at the time of this report).
- Source pinning against node spoofing for up to four independent node identities, operator authentication, and audit logging.

### Project Scope Not Covered

- Drone, UAV, MAVLink, GPS, or IMU-based deployment; these appear only in historical documents and remain excluded from the runtime by an automated scope-guard test [12].
- True RF multilateration or spatial Angle-of-Arrival localization from the live single-antenna node geometry, at any node count.
- Multi-person separation and identification.
- A production-scale multi-tenant database platform; persistence is deliberately file-based.
- Resolution of the currently open four-node empty-room false-positive investigation — that work is defined as the top-priority next step (Chapter 8), not as scope already delivered.

## 1.8 Project Feasibility

Technical feasibility is demonstrated rather than assumed: the repository contains the complete firmware, host runtime, dashboard, and test suites for the 1–4-node system, and the current automated matrix passes in full — **256 TypeScript tests, 0 failures**, and **91 Python tests, 1 environmental skip** [19]. Economic feasibility remains strong: four sensing nodes are still four commodity ESP32-S3 development boards, together costing a small fraction of specialized radar hardware. Operational feasibility is supported by a single-command development stack (`npm run dev`) that auto-detects however many nodes are actually streaming, and by run guides for Windows and Ubuntu hosts [12]. The main residual feasibility risk has shifted somewhat since the two-node edition: it is still primarily a measurement problem (converting the detection chain into defensible accuracy numbers), but it now also includes a **specific, named open engineering question** — why four simultaneously self-pinging, same-channel nodes appear to saturate the motion metric in an empty room — that must be resolved before the room-mode threshold (currently provisional) can be honestly recalibrated [20], [21].

---

# CHAPTER 2 LITERATURE REVIEW

## 2.1 Introduction

The literature landscape surveyed for the original two-node system remains the correct landscape for the four-node system — node count is a deployment/geometry parameter, not a different sensing modality — so this chapter is retained with updated framing of where Phantom Scan now sits relative to each system, plus a new companion Chapter 2A that grounds the underlying physics and math in more depth than the original report attempted.

## 2.2 Review of Existing Systems

### 2.2.1 Wi-Vi: Through-Wall Motion Sensing

Wi-Vi demonstrated that ordinary Wi-Fi transmissions can detect and coarsely track humans moving behind walls, using interference nulling to cancel static reflections and isolate the moving component of the channel [1]. Phantom Scan applies the same "treat the static environment as clutter" principle in time-domain form at every node, whether one, two, three, or four are live: the temporal standard deviation of per-subcarrier amplitude is insensitive to the static channel and responds to motion-induced perturbation, independently per node, before any fusion happens.

### 2.2.2 WiTrack and Vital-Radio: RF Localization and Vital Signs

WiTrack extended radio sensing to 3D tracking via body radio reflections using FMCW carriers [2], and Vital-Radio showed that respiration and heart rate can be extracted from reflected-RF phase at multi-meter range [3]. Phantom Scan's four-node system still cannot match either system's dedicated wideband hardware; it retains phase-based vital-sign estimation as a secondary, per-node feature (both firmware-side and host-side estimators exist) while keeping its primary detection and now-2-D localization claim on the amplitude-turbulence path.

### 2.2.3 CARM: Modeling CSI Dynamics of Human Activity

CARM established that CSI amplitude variance over time is a physically meaningful motion feature [4] — the same theoretical justification the four-node detector still relies on for each of its up-to-four independent per-node turbulence measurements before they are combined.

### 2.2.4 SpotFi: Decimeter Localization on Commodity Wi-Fi

SpotFi achieved decimeter-level localization by super-resolving Angle of Arrival and time of flight from multi-antenna commodity access points [5]. This remains the accuracy ceiling Phantom Scan's single-antenna nodes cannot reach on the live path at any node count. What has changed is *how far* Phantom Scan gets without that hardware: adding a third and fourth single-antenna node does not grant spatial AoA, but it does upgrade the achievable output from a 1-D projection to a genuine 2-D centroid — a middle ground between SpotFi-class precision and the coarser presence-only systems below.

### 2.2.5 ESP32 CSI Sensing: Low-Cost Standalone Nodes

Hernandez and Bulut demonstrated the ESP32 family as a standalone Wi-Fi sensing platform [7] — the direct hardware enabler of Phantom Scan at any node count. The four-node system is a direct, unmodified scale-up of this line of work: four identical low-cost nodes, each running the same engineered transport contract (versioned binary header, sequence numbers, device timestamps, firmware self-ping), with host-side source pinning generalized from one pinned pair to four independently pinned identities.

### 2.2.6 Learned Wi-Fi Sensing: DensePose, Person-in-WiFi 3D, AdaPose

DensePose from WiFi [8], Person-in-WiFi 3D [9], and AdaPose [10] show CSI's information richness but also the central weakness of learned models: environment sensitivity and audit difficulty. Phantom Scan's position at four nodes is unchanged from its position at two: a deterministic, physics-based detector remains the authority, with any learned component confined to an advisory sidecar that cannot alter the deterministic result [12].

## 2.3 Comparison of Existing Solutions

| System | Hardware | Method | Output | Cost / Deployability |
|---|---|---|---|---|
| Wi-Vi [1] | Custom multi-antenna radio | Interference nulling of static clutter | Through-wall motion / coarse gestures | Research hardware; low deployability |
| WiTrack / Vital-Radio [2],[3] | Dedicated FMCW radio | Time-of-flight and phase of body reflections | 3D track; respiration and heart rate | Specialized wideband hardware |
| CARM [4] | Intel 5300 NIC | CSI speed/activity model over amplitude dynamics | Activity classification | Discontinued NIC; offline processing |
| SpotFi [5] | Multi-antenna commodity APs | Super-resolved AoA + ToF | Decimeter 2D location | Needs antenna arrays and dense APs |
| ESP32 CSI sensing [7] | ESP32 (single antenna) | CSI capture on IoT hardware | Presence / activity features | Very low cost; high deployability |
| DensePose / PiW3D / AdaPose [8]–[10] | Commodity Wi-Fi + GPU | Deep learned CSI-to-pose mapping | Dense or 3D human pose | High training and generalization burden |
| **Phantom Scan (2-node mode)** [12],[15] | 2× ESP32-S3 + laptop | Deterministic per-subcarrier turbulence + two-node balance fusion | Gated live detection, 1-D on-axis position, distance, trend | ~$14 sensing hardware; single-command stack |
| **Phantom Scan (4-node `fused_room` mode)** [12],[15] | 4× ESP32-S3 + laptop | Deterministic per-subcarrier turbulence + N-node perturbation-weighted centroid + 2-D Kalman smoothing | Gated live detection, genuine **2-D** room position, per-node distance/trend, honest state | ~$28 sensing hardware; still single-command, auto-detected node count |

*Table 2.1 — Comparison of representative Wi-Fi/RF human-sensing systems and both Phantom Scan fusion modes.*

The four-node row is the key addition: it shows Phantom Scan closing part of the gap toward 2-D localization *without* adopting SpotFi's multi-antenna/AoA requirement, purely by adding more single-antenna observation points and generalizing the same honest, non-multilateration fusion math from a pair to a weighted set.

---

# CHAPTER 2A PHYSICAL AND MATHEMATICAL FOUNDATIONS OF CSI SENSING

*This chapter is new relative to the original report. It exists to make explicit the physical quantities and the classical algorithm (MUSIC) that motivate the implementation chapters, and — critically, to preserve this project's honesty discipline — to state clearly which of this theory the live Phantom Scan pipeline actually computes, versus which is standard background theory that the live single-antenna nodes cannot exploit.*

## 2A.1 Introduction

Every claim Phantom Scan makes about detecting or locating a person ultimately rests on four physical/mathematical building blocks: **amplitude**, **phase**, the **OFDM carrier/subcarrier structure** that Wi-Fi already uses for unrelated reasons, and the **Fresnel-zone geometry** that explains *why* a moving body changes any of the above. A fifth block, the **MUSIC algorithm**, is the classical tool the literature uses to turn CSI phase into a spatial angle — Phantom Scan uses a variant of it, but over *time*, not over *antenna elements*, for reasons explained in §2A.7–2A.9.

## 2A.2 Amplitude — Wave Strength

Amplitude represents the physical height of a radio wave, i.e., the energy it carries at the receiver. In a Wi-Fi CSI system, amplitude functions as a per-subcarrier "signal strength": when a wave travels from transmitter to receiver and encounters a human body (which is mostly water, and therefore absorptive at 2.4 GHz), the body absorbs part of the wave's energy. That absorption/scattering event shows up as a drop — or, for constructively-reflected paths, a rise — in the received amplitude. Phantom Scan's entire live detector is built on tracking exactly this quantity over time, per subcarrier, per node (§6.3.3).

## 2A.3 Phase — Wave Timing

Phase represents the timing alignment of a wave — how far through its cycle the wave is when it arrives, expressed as an angle. When a Wi-Fi wave reflects off a moving person, the total path length from transmitter to receiver changes by a small amount (often a few millimeters for a chest-wall breathing motion, more for a walking gait), which shifts the arrival time by a correspondingly tiny fraction of a wave period. Because phase is directly proportional to propagation delay,

```
φ = 2π · f_c · τ            (τ = propagation delay = distance / c)
```

phase is far more sensitive to small displacement than amplitude is — which is exactly why phase, not amplitude, is the channel of choice for spatial Angle-of-Arrival algorithms such as MUSIC, and for vital-sign extraction (sub-millimeter chest displacement) [documented in detail in `docs/research/csi-phase-in-wifi-sensing.md`].

**The hardware caveat that governs everything downstream:** commodity Wi-Fi radios — the ESP32-S3 nodes used here included — do not synchronize TX/RX clocks or lock packet-detection timing. Raw phase is therefore corrupted by two artifacts before any real motion signal is visible: **Sampling Frequency Offset (SFO)**, a clock-drift term that appears as a linear phase slope across subcarrier index, and **Packet Detection Delay (PDD)**, a variable frame-sync term that appears as a constant phase offset per packet. Both must be sanitized (linear-fit removal, per-packet reference-subcarrier subtraction) before phase is usable for anything spatial. This is precisely why the live position-fusion path in Phantom Scan is built on **amplitude turbulence**, the more robust and less hardware-fragile channel, while phase-based features (vitals, and any AoA-flavored analysis) are confined to the reference/replay DSP path where sanitization can be validated offline.

## 2A.4 Carrier, Channel, and Subcarrier

The **carrier wave / channel** is the full radio-frequency bandwidth a Wi-Fi network is configured to use — e.g., a 20 MHz channel on the 2.4 GHz band is the entire "highway" the signal travels on. Sending one large, undivided block of data down that highway is fragile: any narrowband interference or multipath null anywhere in the band corrupts the whole transmission. OFDM (Orthogonal Frequency-Division Multiplexing) solves this by dividing that 20 MHz channel into dozens of much narrower, mathematically orthogonal frequency slices — **subcarriers** — and spreading data across all of them in parallel. Each subcarrier experiences the multipath channel slightly differently (because wavelength-scale path-length differences matter more at some frequencies within the band than others), which is exactly the diversity Phantom Scan exploits: rather than trusting one fragile "best subcarrier" scalar (an approach the project explicitly tried and discarded — see §6.3.3), it uses the **full per-subcarrier amplitude vector**, up to 64 subcarriers per packet, as the motion signal.

## 2A.5 From Wi-Fi to CSI: The I/Q Model

CSI is, formally, a per-subcarrier report of how the channel modified a known transmitted reference. For each subcarrier `k`, the receiver recovers a single complex number:

```
H(k) = I(k) + j·Q(k)
```

where **I** (in-phase) is the real component and **Q** (quadrature) is the imaginary component. From this complex number, both quantities in §2A.2–2A.3 fall out directly:

```
Amplitude:  A(k) = |H(k)| = sqrt(I(k)² + Q(k)²)
Phase:      φ(k) = ∠H(k) = atan2(Q(k), I(k))
```

The full set of `H(k)` pairs across all usable subcarriers (up to 64 in this project's frame format) constitutes the **CSI matrix** for one packet; a time series of these matrices, one per received packet, is what every downstream algorithm in this report — the turbulence detector, the temporal MUSIC signature, the phase-based vitals estimator — actually consumes. `server/lib/complex.ts` (host) and its Python counterpart implement exactly this arithmetic (add, multiply, conjugate, magnitude) and are the shared foundation under every DSP module in the repository.

## 2A.6 The Fresnel-Zone Model of Human Obstruction

The Fresnel zones are the physical reason amplitude and phase change at all. Between a transmitter and receiver, radio energy does not travel along a single ray; it fills a series of nested, cigar-shaped 3-D regions (Fresnel zones) around the direct line-of-sight path, each successive zone corresponding to path lengths that differ from the direct path by successive half-wavelengths:

```
r_n = sqrt( n·λ·d1·d2 / (d1 + d2) )
```

where `λ` is the wavelength, `d1` is the distance from the transmitter to a point on the zone boundary, and `d2` is the distance from that point to the receiver. Energy arriving via an **odd**-numbered zone interferes **destructively** with the direct path; energy via an **even**-numbered zone interferes **constructively**. A person walking through the sensing area crosses these zone boundaries one after another: each crossing changes which zones are obstructed or newly reflecting, which changes the mix of constructive/destructive interference at the receiver, which is *why* per-subcarrier amplitude fluctuates as a person moves and stays flat when the room is empty. This is the same "static environment as subtractable clutter, motion as the residual signal" principle Wi-Vi first demonstrated [1] (§2.2.1), expressed here as concrete near-field geometry rather than as an interference-nulling engineering technique.

## 2A.7 Angle-of-Arrival and the MUSIC Algorithm

**MUSIC** (MUltiple SIgnal Classification) is the classical algorithm the literature uses to turn a *spatial* array of phase measurements into an estimated angle. Given a multi-antenna array's covariance matrix, MUSIC separates it into a **signal subspace** and a **noise subspace** (via eigendecomposition), then scans a steering vector `a(θ)` across candidate angles and computes the pseudo-spectrum

```
P_MUSIC(θ) = 1 / ( a(θ)^H · E_N · E_N^H · a(θ) )
```

where `E_N` is the noise-subspace matrix. The angle at which `P_MUSIC(θ)` peaks is the estimated Angle of Arrival. Two independent receivers running MUSIC, each producing its own AoA estimate, can in principle triangulate a target's `(x, z)` position as the intersection of the two bearing lines — the classical two-receiver localization construction the literature describes and that motivated this project's own "RuView" two-receiver balance study [15].

MUSIC's well-known weakness is **multipath**: in a cluttered indoor room, wall and furniture reflections produce additional spurious peaks ("ghosts") in the pseudo-spectrum alongside the true target peak, and a genuinely spatial deployment needs either array recalibration or peak-selection heuristics to keep tracking the correct one.

## 2A.8 From Theory to a Position Estimate — Two Paths

The classical pipeline above (Fresnel-zone motion → per-subcarrier amplitude/phase fluctuation → spatial MUSIC → per-receiver AoA → two-line triangulation → `(x, z)`) is the textbook path from physics to a 2-D position, and it is what a genuinely multi-antenna, multi-receiver system would run end-to-end. Phantom Scan's live path takes a **deliberately different, hardware-honest shortcut**, described fully in Chapter 6:

- It skips spatial AoA entirely, because each node has exactly one antenna — there is no array to decompose into signal/noise subspaces at any single node.
- It replaces "two AoA bearings intersecting" with **"relative perturbation energy across multiple nodes"**: the node(s) closer to (or more strongly coupled with) the moving person see a larger amplitude standard deviation, and that *relative* energy — not an angle — is what places the target.
- With exactly two nodes, that relative-energy ratio places the target on the 1-D line between them (a projection, not a bearing intersection). With three or four nodes, the same relative-energy signal is generalized into a perturbation-weighted centroid over all active anchors — genuinely 2-D, but still fundamentally an energy-ratio construction, not a triangulated bearing intersection.
- Phantom Scan *does* run a MUSIC-family computation live (`computeMUSICSpectrum` in `server/lib/signal-processing.ts`), but over a **temporal sample window at a single node**, not over a spatial antenna array — its output is a temporal "signature," useful as a per-node spectral fingerprint and for the dashboard's Signal Signature view, but it is explicitly **not** a spatial bearing and never feeds the live position-fusion math. Spatial, multi-antenna AoA remains synthetic/replay-only, exactly as it was in the two-node edition of this report (§1.4).

## 2A.9 The Cheat-Sheet Pipeline vs. Phantom Scan's Live Pipeline

For clarity, the two pipelines side by side:

| Stage | Classical / textbook pipeline | Phantom Scan **live** pipeline |
|---|---|---|
| 1. RF environment | Fresnel-zone interaction with a moving body | Same physics, same interaction |
| 2. Capture | Multi-antenna array captures I/Q per subcarrier | Single-antenna ESP32-S3 node captures I/Q per subcarrier (up to 64) |
| 3. Preprocessing | Phase unwrap, SFO/PDD sanitization, clutter removal | Amplitude-domain: static-clutter-insensitive temporal std-dev; phase sanitization exists only in the reference/replay path |
| 4. Feature extraction | Amplitude + phase features per subcarrier | Per-subcarrier temporal turbulence (`absStd`), averaged into one motion scalar per node |
| 5. Angle/position estimation | MUSIC → per-receiver AoA → two-line triangulation | Cross-node **relative energy ratio** → 1-D projection (2 nodes) or 2-D weighted centroid (3–4 nodes) — no triangulation, no spatial AoA |
| 6. Smoothing | System-dependent | 2-D constant-velocity Kalman filter (`FusedPositionKalman`), both fusion modes |
| 7. Visualization | System-dependent | Live radar scene, honesty-gated (no target without a passed motion gate) |

*Table 2A.1 — The textbook CSI-sensing pipeline versus what Phantom Scan's live path actually implements. Rows 1–4 are shared theory; rows 5–7 are where the live implementation deliberately departs from the classical spatial-AoA approach, in favor of a simpler, hardware-honest energy-ratio model that scales cleanly from two single-antenna nodes to four.*

This distinction is the chapter's central point: the physics primer above (amplitude, phase, subcarriers, Fresnel zones, and the MUSIC formalism) is the correct conceptual grounding for *why* CSI sensing works at all, and the project's literature review (Chapter 2) is written against that full classical pipeline. But Chapter 6's implementation should be read against the *right-hand column* of Table 2A.1 — a design that trades some of the classical pipeline's theoretical precision for a system that is honest about running on single-antenna, low-cost hardware at 1–4 nodes.

---

# CHAPTER 3 METHODOLOGY AND WORK PLAN

## 3.1 Introduction

The methodology used to extend the system from two nodes to a 1–4-node, auto-selecting deployment is the same hybrid iterative methodology used for the original build, applied to a second major iteration. This chapter retains the original narrative and updates the tooling table to reflect the current test matrix and node count.

## 3.2 System Development Methodology

Phantom Scan continues to follow a hybrid iterative methodology combining upfront architectural decisions (captured as ADRs) with Agile-style implementation cycles. The four-node extension itself followed this pattern precisely: ADR-051 froze the decision that the Node/TypeScript server, not Python, is the sole live runtime authority; ADR-054 froze the decision to keep a *display* balance value and a separate *authoritative* linear balance value, so contrast-sharpening and nearest-node display bias never contaminate any analytical use of the data; ADR-056 froze a gain-normalization fix (dividing each node's raw perturbation by its own mean amplitude before fusing) after a real bug was found where a per-board gain/RSSI mismatch biased the balance toward whichever board happened to have higher effective gain, independent of where the person actually was.

Each cycle again ended with a written verification artifact: `PhantomScan_4Node_Fusion_Report.md` documented the initial room-mode implementation; `PhantomScan_4Node_FusedRoom_Test_Report.md` independently re-verified it against the repository, confirmed the room-mode math generic and correct, and **found and documented a real regression** (the two-node fusion path silently failing for any live pair other than {N1, N2}) that has since been fixed in the current code (§1.4). This is the same evidence-first discipline the original report described, now demonstrably exercised on a second, larger change.

## 3.3 Requirement Gathering Techniques

The four techniques from the original report — literature analysis, repository/artifact analysis, bench experimentation, and scenario-driven analysis — remain the operative techniques, extended with node-count-specific scenarios: exactly 2 nodes live but *not* nodes 1 and 2; 3-of-4 in every combination; a live 4→3→4 dropout/rejoin; and an empty room with all four nodes live and self-pinging simultaneously (the scenario that surfaced the current false-positive investigation).

## 3.4 Project Plan (Gantt Chart)

The phase structure from the original report is retained; the four-node extension was executed as an additional iteration inside Phase P5/P6 rather than as a new phase, consistent with the project's stated preference for overlapping implementation and verification rather than strict phase gating.

| Phase | Period (2026) | Main Activities | Milestone Deliverable |
|---|---|---|---|
| P1 – Problem & background | Jan – Feb | Topic definition, CSI literature study, feasibility analysis | Task 1: Chapter 1 |
| P2 – Literature review | Feb | Comparative review of Wi-Fi sensing systems, gap analysis | Task 2: Chapter 2 |
| P3 – Methodology & requirements | Feb – Mar | Methodology selection, requirement capture, planning | Tasks 3–4: Chapters 3–4 |
| P4 – System design | Mar (due 25 Mar) | Architecture, module interaction, data and UI design | Task 5: Chapter 5 |
| P5 – Implementation (two-node) | Mar – Apr (due 25 Apr) | Firmware, host runtime, two-node fusion detector, dashboard, security | Chapter 6 + working two-node system |
| P5b – Implementation (four-node extension) | Aug – Sep | Room-corner geometry, N-node `fuseNodeTargets`, gain normalization (ADR-056), 2-D Kalman smoothing, generic per-pair 2-node fix | Working 1–4-node system, `fused_room` mode |
| P6 – Testing & evaluation | Sep | Test-matrix runs (256 TS + 91 Python), hardware sessions, four-node false-positive investigation opened | Verification reports, this report's honest-limitations update |
| P7 – Results & final report | Sep | Results analysis, discussion, conclusions, unified report (this document) | Chapters 7–8 + final document |

*Table 3.1 — Gantt-style work plan, updated to show the four-node extension as an explicit sub-phase.*

## 3.5 Development of Tools and Technologies

| Category | Technology | Role and Justification |
|---|---|---|
| Sensing nodes | 1–4× ESP32-S3 dev boards, ESP-IDF (C) | Lowest-cost platform exposing per-subcarrier CSI [11]; firmware unchanged in kind across node counts — capture, framing, self-ping, telemetry, distinguished only by a provisioned `node_id`. |
| Host runtime | Node.js 18+, TypeScript, Express, ws | Single authoritative live path: UDP ingest on :5005 shared by all live nodes, DSP loop, fusion-mode auto-selection, 2-D Kalman smoothing, WebSocket publishing, auth and audit. |
| Frontend | React 18, Vite, React Three Fiber (Three.js) | Real-time radar-style 3D scene rendering up to four node beacons plus telemetry panels. |
| Shared contracts | TypeScript + zod schemas (`shared/`) | One source of truth for message types and geometry constants (`NODE_ANCHORS`, room-corner geometry) across server and client. |
| Analysis path | Python 3.13, numpy/scipy, pytest | Replay of recorded sessions, reference DSP, protocol-parity tests, invariant guards; live mode now explicitly retired. |
| Data formats | Binary ADR-018 frames; per-session CSV + JSON index; a small number of legacy JSONL fixtures | Compact live transport; replayable evidence including new `raw_perturbation_n1..n4` columns; spreadsheet-friendly analysis [16]. |
| Testing | `node:test` via `tsx`; pytest | **256 TypeScript tests, 0 failures**; **91 Python tests, 1 environmental skip**, current matrix at time of writing [19]. |
| Dev tooling | `esptool`/`idf.py` flashing, `esp-flash.py` provisioning, `calibrate-threshold.ts`, dev launcher | Board provisioning of a unique `node_id` (1–4) per board without reflashing app code, empty-room gate calibration, one-command development stack [12]. |

*Table 3.2 — Tools and technologies used in the current 1–4-node implementation.*

---

# CHAPTER 4 SYSTEM SPECIFICATION

## 4.1 Introduction

This chapter specifies what Phantom Scan must do and under what quality conditions, updated for a system whose node count and fusion mode are runtime-determined rather than fixed at build time. As before, several requirements are negative — the system must refuse to display things (ghost targets, fabricated fusion, spoofed nodes, an incorrect fusion mode label) as firmly as it displays real detections — and every requirement below is grounded in the implemented system [12], [19].

## 4.2 Non-Functional Requirements

| Category | Requirement and Current Evidence |
|---|---|
| Performance | Host processing loop still runs at 50 ms (~20 FPS) regardless of live node count; per-node ingest of ≥20 packets/s remains the preflight minimum per node, now checked independently for up to four nodes. |
| Reliability | Any subset of 1–4 nodes may be silent or unplugged without crashing the host; a silent node's motion window decays to zero within 1.5 s; stale targets clear within 5 s across all three fusion modes; a node-mode flip (e.g., 2→4 nodes) resets the Kalman filter's velocity/covariance state so it never leaks across modes. |
| Security | WebSocket connections remain token/cookie authenticated; UDP source pinning now independently guards up to four node identities sharing one port; audit events persist as JSONL. |
| Usability | The operator can always distinguish live, degraded, stale, and empty states across `single_node`/`fused_two_node`/`fused_room`; caveat labels state that the 2-node position is an on-axis projection and the room-mode position is a perturbation-weighted centroid, never true ranging. |
| Honesty / Integrity | Synthetic, replayed, or single-node data can never be presented as fused live truth at any node count; the currently open four-node false-positive investigation is itself documented as a limitation rather than smoothed over in this report or the README. |
| Maintainability | Strict layer boundaries retained; shared zod schemas remain the single geometry/message contract; **256 TypeScript + 91 Python** automated tests at time of writing [19]. |
| Portability | Host stack still runs on Windows and Ubuntu; firmware still builds under ESP-IDF, with provisioning documented per node ID via `esp-flash.py`. |
| Configurability | Detection parameters remain environment-tunable; `PHANTOM_MOTION_THRESHOLD` default is now **0.6** (provisional: re-set from the original **0.12** using a single 60 s two-node empty-room recording — see the open four-node caveat above), alongside `PHANTOM_MOTION_WINDOW_MS`, `PHANTOM_BALANCE_CONTRAST`, `PHANTOM_BALANCE_BIAS_EXPONENT`, and `PHANTOM_TREND_DEADBAND_MPS`. |

*Table 4.1 — Non-functional requirements with current evidence, updated for the 1–4-node system.*

## 4.3 Functional Requirements

| ID | Functional Requirement | Implemented By |
|---|---|---|
| FR1 | Each of up to four nodes shall capture Wi-Fi CSI and stream binary frames (32-byte versioned header, sequence number, RSSI, device timestamps, raw I/Q payload) over UDP to the host [16]. | `csi_collector.c`, `stream_sender.c` |
| FR2 | Each node shall self-generate channel traffic (~50 Hz gateway ping) independently of any other node, and shall rate-limit its own transmission (current firmware: 10 ms send gate). | `csi_collector.c` |
| FR3 | The host shall be the sole owner of UDP port 5005 for all live nodes simultaneously, and shall parse/validate CSI frames, heartbeats, and firmware feature-state packets from any of up to four node identities. | `server/lib/udp-server.ts` |
| FR4 | The host shall independently pin each of up to four node identities to its first-seen source address and reject frames for a known node arriving from a foreign source, with rate-limited security logging. | `SourcePinningGuard` (`udp-server.ts`) |
| FR5 | The host shall compute a per-node motion metric — gain-normalized, per-subcarrier temporal standard deviation of CSI amplitude — independently for however many nodes (1–4) are currently live. | `node-fusion.ts`, `websocket.ts` |
| FR6 | The system shall emit **no target** when no live node's motion clears the calibrated gate, in every fusion mode. | `computeEnergyGatePassed`, `fuseTwoNodeTarget`, `fuseNodeTargets` |
| FR7 | With exactly two nodes live, the host shall fuse them into a 1-D on-axis position (`fuseTwoNodeTarget`, using whichever two node IDs are actually live, not a fixed pair). With three or four nodes live, the host shall fuse them into a 2-D perturbation-weighted centroid (`fuseNodeTargets`), each with per-node distance and trend readouts. | `node-fusion.ts`, `websocket.ts` |
| FR8 | With exactly one node live, the system shall enter an explicitly labeled degraded `single_node` state and shall not fabricate fused output, using the same per-node motion gate as the fused modes, whose 0.6 threshold is provisional (not the separate scalar gate with its short auto-calibration window). | `target-state.ts`, `singleNodeMotionDetected` |
| FR9 | Both fusion outputs shall be smoothed by a shared, natively 2-D constant-velocity Kalman filter before broadcast, with the filter reset whenever the active fusion mode changes. | `fused-position-kalman.ts` |
| FR10 | Targets shall become "stale" 1.5 s after the last live sample and shall be hard-cleared after 5 s, identically across all three fusion modes; disconnects clear all client state. | `target-state.ts`, `use-websocket.ts` |
| FR11 | The host shall publish live state (fused target, truthful target state, per-node telemetry for however many nodes are configured, temporal spectra, vitals, firmware feature states) over an authenticated WebSocket. | `websocket.ts`, `shared/schema.ts` |
| FR12 | The dashboard shall render one node beacon per currently-configured anchor (up to four), the fused target, motion vectors, temporal spectral views, and Board-DSP cards, gated by presentation-honesty helpers shared across all fusion modes. | `client/src/components/dashboard/` |
| FR13 | Operators shall authenticate before accessing the dashboard or privileged actions; security-relevant events shall be audit-logged. | `server/auth/`, `server/audit/` |
| FR14 | The system shall support per-session CSV recording (with a JSON session index) and deterministic replay, including unclamped `raw_perturbation_n1..n4` columns added specifically to diagnose the four-node calibration question. | `recording-export.ts`, `session-store.ts`, `phantom/` package |
| FR15 | The system shall provide an empty-room and negative-control calibration tool. A single short run yields descriptive statistics only; a candidate threshold is produced only from an empty soak of at least 60 min plus a fan control of at least 5 min in one link state with the empty-vs-empty drift check passing. The current gate (0.6) is provisional and requires re-validation at four-node room-mode operation; its false-alarm and detection rates are `[TO BE MEASURED]`. | `scripts/calibrate-threshold.ts` |

*Table 4.2 — Functional requirements traced to implementing modules, updated for 1–4-node operation.*

---

# CHAPTER 5 SYSTEM DESIGN

## 5.1 Introduction

The layered architecture from the original report is retained; this chapter updates the architecture table with the new fusion-and-smoothing module, updates the data design with the room-corner geometry and the new recording columns, and updates the UI description to reflect a dashboard whose node-beacon count and fusion-mode label are runtime-determined.

## 5.2 System Architecture Design

| Layer | Responsibility | Representative Modules |
|---|---|---|
| Presentation | Operator dashboard, truthful rendering across all three fusion modes, review routes | `client/src/pages/dashboard.tsx`, `components/dashboard/*` |
| Application | Ingest (1–4 nodes), windowing, fusion-mode auto-selection, 2-D Kalman smoothing, state machine, publication | `server/lib/udp-server.ts`, `websocket.ts`, `node-fusion.ts`, `fused-position-kalman.ts`, `target-state.ts` |
| Data | Recording (per-session CSV + JSON index), replay, session store | `server/lib/recording-export.ts`, `session-store.ts`, `phantom/recording.py` |
| Integration | UDP :5005 in (shared by all live nodes), WebSocket /ws out, optional AI sidecar on 127.0.0.1:5006 | `udp-server.ts`, `websocket.ts`, `scripts/ai_inference.py` |
| Security | Operator auth, WS auth, independent source pinning per node ID (1–4), audit logging | `server/auth/`, `SourcePinningGuard`, `server/audit/logger.ts` |

*Table 5.1 — Layered architecture, updated with the fusion/Kalman module.*

```text
ESP32-S3 node 1 ----\
ESP32-S3 node 2 -----\        UDP :5005 ingest        targetState / metrics
ESP32-S3 node 3 -------> Node/TS host runtime ------------------------------> React dashboard
ESP32-S3 node 4 -----/      |          \
  (1-4 live; mode      |           \-> per-session CSV + JSON index (data/sessions/)
   auto-selected)      |
                        \-> deterministic DSP -> node-fusion (2-node or N-node) -> Kalman smoothing -> WebSocket /ws
```

*Figure 5.1 — End-to-end data pipeline from firmware capture to dashboard rendering, updated to show 1–4 live nodes feeding one shared ingest port and one shared Kalman-smoothing stage regardless of fusion mode.*

## 5.3 Module Interaction Design

The genuine runtime classes remain `SignalProcessingServer` (the orchestrator, now also owning the shared `FusedPositionKalman` instance), `SourcePinningGuard` (now independently tracking up to four node identities), and the legacy single-node DSP helpers. Pure, exhaustively-unit-tested functions still carry the detection mathematics — `computeNodeMotionFromMatrix`, `computeGainNormalizedPerturbation` (new since the two-node edition — see §6.3.4), `fuseTwoNodeTarget`, `fuseNodeTargets` (new), `biasBalanceTowardNearestNode`, and `computeNodeTrends`, all in `server/lib/node-fusion.ts` [15].

| Module/Entity | Interacts With | Contract |
|---|---|---|
| `csi_collector.c` (firmware) | `stream_sender.c` | `csi_serialize_frame()` writes the ADR-018 32-byte header + raw I/Q, identical per node regardless of total node count [16]. |
| `stream_sender.c` (firmware) | `udp-server.ts` | UDP datagrams to configured host:5005; 32-slot queue, ENOMEM backoff. |
| `udp-server.ts` | `websocket.ts` | `CSISample { timestamp, nodeId (1–4), rssi, h1, h2, amplitudes[] }` via `ingestSample()`. |
| `node-fusion.ts` | `websocket.ts` | `NodeMotion { mean, absStd, motion }`; `FusedTarget` (2-node, with `balance`/`balanceLinear`) or `FusedRoomTarget` (3–4-node centroid, no single-axis `balance`) or `null`. |
| `fused-position-kalman.ts` | `websocket.ts` | `predict(nowMs)` / `update([x, z])` → filtered `{x, z}` consumed by every downstream broadcast; reset on any fusion-mode change. |
| `target-state.ts` | `websocket.ts`, client | `TargetState { state, node_mode ("single_node"|"fused_two_node"|"fused_room"), target_visible, position_confident, bearing, range, staleness }`. |
| `shared/schema.ts` | server + client | zod schemas for every WS message type; `NODE_ANCHORS` (room-corner geometry), `ROOM_WIDTH_M`/`ROOM_DEPTH_M`, `NODE_SEPARATION_M`. |
| `shared/bearing.ts` | server + client | Single source of truth for compass bearing (`theta`) vs. travel-direction angle (`angle`) conventions. |
| `use-websocket.ts` (client) | dashboard components | Typed live state with a 5 s client-side staleness watchdog, node-beacon count driven by however many anchors are configured. |
| `phantom/` package | recorded sessions | JSONL/CSV session records; reference DSP and replay, live mode explicitly retired. |

*Table 5.2 — Module-interaction contracts, updated with the Kalman-smoothing module and the N-node fusion type.*

## 5.4 Database and Data Design

The file-based persistence philosophy is unchanged. The geometric data model has moved from a centered 3 m two-node baseline to a room-corner rectangle, and the recording schema has gained columns to support up to four nodes and the false-positive investigation:

| Data Artifact | Structure | Persistence |
|---|---|---|
| ADR-018 CSI frame | Unchanged 32-byte header + raw int8 I/Q pairs per node [16] | Transient (UDP) |
| Feature-state frame | Unchanged, magic `0xC5110006`, 1 Hz per node | Transient (UDP) |
| Runtime target model | `FusedTarget` (2-node) or `FusedRoomTarget` (3–4-node centroid); `TargetState`; up to four `SensorNode { node_id, x, z, motion, distanceM, trend, rssi }` | In-memory |
| Per-session CSV | `session_ts_ms`, `x_disp_m`/`z_disp_m`, `distance_n1_m..n4_m`, `trend_n1..n4`, `motion_n1..n4`, **`raw_perturbation_n1..n4`** (new, unclamped), `node1_fps..node4_fps`, `target_visible`, `node_mode`, ground-truth columns when tagged | `data/sessions/*.csv` |
| JSON session index | Per-session summary (id, name, timing, frame count, classification, average distance/speed, data source) | `data/sessions/_index.json` + one standalone `<id>.json` per session |
| Operator & audit data | scrypt-hashed local operator record; append-only JSONL audit trail | `data/operator.json`, `data/audit/` |

*Table 5.3 — Data design, updated with the room-corner geometry and the four-node diagnostic columns.*

The geometric data model is fixed in `shared/schema.ts`: node anchors now sit **one per corner of a 4 m × 6 m room** — `N1 = (-2, -3)`, `N2 = (+2, -3)`, `N3 = (+2, +3)`, `N4 = (-2, +3)` meters, origin at the room center, listed in perimeter order 1→2→3→4→1 so the client can draw a clean, non-crossed room-boundary polygon. With exactly nodes 1 and 2 live, the target still slides along their 4 m line (`NODE_SEPARATION_M`); with 3–4 live, it is the weighted centroid described in §6.3.4. Both server fusion and client rendering import these constants from one shared file, so the display can never disagree with the mathematics about where the nodes are [12].

## 5.5 User Interface (UI) Design

The dashboard's design intent is unchanged — an operator console that never overstates its evidence — but its rendering must now scale to however many of the four possible node beacons are actually configured and live, and must correctly label three fusion modes instead of one.

- **Radar scene:** node beacons (1–4, cyan/pink/etc. per node), the room-boundary polygon connecting all configured anchors, the fused target, motion vectors, and a mode-appropriate caveat — "on-axis estimate, not room position" for `fused_two_node`, "perturbation-weighted room centroid, not RF ranging" for `fused_room`.
- **Signal Signature panels:** the temporal MUSIC signature and its time-stacked heatmap remain per-node views (§2A.8–2A.9 — these are temporal signatures, not spatial AoA, and the dashboard's own component naming/comments are explicit about that honesty note).
- **Distance meter, target identity card, vitals monitor, Board-DSP card:** unchanged in kind, now instantiated once per live node rather than assuming exactly two.
- **A new floor-glow / Signal Field visualization** (`SignalFieldGrid`, `fused_room` mode only) spreads each active node's motion/perturbation value across the room as an inverse-distance-weighted grid — explicitly documented in the schema as a rendering aid, **not** a physical RF field measurement, and never fed back into localization.

The original report's Appendix F screenshots depict the two-node-era UI (single on-axis target, two beacons) and are retained in Appendix F of this report for historical continuity, but they are **not** representative of the current four-node `fused_room` UI; recapturing them against a live four-node session is listed as an open documentation item (§8.3).

---

# CHAPTER 6 SYSTEM IMPLEMENTATION

## 6.1 Introduction

This chapter documents how the design of Chapter 5 is realized in code, updated wherever the two-node edition's description no longer matches the live 1–4-node system. Every file, function, constant, and threshold cited here exists in the current repository [12].

## 6.2 Implementation Overview

| Area | Technology | Key Files |
|---|---|---|
| Firmware | ESP-IDF / C on ESP32-S3 | `firmware/esp32-csi-node/main/`: `main.c`, `csi_collector.c`, `stream_sender.c`, `nvs_config.c`, `edge_processing.c` — unchanged in kind across 1–4 boards |
| Live host | Node.js + TypeScript | `server/lib/`: `udp-server.ts`, `websocket.ts`, `node-fusion.ts`, **`fused-position-kalman.ts`** (new), `target-state.ts` |
| Contracts | TypeScript + zod | `shared/schema.ts` (room-corner `NODE_ANCHORS`), `shared/bearing.ts`, `shared/target-presentation.ts` |
| Dashboard | React + Three.js (R3F) | `client/src/pages/dashboard.tsx`, `components/dashboard/RadialScene.tsx` and sibling panels, now node-count-aware |
| Python path | Python 3.13 | `phantom/`: `protocol.py`, `dsp.py`, `runtime.py`, `ingest.py`, `recording.py`, `api.py` — live mode explicitly retired |
| Tooling | TS + Python scripts | `scripts/calibrate-threshold.ts`, `esp-flash.py` (per-node provisioning), replay/capture utilities, session reporter |

*Table 6.1 — Implementation areas and their key source files, updated with the Kalman-filter module.*

## 6.3 Implementation Details

### 6.3.1 Firmware: CSI Capture and Transport

Unchanged from the two-node edition in every respect except deployment count: each of up to four boards independently loads its own `node_id` from NVS before Wi-Fi starts, joins the same 2.4 GHz network, enables promiscuous-mode CSI capture with self-ping, and streams rate-limited ADR-018 frames to the same host:5005. Nodes never coordinate with each other — the only thing that changes with node count is how many independent UDP streams the host receives and how many entries `SourcePinningGuard` tracks.

### 6.3.2 Host Ingest: Parsing and Source Authenticity

`server/lib/udp-server.ts` still binds a single UDP socket on port 5005 for all live nodes, without address reuse. `SourcePinningGuard` now independently pins **up to four** node identities to their first-seen source addresses (generalized from a fixed pair via `mapRuntimeNodeIdToHardwareId`, a generic ID-to-hardware map lookup with no hardcoded `1`/`2` special case remaining in the ingest path). The per-subcarrier amplitude vector `amp[j] = sqrt(re² + im²)` is computed identically per node regardless of how many others are live.

### 6.3.3 How the System Detects a Moving Human

Unchanged in its core mathematics from the two-node edition (per-node `computeNodeMotionFromMatrix` over a 1500 ms window, `absStd`/`mean`-normalized display `motion`), now computed independently for each of up to four live nodes:

```typescript
// server/lib/node-fusion.ts — per-subcarrier turbulence (per node, any of 1-4)
export function computeNodeMotionFromMatrix(frames: number[][]): NodeMotion {
  const k = Math.min(...usable.map((f) => f.length)); // common subcarrier count
  let stdSum = 0;
  for (let j = 0; j < k; j++) {          // temporal std of each subcarrier j
    let m = 0;
    for (const f of usable) m += f[j];
    m /= usable.length;
    let acc = 0;
    for (const f of usable) { const d = f[j] - m; acc += d * d; }
    stdSum += Math.sqrt(acc / usable.length);
  }
  const absStd = stdSum / k;             // raw motion energy for THIS node
  const motion = Math.min(1.0, (absStd / base) * MOTION_SATURATION_SCALE); // x4
  return { mean: base, absStd, motion };
}
```
*Listing 6.1 — Per-node turbulence detector (unchanged mathematics; now instantiated once per live node, 1–4).*

The empty-room gate itself has been recalibrated since the two-node edition: `DEFAULT_MOTION_THRESHOLD` is now **0.6** (env `PHANTOM_MOTION_THRESHOLD`), set 2026-07-20 from the two-node rig's measured empty-room baseline — a single 60 s recording (`max(motion1, motion2)` over 296 samples: mean 0.49, σ 0.027, max 0.58; 0.6 sits just above that recording's maximum, it is **provisional** and not a mean + k·σ result) — up from the original placeholder of 0.12. This is the threshold currently under active re-investigation for four-node operation (§1.4, §8.3) — the two-node calibration does not automatically transfer to four simultaneously self-pinging nodes.

### 6.3.4 Gain Normalization, Two-Node Balance, and N-Node Room Fusion

This section replaces "Two-Node Balance Fusion and 1-D Localization" from the original report; it is the section with the largest substantive change.

**Gain normalization (new, ADR-056).** Before any fusion, each node's raw perturbation is normalized by its own mean amplitude:

```typescript
export function computeGainNormalizedPerturbation(absStd: number, mean: number): number {
  const s = Number.isFinite(absStd) ? Math.max(0, absStd) : 0;
  const m = Number.isFinite(mean) && mean > 0 ? mean : 1.0;
  return s / m;
}
```
This was added after a real bug (PS-BEHTEST-004) was found: raw, un-normalized `absStd` scales linearly with any per-board gain/RSSI mismatch, which biased the fused position toward whichever board happened to have higher effective gain — independent of where the person actually was. Every fusion call (2-node and N-node alike) now consumes this gain-normalized `r`, not raw `absStd`.

**Two-node mode (`fuseTwoNodeTarget`, unchanged core math, now generically paired).** With exactly two nodes live, the host reads `const [firstId, secondId] = activeIds` — whichever two node IDs are actually reporting — and fuses them:

```typescript
// server/lib/node-fusion.ts — two-node balance fusion, generic pair
export function fuseTwoNodeTarget(input: FuseInput): FusedTarget | null {
  const threshold = input.motionThreshold ?? DEFAULT_MOTION_THRESHOLD; // 0.6
  const present = Math.max(input.motion1, input.motion2) >= threshold && r1 + r2 > EPS;
  if (!present) return null;                      // empty room => NO target
  const p = input.contrastExponent ?? BALANCE_CONTRAST_EXPONENT; // 2.0
  const balance = r2**p / (r1**p + r2**p);         // 0 -> firstId ... 1 -> secondId
  const biasedBalance = biasBalanceTowardNearestNode(balance); // display bias, 0.72
  const x = n1.x + (n2.x - n1.x) * biasedBalance;  // 1-D position on the active axis
  const z = n1.z + (n2.z - n1.z) * biasedBalance;
  return { x, z, balance, balanceLinear: r2/(r1+r2), distToNearestNodeM: Math.min(d1, d2) };
}
```
*Listing 6.2 — Two-node fusion, now parameterized by whichever pair is live rather than hardcoded to nodes 1 and 2.*

**N-node room-centroid mode (`fuseNodeTargets`, new).** With three or four nodes live, the host instead computes a contrast-weighted centroid over every active anchor — the direct generalization of the two-node ratio:

```typescript
// server/lib/node-fusion.ts — N-node weighted centroid (3-4 active anchors)
export function fuseNodeTargets(samples: NodeFuseSample[], opts): FusedRoomTarget | null {
  const threshold = opts.motionThreshold ?? DEFAULT_MOTION_THRESHOLD;
  const totalR = clean.reduce((sum, s) => sum + s.r, 0);
  const maxMotion = clean.reduce((max, s) => Math.max(max, s.motion), 0);
  if (!(maxMotion >= threshold && totalR > EPS)) return null;   // empty room => NO target

  const p = opts.contrastExponent ?? BALANCE_CONTRAST_EXPONENT; // 2.0, same exponent as 2-node
  const weighted = clean.map((s) => ({ ...s, w: Math.pow(s.r, p) }));
  const totalW = weighted.reduce((sum, s) => sum + s.w, 0);
  // pos = Σ(anchor_i * r_i^p) / Σ(r_i^p) — perturbation-weighted centroid
  let x = 0, z = 0;
  for (const s of weighted) { x += s.anchor.x * (s.w / totalW); z += s.anchor.z * (s.w / totalW); }
  return { x, z, distToNearestNodeM, classifierCorroboration };
}
```
*Listing 6.3 — N-node room-centroid fusion: the same contrast exponent and gate as the 2-node case, generalized to a weighted centroid over 3–4 anchors instead of a linear interpolation between 2.*

Deliberately **absent** from `fuseNodeTargets` is any equivalent of `biasBalanceTowardNearestNode` — that display squeeze only makes sense projected onto a single axis; the contrast exponent `p` alone does the equivalent "pull toward the dominant node" work once the projection is genuinely 2-D. Also absent, by design, are the single-axis `balance`/`balanceLinear` fields (`FusedRoomTarget` leaves them `undefined`) — a room centroid has no one axis to report a balance scalar against, and reporting a fabricated one would violate the same honesty contract that governs everything else in this project (ADR-054).

**The empty-room gate itself is identical in structure across both modes** — `max(motion_1..N) >= PHANTOM_MOTION_THRESHOLD` and a numerical energy floor — so the honesty guarantee ("no target without live evidence") is enforced by the same logical test whether the live node count is 2, 3, or 4.

### 6.3.5 Fused-Position Kalman Smoothing (new since the two-node edition)

Both fusion branches' raw output is recomputed from scratch every ~50 ms tick with zero history, which produces a visibly jittery on-screen marker — more noticeable in `fused_room` mode, where the target can now move in two genuinely independent dimensions rather than sliding along one fixed axis. `server/lib/fused-position-kalman.ts` (`FusedPositionKalman`) addresses this:

- **Natively 2-D:** two independent 1-D constant-velocity Kalman filters (state `[pos, vel]` per axis), separate from the repository's other, unrelated 6-state 3-D Kalman filter used only by the single-node DBSCAN spatial-tracking path.
- **`predict(nowMs)`** clamps `dt` to `[0.001s, 0.3s]` — the ceiling prevents one large stale-drop gap from producing one outsized position jump, and sits below the 0.4–0.83 s max inter-tick gaps actually observed in live four-node sessions.
- **`update([x, z])`** gates the innovation at 3.0σ per axis, so a single wild-tick outlier is skipped rather than yanking the marker, without loosening R for every subsequent tick.
- **Q/R are derived from real captured four-node `fused_room` session data**, not placeholders: `R_X = 0.0044 m²`, `R_Z = 0.0011 m²` (from the best available near-still segment), `Q_POS` at ~2.5× the respective R, `Q_VEL = 0.5 (m/s²)²` (pedestrian acceleration process noise) — explicitly flagged in the source as initial, data-grounded starting values pending a dedicated stationary-target soak, not a fully validated calibration.
- Wired into **both** fusion branches: `predict()`/`update()` run every tick before velocity/trend math, and the filtered `x`/`z` — never the raw fused position — feed every downstream broadcast. `clearFusedSnapshot()` resets the filter whenever the node-mode flips (e.g., a session going from `fused_two_node` to `fused_room` mid-run), so no stale velocity/covariance leaks across modes.

Validated in `server/lib/fused-position-kalman.test.ts` against real recorded positions and real inter-tick timestamps: filtering reduces mean tick-to-tick jitter on both axes, while the filtered track stays within roughly 0.002 m median / 0.02 m p95 of the raw recorded track — evidence that the smoothing is not laggy enough to misrepresent real motion.

### 6.3.6 Orchestration, Truth Model, and Publication

`SignalProcessingServer` in `websocket.ts` still runs the pipeline on a 50 ms interval. Each tick it now calls `resolveLiveNodeMode()`:

```typescript
private resolveLiveNodeMode(): TargetState["node_mode"] {
  const activeCount = this.activeHardwareNodeIds().length;
  if (activeCount >= 3) return "fused_room";
  if (activeCount === 2) return "fused_two_node";
  return "single_node";
}
```
*Listing 6.4 — Fusion-mode auto-selection: purely a function of how many of the up-to-four configured nodes are currently reporting, re-evaluated every tick.*

`computeFusedTarget()` then dispatches to `fuseNodeTargets` (≥3 active) or `fuseTwoNodeTarget` (exactly 2 active, whichever pair), applies the shared Kalman filter, and updates a single per-tick fused snapshot that every outgoing message reads — so the radar dot and the node labels can never disagree, regardless of live node count. A single-node presence gate (`singleNodeMotionDetected`) was also unified during this work to reuse the same per-node motion metric and the same provisional threshold the fused paths use, after real empty-room single-node recordings showed the previously separate scalar gate (auto-calibrated over only its first ~100 samples) producing a ghost target on 98–99% of ticks with nobody in the room.

### 6.3.7 Dashboard Rendering

`client/src/hooks/use-websocket.ts` and `dashboard.tsx` are unchanged in architecture — every render decision still routes through `shared/target-presentation.ts` — but component instantiation (node beacons, per-node distance/trend readouts) now scales to however many anchors `NODE_ANCHORS` actually defines and however many are currently live, rather than assuming exactly two.

### 6.3.8 Authentication, Audit, and Persistence

Unchanged from the two-node edition.

### 6.3.9 Python Replay and Tooling Path

Unchanged in architecture; the live-authority gate is now stricter — `python -m phantom.runtime live` refuses to bind by default and requires the explicit compatibility override `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1`, which must never be set while the dashboard is running (ADR-051).

## 6.4 Component Integration and Workflow

The integrated live workflow now begins with however many of the four boards are powered on: each pins its identity independently; the host resolves `single_node`/`fused_two_node`/`fused_room` every tick from the live count alone; when a person moves, per-subcarrier turbulence rises on the live node(s) nearest them, the shared gate opens, and the appropriate fusion function produces a raw position that the shared Kalman filter smooths before broadcast; when the person leaves, motion decays below the gate and the scene empties, in every mode; adding or removing a node mid-session (e.g., 2→3, or 4→3) transitions the mode and resets the Kalman filter cleanly. `npm run dev` launches the full chain with one command and needs no flag to say how many nodes will connect.

## 6.5 Implementation Testing Support

The implementation is guarded by **256 TypeScript tests** (`node:test` via `tsx`) and **91 Python tests** (`pytest`, 1 environmental skip), current at time of writing [19] — up from 91 TypeScript / 82 Python in the two-node edition, the growth driven substantially by the four-node fusion, gain-normalization, and Kalman-smoothing work. Cross-language invariants in `tests/test_invariants.py` continue to pass, including the dual-node midpoint invariant, the AI-firewall tests (AI-sidecar input cannot change the deterministic human gate, and cannot emit authoritative identity/AoA), the "no upstream hardware controls from the dashboard" test, and the flight-control scope-guard.

## 6.6 Summary

The implementation still converts one physical effect — motion-induced multipath perturbation — into a gated, fused, honestly-presented live detection, through the same chain of small, individually tested stages described in the two-node edition, now generalized: per-node capture with self-ping (1–4 boards), a versioned binary contract, independently pinned ingest, windowed per-subcarrier turbulence with gain normalization, a thresholded gate identical in structure across fusion modes, a fusion stage that auto-selects between a 1-D projection and a 2-D weighted centroid, a shared 2-D Kalman smoother, a truth-state machine, and state-honest rendering that scales to however many nodes are actually deployed.

---

# CHAPTER 7 RESULTS AND DISCUSSION

## 7.1 Introduction

This chapter evaluates the four-node system against its objectives using the evidence that actually exists, following the same strict honesty rule as the original report: synthetic, replayed, or single-node runs cannot graduate a headline sensing metric [21], and this chapter reports the four-node false-positive investigation as an unresolved finding, not as a footnote.

## 7.2 Data Collection and Research

Evidence now spans four tiers instead of three. First, committed protocol fixtures, unchanged. Second, the original two-node recorded datasets (February–June 2026). Third, dated verification documents for the two-node system [17]–[19]. Fourth, and new to this edition: two dated four-node verification documents — `PhantomScan_4Node_Fusion_Report.md` (2026-08-24), documenting the initial room-mode implementation and geometry change, and `PhantomScan_4Node_FusedRoom_Test_Report.md`, an independent re-verification that confirmed the room-mode fusion math generic and correct via static/code-level analysis and the full automated test suite, explicitly declined to fabricate any live-hardware accuracy numbers it could not measure in that session, and identified the now-fixed two-node-pair regression described in §1.4.

## 7.3 System Testing and User Feedback

### 7.3.1 Functional Testing (Automated)

The current test matrix passes in full: **256 TypeScript tests, 0 failures**; **91 Python tests, 1 environmental skip** [19]. Table 7.1 updates the two-node edition's suite summary with the tests added for the four-node work.

| Suite | What It Verifies |
|---|---|
| `node-fusion.test.ts` | Two-node balance (any live pair, not just {1,2}); empty-room returns no target; gain-normalized perturbation; **N-node weighted centroid** (`fuseNodeTargets`) correctness across 3- and 4-node combinations; contrast exponent; trend hysteresis. |
| `fused-position-kalman.test.ts` (new) | Jitter reduction and lag bound against real recorded 2-D tracks and real inter-tick timestamps; gate rejection of outlier ticks; reset behavior on a fusion-mode flip. |
| `udp-server.test.ts` | ADR-018 frame parsing; source-pinning accept/reject, now exercised across up to four independently pinned node identities sharing one port. |
| `target-state.test.ts` | Freshness windows, degraded labeling, stale demotion/hard clear, identical across `single_node`/`fused_two_node`/`fused_room`. |
| `websocket.test.ts` (AI-firewall subset) | Non-AI-client messages produce no state change; AI-client equivalents relay only as `advisory*`, never write authoritative identity/vitals — unchanged guarantee, re-verified after the fusion generalization. |
| `tests/test_invariants.py` | Dual-node midpoint invariant; AI firewall; no upstream hardware controls; UAV/flight-control scope guard — all still passing. |

*Table 7.1 — Automated test coverage in the current passing matrix (256 TS + 91 Python) [19].*

### 7.3.2 Four-Node Verification Findings (Non-Live Evidence)

The `PhantomScan_4Node_FusedRoom_Test_Report.md` verification pass is the strongest available non-live evidence for the four-node extension. Its findings, reproduced honestly here:

- Room-mode fusion (3–4 nodes) verified **solid and generic** by direct code trace — the `activeIds.length >= 3` branch correctly handles every combination of 3-of-4 or all-4 nodes, with no fixed-pair assumption.
- A **real regression was found and documented**: at the time of that report, the two-node fusion branch was still hardcoded to read nodes 1 and 2's motion windows regardless of which two node IDs `resolveLiveNodeMode()` had actually identified as live, producing a silent false-negative (no target shown) whenever a different pair (e.g., N3+N4) was the one actually live and sensing a real person. This report's own review of the current `websocket.ts` (§6.3.6) confirms this has since been fixed — the fusion call now reads `activeHardwareNodeIds()` generically.
- **No live-hardware accuracy numbers were fabricated** when they could not be measured in that verification session — the report explicitly declines to report a meter-level position error, consistent with the project's honesty rule that `fuseNodeTargets` is a perturbation-weighted centroid, not RF ranging, and any such number would be dishonest.
- The empty-room negative control specifically for `fused_room` mode was **not yet executed** at the time of that report and remains, per the current README, an **open, actively investigated issue**: real four-node empty-room recordings taken since then show persistent false-positive presence detection, with the per-node motion metric saturated on roughly half of all ticks.

### 7.3.3 Measured Versus Pending Results

| Metric | Status | Evidence / Blocking Condition |
|---|---|---|
| Software correctness (parsers, 2-node and N-node fusion math, Kalman filter, state machine) | **MEASURED PASS** | 256 TS + 91 Python tests green [19]. |
| Two-node live ingest rate and RSSI envelope | MEASURED (two-node rig) | ~40 pkt/s aggregate, RSSI −23 to −38 dBm, yield 41–43 pps/node, pre-2026-10-18 firmware; current recordings 64–67 frames/s per node [19]. |
| Four-node room-mode fusion math correctness | **MEASURED PASS (static/code-level)** | Independent verification pass confirmed generic correctness; no live hardware exercised in that session [this report, §7.3.2]. |
| Four-node empty-room false-positive rate | **[TO BE MEASURED — currently unresolved, actively investigated]** | Existing recordings are motion-metric-saturated (censored) on ~half of all ticks; cannot honestly support re-deriving the threshold yet; `raw_perturbation_n1..n4` added to unblock diagnosis. |
| Four-node room-centroid localization error vs. ground truth | **[TO BE MEASURED]** | Ready-to-run 9-point ground-truth walk procedure specified in the verification report; not yet executed against live hardware. |
| Respiration / heart-rate MAE vs. reference sensors | [TO BE MEASURED] | Unchanged from the two-node edition; requires reference-sensor sessions. |
| Through-wall detection matrix | [TO BE MEASURED] | Unchanged from the two-node edition. |

*Table 7.2 — Honest results ledger, updated to add the four-node-specific rows and to flag the false-positive investigation as unresolved rather than merely unmeasured.*

### 7.3.4 User Feedback

Unchanged in method from the two-node edition: no questionnaire-based study; operator-facing feedback is captured through acceptance checklists and campaign templates. The four-node extension's most direct "user feedback" is arguably the independent verification report itself (§7.3.2), which functioned exactly as an acceptance review would — finding one real regression and one real open calibration question rather than rubber-stamping the initial implementation report.

## 7.4 Discussion

Judged as a systems-engineering result, the four-node extension meets its objectives: the fusion math correctly generalizes from a fixed pair to a variable 1–4-node deployment, a real regression was found and fixed rather than shipped silently, a new Kalman-smoothing stage was added with data-derived (not guessed) constants, and the automated test matrix grew substantially alongside the new functionality [19].

Judged as a metrology result, the project is — by its own explicit choice — less finished at four nodes than it was at two: the two-node system had at least a validated empty-room baseline behind its motion threshold; the four-node system currently does **not**, because the same threshold was inherited from the two-node calibration and real four-node recordings suggest it may not transfer. This is reported here as a finding, not hidden as a rounding error, because the alternative — quietly shipping a four-node "fused_room" mode with an unvalidated gate and describing it as equivalent to the two-node system's evidence base — would violate the honesty discipline this project has otherwise consistently applied.

The discussion should also register what the four-node extension does **not** change: the method's intrinsic single-antenna ceiling (§2A.8) is unaffected by node count. Four single-antenna receivers still cannot do spatial AoA; they can only add more independent energy-ratio observation points. The move from a 1-D projection to a genuine 2-D centroid is a real capability gain, but it is a gain in *how many axes the energy-ratio proxy can be applied along*, not a gain in *ranging precision* — the project's decision to keep stating this plainly (via `distToNearestNodeM` remaining "physically meaningful" while `x`/`z` remain explicitly a centroid, never a range) is the same transferable honesty pattern the two-node edition's discussion chapter identified as its most reusable contribution.

---

# CHAPTER 8 RECOMMENDATIONS AND CONCLUSION

## 8.1 Introduction

This chapter summarizes what the four-node extension achieved against the project's objectives, restates the limitations that remain (including one new, currently open issue), and reprioritizes future work now that the geometry extension itself — item 3 in the original report's future-work list — has been delivered.

## 8.2 Conclusion

Phantom Scan set out to detect a moving human with commodity Wi-Fi hardware and present that detection truthfully; the delivered four-node system does both, and does more of the second job (a genuine 2-D position rather than a 1-D projection) without giving up any of the honesty discipline the two-node system established. One to four low-cost ESP32-S3 nodes capture per-subcarrier CSI and stream a versioned binary contract to a laptop host; a deterministic, gain-normalized detector converts windowed per-subcarrier amplitude turbulence into gated motion evidence for each live node; a fusion stage automatically selects between a 1-D on-axis projection (2 nodes) and a 2-D perturbation-weighted centroid (3–4 nodes); a shared 2-D Kalman filter smooths whichever output is active; and an authenticated React dashboard renders exactly what the evidence supports, across three fusion modes instead of one.

The engineering result remains verifiable rather than claimed: **256 TypeScript and 91 Python automated tests pass**, the wire protocol remains fixture-locked, an independent verification pass found and the current code has since fixed a real two-node-pair regression, and a new Kalman-smoothing stage ships with constants derived from real recorded four-node sessions rather than guessed values [19]. Equally important, in keeping with the project's stated priorities, is what it still refuses to claim: the four-node empty-room false-positive question is reported here as **open and actively investigated**, not as a resolved footnote, and superseded ambitions (drone deployment, multistatic meshes, learned pose authority) remain fenced out of the runtime by the same automated guards as before.

## 8.3 Limitations and Recommendations for Future Work

### Principal Limitations

- **Open, actively investigated:** four-node empty-room false-positive presence detection, with the motion metric saturated on roughly half of recorded ticks — see §1.4 and §7.3.3.
- Fusion remains a perturbation-weighted proxy, not RF multilateration, at any node count (1-D projection at 2 nodes, 2-D centroid at 3–4).
- Single-antenna nodes still cannot perform spatial Angle-of-Arrival on the live path, at any node count (§2A.8).
- The room-mode trend arrows (per-node approaching/receding label in `fused_room` mode) are still hard-typed to a 2-endpoint concept and currently fall back to `"stable"` rather than reflecting true per-node radial velocity — a known, deferred design gap distinct from the false-positive issue.
- Pending metrology (detection rate, four-node localization error against ground truth, vitals accuracy) remains protocol-defined but unmeasured, now with a ready-to-run 9-point ground-truth procedure specified but not yet executed.
- Documentation lag: Windows/Ubuntu setup guides do not yet describe COM-port provisioning for a third or fourth node; Appendix F screenshots in this report still depict the two-node-era UI.

### Recommendations for Future Work (reprioritized)

1. **Resolve the four-node empty-room false-positive investigation first**, using the newly-added unclamped `raw_perturbation_n1..n4` export: confirm or rule out same-channel, same-AP self-ping interference among four simultaneously active nodes before touching `PHANTOM_MOTION_THRESHOLD` or `MOTION_SATURATION_SCALE` — the two must be re-derived together from real uncensored data, never independently or guessed.
2. Execute the ready-to-run four-node ground-truth walk and empty-room negative-control procedures specified in `PhantomScan_4Node_FusedRoom_Test_Report.md`, populating the results ledger (Table 7.2) with defensible live numbers.
3. Implement per-node radial-velocity tracking so `fused_room` mode's trend labels reflect real motion instead of a hardcoded `"stable"` fallback.
4. Update the Windows/Ubuntu firmware setup guides for third/fourth-node COM-port provisioning, and recapture Appendix F's dashboard screenshots against a live four-node session.
5. Promote the firmware edge-DSP tier so board-side presence/respiration estimates can cross-check host fusion at any node count, host remaining authoritative.
6. Investigate multi-antenna ESP32-S3 configurations or a hybrid node to enable genuine live spatial AoA and reduce the single-target limitation — the item most directly informed by the physics primer in Chapter 2A.
7. Complete the deferred runtime unification so the Python authority can serve as a fully interchangeable live backend behind the same truth contracts, now including the N-node fusion path.

---

# REFERENCES

[1] F. Adib and D. Katabi, "See through walls with Wi-Fi!," in *Proc. ACM SIGCOMM*, Hong Kong, 2013, pp. 75–86.

[2] F. Adib, Z. Kabelac, D. Katabi, and R. C. Miller, "3D tracking via body radio reflections," in *Proc. 11th USENIX NSDI*, Seattle, WA, 2014, pp. 317–329.

[3] F. Adib, H. Mao, Z. Kabelac, D. Katabi, and R. C. Miller, "Smart homes that monitor breathing and heart rate," in *Proc. ACM CHI*, Seoul, 2015, pp. 837–846.

[4] W. Wang, A. X. Liu, M. Shahzad, K. Ling, and S. Lu, "Understanding and modeling of Wi-Fi signal based human activity recognition," in *Proc. ACM MobiCom*, Paris, 2015, pp. 65–76.

[5] M. Kotaru, K. Joshi, D. Bharadia, and S. Katti, "SpotFi: Decimeter level localization using WiFi," in *Proc. ACM SIGCOMM*, London, 2015, pp. 269–282.

[6] Y. Ma, G. Zhou, and S. Wang, "WiFi sensing with channel state information: A survey," *ACM Computing Surveys*, vol. 52, no. 3, pp. 1–36, 2019.

[7] S. M. Hernandez and E. Bulut, "Lightweight and standalone IoT-based Wi-Fi sensing for active repositioning and mobility," in *Proc. IEEE WoWMoM*, Cork, 2020, pp. 277–286.

[8] J. Geng, D. Huang, and F. De la Torre, "DensePose from WiFi," arXiv:2301.00250, 2022.

[9] Y. Yan et al., "Person-in-WiFi 3D: End-to-end multi-person 3D pose estimation with Wi-Fi," in *Proc. IEEE/CVF CVPR*, Seattle, WA, 2024.

[10] Y. Kang et al., "AdaPose: Towards cross-site device-free human pose estimation with commodity Wi-Fi," arXiv preprint, 2023.

[11] Espressif Systems, "ESP-IDF Programming Guide: Wi-Fi Channel State Information," 2024. [Online]. Available: https://docs.espressif.com

[12] T. Bayyari, "Phantom Scan repository README and system documentation (4-node `fused_room` edition)," project repository, 2026.

[13] Phantom Scan project, "System Design and Technical Architecture," internal design document, 2026.

[14] Phantom Scan project, "System Architecture and Methodology," internal design document, 2026.

[15] Phantom Scan project, "RuView two-receiver balance model integration analysis," internal study, 2026.

[16] Phantom Scan project, "ADR-018: Binary CSI frame contract (32-byte header)," Architecture Decision Record, 2026.

[17] Phantom Scan project, "Software validation pass," dated verification report, Jul. 1, 2026.

[18] Phantom Scan project, "Target-verification and dashboard truth-model report," dated verification report, Jun. 29, 2026.

[19] Phantom Scan project, "Hardware-session and test-matrix report; README current verified state," dated verification reports, Jul. 8, 2026 and Sep. 9, 2026.

[20] Phantom Scan project, "REAL_TEST_REPORT.md positional-fidelity campaign," measurement protocol, 2026.

[21] Phantom Scan project, "MEASUREMENT_PLAN.md headline metric measurement protocol," 2026.

[22] Phantom Scan project, "Through-wall detection report," measurement protocol, 2026.

[23] Phantom Scan project, "Hardware acceptance checklist and campaign templates," 2026.

[24] Phantom Scan project, "ADR-051: Runtime authority (Node/TS server as sole live authority)," Architecture Decision Record, 2026.

[25] Phantom Scan project, "ADR-054: Fusion display-vs-authoritative balance," Architecture Decision Record, 2026.

[26] Phantom Scan project, "ADR-056: Gain-normalized node balance," Architecture Decision Record, 2026.

[27] Phantom Scan project, "PhantomScan_4Node_Fusion_Report.md," dated implementation report, Aug. 24, 2026.

[28] Phantom Scan project, "PhantomScan_4Node_FusedRoom_Test_Report.md," independent verification report, 2026.

[29] Phantom Scan project, "docs/research/csi-phase-in-wifi-sensing.md — CSI phase theory and its live/reference-path usage," internal technical note, 2026.

---

# APPENDICES

## Appendix A — ESP32-S3 Firmware Source (`firmware/esp32-csi-node/main/`)

Unchanged file-for-file from the two-node edition (`main.c`, `csi_collector.c`, `stream_sender.c`, `nvs_config.c`, `edge_processing.c`, `rv_feature_state.c`, `rvf_parser.c`, display/OTA/power/WASM subsystems). Each of up to four physical boards runs an identical build, differentiated only by its provisioned `node_id`, `esp-flash.py`.

## Appendix B — Host Runtime and Shared Contracts (`server/`, `shared/`)

All modules listed in the two-node edition's Appendix B remain current, with one addition:

| File | Description |
|---|---|
| `server/lib/fused-position-kalman.ts` | **New.** Natively 2-D constant-velocity Kalman filter (`FusedPositionKalman`) smoothing the fused position for both `fused_two_node` and `fused_room` modes; data-derived Q/R constants; outlier gating; reset on fusion-mode change. |
| `server/lib/node-fusion.ts` | Now also exports `computeGainNormalizedPerturbation` (ADR-056) and `fuseNodeTargets` (N-node centroid), alongside the original `fuseTwoNodeTarget` and per-subcarrier turbulence functions. |
| `server/lib/udp-server.ts` | `SourcePinningGuard` generalized to independently pin up to four node identities via a generic hardware-ID map, not a hardcoded pair. |
| `shared/schema.ts` | `NODE_ANCHORS` now four room-corner coordinates (`ROOM_WIDTH_M`, `ROOM_DEPTH_M`) instead of a centered two-node baseline; `node_mode` enum gains `fused_room`. |

*All other files (`server/auth/`, `server/audit/logger.ts`, `server/routes.ts`, `shared/bearing.ts`, `shared/target-presentation.ts`, `shared/target-spatial.ts`, etc.) are unchanged from the two-node edition's Appendix B and are not reprinted here.*

## Appendix C — Operator Dashboard Client (`client/src/`)

Unchanged file list from the two-node edition's Appendix C; `RadialScene.tsx`, `point-cloud-3d.tsx`, `distance-meter.tsx`, `target-identity-card.tsx`, and the node-features/Board-DSP cards now instantiate once per configured anchor (1–4) rather than assuming exactly two. A new `SignalFieldGrid`-style floor-glow visualization (`fused_room` mode only) spreads per-node motion across the room as a rendering aid, explicitly not a physical field measurement.

## Appendix D — Python Replay and DSP Toolkit (`phantom/`)

Unchanged from the two-node edition; live mode (`runtime.py`) now requires the explicit `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1` override per ADR-051, up from the earlier softer "gated behind an env var" description.

## Appendix E — Key Tooling Scripts (`scripts/`)

Unchanged from the two-node edition, plus `esp-flash.py`'s role is now explicitly documented as the mechanism for provisioning a distinct `node_id` (1–4) per board without reflashing application code.

## Appendix F — Dashboard User Interface Screenshots

*Retained from the two-node edition for historical continuity. As noted in §5.5, these depict the original two-beacon, 1-D on-axis UI and are not representative of the current four-beacon `fused_room` dashboard. Recapturing this appendix against a live four-node session is listed as open future work (§8.3).*

## Appendix G — Hardware Configuration and Deployment Geometry

**G.1 Bill of materials (current, four-node primary deployment)**

| Item | Quantity | Role |
|---|---|---|
| ESP32-S3 development board (single antenna) | up to 4 | CSI sensing nodes N1–N4, one per room corner |
| USB cables / 5V supplies | up to 4 | Node power |
| 2.4 GHz Wi-Fi router | 1 | Shared network; CSI measured on traffic to/from its gateway |
| Laptop (Windows 11 or Ubuntu) | 1 | Host: live ingest, fusion, Kalman smoothing, dashboard |

**G.2 Deployment geometry**

Up to four nodes are placed one per corner of the monitored room, at similar height with clear line of sight to the monitored area. The system's world frame fixes the four anchors at the corners of a 4 m × 6 m rectangle, origin at the room center, in perimeter order (constants `NODE_ANCHORS`, `ROOM_WIDTH_M`, `ROOM_DEPTH_M` in `shared/schema.ts`):

```text
N1 = (-2, -3)   N2 = (+2, -3)   N3 = (+2, +3)   N4 = (-2, +3)
```

With exactly nodes 1 and 2 live, the system falls back to the 4 m on-axis line between them (the direct generalization of the original two-node rig's 3 m baseline — note the baseline itself grew from 3 m to 4 m as part of the room-corner geometry change, which changes `fuseTwoNodeTarget`'s numeric output even though the function's code is unchanged). With 3–4 nodes live, all localization is the weighted centroid described in §6.3.4.

## Appendix H — Test and Verification Evidence

**H.1 Automated test matrix (current)**

| Check | Result |
|---|---|
| TypeScript test suite (`tsx --test`) | **256 tests passed** |
| Python test suite (`pytest tests/`) | **91 passed, 1 environmental skip** |
| TypeScript typecheck (`tsc`) | Clean |
| Production build | Clean |

**H.2 Four-node verification evidence**

- `PhantomScan_4Node_Fusion_Report.md` (2026-08-24): documents the initial room-corner geometry and `fuseNodeTargets` implementation.
- `PhantomScan_4Node_FusedRoom_Test_Report.md`: independent re-verification; confirmed room-mode fusion generic and correct via code trace and the automated suite; found and documented the (since-fixed) two-node-pair regression; explicitly declined to fabricate live-hardware accuracy figures it could not measure; specified but did not execute the ground-truth walk and empty-room negative-control procedures.
- README "Honest Limitations" (current): documents the open, actively-investigated four-node empty-room false-positive issue as the system's most serious current known limitation.

**H.3 Honest pending items**

Four-node empty-room false-positive rate, four-node localization error vs. ground truth, and respiration/heart-rate accuracy remain **[TO BE MEASURED]**, per the same honesty rule as the two-node edition: software runs and single anecdotal sessions may not substitute for these numbers.

## Appendix I — Run and Installation Guide

**I.1 Prerequisites** — unchanged from the two-node edition (Node.js 18+, Python 3.13, ESP-IDF v5.2 toolchain), except hardware now scales to 1–4 ESP32-S3 boards.

**I.2 Flashing and provisioning the nodes**

1. Build the firmware once (identical for all boards) in `firmware/esp32-csi-node/` (ESP-IDF; Docker build path documented in the firmware README).
2. Flash each board individually — repeat per COM port, one flash per physical node, up to four.
3. Provision each board's unique identity **without reflashing app code**: `python esp-flash.py --port COMx --ssid "..." --password "..." --target-ip <host-ip>`, then set a distinct `node_id` (1–4) per board via the same tool.
4. Verify on the serial monitor that each node reports its `node_id` before Wi-Fi connects and that CSI yield reaches ≥20 pkt/s independently for each board.

**I.3 Starting the dashboard host**

1. `npm install` (first time only), then `npm run dev` (dashboard + Python reference runtime) or `npm run dev:dashboard` (dashboard only) — no flag needed for node count; the host auto-detects 1–4 live nodes.
2. Open the dashboard, log in, and confirm the top bar shows the correct live node count and the correct `node_mode` label (`single_node`/`fused_two_node`/`fused_room`) as boards come online.
3. Do not run the Python live authority alongside the dashboard; it is retired and requires `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1` to bind at all, precisely to avoid a UDP :5005 collision.

**I.4 Calibrating the detection gate (per room, per node count)**

1. Stop the dashboard (the calibration tool needs port :5005).
2. With the room empty and **the intended live node count actually connected** (this matters more now than in the two-node edition — a two-node calibration does not necessarily transfer to four-node operation), run `scripts/calibrate-threshold.ts`.
3. Set the chosen value via `PHANTOM_MOTION_THRESHOLD` and restart the dashboard. Validate with a negative control (fan/curtain must not trigger) and a positive control (person walking through the monitored area must trigger), at the same node count used for calibration.

**I.5 Recording and replay**

Unchanged from the two-node edition; recorded CSV now additionally carries `raw_perturbation_n1..n4` (unclamped) specifically to support diagnosing the open four-node false-positive investigation.
