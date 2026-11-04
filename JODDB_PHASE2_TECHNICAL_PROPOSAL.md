# Phantom Scan — Phase 2 Technical Proposal

**Multi-Node, Through-Wall Wi-Fi CSI Human Presence, Movement & Localization Sensing**

Prepared for: JODDB (Jordan Design & Development Bureau) technical review
Prepared by: Phantom Scan project team
Status of figures in this document: current-system facts are drawn directly from the
shipped codebase and its own audit/test reports (cited inline); Phase 2 numbers are
**projections and research-literature evidence**, not measured results, and are labeled
as such throughout. No cost/pricing figures are included in this version, per project
lead's instruction — only hardware types, specs, and quantities.

---

## 1. Executive Summary

Phantom Scan is a working, two-node Wi-Fi Channel State Information (CSI) sensing
system that detects human presence and coarse (1-dimensional) movement through walls,
using two $7-class ESP32-S3 radios and no cameras or wearables. The system is real,
tested (132 TypeScript + 81 Python automated tests passing), and instrumented with an
honesty discipline that is unusual for a prototype-stage project: the UI, reports, and
documentation actively refuse to claim capabilities (true spatial angle-of-arrival,
2-D position, multi-target tracking, or a validated accuracy number) that the current
2-node, single-antenna hardware cannot physically deliver.

This proposal requests JODDB's review and support to move from that honest 2-node
baseline to four capabilities the project's current stakeholders have prioritized for
this phase:

1. **Single human movement detection** — already architecturally present; needs
   real-hardware calibration and its first **measured** accuracy campaign.
2. **Multiple human movement detection** — **not yet implemented**; requires new
   multi-node signal-separation work, scoped here as a staged, research-grade track.
3. **Target location on a radar-style display, through walls** — currently limited to
   a **1-dimensional** position (target's location along the line between the two
   nodes only); this phase proposes expanding to **N≥3 non-collinear nodes** for
   genuine, if coarse, 2-D room-zone localization.
4. **CSI sniffing without joining or hosting a Wi-Fi network** — **not yet
   implemented**; the current firmware must associate to an access point as a normal
   client to receive CSI. This phase scopes a promiscuous-mode (passive/monitor-mode)
   capture R&D track, with an explicit regulatory-review checkpoint before any field
   test against a network the team does not own or administer.

The proposal also addresses the project's own open question — *algorithms vs. an AI
model vs. CNN-LSTM* — with a literature-grounded recommendation: **keep a
deterministic, physics-based detector as the sovereign decision-maker, and introduce a
compact CNN-LSTM/CNN-GRU model as a bounded confidence input, never as a replacement.**
This is not a hedge; it is what the published evidence (§4.1, §7) and the project's own
existing invariant tests support.

---

## 2. Current System Baseline (verified against the shipped codebase)

| Property | Current reality | Source |
|---|---|---|
| Node count | **Exactly 2** ESP32-S3 boards, fixed 3 m baseline, `N1=(-1.5,0)`, `N2=(+1.5,0)` | `shared/schema.ts` `NODE_ANCHORS`, README |
| Antennas | **1 receive antenna per node** — no antenna array | `PhantomScan_HardwareReality_Alignment_Report.md`, CNN-LSTM research doc |
| CSI acquisition mode | Node **associates to a Wi-Fi AP as a normal STA client** and self-pings it (~50 Hz ICMP) to keep a steady CSI packet rate | `firmware/esp32-csi-node/main/main.c` (`esp_wifi_set_mode(WIFI_MODE_STA)`, `esp_wifi_connect()`) |
| Effective CSI rate | ~41–43 packets/sec/node measured (50 Hz firmware cap, not guaranteed) | README wire-protocol table |
| Subcarriers | 64 per packet, amplitude (+ raw phase, not yet SFO/PDD-sanitized for use) | README, ADR-058 |
| Localization | **1-D only** — target is placed along the N1–N2 axis using a cross-node motion-energy ratio (`balance = r2^p/(r1^p+r2^p)`); there is **no true 2-D position** and no spatial angle-of-arrival (single antenna per node makes AoA physically impossible) | README §Phantom Balance Fusion, `server/lib/node-fusion.ts` |
| Multi-target tracking | **Not implemented.** No multi-target data structures, IDs, or count logic exist anywhere in `server/`, `client/`, or `shared/` | verified by direct code search, this session |
| Detection logic today | Deterministic amplitude-variance / motion-energy threshold gate (`PHANTOM_MOTION_THRESHOLD`, currently **provisional**: 0.6, set from one 60 s two-node empty-room recording; not validated against a fan negative control, a long empty soak or four-node operation, and its false-alarm and detection rates are `[TO BE MEASURED]`) | README §Honest Limitations |
| Measured accuracy | **`TO_BE_MEASURED`.** A full accuracy-scoring harness (recall, false-positive rate, precision, F1, time-to-first-detect) was built and unit-tested this cycle, and validated end-to-end against synthetic data — but has never been run against a real human subject on real hardware. No detection-rate or false-positive number for Phantom Scan exists yet. | `ACCURACY_HARNESS_REPORT.md`, `CURRENT_STATE.md` |
| AI/ML today | Optional, isolated advisory sidecar (`scripts/ai_inference.py`); explicitly **cannot** override or write the authoritative human/non-human verdict — enforced by an automated invariant test (`test_f1_ai_perturbations_do_not_change_deterministic_human_gate`) | `PhantomScan_HardwareReality_Alignment_Report.md` |
| Software/test state | 132 TypeScript + 81 Python tests passing at last full run; `tsc --noEmit` clean | README badges, remediation report |

**Why this baseline matters for JODDB's review**: the project does not currently
overstate what it can do. The dashboard's own AoA/heatmap panels were relabeled
mid-project from "Angle of Arrival" to "temporal signature" specifically because the
team audited its own UI and found it implying a physical capability (spatial angle
measurement) the single-antenna hardware cannot provide, and fixed it rather than
leaving the stronger-sounding label in place. This proposal continues that discipline:
every capability requested below is framed against what is genuinely new, not a
relabeling of what already exists.

There is also an existing sponsorship pitch script in this repository
(`docs/presentations/JODDB-Sponsorship-Pitch-Script.md`) written for a live 15–20
minute spoken presentation with a demo. This document is different in purpose: it is
the written technical backing material — architecture, evidence, roadmap, and hardware
ask — intended for JODDB's technical reviewers to read and evaluate, and the pitch
script's talking points should be checked against it before use.

---

## 3. Phase 2 Objectives, Mapped to Current Gaps

| # | Goal (as stated) | Current status | What Phase 2 actually requires |
|---|---|---|---|
| 1 | Single human movement detection | Architecturally present, **never accuracy-tested on real hardware** | Real-hardware calibration + the first measured S1–S8 campaign (§7) |
| 2 | Multiple human movement detection | **Not implemented** | New multi-node feature-separation / counting model; staged, research-grade (§4.3) |
| 3 | Target location on radar (through-wall) | **1-D only**, 2-node | N≥3-node geometry + multilateration for coarse 2-D room-zone position (§4.4) |
| 4 | CSI sniffing without joining/creating a network | **Not implemented** — firmware requires STA association today | Promiscuous/monitor-mode capture R&D + DSP redesign for irregular sampling (§4.5) |

---

## 4. Technical Approach

### 4.1 The algorithms-vs-AI-vs-CNN-LSTM question

This question was already the subject of a dedicated literature review completed
inside the project (`docs/CNN-LSTM Deep Learning for Wi-Fi CSI Human.md`), surveying
~30 peer-reviewed and preprint sources specific to Wi-Fi CSI human sensing, including
systems architecturally close to Phantom Scan (Pulse-Fi: two single-antenna ESP32s;
Wi-MoID/SrcSense/"Who Moved My Cheese?": single-link human-vs-non-human discrimination
through walls). The findings, summarized:

- **A CNN-LSTM (or CNN-GRU) classifier is a well-supported upgrade for the
  motion/presence task**, not a speculative one — comparable single-link systems in
  the literature reach 92–98% in-domain. But headline numbers in this literature are
  **systematically inflated** by subject-mixed train/test splits (documented data
  leakage, Varga et al., *Sensors* 2024/*Signals* 2025); realistic cross-subject,
  cross-room accuracy is typically **10–30 percentage points lower**. Any number
  Phantom Scan reports to JODDB must use subject- and room-separated evaluation, or it
  will not be credible.
- **The human-vs-non-human (vibration, fan, pet) false-trigger problem is largely
  solved in the literature *without* deep learning** — via autocorrelation/periodicity
  features on a single link (97–99% reported by the Origin Wireless/UMD lineage). This
  is the **highest-ROI, lowest-risk next step**: add periodicity/ACF rejection features
  to the existing deterministic gate before introducing any neural network.
- **Single antenna per node is not a blocker** for presence/motion or single-target
  vital-sign work — it *is* a hard architectural blocker for true spatial
  angle-of-arrival, which is why this proposal does not request AoA and instead
  proposes N-node multilateration (§4.4) for 2-D coverage.
- **A full CNN-LSTM belongs on the host PC, not the ESP32.** A compact (<200k
  parameter) CNN-GRU can run in real time on ordinary CPU hardware; an on-node
  TensorFlow-Lite-Micro model is feasible only for a trivial motion gate and is not
  recommended for this phase.
- **The model's output must feed a bounded confidence adjustment into the existing
  deterministic verdict — never replace it.** This is already an enforced invariant in
  the codebase for the current advisory AI sidecar and should remain the design rule
  for any new model.

**Recommendation to JODDB: a phased hybrid, not a binary choice.** Phase 2.3 (§8)
keeps the deterministic detector sovereign, adds physics-based ACF/periodicity
features first, and only then trains a bounded-confidence CNN-GRU — with an explicit
accuracy threshold (>90% cross-subject) below which the project pivots back to
physics-based features rather than continuing to invest in the neural-network path.

### 4.2 Single human movement detection

Already implemented as a deterministic amplitude-variance/motion-energy threshold
(`server/lib/node-fusion.ts`). What's missing is **validation**, not new capability:

1. Real-hardware empty-room and fan/HVAC negative-control calibration
   (`scripts/calibrate-threshold.ts` already exists and is ready to run — it has never
   been run to completion on real hardware).
2. The first real accuracy measurement using the already-built harness
   (`scripts/accuracy/`), scored against the S1–S8 campaign already defined in
   `MEASUREMENT_PLAN.md`.

This is the lowest-risk, fastest deliverable in this proposal and should be the first
real number JODDB sees from the project.

### 4.3 Multiple human movement detection

This is the hardest goal in this phase and is scoped honestly as **staged and
research-grade**, not a near-term guarantee:

- Separating more than one simultaneous mover from a single Wi-Fi link's amplitude
  stream is an open research problem. The closest published comparable (DeepCount,
  CNN+LSTM crowd counting) reaches 86.4% accuracy **up to 5 people**, and that is
  *counting*, not per-person tracking with identity.
- **Recommended Phase 2 target: coarse presence-count** (e.g., "1 person" vs. "2+
  people" in the room), using multi-node feature clustering across N≥4 nodes with
  spatial diversity — **not** full multi-target 2-D trajectories with persistent
  per-person IDs. The latter is set as future work beyond this phase.
- A published caution directly relevant here: a 2026 dilution-effect study found that
  in a dense multi-link mesh, **a single well-placed link outperformed naive
  multi-link fusion**. This proposal's design therefore fuses at the
  feature/decision level, not by naive raw concatenation, and explicitly budgets time
  to validate that more nodes actually help before committing to a larger mesh.

### 4.4 Target location on radar, through walls (2-D)

The current 2-node system can only ever place a target along the straight line
between the two boards — this is a real physical limit, not a bug, and the project's
own README says so.

Genuine 2-D coverage requires **at least 3 non-collinear nodes**. Proposed approach:

- Arrange N≥3 (recommend starting at 4) ESP32-S3 nodes around the perimeter of a
  single test room, at known, non-collinear positions.
- Extend the existing per-node motion-energy metric (already computed today for the
  2-node balance calculation) into a **weighted multilateration** across all N nodes —
  each node's relative motion-energy/amplitude-ratio acts as a coarse "closeness"
  weight, similar in spirit to how the existing 2-node balance already works, just
  generalized to N points instead of 2.
- **Honesty commitment carried forward from the current codebase**: this will be
  reported as *coarse room-zone position* (which part of the room the target is in),
  not centimeter-precision radar tracking. Wi-Fi CSI/RSSI-based ranging is well known
  in the literature to be noisy (commonly ±1–3 m); claiming finer precision than that
  without measurement would repeat exactly the kind of overclaim this project has
  previously caught and fixed in its own UI.
- Validate against ground truth using the position-tracking infrastructure that
  **already exists** in the repo (`scripts/join-groundtruth.ts`, used for the S3–S8
  on-axis localization campaign) — extended from 1-D to 2-D ground-truth points.

### 4.5 CSI sniffing without joining or hosting a Wi-Fi network

This is the one goal where the current implementation is furthest from done, and it
is scoped here explicitly as an **R&D track with a regulatory checkpoint**, per the
project lead's direction.

**Current reality**: `firmware/esp32-csi-node/main/main.c` puts the ESP32-S3 in
`WIFI_MODE_STA` and calls `esp_wifi_connect()` — the node must have valid credentials
for, and actively join, a Wi-Fi network before it can receive any CSI at all. It then
self-pings that network's gateway at ~50 Hz specifically to guarantee the steady
packet rate the DSP pipeline is tuned for.

**Proposed R&D path**:

1. Switch the ESP32 Wi-Fi driver into **promiscuous (monitor) mode**
   (`esp_wifi_set_promiscuous(true)`) on a fixed channel, instead of associating to
   any AP. Espressif's CSI extraction hooks (`esp_wifi_set_csi_config`,
   `esp_wifi_set_csi_rx_cb`) fire on receipt of the PHY-layer training fields of *any*
   Wi-Fi frame the radio decodes while in this mode — including ambient traffic
   between other devices that the node never joins or authenticates to. This is
   documented as feasible in the ESP32 CSI research literature (passive-mode CSI
   tools), though with far less-studied, less-benchmarked results than the
   STA-association mode this project currently uses.
2. **Key engineering consequence**: promiscuous capture depends entirely on how much
   ambient Wi-Fi traffic happens to exist on the chosen channel — packet rate will be
   irregular and environment-dependent, unlike the current guaranteed ~42 pps. The DSP
   pipeline's windowing (currently tuned for a near-constant rate) will need to
   tolerate variable-rate, gappy input — a real design change, not a firmware flag
   flip.
3. **Regulatory note — flagged explicitly, not glossed over**: passively receiving
   the unencrypted physical/MAC-layer headers of nearby Wi-Fi frames (to extract CSI)
   without ever associating to, authenticating with, or decrypting the payload of a
   network is generally in the same category as ordinary RF spectrum monitoring. It is
   materially different, however, from capturing frames on a network the team
   administers. **Before any field trial against ambient or third-party networks, this
   proposal recommends JODDB's legal/regulatory office confirm compliance with
   Jordan's Telecommunications Regulatory Commission (TRC) rules and any
   institution-specific policy.** This is standard practice for RF-sensing R&D under
   institutional authorization and should not block lab-bench prototyping against a
   network the team owns and controls in the interim.

---

## 5. Hardware Requirements (Prototype Scale — No Cost Figures)

Per the project lead's direction, this section lists hardware **types, specifications,
and quantities only** — no pricing.

### 5.1 Sensing nodes

| Item | Quantity | Notes |
|---|---|---|
| ESP32-S3 development board (e.g. ESP32-S3-DevKitC-1 class) | **4** (start), expandable to 6 | Matches the currently-working firmware target (`idf.py set-target esp32s3`); keep **single onboard/PCB antenna per node** — literature review found multi-antenna mainly helps AoA/phase-difference methods, which are out of scope, not motion/presence/coarse-localization |
| USB-A→USB-C data/power cables | 4–6 | One per node, for flashing and continuous power |
| Multi-port USB power adapter or PoE splitters | 1 | For wall/corner-mounted nodes away from convenient outlets |
| Small non-metallic enclosures (3D-printed or ABS project box) | 4–6 | Metal enclosures would shield the antenna — must be RF-transparent |

### 5.2 Test environment fixtures

| Item | Quantity | Purpose |
|---|---|---|
| Laser rangefinder or measuring tape | 1 | Precisely record N-node geometry for `NODE_ANCHORS`-equivalent configuration |
| Oscillating fan (or similar mechanical-vibration source) | 1 | Negative-control calibration (`calibrate-threshold.ts` already supports this workflow) |
| Access to a single room with an interior wall (drywall preferred as the baseline through-wall material) | 1 room | Through-wall validation; drywall is the favorable case per literature — concrete/metal degrade signal severely and should be tested only as a stretch goal |
| USB or IP camera (optional) | 0–1 | The accuracy harness's ground-truth logger (`scripts/accuracy/groundtruth-logger.ts`) already supports manual keypress-based ground truth without a camera; a camera improves precision but is not required to start |

### 5.3 Host / compute

| Item | Spec guidance | Notes |
|---|---|---|
| Development PC or laptop | Modern multi-core CPU (6+ cores recommended), 16–32 GB RAM | Sufficient to run the existing Node/TS + Python stack, the accuracy harness, and train a compact (<200k-parameter) CNN-GRU on CPU in reasonable time — **no dedicated GPU is required** for a prototype of this scale |
| Discrete GPU | Optional — any modern consumer CUDA-capable GPU, 6 GB+ VRAM | Not required; only accelerates model-training *iteration speed* during Phase 2.3, not a hard prerequisite |
| Wi-Fi access point / router | 1 (existing/available) | Required for the current STA-association CSI mode (§2); becomes optional if/when the passive-mode R&D track (§4.5) succeeds |
| ESP-IDF v5.2 Docker toolchain | Already working per README | No new firmware tooling required; existing build/flash/provision scripts are reused as-is |

### 5.4 What is deliberately **not** requested

- No antenna arrays or multi-antenna modules — not needed for the goals in this
  phase and would not by itself unlock true AoA on the ESP32-S3's single-RF-chain
  hardware.
- No specialized research-grade NICs (Intel 5300 / Atheros class) — ESP32 was
  chosen originally, and remains chosen here, specifically for deployability and
  reproducibility; the accuracy tradeoff is documented and accepted (§9).
- No GPU server / cluster — the recommended model size does not need one at
  prototype scale.

---

## 6. Software Deliverables (What Gets Built)

| Component | Status today | Phase 2 work |
|---|---|---|
| `shared/schema.ts` node geometry | Fixed 2-node `NODE_ANCHORS` | Generalize to configurable N-node geometry |
| `server/lib/node-fusion.ts` | 2-node, 1-D balance | Extend to N-node weighted multilateration (§4.4) |
| Presence/motion gate | Deterministic threshold, uncalibrated on real hardware | Real-hardware calibration; add ACF/periodicity vibration-rejection features |
| `scripts/accuracy/` harness | Built, unit-tested, synthetic-data smoke-tested | Run for real against the S1–S8 campaign (first real numbers) |
| Multi-target logic | None | New: coarse presence-count model (§4.3), explicitly staged/research-grade |
| CNN-GRU confidence model | None | New: trained on PC, feeds bounded confidence into existing sovereign verdict, never replaces it |
| Firmware Wi-Fi mode | STA-association only | New: promiscuous-mode capture prototype (§4.5), parallel R&D track |

---

## 7. Accuracy Measurement & Honesty Commitment

Phantom Scan already has a working accuracy-scoring harness
(`scripts/accuracy/run-accuracy-trial.ts`) that computes recall, false-positive rate,
precision, F1, time-to-first-detect, and drop-out duration from either a replayed
recording or a live session, against operator-logged or camera-derived ground truth.
It has been fully unit-tested (16 tests) and smoke-tested end-to-end on synthetic data,
but — stated plainly, matching the project's own internal reporting standard — **it
has never scored a real trial**. Every accuracy figure the project could report today
is `TO_BE_MEASURED`, and this proposal commits to keeping that label until an actual
trial is recorded and scored through this tool, rather than presenting a projected or
literature-derived number as if it were measured.

Phase 2.1 (§8) is scoped specifically to produce the **first real numbers** — this is
deliberately sequenced early in the roadmap so JODDB's review can be anchored to
measured evidence as soon as possible rather than projections.

---

## 8. Phased Roadmap

| Phase | Focus | Rough duration | Key deliverable | Go/no-go signal |
|---|---|---|---|---|
| **2.0 — Foundation** | Bring up N=4 nodes; generalize node geometry in schema/config; run real-hardware empty-room + fan negative-control calibration | 2–4 weeks | First `PHANTOM_MOTION_THRESHOLD` derived with the soak + negative-control protocol (the current 0.6 is provisional, from one 60 s recording), not a placeholder | Empty-room false-positive rate materially below the fan-negative-control ceiling |
| **2.1 — Single-human accuracy** | Run the S1–S8 measurement campaign through the existing harness | 2–3 weeks | First **measured** recall/FPR/F1/precision numbers for Phantom Scan | Recall and FPR at levels the team is willing to report to JODDB |
| **2.2 — N-node 2-D localization** | Extend node-fusion to weighted multilateration across N≥3 nodes | 3–5 weeks | Coarse room-zone position with measured position error (via extended `join-groundtruth.ts`) | Position error acceptable for a room-zone (not centimeter) claim |
| **2.3 — AI-assisted detection** | ACF/periodicity features first, then compact CNN-GRU as bounded confidence input | 4–8 weeks | Cross-subject, cross-room accuracy report; false-alarm rate vs. the deterministic-only baseline | **>90% cross-subject accuracy and a measurable improvement over the physics-only baseline**, or pivot back to physics-based features only |
| **2.4 — Multi-human detection (research-grade)** | Multi-node feature clustering for coarse presence-count | 6–10+ weeks | "1 vs 2+ people" classifier with measured accuracy | Explicit go/no-go — if this does not clear a usable accuracy bar, report it honestly as future work, not a shipped capability |
| **2.5 — Passive CSI capture (parallel R&D track)** | Promiscuous-mode prototype on one spare node; DSP redesign for irregular sampling | 4–8 weeks | Working passive capture on a lab-owned network; documented packet-rate/quality characterization | Regulatory sign-off obtained before any test against a network the team does not own |

Phases 2.0–2.2 are sequential and lower-risk. Phases 2.3–2.5 can run partly in
parallel once 2.0–2.1 hardware and calibration are in place.

---

## 9. Risks and Open Questions (Stated Honestly)

- **ESP32 CSI is lower-fidelity than the research-grade NICs (Intel 5300, Atheros)
  behind most of the literature's headline numbers.** Phantom Scan's real-world
  accuracy will likely trail published figures; this is a known, accepted tradeoff for
  deployability and reproducibility, not an oversight.
- **Cross-subject/cross-room generalization is the dominant failure mode** in this
  literature — in-domain numbers are not a reliable predictor of field performance.
  Phase 2.1 and 2.3 are structured specifically to measure this rather than assume it.
- **Static or seated humans, and pets, remain the hardest cases** across the
  literature. A "no detection" result must never be reported as "confirmed no human
  present" — this framing should be preserved in any operator-facing UI.
- **Heart-rate extraction is marginal at the current ~42 packets/sec/node** sampling
  rate; respiration is achievable, heart rate is a stretch goal, not a phase-2
  deliverable.
- **Clock drift across independently-clocked ESP32 nodes** (~20–50 ppm) rules out
  raw-signal-level fusion across more than 2 nodes; the N-node multilateration in
  §4.4 must fuse at the feature/decision level, as the current 2-node system already
  does, not at the raw-phase level.
- **Multi-node fusion is not guaranteed to help.** A published dilution-effect
  finding (§4.3) showed a single well-placed link can outperform naive multi-link
  fusion — Phase 2.2/2.4 include an explicit check for whether additional nodes
  measurably improve results before committing further hardware.
- **Passive/promiscuous CSI capture is the least mature part of this proposal** —
  feasible per the literature, but not yet demonstrated inside this project, and
  carries a regulatory dependency (§4.5) that is outside the engineering team's
  authority to resolve alone.

---

## 10. Request to JODDB

1. **Review and feedback** on the phased approach above, particularly the
   multi-human (§4.3/2.4) and passive-CSI (§4.5/2.5) tracks, which carry the most
   technical and regulatory risk respectively.
2. **Hardware support** per §5: additional ESP32-S3 nodes (bringing the deployed
   count from 2 to 4, expandable to 6), enclosures, and standard lab fixtures — no
   specialized or high-cost equipment is requested for this phase.
3. **Test-space access**: a single room with at least one interior (preferably
   drywall) wall, available for repeated short sessions across the roadmap above.
4. **Legal/regulatory guidance** specifically for the passive-CSI-capture R&D track
   (§4.5) before any test against a network the team does not administer — this is
   requested proactively, ahead of the engineering work reaching that point.
5. **Engineering time allocation** consistent with the phase durations in §8, with
   Phase 2.1 (first measured single-human accuracy numbers) prioritized as the
   earliest checkpoint for JODDB to evaluate real, not projected, results.

---

*This document draws directly on the current Phantom Scan codebase and its own
internal audit/test reports (`README.md`, `CURRENT_STATE.md`,
`ACCURACY_HARNESS_REPORT.md`, `PhantomScan_HardwareReality_Alignment_Report.md`,
`docs/CNN-LSTM Deep Learning for Wi-Fi CSI Human.md`, `docs/adr/ADR-012-esp32-csi-sensor-mesh.md`),
current as of 2026-08-12. Figures describing the shipped system are verified against
source; figures describing Phase 2 outcomes are explicitly projections pending
measurement, per §7.*
