# Phantom Scan Fix-All Round + RuView 4-Node Citation Audit — Session Report

Branch: `feat/two-node-radar-live-detection`. Ground truth unchanged: 2 physical ESP32-S3 nodes,
1 Rx antenna each, fixed 3m baseline, `fused_two_node` primary mode. No safety-relevant
calibration constant was touched. No `[MEASURED]` accuracy figure was fabricated. No RuView-style
multistatic/multi-node fusion code was implemented.

## Task 0 — Current-state audit

| Item | Prior claimed status | Current confirmed status | Action needed this session |
|---|---|---|---|
| 1. Repo clean, prior fixes committed not stray | Done | Confirmed clean — all 6 "already done" items below are genuinely committed, not sitting uncommitted (the main risk this task was designed to catch never materialized). One irrelevant untracked embedded-repo dir under `ai model and densepose/model` — unrelated to any claim. | None |
| 2. ACF/periodicity classifier wired into single-node presence gate | Done | Confirmed — `server/lib/websocket.ts:1135`, `server/lib/node-fusion.ts:599-611`. Classifier can only suppress, never assert, on top of the energy gate. | None |
| 3. Single-node ghost-target fix (legacy `MotionGate` vs. `computeNodeMotionFromMatrix`) | Done | Confirmed — `websocket.ts:1547-1574,1604`. Legacy `MotionGate` is demoted to display-only, not removed; `computeNodeMotionFromMatrix` drives the gate. | None |
| 4. PS-GAP-TRK-001 (cold-start coasting ghost target) | Done | Confirmed — `server/lib/tracking.ts:422-427`. | None |
| 5. PS-GAP-MUSIC-001 (eigen-deflation collapse) + "Signal Signature" relabel | Done | Confirmed — `signal-processing.ts:71-185`; panel relabeled in `aoa-spectrum.tsx`. | None |
| 6. README sampling-rate discrepancy | Done | Confirmed — `README.md:192` matches firmware `CSI_MIN_SEND_INTERVAL_US` (50 Hz cap). | None |
| 7. Firmware SFO/PDD deferred via ADR-058 | Done | Confirmed — `docs/adr/ADR-058-firmware-sfo-pdd-out-of-scope.md`, Accepted, cites `docs/research/csi-phase-in-wifi-sensing.md` correctly. | None |
| 8. ADR-048 reconciled with Superseded section | Done | Confirmed — `docs/adr/ADR-048-adaptive-csi-classifier.md:1-63`. | None |
| 9. `docs/research/csi-phase-in-wifi-sensing.md` committed | Done | Confirmed, added in `920595d`, present on both this branch and `main`. | None |
| 10. 12 legacy `.jsonl` files removed/gitignored | Partially done | **Gap found**: `.gitignore` had the rule (`/*.jsonl`, added in `960f678`) but the 12 already-tracked files were never `git rm --cached`'d — gitignore doesn't retroactively untrack. Root-cause fix (session-writer tests now use pytest's `tmp_path` instead of writing to the repo root) was real and already committed. | **Fixed this session** — see Task 1c. |
| 11. AoA honesty caveat: permanent banner + hidden peak marker | Partially done | Banner was already permanent. Peak marker was de-emphasized (muted diamond, clarifying hover text) but still rendered on the plot — not actually hidden. | **Fixed this session** — see Task 1a. |
| 12. `REAL_TEST_REPORT.md` HISTORICAL flag | Done | Confirmed present at line 1. | None (Task 1b — decision needed, see below) |

## Task 1 — Documentation decisions

**1a. AoASpectrum honesty caveat — Status: Done.**
Removed the peak-marker Plotly trace entirely from `client/src/components/dashboard/aoa-spectrum.tsx`
(previously a muted `diamond-open` marker at the spectrum peak) — the curve alone now renders,
with the permanent `TEMPORAL SIGNATURE — NOT SPATIAL ANGLE` banner unchanged. Checked
`client/src/pages/report.tsx` (no AoA/MUSIC export exists there — nothing to fix there) and
`scripts/build_academic_reports.py` (already uses "Signal Signature (temporal MUSIC)" naming and
an explicit single-antenna/no-live-AoA caveat at lines 954/1445 — no fix needed). No other
exporter or offline script surfaces this panel.

*Regression-history note:* this panel has caused two real prior regressions (PS-GAP-MUSIC-001,
and an earlier target-visibility bug from relabeling this same panel). No test anywhere asserts
the peak marker's presence or absence, and this project has **no React component test
infrastructure at all** — the `npm test` runner (`tsx --test`) only covers `.ts` logic files
(`server/lib`, `client/src/lib`, `tests/behavioral`, `scripts/accuracy/__tests__`); there is no
`jsdom`, `@testing-library/react`, or any `.tsx`-capable test harness in `package.json`. Standing
up a full component-test harness to guard one marker-removal was judged out of scope for this
session (disproportionate infra addition for one assertion) — flagging this explicitly rather than
silently skipping it, per the plan's own contingency. If this panel regresses a third time, that's
the point to invest in component-test infrastructure, not before.

**1b. `REAL_TEST_REPORT.md` — Status: Needs Thaer's decision.**
Still HISTORICAL-flagged (confirmed, line 1). Not touched this session. Two options, unchanged
from the prior session's framing:
- **Option A — unflag in place:** remove the HISTORICAL banner and treat the document as the
  live, current test report again. Simple, but only correct if its contents (session dates,
  claimed state) are still accurate — worth a quick skim before choosing this.
- **Option B — create a successor doc:** leave `REAL_TEST_REPORT.md` HISTORICAL as an archival
  snapshot, and start a new report (e.g. `REAL_TEST_REPORT_2026.md` or similar) for ongoing S1-S8
  campaign results. Cleaner separation between the old point-in-time record and the still-empty
  S1-S8 campaign tables, at the cost of one more file in the report-naming convention.

**1c. Legacy `.jsonl` files — Status: Done.**
`git rm`'d all 12 tracked files at repo root (confirmed stale — no script, test, or doc
references them). Sequenced after Task 3's smoke tests, and confirmed no overlap regardless: the
12 files are hash-named CSI-frame dumps at repo root, while Task 3's tooling reads `.csv`
recordings from the separate `recordings/` directory.

## Task 2 — Area 5 (DBSCAN/Kalman) fallback-path determination — Status: Done (audit only)

**Determination: confirmed executing every tick in both modes; live and consequential only in
single-node fallback mode; inert-by-discard in the primary `fused_two_node` pipeline.**

- `DBSCAN`/`KalmanFilter`/`TrackingProcessor` (`server/lib/tracking.ts:68,160,332`) run every
  frame in both modes — the single call site (`websocket.ts:929`) is gated only on
  `isarEnabled`, not on `node_mode`, and is fed a real point cloud built from the live AoA
  spectrum regardless of mode.
- In `fused_two_node`: whenever `computeFusedTarget()` returns non-null, its output
  unconditionally overwrites the Kalman/fallback-derived position/velocity
  (`websocket.ts:1012-1058`); when it returns null, the hold/clear branch runs and nothing from
  the tracker broadcasts to `radialTarget` at all.
- In `single_node` fallback: the same tracker output directly drives the broadcast `radialTarget`
  and the ADR-057 presence gate — the only mode where it's consequential.

**Follow-up finding surfaced during review of this determination:** the `TrackingProcessor`'s
Kalman state is **not reset on a fused↔single_node mode flip**. A mode-flip detector already
exists (`websocket.ts:970-974`, `prevNodeModeForFallback`/`invalidateFallbackVelocity()`), but it
only invalidates the separate non-Kalman fallback-velocity sample — it never calls
`this.trackingProcessor.reset()`. That reset is only wired to `startProcessing()` and
`setDataSource()`, neither of which fires on a mid-session node-count change. So if a node drops
mid-session and the system falls back from `fused_two_node` to `single_node`, the Kalman filter
hands off whatever position/velocity/covariance state it silently accumulated while its output was
being discarded — a warm-but-untested prior at exactly the moment the system needs to degrade
gracefully. Confirmed via search that no test in `server/lib/websocket.test.ts` exercises a
`fused_two_node ↔ single_node` transition at all.

No refactor was made this session, per the prompt's explicit instruction. Both findings —
the discard behavior and the untested warm-handoff — are flagged as candidates for a future
session: either add a `trackingProcessor.reset()` call on mode flip, or add a regression test
proving the handoff is safe before deciding whether a reset is even necessary.

## Task 3 — S1-S8 positional-fidelity campaign readiness — Status: Done (tooling verified, all trials blocked on hardware)

| Stage | Tooling | Readiness |
|---|---|---|
| S1 (empty-room calibration) | `scripts/calibrate-threshold.ts` | **Ready — smoke-tested this session** |
| S2 (negative controls) | `docs/NEGATIVE_CONTROL_CHECKLIST.md` + `scripts/analyze_negative_control.py` | Ready — checklist itself confirms no post-fix session has been run yet |
| S3-S7 (dwell/walk/trend/off-axis/mirror) | `scripts/join-groundtruth.ts` + `scripts/accuracy/run-accuracy-trial.ts` | **Ready — smoke-tested this session** |
| S8 (robustness/confounds) | No dedicated script — manual observation columns only | Blocked on a real tooling gap: no automated dropout/fallback/multi-person harness exists |

**Smoke tests actually run this session (tooling validation only — no trial, no accuracy claim):**
- `run-accuracy-trial.ts` (exercising `join-groundtruth.ts`'s shared CSV-parsing code path):
  ran in replay mode against a hand-fabricated minimal `system_state.csv` + `groundtruth.csv`
  pair (schema verified against `scripts/accuracy/system-state-adapter.ts` and
  `ground-truth-adapter.ts`), both files written to the session scratchpad, never the repo. Exit
  0: `[run-accuracy-trial] wrote report to <scratchpad>\report (preconditions PASS)`.
- `calibrate-threshold.ts`: ran on a scratch UDP port (`UDP_PORT=15006`, not the live dashboard's
  :5005) against `synth-csi-udp.py` emitting for both node IDs. First two attempts failed with
  "No samples collected" — traced to the sandboxed Bash tool launching each background process in
  its own isolated environment without a shared loopback network path, **not a defect in the
  script**. Running receiver and both senders as jobs within one shared shell fixed it
  immediately: `33 samples over 8s`, `max(motion1,motion2): mean=0.0588 sigma=0.0007
  max=0.0597`, `suggested PHANTOM_MOTION_THRESHOLD: mean+3s=0.0608 mean+4s=0.0615 mean+5s=0.0622`
  — clean exit 0. (These numbers are synthetic-emitter noise, not a real-room calibration result;
  not usable for anything beyond confirming the script runs.)

All hardware-trial rows (the actual S1-S8 field data) remain blocked purely on hardware rig time —
no tooling gap blocks any stage except S8's missing automated confound harness.

## Task 4 — Threshold recalibration / negative-control readiness — Status: Done (audit only)

- `scripts/calibrate-threshold.ts` re-confirmed complete and correct: samples
  `max(motion1, motion2)` via `computeNodeMotionFromMatrix`, imports resolve, and (per Task 3) it
  runs cleanly end-to-end.
- `DEFAULT_MOTION_THRESHOLD` = 0.6 (`node-fusion.ts:43-45`) — **not touched**.
- `docs/NEGATIVE_CONTROL_CHECKLIST.md` present and complete, but its own status section confirms
  it has not been re-run against the current (post-fix) build.
- **61.7% false-positive figure (`emty_room_test_2026-07-20T18-18`):** per the prompt's explicit
  instruction, no guess is made between the two competing explanations. This still requires a
  fresh live empty-room + fan-on-axis soak, run separately for single-node and two-node
  configurations, using the existing tooling — that is the concrete next physical step to close
  this item.
- **"Node 2 structurally near-inert" flag:** already durably tracked and **already retracted** in
  `PhantomScan_Node2_Diagnostic_Report.md:89-98` — no new tracking doc was needed. The evidence
  backing that retraction is the stronger claim, not just "falls within statistical variance": a
  same-day before/after pair (a low-ratio session at 17:27 vs. a follow-up session at 17:36,
  "presumably the same physical setup," recovering to a normal 78.8% ratio nine minutes later
  with no rig touched in between) plus near-symmetric negative-control resting behavior
  (empty-room/fan sessions, 74-93% ratio) — positive evidence node 2 contributes normally in the
  general case, not merely that the one low-ratio session was statistically unremarkable.

## Task 5 — RuView citation audit — Status: Done

**Provenance check (before editing anything):** four of the seven target files
(`04-transformer-architectures-graph-sensing.md`, `08-temporal-graph-evolution-ruvector.md`,
`09-resolution-spatial-granularity.md`, `13-nv-diamond-neural-magnetometry.md`) were verified to
be Phantom-Scan-authored content, not vendored copies of RuView's own docs, despite one
(NV-diamond quantum sensing) having no obvious relationship to WiFi CSI on its face:
- `git ls-files` confirms all four are tracked at `docs/research/...` in the main repo, with no
  nested `.git`/`.gitmodules` anywhere under `docs` — not inside the unrelated untracked
  embedded-repo dir noted in Task 0 item 1.
- Each opens with its own front-matter identifying it as part of this project's own 22-document
  "RF Topological Sensing Series" research survey, e.g. `13-nv-diamond-neural-magnetometry.md:1-8`
  ("SOTA Research Document — RF Topological Sensing Series (13/22)... Status: Research Survey").
- All four were added in the same commit (`2848391`, 2026-06-28, Thaer Bayyari) as the rest of
  this project's own research corpus, not a separate vendor-sync commit.

Also verified `PhantomScan_4Node_Fusion_Report.md`'s "already skeptical, no fix needed" call with
an actual quote rather than a name check — `PhantomScan_4Node_Fusion_Report.md:73` already states
that RuView's own 4-node implementation, read for reference, turned out to be "the same 2-node
limitation under a 4-node label," confirming that document actively deflates RuView's 4-node
claim rather than repeating it.

**Caveat added** (documentation-only, no implementation code touched) at every location where
RuView's N-node/multistatic capability was cited without qualification — each note states: (a)
ADR-029/ADR-031 are `Proposed`, not `Accepted`, with no attached Results & Proof table unlike
RuView's validated 82.3%/82.69% figures; (b) architecturally inapplicable to Phantom Scan's
2-node, single-antenna hardware regardless of status; (c) Phantom Scan's own multi-node roadmap
is materially simpler multilateration-based 2D localization, not multistatic Doppler/pose fusion
(`JODDB_PHASE2_TECHNICAL_PROPOSAL.md` §4.4); (d) cites Phantom Scan's own "dilution effect"
finding (`PhantomScan_Research_Gap_Analysis.md` §5) as the evidence basis:

- `docs/research/ruview-multistatic-fidelity-sota-2026.md` — two notes added (N×(N-1) claim; the
  "(target)" table whose summary sentence had dropped the hedge — reworded to "*targets*" with an
  explicit projection caveat)
- `docs/research/04-transformer-architectures-graph-sensing.md` — two notes added (top context
  line; closing ADR-support note)
- `docs/research/09-resolution-spatial-granularity.md` — one note added
- `docs/research/08-temporal-graph-evolution-ruvector.md` — two notes added
- `docs/research/13-nv-diamond-neural-magnetometry.md` — one note added
- `docs/adr/ADR-032-multistatic-mesh-security-hardening.md` — one note added at the top (this ADR
  hardens a mesh that is itself unbuilt/`Proposed`)
- `docs/adr/ADR-033-crv-signal-line-sensing-integration.md` — one note added after the
  relationship table (inline table edits would have broken formatting)

No fix needed in `PhantomScan_4Node_Fusion_Report.md`, `README.md:356-357`, the two
`docs/CNN-LSTM...`/`compass_artifact...` files, `PhantomScan_Research_Gap_Analysis.md`, or
`JODDB_PHASE2_TECHNICAL_PROPOSAL.md` §4.4/roadmap — verified these are already skeptical, already
cite the dilution-effect finding, or already use "multilateration" rather than RuView's
multistatic terminology. `git diff` on all seven edited files confirms only caveat/hedging text
was added — no existing claim or number was removed.

## Task 6 — Full regression pass — Status: Done, all green

**TypeScript test suite (`npm test`):**
```
ℹ tests 243
ℹ suites 0
ℹ pass 243
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 11241.3038
```

**Python test suite (`npm run test:py`):**
```
.s..............................sssss................................... [ 78%]
....................                                                     [100%]
86 passed, 6 skipped, 7551 warnings in 79.08s (0:01:19)
```
(Warnings are pre-existing `pywt` boundary-effect UserWarnings from wavelet decomposition level,
unrelated to this session's changes.)

**F1/F2 invariant tests, explicit run (`pytest tests/test_invariants.py -v`):**
```
tests/test_invariants.py::test_dual_node_equal_balance_midpoint PASSED   [ 20%]
tests/test_invariants.py::test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED [ 40%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 60%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [ 80%]
tests/test_invariants.py::test_runtime_scope_guard_has_no_flight_control_imports PASSED [100%]
5 passed in 0.22s
```
The AI-firewall (`server/lib/websocket.test.ts`) tests are included in the full TS run above,
e.g. `AI client's targetIdentity is relayed as advisoryIdentity and never writes
currentTargetIdentity`, `non-AI client's targetIdentity produces no state change and no
broadcast` — all passed.

**`npx tsc --noEmit -p .`:** clean, no output.

**JSONL-clutter regression check:** ran `tests/test_phantom_cross_node_correlation.py` twice —
`3 passed` both times — and confirmed via `git status --porcelain -- "*.jsonl"` that only the 12
intentional `D` (staged deletion) entries from Task 1c appear; zero new `.jsonl` files landed in
the repo root.

**Full `git status --porcelain`:** exactly the expected diff — 12 `.jsonl` deletions, the
`aoa-spectrum.tsx` peak-marker removal, and the 7 RuView-caveat doc edits — plus the pre-existing
`ai model and densepose/model` embedded-repo dirty state and three untracked
`PhantomScan_*.md` files that predate this session, both unrelated to this work.

## Decisions needed from Thaer

1. **`REAL_TEST_REPORT.md` (Task 1b):** unflag it in place, or start a successor doc for the
   still-empty S1-S8 campaign tables? See the two options above — either is a one-message
   decision from here.

Everything else in this session either closed by default-safe action (Task 1a, 1c, Task 5's
caveats) or is a pure audit/report deliverable requiring no decision (Tasks 0, 2, 3, 4).
