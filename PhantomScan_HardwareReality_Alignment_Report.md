# Phantom Scan — Hardware-Reality Alignment Report (2026-08-08)

Ground truth checked against: **exactly 2 physical ESP32-S3 nodes, 1 Rx antenna each, fixed 3 m
baseline, N1=(-1.5,0)/N2=(+1.5,0), primary mode `fused_two_node`, single-node mode a degraded
fallback, no true spatial AoA physically possible — only 1-D on-axis position.**

This consolidates a full-repo pass: verifying two already-implemented-but-uncommitted fixes,
auditing code/docs/UI/reports for anything implying hardware that doesn't exist, and re-confirming
every previously-fixed item this thread has touched.

---

## Part 1 — The two confirmed open bugs

### 1a. False-positive ghost target — status: **fixed, verified, uncommitted**

This was already fully investigated and fixed in an uncommitted working-tree change
(`server/lib/websocket.ts`, `server/lib/websocket.test.ts`, documented in
`PhantomScan_GhostTarget_Fix.md`) before this session started. I verified the diff against the
report's claims line-by-line and re-ran everything fresh rather than trusting the prior write-up:

- **Root cause** (re-confirmed): single-node mode's presence gate used a *separate*, unvalidated
  legacy `MotionGate` (auto-calibrates a threshold from just the first ~2.4s of each session) —
  not the same `computeNodeMotionFromMatrix` / `DEFAULT_MOTION_THRESHOLD` metric the two-node
  fused gate already trusts. Confirmed real single-node empty-room sessions
  (`emty_room_test_2026-07-20T18-18`, `emty_2026-07-20T18-21`) showed 98-99% false-positive rates
  under the old mechanism.
- **Fix** (re-confirmed present, `websocket.ts:1485-1512`): new `singleNodeMotionDetected()` reuses
  the validated `nodeMotionFor()` + `fusedTargetMotionThreshold`, wired into the single-node
  presence-gate call site.
- **The prompt framed this as a "two-node fused mode" false positive.** The evidence doesn't
  support that framing: every genuine two-node fused empty-room negative control in
  `data/sessions/` (`empty_room_fan_off_20260720`: 0.0%, `emty_room_test_2026-07-23T12-06`: 17.2%,
  within known fan-baseline range) shows the fused gate behaving correctly. The one fused-mode
  session with a high false-positive rate (`live_hw_verify_20260720_v2`, 95.9%) is self-labeled as
  live hardware setup/testing, not a settled empty room, and its motion levels are 2x every other
  empty-room recording — not evidence of a fused-gate defect. **The real ghost target was in
  single-node fallback mode**, and that's what's fixed.
- **Before/after** (real recorded sessions, same metric before and after):

  | session | old (legacy MotionGate) | new (validated metric) |
  |---|---|---|
  | `emty_2026-07-20T18-21` | 98.2% | **0.0%** (0/839) |
  | `emty_room_test_2026-07-20T18-18` | 99.4% | **61.7%** (1464/2374) — see honest caveat below |

  Honest caveat carried over from the prior investigation: `emty_room_test_2026-07-20T18-18`'s own
  node2 baseline averages 0.631 — already above the 0.6 threshold using the *same* metric the
  fused gate trusts. The fix removes the separate under-calibrated mechanism but can't manufacture
  headroom that isn't in that particular day's recording. Two explanations remain open (early/
  pre-calibration noise that day, vs. a single active node's noise floor not matching a two-node
  calibration baseline) — flagged, not resolved, since it needs a fresh negative-control capture
  to distinguish.
- **True-positive regression check**: real moving-target-scale motion still trips the fixed gate
  (new test: `singleNodeMotionDetected: real moving-target-scale node motion still trips the gate
  (no over-correction)` — passes).
- **Fresh full-suite verification this session** (not reused from the prior write-up):
  ```
  npx tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts
  tests 223 / pass 223 / fail 0

  python -m pytest tests/ -q
  91 passed, 1 skipped, 7551 warnings in ~97-138s

  python -m pytest tests/test_invariants.py -v
  test_dual_node_equal_balance_midpoint PASSED
  test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
  test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
  test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
  test_runtime_scope_guard_has_no_flight_control_imports PASSED
  5 passed

  npx tsc --noEmit -p .
  (clean, no errors)
  ```
- **Status: this fix is still UNCOMMITTED.** It matches everything the report claims and is fully
  verified, but it's sitting as a working-tree change alongside this session's new fixes. Nothing
  in this session committed it — that's a decision for you (see final checklist).

### 1b. Presence-gate threshold recalibration tooling — status: **confirmed in good order, no changes needed**

`scripts/calibrate-threshold.ts` already samples `max(motion1, motion2)` via
`computeNodeMotionFromMatrix` — **the exact same metric** 1a's fix wired into the single-node gate.
The script needed no update: it was already measuring the right thing; the fix just made the
single-node code path start trusting the same measurement the fused path (and this script) already
target.

- **Why it can't be dry-run without hardware**: it binds directly to live UDP `:5005`
  (`sock.bind(PORT, "0.0.0.0", ...)`) and has no file-replay/offline input path — by design, it's a
  live negative-control soak tool, not a CSV analyzer.
- **The original 1b problem (0.6 threshold sitting close to real signal / noise ceiling) is still
  open** — this pass only confirmed the tooling is correct and doesn't need updating for 1a; it
  did not and could not perform an actual recalibration (needs your hardware time).

**Ready-to-run instructions for Thaer:**
```
# 1. Stop the dashboard (dev server) — it owns UDP :5005, only one process can bind it.
# 2. Empty room, nobody moving, run for 2 minutes:
npx tsx scripts/calibrate-threshold.ts --seconds 120
# 3. Note the "suggested PHANTOM_MOTION_THRESHOLD: mean+3s=... mean+4s=... mean+5s=..." line.
# 4. Fan on-axis (or other worst-case non-human motion source), same room, same duration:
npx tsx scripts/calibrate-threshold.ts --seconds 120
# 5. Pick the smallest k (3/4/5) from step 2 whose empty-room threshold is still ABOVE the
#    fan run's observed max — that's your new PHANTOM_MOTION_THRESHOLD.
```
Run this **after** restarting the dev server with 1a's fix live (see final checklist) — not
before. The single-node gate now measures motion the same way the fused gate and this script
already do, so calibrating before the restart would validate the old, already-superseded
mechanism's assumptions rather than the one actually running.

---

## Part 2/3 — Mismatch audit (code, docs, UI, reports)

Two parallel audits (codebase; docs/UI/reports) ran against everything **not already fixed** by
commit `960f678` (which relabeled `aoa-spectrum.tsx`, `metrics-panel.tsx`, fixed README sampling
rate, added ADR-058/negative-control tooling). Findings below, grouped by disposition.

### Fixed this session (real mismatches, now corrected)

| # | File | Issue | Fix |
|---|---|---|---|
| 1 | `client/src/components/dashboard/RadialScene.tsx:481` | Procedural human-body wireframe (`HumanMesh`) rendered on every human-classified target, bypassing `canPresentVolumetricTarget` (hardcoded `false`, docstring: "the system cannot honestly claim body shape from CSI") — the AI poseFrame skeleton was correctly gated in `dashboard.tsx`, but the procedural fallback body wasn't. **Highest-severity finding.** | `canRenderConfidentHuman` now hardcoded `false`, mirroring the existing mechanical-overlay pattern in the same file. |
| 2 | `client/src/components/dashboard/distance-meter.tsx` | "Bearing" compass readout (N/NE/E/…) bypassed `getLivePositionCaveat` entirely; in fused mode the value is architecturally E/W-only (z always 0) but presented as an ordinary bearing. | Added `presentationCaveat` prop (wired from `dashboard.tsx`'s existing `livePositionCaveat`), relabeled to "Axis Side" in fused mode, added the same amber caveat block `TargetIdentityCard` already uses. |
| 3 | `client/src/pages/report.tsx:368-426` | Exported Session Report's "Movement Bounding Box" shows independent X/Z ranges with zero caveat that Z is architecturally 0 in fused mode. | Added an explicit "NOT A ROOM POSITION" caveat paragraph under the bounding-box grid. |
| 4 | `scripts/reporting/session_reporter.py:471-482` | Same issue in the **live-wired PDF export** (`websocket.ts:618-624` spawns this on every `stopRecording()`, served via `/api/recording/download?format=pdf`) — the artifact a stakeholder like JODDB would actually read. | Added the same caveat line to the PDF's "SPATIAL METRICS" section. |
| 5 | `client/src/components/dashboard/control-panel.tsx:190-241` | Live operator-facing "ISAR/MUSIC" settings panel still labeled controls "Array Length" / "AoA Range (degrees)" and said MUSIC uses time samples "as a spatial antenna array" — the exact framing the dashboard panel itself was fixed away from. | Relabeled to "Window Length (samples)" / "Signature Range (display only)"; rewrote explanatory copy to match `aoa-spectrum.tsx`'s honesty-note tone. |
| 6 | `README.md:276` | Doc-surface table still said "AoA heatmap & spectrum \| Angle-of-arrival energy per node" after the components it describes were relabeled. | Updated to "Signal Signature heatmap & spectrum \| Temporal MUSIC signature per node (not spatial angle)". |
| 7 | `docs/research/csi-phase-in-wifi-sensing.md:64` | README-linked "current/binding" doc describes a genuine multi-antenna spatial MUSIC pipeline, contradicting the live single-antenna-per-node code. | Added a caveat blockquote after the mechanism table, pointing to the live honesty note and relabeled panel. |
| 8 | `server/lib/udp-server.ts:672` | Live comment framed a 2nd-antenna packet as plausible "future proofing" rather than physically excluded. | Reworded to state this hardware has exactly 1 antenna per node and the branch is defensive-only/unreachable. |
| 9 | `firmware/esp32-csi-node/main/csi_collector.h:22` | Buffer-size comment said "4 antennas" for what's actually a defensive oversized allocation. | Comment reworded; buffer size (correctly conservative) left unchanged. |
| 10 | `shared/schema.ts:56-70, 91-97` | `aoaSpectrumPointSchema`/`isarFrameSchema`/`heatmapDataSchema.angles` names still say "AoA"/"angle" with no comment explaining the post-fix reality. Field/type names were **deliberately not renamed** (wire-protocol risk, cosmetic-only benefit) — honesty comments added instead. | Added honesty comments above each schema pointing to the live honesty note. |
| 11 | `scripts/build_academic_reports.py:828, 954` | Internally inconsistent with the file's own honesty caveats elsewhere — used stale "AoA" panel naming. | Reworded to "Signal Signature (temporal MUSIC)" naming, consistent with the rest of the doc. |
| 12 | `scripts/build_how_project_detact_the_humen.py` §4.3 | Exported project doc (`.docx`) made an uncaveated true-spatial-AoA claim, reproducing exactly the false-precision pattern fixed in the live UI. Predates 960f678, never revisited. | Added a caveat paragraph after the existing claim. |
| 13 | `scripts/csi_filter_pipeline.py:331-355, 1010-1015` | Self-described "OFFLINE/REFERENCE — full-fidelity" tool (confirmed unreferenced by any live path) still computes and uses a MUSIC peak as a literal bearing with no caveat, unlike the TS equivalent it claims parity with. | Added HONESTY NOTE block + inline comment at the `theta = radians(peakAngle)` line. Math unchanged. |
| 14 | `docs/adr/ADR-012-esp32-csi-sensor-mesh.md` | N-node mesh ADR, "Accepted — Partially Implemented," no supersession note (unlike ADR-048/058 which got one). | Added a "Status Update (2026-08-08): Two-Node Reality" section mirroring ADR-048's format, pointing to `shared/schema.ts` as ground truth. |
| 15 | `generated_reports/Section-5.5-UI-Design-Dashboard-Components.md`, `generated_reports/PHANTOM_SCAN_DATA_PROCESSING_REPORT.md` | Stale pre-fix (2026-07-14) generated snapshots describing AoA panels with the old framing. Not regenerated (out of scope — requires running the full report pipeline). | Added a "STALE SNAPSHOT" banner to each pointing at current sources. |

All 15 fixes are documentation/comment/label wording only — **no runtime logic, wire-protocol
field names, or data schemas changed.** Re-verified after all 15 landed:
```
npx tsx --test ...        223 pass, 0 fail
python -m pytest tests/test_invariants.py -v   5 passed
npx tsc --noEmit -p .     clean
```

### Confirmed correctly-labeled historical/Phase-2 content — no action needed

- `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md`, `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`, `docs/WIFI_DENSEPOSE_INTEGRATION.md`, `docs/system_architecture_methodology.md` — all carry explicit "HISTORICAL (superseded)" banners pointing at README/RUN.md as current source. Correctly archived.
- `docs/adr/README.md` and the broader 44-ADR catalog (ADR-027 MERIDIAN, ADR-028, etc.) — README already frames these as "a broader, more ambitious... vision than the two-node system actually shipped." Fine as-is.
- `docs/ruview-2node-full-analysis-report.md` — explicitly archived per README.
- `docs/research/00-rf-topological-sensing-index.md` and its research compendium — framed as forward-looking SOTA research, not a description of the shipped system; not referenced from README's current doc index. Low-confidence pass; flagged for you to consider a "HISTORICAL/RESEARCH" banner for consistency with its siblings, but not treated as a defect.
- `server/lib/signal-processing.ts:990-1040` (`DemoDataGenerator`) — loose "antenna" wording, but explicitly a demo-data generator for testing, not live-labeled.
- `scripts/ai_inference.py:657-687` (`run_synthetic_feed`) — explicitly synthetic-only fallback, comments say so.
- `tests/network_link_validation.py:778-789` — "Simulate UAV flight interference" is a generic RSSI-fluctuation stress-test label, not a claim about node mounting.
- `README.md:19`, `CURRENT_STATE.md:75` — correctly disclaim UAV/drone/flight-control scope.
- `tests/test_invariants.py:48-59` (`test_runtime_scope_guard_has_no_flight_control_imports`) — confirmed as real enforcement (not just a comment): fails the build if `mavlink|uav|drone|gps|imu|psc` leaks into the runtime/API/ingest modules or `server/index.ts`.

### F1 invariant (AI advisory-only) — re-confirmed against current code, not just trusted

Read `server/lib/websocket.ts:351-395` directly:
- `registerAIClient` only sets `client.isAI = true`.
- AI-submitted `targetIdentity`/`vitalSigns` broadcast **only** on distinct `advisoryIdentity`/
  `advisoryVitalSigns` channels — never written to the authoritative `currentTargetIdentity`/
  `currentVitalSigns`, which remain exclusively written by the deterministic classifier inside
  `processFrame()`. Non-AI clients sending these are rejected and logged (`PS-AUDIT-014`).
- `scripts/ai_inference.py:441-450` confirmed to never emit the substring `"aoa"` and to keep
  `label: "unknown"` for its own output, with opinions only as `advisoryLabel`.
- **No AoA/authoritative-identity leak found through the AI channel. F1 holds in current code.**

### Geometry — verified, no drift

`shared/schema.ts:284-290` remains the single source of truth (`NODE_ANCHORS = {1: {x:-1.5,z:0},
2: {x:1.5,z:0}}`, `NODE_SEPARATION_M = 3`); every consumer checked (`recording-export.ts`,
`websocket.ts`, `RadialScene.tsx`, `build_academic_reports.py`, `shared/bearing.ts`) imports these
constants directly — no independent hardcoded baseline literal found anywhere else.

### Node count — verified, no drift

No node-count selector, `nodeId===3`-style logic, or >2-node live capability found anywhere in
`client/`, `server/`, or `shared/`. `RadialScene.tsx`'s node-color map only defines colors for
node IDs 1 and 2; its "≥2 nodes" loop guards are generic defensive checks, not a claim of >2 live
nodes.

---

## Part 4 — Previously-fixed items, re-confirmed intact

| Item | Status |
|---|---|
| `scripts/node_health_diagnostic.py` | **Present**, file exists at expected path. |
| WebSocket handler-leak fix | **Present** — `client/src/hooks/use-websocket.ts:538-549` explicitly detaches `onopen/onmessage/onclose/onerror` before `close()` on unmount, with a comment explaining the zombie-reconnect leak this prevents (a late-firing `onclose` on a dead socket would otherwise schedule a new reconnect with no owner to clean it up). |
| Target-state stale-forever fix | **Present** — `server/lib/target-state.ts` still has the intact hold/stale/clear lifecycle (`LIVE_TARGET_STALE_TIMEOUT_MS` at 1.5s, full clear at 5s, `LiveHoldState` = startup/live/stale_hold/cleared), plus the client-side defense-in-depth watchdog in `use-websocket.ts:520-532`. |
| **Dev-server restart status: UNKNOWN — I cannot verify this from the sandbox.** This was flagged unconfirmed in an earlier session and remains unconfirmed. **Thaer: please confirm whether your dev server has been restarted since the target-state fix landed, and again after committing 1a's fix in this session — server-side TS changes do not hot-reload.** |
| ADR-048 reconciliation | **Intact** — Status line: "Accepted (original decision) — §2 classifier superseded, see update below"; "Status Update (2026-08-06): Adaptive Classifier Superseded" section present. |
| ADR-058 (firmware SFO/PDD out of scope) | **Present** at `docs/adr/ADR-058-firmware-sfo-pdd-out-of-scope.md`. |
| `.gitignore` JSONL root-clutter rule | **Intact** — `/*.jsonl` rule present (lines 36-42); confirmed zero untracked root-level `.jsonl` files in current `git status`. |

---

## What Thaer needs to do on real hardware next (priority order)

1. **Review and commit (or ask for changes to) the uncommitted diff** in `server/lib/websocket.ts`
   / `server/lib/websocket.test.ts` (1a's ghost-target fix) plus this session's 17 documentation/
   UI fixes (RadialScene.tsx, distance-meter.tsx, dashboard.tsx, report.tsx,
   session_reporter.py, control-panel.tsx, README.md, and the smaller doc/comment fixes listed
   above) — nothing was committed automatically.
2. **Restart the dev server** after committing, so the server-side single-node presence-gate fix
   (1a) and the target-state fix actually take effect live — confirm this explicitly, since it's
   been an open question across sessions.
3. **Verify live**: with the room genuinely empty for >5s in single-node mode (e.g. only one node
   powered/reporting), confirm no ghost target appears — this is the first real-hardware test of
   1a's fix; nothing here was validated on live hardware, only against recorded sessions.
4. **Run `calibrate-threshold.ts`** per the Part 1b instructions above (empty room, then fan
   on-axis, 120s each) to get a real recalibrated `PHANTOM_MOTION_THRESHOLD` — the original 1b
   problem (0.6 sitting close to both the noise ceiling and real signal) is still open and needs
   your hardware time.
5. **Re-test the two-node fused mode** with a real moving target to confirm true-positive detection
   wasn't affected by any of this session's changes (none of them touch fused-mode gating logic,
   but a live confirmation costs little and closes the loop).
6. **Re-run `node_health_diagnostic.py`** if you've made any physical changes to node placement/
   hardware since the last diagnostic run.
7. Optional, low-priority: consider a "HISTORICAL/RESEARCH" banner on
   `docs/research/00-rf-topological-sensing-index.md` for consistency with its sibling docs
   (flagged, not a defect); consider regenerating the two stale `generated_reports/*.md` snapshots
   via their source scripts once you've reviewed this session's script-level fixes.

This supersedes any scattered next-steps lists from individual prior session reports.
