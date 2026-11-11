# Phantom Scan — Fix-All Session Report

**Date:** 2026-08-06
**Scope:** Items 1-8 of the prioritized gap list from `PhantomScan_Research_Gap_Analysis.md`. Items 9-10 explicitly out of scope per the task mandate.
**Discipline:** every repo claim re-verified against current file state before acting; nothing labeled measured unless it came from a real run.

---

## 1. Status table

| Item | Title | Status | One-line reason |
|---|---|---|---|
| 1 | Wire ACF/periodicity classifier into live presence gate | **Done** | `evaluateClassifierCorroboration` corroborating gate added to `fuseTwoNodeTarget` + `hasSingleNodePresenceEvidence`, wired live, observable, 17 new unit tests |
| 2 | Real-hardware negative-control session | **Done (tooling) / Blocked on hardware (measurement)** | Checklist + recording column + analysis script ready; pre-Item-1 baseline measured from real existing sessions; post-fix rate `[TO BE MEASURED]` |
| 3 | P0-S8 positional-fidelity campaign | **Partially done / Blocked on hardware** | Doc confirmed self-flagged HISTORICAL but structurally still the only campaign plan; tooling smoke-tested; S2 gap filled; execution needs a rig session |
| 4 | Spatial/DBSCAN noise-floor calibration | **Done (logic+tooling) / Blocked on hardware (constant)** | `calibrateEnergyThreshold` + configurable `TrackingProcessor` threshold + `--spatial` capture mode; default unchanged (10); calibrated value `[TO BE MEASURED]` |
| 5 | Test coverage for `signal-processing.ts` / `tracking.ts` | **Done** | 22 + 22 new tests; two real pre-existing bugs found (PS-GAP-TRK-001 fixed, PS-GAP-MUSIC-001 documented) |
| 6 | README sampling-rate discrepancy | **Done** | ~20 Hz corrected to measured ~41-43 pps (50 Hz cap noted) in README + firmware README (5 spots) + system_architecture_methodology.md; historical ADRs left as record |
| 7 | Firmware SFO/PDD regression | **Done (formally deferred)** | Re-verified live path already cancels via conjugate multiplication and firmware phase is non-authoritative → ADR-058 marks out-of-scope with revisit trigger |
| 8 | ADR-048 reconciliation | **Found already fixed (this session, prior turn) — re-verified** | Amendment intact; no `crates/`/`Cargo.toml` exists; guard+tests re-run green; drifted line refs corrected (366-390 → 370-394) |

## 2. New findings surfaced while testing (not in the original gap list)

- **PS-GAP-TRK-001 (fixed + regression-tested):** `TrackingProcessor.process()` coasted through misses even when no target had ever been acquired — a cold start with only sub-threshold noise clusters returned a fabricated target at the Kalman origin (confidence 0.9) for up to 10 ticks. That non-null return is exactly the `hasTrackedTarget` evidence ADR-057's single-node gate trusts, so this directly fed the ghost-target bug class. Verified pre-existing via `git show HEAD:server/lib/tracking.ts`. Fix: coasting now requires a prior real acquisition ([tracking.ts](server/lib/tracking.ts), `acquiredThisTick || this.lastTarget`).
- **PS-GAP-MUSIC-001 (documented, NOT fixed):** `computeMUSICSpectrum` on a single snapshot (its only production usage pattern) builds a rank-1 covariance; `powerIterationEigen`'s deflation collapses the residual below the `norm < 1e-10` guard, so noise eigenvectors are the raw seeded start vector — never derived from the input. Verified empirically: plane waves from 0°, +30°, and -30° all produce the identical peak (43°, power -1.3996…, bit-for-bit). The single-source AoA peak is **independent of the true angle**. This is *in addition to* the documented "AoA is synthetic-only on single-antenna hardware" caveat. A proper fix (multi-snapshot covariance/spatial smoothing) is out of scope for a test-coverage task; a pinned test (`signal-processing.test.ts`) will start failing if it's ever fixed, flagging the test for update.

## 3. Files changed and tests added

**Implementation (TS):**
- [server/lib/node-fusion.ts](server/lib/node-fusion.ts) — `ClassifierGateInput`/`ClassifierCorroboration` types, `DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX` (0.2, env `PHANTOM_MECHANICAL_REJECT_MAX`, placeholder pending Item-2 data), `evaluateClassifierCorroboration`, `wasSuppressedByClassifier`, `computeEnergyGatePassed` factored out; `fuseTwoNodeTarget` + `hasSingleNodePresenceEvidence` accept optional classifier evidence (omitting it = byte-for-byte pre-Item-1 behavior); `FusedTarget.classifierCorroboration` added.
- [server/lib/websocket.ts](server/lib/websocket.ts) — classifier passed into `computeFusedTarget` and the single-node gate; per-tick corroboration tracked (`lastTickClassifierCorroboration`); hold-reasons now distinguish `*_classifier_vetoed*` from `*_no_detection*`/`*_below_motion_threshold*`; corroboration added to the `radialTarget` broadcast and the recording row.
- [server/lib/tracking.ts](server/lib/tracking.ts) — `calibrateEnergyThreshold` (mean+k·σ), `DEFAULT_SPATIAL_ENERGY_THRESHOLD` (env-overridable, default 10 = old literal), `TrackingProcessor(energyThreshold)` constructor param, PS-GAP-TRK-001 coast fix.
- [server/lib/recording-export.ts](server/lib/recording-export.ts) — `classifier_corroboration` CSV column, populated on every row (not gated on `target_visible`).
- [shared/schema.ts](shared/schema.ts) — optional `classifierCorroboration` enum on `radialTargetSchema`.
- [scripts/calibrate-threshold.ts](scripts/calibrate-threshold.ts) — `--spatial` mode (per-packet energy sampling → suggested `PHANTOM_SPATIAL_ENERGY_THRESHOLD`).

**New tests:**
- [server/lib/node-fusion.test.ts](server/lib/node-fusion.test.ts) — +17 tests: the full (a)-(d) matrix from the task spec for both `fuseTwoNodeTarget` and `hasSingleNodePresenceEvidence`, `evaluateClassifierCorroboration` unit tests, `wasSuppressedByClassifier`, and backward-compat pins.
- [server/lib/tracking.test.ts](server/lib/tracking.test.ts) — **new file**, 22 tests: calibration math, default-threshold regression pin, DBSCAN cluster count/membership/noise/chain, Kalman convergence/clamp/finiteness, PS-GAP-TRK-001 regressions.
- [server/lib/signal-processing.test.ts](server/lib/signal-processing.test.ts) — **new file**, 22 tests: MUSIC shape/determinism/guard + PS-GAP-MUSIC-001 pin, Hampel, MicroDopplerClassifier (mechanical vs aperiodic), PDPRanger RSSI fallback/clamps, BackgroundSubtractor static-suppression/step, MotionGate calibration/detection/manual-override/reset. All synthetic-input algorithmic tests, labeled as such.

**Tooling / docs:**
- [scripts/analyze_negative_control.py](scripts/analyze_negative_control.py) — **new**: real-recordings-only false-positive analysis, per-device, with `classifier_corroboration` breakdown, pre-Item-1-column detection, and `[BUG SUSPECTED]` self-check (visible+contradicted should be impossible).
- [docs/NEGATIVE_CONTROL_CHECKLIST.md](docs/NEGATIVE_CONTROL_CHECKLIST.md) — **new**: device list, positions, durations, exact commands, pass/fail, measured pre-Item-1 baseline.
- [docs/SPATIAL_CALIBRATION.md](docs/SPATIAL_CALIBRATION.md) — **new**: Item-4 status, procedure, result log (`[TO BE MEASURED]`).
- [docs/adr/ADR-058-firmware-sfo-pdd-out-of-scope.md](docs/adr/ADR-058-firmware-sfo-pdd-out-of-scope.md) — **new**: formal Item-7 deferral with revisit trigger.
- [README.md](README.md), [firmware/esp32-csi-node/README.md](firmware/esp32-csi-node/README.md) (5 spots), [docs/system_architecture_methodology.md](docs/system_architecture_methodology.md) — sampling-rate corrections.
- [REAL_TEST_REPORT.md](REAL_TEST_REPORT.md) — S2 cross-link to the checklist.
- [docs/adr/ADR-048-adaptive-csi-classifier.md](docs/adr/ADR-048-adaptive-csi-classifier.md) — drifted line references corrected.

## 4. Test commands run and results (final state)

```
> npx tsx --test server/**/*.test.ts
ℹ tests 189
ℹ pass 189
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0

> python -m pytest tests/
========== 86 passed, 1 skipped, 7551 warnings in 119.07s (0:01:59) ===========
```

(The 1 pytest skip is the pre-existing hardware-conditional `tests/test_esp_capture_e2e.py` recordings test — unchanged from before this session. TS suite grew from 141 → 189 tests during this session; all green.)

Safety invariants explicitly re-run and green after every code item:
- AI-firewall (F1/PS-AUDIT-014): `server/lib/websocket.test.ts` (8 tests) + `tests/test_invariants.py::test_f1_*` — **pass**.
- GCS-passive (F2): `tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls` — **pass**.

**Item 1 classifier ≠ AI clarification (required by the task):** `MicroDopplerClassifier` is deterministic DFT+autocorrelation DSP computed inside `processFrame()` — it is NOT the AI sidecar and is NOT routed through the advisory-only pathway. It enters the gate as deterministic evidence via a plain function parameter, entirely separate from the `advisoryIdentity`/`advisoryVitalSigns` channel, which remains exactly as before (verified by the still-green firewall tests above).

## 5. Everything still `[TO BE MEASURED]` / `[UNVERIFIED]`

1. **Post-Item-1 false-positive rate under fan/curtain/HVAC** — `[TO BE MEASURED]`. Tooling ready; requires a human hardware session per `docs/NEGATIVE_CONTROL_CHECKLIST.md`. The measured **pre-Item-1** baselines from real existing recordings: fan-off empty room 0.0% (465 ticks), fan-on 11.8% (1,455 ticks) and 31.2% (5,000 ticks) — real numbers, but they predate the fix and cannot show its effect.
2. **`DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX = 0.2`** — placeholder threshold; retune from the Item-2 session data.
3. **Calibrated spatial energy threshold** — `[TO BE MEASURED]`; default remains the historical 10 until a real empty-room `--spatial` calibration run (`docs/SPATIAL_CALIBRATION.md`).
4. **P0-S8 campaign results** — all stages still unexecuted; every stage table remains empty pending rig time.
5. **Whether Item 1's gate actually suppresses real-fan triggers** — plausible by construction (fan = periodic → high `mechanicalScore`), but `[UNVERIFIED]` on real hardware until #1 runs.
6. **Firmware respiratory-gate thresholds** (`EDGE_RESP_PERIOD_CV_MIN` etc.) — still synthetic-only calibrated per `PHANTOM_SCAN_REMEDIATION_REPORT.md`; unchanged by this session.

## 6. Open questions for Thaer

1. **REAL_TEST_REPORT.md's status is contradictory** — it is self-flagged "HISTORICAL (superseded)" yet is simultaneously the only P0-S8 campaign plan and the file both audits point at for missing evidence. Nothing replaced it (searched; `MEASUREMENT_PLAN.md` covers different ground). Decide: un-flag it as live, or create a successor campaign doc. I cross-linked S2 to the new checklist but did not un-flag it on your behalf.
2. **Item 7 premise changed:** `docs/research/csi-phase-in-wifi-sensing.md` was already committed and pushed to `main` earlier today (commit `920595d`, at your "push all new to github" instruction), so the task's "don't commit someone else's untracked scratch file" concern is moot — but confirm you're happy with it being permanent documentation, since ADR-058 now formally builds on it.
3. **PS-GAP-MUSIC-001:** the MUSIC single-snapshot defect means the AoA peak angle is input-independent in production. Given AoA is already display-texture-only on this hardware, is a proper fix (multi-snapshot covariance) worth scheduling at all, or should the AoA spectrum panel be considered purely cosmetic and documented as such?
4. **Hardware session sequencing** (carried over from the gap analysis, now sharper): the single highest-value session is now: run `docs/NEGATIVE_CONTROL_CHECKLIST.md` (measures Item 1's real effect) + the `--spatial` calibration (`docs/SPATIAL_CALIBRATION.md`) in the same sitting — roughly half a day total. P0-S8 is a separate, longer campaign.
5. **Root-level `*.jsonl` clutter:** pytest session-writer tests drop JSONL files into the repo root (four created by this session's test run were deleted; several from 2026-07-23 remain untracked). Worth a small fix to point the test writers at a temp/output dir — didn't touch it since it's outside the 8 items.
