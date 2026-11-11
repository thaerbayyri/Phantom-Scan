# Phantom Scan — Research-to-Repo Gap Analysis

**Scope:** Applicability assessment of the attached research report *"CNN-LSTM Deep Learning for Wi-Fi CSI Human Motion/Presence Detection"* against the live state of this repository, verified by direct code/doc reading on 2026-08-06.

**Method note:** Every claim about the repo below is cited to a specific file and, where reasonable, a line number. Claims that could not be verified are labeled `[UNVERIFIED]`. Claims about published CNN-LSTM/CSI research are taken from the attached report as trusted literature-review input and are not re-verified here.

---

## 1. Executive summary

A CNN-LSTM/CNN-GRU motion-classification upgrade is **not currently justified as the next priority**. The repo's actual detection pipeline is a fully heuristic, deterministic DSP system (variance thresholds, MUSIC AoA, autocorrelation-based periodicity, Kalman/DBSCAN tracking) with zero ML in the decision path today — and several of the concrete gaps the research report would have a CNN-LSTM address (ACF-based human/mechanical discrimination, PC/edge-only deployment, an advisory-only confidence-scalar integration point) are **already implemented and tested**, just not fully wired into the live authoritative path. The higher-priority work is: (1) promote the already-computed ACF/periodicity feature on the live TypeScript path from a display-only label into an actual presence-gate input, matching what firmware already does; (2) run the real-hardware fan/HVAC negative control and the entirely-unexecuted P0–S8 positional-fidelity campaign, both of which are prerequisites for *any* accuracy claim, ML or heuristic; and (3) close test-coverage and calibration gaps on the spatial/tracking path. None of these require a trained model. The architecture pattern the research recommends for a *future* classifier (PC/edge hosting, advisory-confidence-only, never override the sovereign verdict) is already built and covered by tests in this repo — so if/when a labeled dataset exists, integration is comparatively cheap; the dataset itself, not the model architecture, is the binding constraint, exactly as the research report's own Recommendation 2 states.

---

## 2. Verified current state (repo ground truth)

### 2.1 How motion/presence detection is currently computed

There is **no ML in the presence/motion decision anywhere in this repo**. Three independent, heuristic, never-cross-fused presence mechanisms exist:

1. **Server two-node fusion gate** — `server/lib/node-fusion.ts:277` (`fuseTwoNodeTarget`): `present = max(motion1, motion2) >= threshold && r1 + r2 > EPS`, where `threshold` defaults to `DEFAULT_MOTION_THRESHOLD = 0.6` (`node-fusion.ts:43-45`, calibrated 2026-07-20 against an empty-room baseline, mean 0.49/σ 0.027 over 296 samples). `motion1/2` are saturated amplitude-variance ratios from `computeNodeMotionFromMatrix` (`node-fusion.ts:136-176`, `* MOTION_SATURATION_SCALE=4`, capped at 1). `r1/r2` are the PS-BEHTEST-004 gain-normalized unsaturated ratios (`computeGainNormalizedPerturbation`, `node-fusion.ts:238-242`), live-wired at `server/lib/websocket.ts:1504-1505` per ADR-056. Returns `null` (no target) if the gate fails — this is the deliberate empty-room ghost-target prevention.
2. **Server single-node gate (ADR-057)** — `hasSingleNodePresenceEvidence = motionDetected || hasTrackedTarget` (`node-fusion.ts:373-375`), live via `server/lib/websocket.ts:1059-1076`. This closed a real bug: previously, single-node mode had *no* presence check at all, so the MUSIC-spectrum point cloud + DBSCAN/Kalman tracker could cluster ambient noise/multipath and broadcast a continuous ghost target with nobody in the room. The doc comment (`node-fusion.ts:369-371`) itself admits this does **not** fully solve detecting a perfectly stationary person via spatial clustering alone — see §2.2/§4 item 2 below.
3. **Board (ESP32 firmware) presence verdict** — `edge_dsp_pure.c:201-218` (`edge_evaluate_human_presence`): requires `motion_present AND breathing_data_ready AND in_band [6-30 BPM] AND confident (resp_conf>=0.5) AND natural_jitter (period CV check)`. Wired at `edge_processing.c:772-805`. **This board-side verdict is never fused with the server/host decision** — `udp-server.ts:568-569,578-580` explicitly routes it only to a separate "Board DSP card," display-only.

`server/lib/target-state.ts` (`buildTargetState`, lines 102-155) is the final UI-state arbiter (`none/stale/idle/moving/degraded`) but does not itself decide presence — it classifies whatever mechanisms #1/#2 already gated, using a hardcoded `confidence >= 0.45` threshold (line 122) and 1.5s/5s stale/clear timers (lines 12-14).

The `MicroDopplerClassifier` (`server/lib/signal-processing.ts:342-452`) computes a DFT + autocorrelation-based `human`/`mechanical`/`unknown` label — this is ACF-based but **display-only**; it is never consulted by the presence/movement decision (confirmed: `target-state.ts` has zero references to `classification`/`humanProb`/`label`). See §4 for why this matters.

### 2.2 Periodicity/ACF-style vibration-rejection feature

**Implemented in code, but with a split authority that leaves the live path partially open.**

- **Firmware — implemented and enforced.** `edge_dsp_pure.c:142-199` (`estimate_periodicity_autocorr`) + `edge_dsp_pure.c:85-140` (`estimate_period_regularity_cv`, a coefficient-of-variation "natural jitter" check that rejects unnaturally-regular mechanical/fan tones, including sub-harmonic aliasing) feed directly into `edge_evaluate_human_presence` (§2.1 item 3) — a genuine gate, not just a label. Unit-tested with fan/curtain and tonal-aliasing negative controls in `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c:113-128,342-360`, though this test harness is **not wired into the ESP-IDF build or CI** (per its own header comment).
- **Live TS/dashboard path — implemented but does not gate.** The same ACF-style feature exists (`MicroDopplerClassifier`, §2.1), but only annotates an already-asserted target; it cannot suppress a false trigger from a fan or vibration on the path that actually drives the live dashboard.
- **Open risk, documented by the project's own audit:** `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:439` — *"`UNVERIFIED` — active TS-path empty-room false-positive rate under non-human movers... Needed: recorded negative-control captures (fan, curtain, HVAC, empty room) replayed through the actual authority path."* Even the firmware fix is caveated: `PHANTOM_SCAN_REMEDIATION_REPORT.md:481-483,494-498` states its threshold is "calibrated only against synthetic data" and that "real two-board hardware end-to-end verification... remains unverified."

**Verdict: partially mitigated, not fully open, but the mitigation is strongest on the path (firmware) that is not the one driving the live dashboard's presence verdict.**

### 2.3 ML/learned model wiring and the confidence-scalar invariant

**An optional, out-of-process AI sidecar exists (`scripts/ai_inference.py`, loads real weights: `csi-embed-v2.safetensors`, `pose_v1.safetensors`, `presence-head.json`, LoRA adapters `node-1/2.json`), but it is not started by default** (`script/dev-full.cjs:105-151` starts only the TS dashboard; the sidecar must be launched manually).

The **confidence-scalar-only, never-overrides-verdict invariant is enforced in code and backed by tests** — this is a genuine, verified positive finding:
- Guard clause: `server/lib/websocket.ts:366-390` — an AI client's `targetIdentity`/`vitalSigns` messages are relayed only as `advisoryIdentity`/`advisoryVitalSigns`; a non-AI client's attempt is dropped entirely; `currentTargetIdentity`/`currentVitalSigns` (the authoritative, served fields) are written only by the deterministic pipeline.
- Tests proving it: `server/lib/websocket.test.ts:83-100,150-178` (AI-injected identity never writes authoritative state; new-client snapshot always serves the deterministic value) and `tests/test_invariants.py:16-36` (`test_f1_ai_perturbations_do_not_change_deterministic_human_gate` — asserts identity-equality of the gate output under extreme adversarial AI-side inputs; also greps `scripts/ai_inference.py` to confirm its authoritative `"label"` field stays `"unknown"`).
- Two files whose names suggest this invariant but don't test it: `tests/behavioral/firewall-f2.test.ts` (tests a different guarantee — hardware-config write rejection) and `tests/behavioral/fusion-invariants.test.ts` (tests fusion gain-normalization math, no AI involvement).

**One documentation/reality mismatch found:** ADR-048 ("Adaptive CSI Activity Classifier") describes a Rust logistic-regression classifier (`crates/wifi-densepose-sensing-server/src/adaptive_classifier.rs`) that can *"override classification when loaded."* **This component does not exist anywhere in the repo** — no `crates/` directory, no `.rs`/`Cargo.toml` file at all. It is documented intent only, never implemented, and its "override" design directly contradicts the advisory-only invariant that *is* implemented and tested elsewhere. See §4(d) and §5.

### 2.4 CSI sampling rate: code vs. documented

- **Code:** no fixed sample-rate constant exists. `firmware/esp32-csi-node/main/csi_collector.c:66` sets a 20ms/50Hz *send-rate cap* (`CSI_MIN_SEND_INTERVAL_US`); a self-ping at `interval_ms=20` (line 107) stimulates CSI capture at up to 50Hz. `nvs_config.c`/`nvs_config.h` has **no** configurable sample-rate field.
- **Measured (real hardware log, not a code constant):** `TEST_AND_CLEANUP_REPORT.md:58` — *"steady ~200 packets / 5 s (~40 pkt/s aggregate)... firmware serial 'medium tick: yield=41-43pps' per board."* This is a genuine logged measurement, independently echoed in `generated_reports/Appendix.md` and `scripts/build_academic_reports.py`.
- **Documented (prose) — diverges from measurement:** `README.md:192`'s wire-protocol table states **~20 Hz/node**, roughly half the measured ~41-43 Hz — this appears stale/wrong. `MEASUREMENT_PLAN.md:15-23` is the one doc that correctly refuses to assert a number (`[TO BE MEASURED]`).
- **Conclusion:** the "~41-43 packets/s" figure referenced in the research-input prompt is **confirmed, not an assumption** — it comes from a real logged hardware run in this repo. README's ~20Hz claim should be corrected (§4, prioritized list item).

### 2.5 Test coverage for detection/gating logic

- **Zero test coverage:** `server/lib/signal-processing.ts` (MUSIC AoA, MotionGate, PDP ranger, background subtraction — 980 lines) and `server/lib/tracking.ts` (DBSCAN + Kalman — 380 lines) have **no** dedicated test file anywhere in the repo.
- **Covered, but only with synthetic/fabricated data:** `node-fusion.test.ts`, `target-state.test.ts`, `udp-server.test.ts` (hand-built hex fixtures), `tests/test_invariants.py`, `tests/test_phantom_runtime.py`, `tests/test_phantom_cross_node_correlation.py` (deterministic LCG-generated sine waves) all use synthetic or hand-constructed inputs, not real captures.
- **Real recorded data exists** (`data/sessions/`, 388 files, real CSVs/JSONL) but only **one** test touches it: `tests/behavioral/replay-authority.test.ts:44-60`, and its own doc comment states this is parser-fidelity-only — *"It does NOT re-run the fusion/motion pipeline on this real data."*
- **No subject-separated or room-separated splits exist anywhere** — expected and consistent, since the system is deterministic/heuristic, not ML-evaluated, today. The only place this concept appears is a literature-review doc discussing it as future work *if* an ML classifier is ever added.

---

## 3. Gap analysis — research findings vs. repo reality

### (a) ACF/periodicity vibration-rejection features
- **Applicable now?** Partially — already implemented on firmware; the gap is narrower than "build this feature," it's "wire the existing feature into the live gate."
- **What's missing to adopt it:** No new DSP feature needs to be built. What's missing: (1) wiring `MicroDopplerClassifier`'s `humanProb`/label into the live TS presence gate (`fuseTwoNodeTarget`/`hasSingleNodePresenceEvidence`) as a corroborating signal, following the pattern firmware already uses (`edge_evaluate_human_presence`); (2) a real-hardware fan/HVAC/curtain negative-control capture replayed through the actual live authority path (explicitly flagged missing in `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:439`).
- **Effort estimate:** Low-to-medium — 1-3 days of code wiring plus a hardware negative-control session (~1 day).
- **Risk if skipped:** The live dashboard (not firmware) remains provably vulnerable to fan/vibration/pet false triggers; this is the project's own audit finding, not a hypothetical.

### (b) Dataset collection requirements (subject/room diversity, ground truth)
- **Applicable now?** No — only relevant once a learned classifier is actually being built (research's own Phase 1.5/2).
- **What's missing:** No subject- or room-diverse labeled dataset exists; `data/sessions/` has real captures but no confirmed labeling/diversity scheme; no ground-truth device (camera/respiration belt) integration found.
- **Effort estimate:** Weeks (multi-subject, multi-room capture campaign + labeling harness), independent of any model work.
- **Risk if skipped:** None acute today — the current heuristic system does not depend on a dataset. Risk is contained entirely to future ML work being unstartable without it.

### (c) Compact CNN-GRU/CNN-LSTM presence/human-vs-non-human classifier
- **Applicable now?** No.
- **What's missing:** Dataset (see b) is the binding constraint; no training pipeline, no model file for this specific task exists. Note: the *task* this would solve (human-vs-non-human discrimination) is already served reasonably well by the existing deterministic ACF/DFT `MicroDopplerClassifier` — which is directly consistent with the research report's own Finding 3 (ACF/statistical methods, not deep nets, are the validated approach for this exact discrimination task).
- **Effort estimate:** Weeks-to-months, gated entirely on (b).
- **Risk if skipped:** Low — deferring this is aligned with, not contrary to, the research's own evidence.

### (d) Confidence-scalar integration point and its test coverage
- **Applicable now?** N/A — already built and tested (§2.3). This is the one recommendation from the research report that is furthest ahead of where the research assumed the repo to be.
- **What's missing:** Nothing functionally. The one loose end is documentation hygiene: ADR-048 describes a conflicting "override" design that was never implemented and should be reconciled with the invariant that *is* implemented (see §5).
- **Effort estimate:** None for the integration point itself; <1 hour to amend/deprecate ADR-048.
- **Risk if skipped:** Low — ADR-048's stale text could mislead a future contributor into building the override design it describes; worth a documentation fix regardless of ML roadmap timing.

### (e) Sampling-rate adequacy for respiration vs. heart-rate targets
- **Applicable now?** Yes, as an evaluation question, not a build task.
- **What's missing:** Measured ~41-43 pps/node (§2.4) comfortably clears the ≥10 Hz the research cites as needed for respiration. Heart-rate accuracy is unverified — no ground-truth (pulse-ox) validation session was found in the repo's test plans, consistent with the research's own caveat that ESP32-class hardware and this sampling regime make heart-rate marginal.
- **Effort estimate:** None for respiration; a dedicated ground-truth validation session (a day or more) if heart-rate claims are ever required.
- **Risk if skipped:** Low near-term — heart-rate is explicitly framed by the research itself as a stretch goal, not a deliverable.

### (f) On-node (ESP32-S3/TFLM) vs. PC/edge deployment placement
- **Applicable now?** N/A — already correctly decided and implemented this way.
- **What's missing:** Nothing. Firmware runs zero ML (pure heuristic DSP, §2.1 item 3); the one real model sidecar already runs off-node and isn't even started by default. This matches the research's Recommendation 5 exactly, without any of it having been built in response to this research (it predates the research report).
- **Effort estimate:** None.
- **Risk if skipped:** N/A — not a gap.

---

## 4. Prioritized fix/change list

| ID | Item | Type | Blocking? | Evidence | Recommended action | Effort |
|---|---|---|---|---|---|---|
| 1 | Live TS-path ACF/periodicity signal is display-only, not gating | gap | Y | `signal-processing.ts:342-452` (display-only); `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:439` (UNVERIFIED) | Wire `MicroDopplerClassifier` output into the live presence gate as a corroborating signal, mirroring firmware's `edge_evaluate_human_presence` pattern | 1-3 days |
| 2 | Real-hardware fan/HVAC/curtain negative control never run on either path | gap | Y | `PHANTOM_SCAN_REMEDIATION_REPORT.md:481-483,494-498` | Run the negative-control session specified in `REAL_TEST_REPORT.md` Stage S2 against both TS and firmware paths | ~1 day (hardware) |
| 3 | Positional-fidelity campaign P0–S8 entirely unexecuted | gap | Y (for any positional-accuracy claim) | `REAL_TEST_REPORT.md` — every stage table empty, doc self-flagged "HISTORICAL (superseded)" | Execute the existing P0–S8 plan or explicitly re-scope/replace it | days (multi-session) |
| 4 | Spatial/DBSCAN presence path (`tracking.ts` `maxEnergy>10`, MUSIC `pThreshold=maxPower-10`) has no calibrated absolute noise floor | gap | N (temporal gate covers moving targets; stationary-person detection is the exposure) | ADR-057 (self-flags "unverified on real hardware"); `tracking.ts:326`; `websocket.ts:865` | Capture a calibrated empty-room baseline on real hardware; derive an absolute noise floor for the spatial clustering stage | 1-2 days |
| 5 | Zero test coverage on `signal-processing.ts` and `tracking.ts` (TS) | gap | N | no matching `*.test.ts` found for either module | Add unit tests for MUSIC AoA, MotionGate, DBSCAN, Kalman filter | 2-4 days |
| 6 | README wire-protocol table claims ~20Hz/node CSI rate; measured is ~41-43 pps/node | bug (doc) | N | `README.md:192` vs `TEST_AND_CLEANUP_REPORT.md:58` | Correct the README figure | <1 hour |
| 7 | Firmware `edge_processing.c` lacks the cross-subcarrier SFO/PDD regression that `phase_sanitizer.py` implements offline | gap | N (live path already cancels SFO/PDD via conjugate multiplication; firmware phase isn't relied on today) | `docs/research/csi-phase-in-wifi-sensing.md` (untracked, open-gap note); `edge_processing.c` has only temporal unwrap, no cross-subcarrier fit | Port the linear-fit approach into firmware, or formally document as out-of-scope | 1-2 days if pursued |
| 8 | ADR-048 describes a Rust "override"-capable classifier that was never implemented and contradicts the tested advisory-only invariant | enhancement (doc) | N | ADR-048 vs. `websocket.ts:366-390` + tests | Amend or mark ADR-048 superseded to match the now-proven advisory-only pattern | <1 hour |
| 9 | Heart-rate (±5 BPM) accuracy unvalidated against ground truth | research-validation | N | no ground-truth vitals validation found in test plans | Treat as stretch goal per the research report's own framing; add pulse-ox ground truth only if prioritized | N/A now |
| 10 | CNN-GRU/CNN-LSTM presence classifier | research-validation / enhancement | N | no labeled dataset exists; existing ACF heuristic already research-aligned | Defer to Phase 2+, gated on dataset collection (item not started) | weeks (deferred) |

---

## 5. Explicit non-recommendations

- **Building the CNN-GRU/CNN-LSTM classifier now.** No dataset exists, and the discrimination task it would target (human-vs-non-human) is already served by a validated-in-the-literature approach (ACF/statistical) that's already implemented. Building the model now would be solving a problem the repo doesn't currently have evidence of needing solved by deep learning specifically.
- **On-node TFLM deployment.** The repo already correctly keeps all ML off the ESP32-S3; the research's own findings on tight SRAM margins (an unrolled LSTM needing ~398KB failed to load on a 256KB-class board) reinforce not revisiting this.
- **Expanding two-node fusion complexity / adding more nodes for accuracy.** The research's own "dilution effect" finding (a single well-placed link outperformed 72-link fusion) argues against this; the existing two-node amplitude-balance approach with the second node as coverage redundancy (not an accuracy multiplier) is the right shape already.
- **GAN/diffusion-based CSI data augmentation.** Premature — there is no first real dataset yet to augment.
- **Heart-rate / multi-target classification as near-term deliverables.** The research itself calls these "research-grade stretch goals," and this repo has no ground-truth validation infrastructure for them yet.
- **Resurrecting ADR-048's Rust "override" classifier design.** It directly conflicts with the advisory-only invariant that is already implemented and tested; reviving it would be a regression, not progress.

---

## 6. Open questions for Thaer

1. `docs/research/csi-phase-in-wifi-sensing.md` is currently untracked/uncommitted (per git status) and is the only place the firmware SFO/PDD gap is documented — is this meant to become permanent, committed documentation, or was it exploratory scratch work?
2. Items #1/#2 (live-path ACF gating + real hardware negative control) and item #3 (P0–S8 campaign) both need hardware rig time and are both currently open — which should be sequenced first given available hardware/lab time?
3. Is there budget or timeline intent for a subject- and room-diverse labeled dataset collection effort at all, or should ML classifier work stay indefinitely deferred?
4. Should ADR-048 be formally marked superseded/deprecated given its "override" design was never implemented and now conflicts with the tested advisory-only architecture — or is there a reason it's being kept as-is?
5. Is heart-rate estimation (±5 BPM) an actual stakeholder requirement (e.g., for a SAR/civil-defence use case), or can it be dropped from stated goals given the sampling-rate and ESP32 CSI-quality caveats the research itself raises?
