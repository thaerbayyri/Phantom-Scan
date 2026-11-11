# Phantom Scan Remediation Report

Date: July 19, 2026 (WP-12 through WP-16 added July 20, 2026)
Source audit: `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
Runtime authority: Node/TS server per `docs/adr/ADR-051-runtime-authority.md`

## Scope

This report summarizes the remediation work present in the current working tree as of
July 20, 2026. It covers the secret-removal work already landed in the firmware tree, the
runtime-authority decision already recorded in ADR-051, the WebSocket F1 presentation fix
already present in `server/lib/websocket.ts`, the additional code and documentation
changes completed on July 19, 2026, and a further close-out pass (WP-12 through WP-16,
July 20, 2026) covering the dashboard AI advisory surface, the stale RuView analysis
report, Python cross-node-correlation test coverage, the fusion display/authoritative
balance split, and a tonal-aliasing mitigation for the firmware respiratory gate.

Verification for the July 19, 2026 portion of this report:

- `npm test` -> `112 pass, 0 fail`
- `C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests -q`
  -> `83 passed, 1 skipped in 52.84s`

Verification for the WP-12 through WP-16 portion (July 20, 2026) is recorded at the end
of this report, in "WP-12 through WP-16 Verification Results".

## Findings Summary

| Finding | Status | Notes |
|---|---|---|
| `PS-AUDIT-001` | DECISION / FIXED | Node/TS live authority recorded in ADR-051 and README. |
| `PS-AUDIT-002` | FIXED (WP-16 follow-up) | Firmware sovereign respiratory gate present; WP-16 adds a tonal-aliasing mitigation for the previously-open follow-up. |
| `PS-AUDIT-003` | FIXED (WP-15, additive) | Canonical linear `balanceLinear` added alongside the unchanged display `balance`; live display math itself not changed (see ADR-054). |
| `PS-AUDIT-004` | FIXED | Legacy 20-byte CSI retired from live path; compat-only gate added. |
| `PS-AUDIT-005` | FIXED | Canonical hardware-ID mapping layer added at authority ingest. |
| `PS-AUDIT-006` | FIXED | Python reference geometry/sample-rate corrected. |
| `PS-AUDIT-007` | FIXED | Live authority now rejects replay/out-of-order packets. |
| `PS-AUDIT-008` | FIXED | Retired Python live bind now fail-closed; `SO_REUSEADDR` removed. |
| `PS-AUDIT-009` | FIXED | Stale 20-byte / draft protocol text labeled superseded in deliverable. |
| `PS-AUDIT-010` | FIXED (WP-13) | `docs/ruview-2node-full-analysis-report.md` collapsed to a short archived-note stub; stale coordinates/bridge-as-live narrative removed from the body. |
| `PS-AUDIT-011` | FIXED (WP-15) | README fusion section corrected to describe the actual contrast+bias transform and 1500ms window; `balanceLinear`/ADR-054 document the display-vs-authoritative split. |
| `PS-AUDIT-012` | FIXED | Credential placeholders + gitignore/provisioning already present. |
| `PS-AUDIT-013` | FIXED | Static source pinning support added to live authority. |
| `PS-AUDIT-014` | FIXED (WP-12 closes carry-forward) | Non-AI verdict-adjacent WS writes blocked; advisory channel split already present. WP-12 closes `PS-REMED-WP3-FOLLOWUP-01`: dashboard now renders `advisoryIdentity`/`advisoryVitalSigns`. |
| `PS-AUDIT-015` | FIXED | First-operator bootstrap restricted to loopback or token. |
| `PS-AUDIT-016` | FIXED (confirmed + WP-14 regression test) | Python fused reference uses motion histories/metrics instead of stale path; WP-14 adds a regression test locking this in (was already fixed in code, only test coverage was missing). |
| `PS-AUDIT-017` | FIXED | Unmeasured “validated” claims downgraded to targets in main deliverable/model README. |
| `PS-AUDIT-018` | FIXED | Root reports updated to centered 3 m baseline. |

## Work Completed

### WP-0 — Secret Rotation (`PS-AUDIT-012`)

Status: FIXED

Already present in repo state before this run:

- `firmware/esp32-csi-node/sdkconfig.defaults` uses `REPLACE_ME` placeholders.
- `firmware/esp32-csi-node/.gitignore` excludes `sdkconfig`, `sdkconfig.old`,
  and `nvs_node*.bin`.
- `firmware/esp32-csi-node/PROVISIONING.md` documents local NVS provisioning.

Residual note:

- Router-side password rotation and history rewrite remain operator actions outside this repo.

### WP-1 — Runtime Authority (`PS-AUDIT-001`)

Status: FIXED / DECISION

Already present in repo state before this run:

- `docs/adr/ADR-051-runtime-authority.md` records Option B on July 17, 2026.
- `README.md` now consistently states that the Node/TS server is the sole live UDP `:5005`
  authority and that Python live mode is retired.

### WP-2 — Firmware Sovereign Respiratory Gate (`PS-AUDIT-002`)

Status: FIXED

Already present in repo state before this run:

- `firmware/esp32-csi-node/main/edge_processing.c` uses
  `edge_evaluate_human_presence(...)` instead of motion-only presence.
- `firmware/esp32-csi-node/main/edge_dsp_pure.c/.h` contain the pure verdict logic.
- `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c` covers:
  - broadband/fan-like motion does not assert human presence,
  - breathing-band motion does,
  - cardiac-only paths cannot flip a negative respiratory verdict.

This run did not modify the firmware verdict path further.

### WP-3 — F1 WebSocket Presentation Gap (`PS-AUDIT-014`)

Status: FIXED

Already present in repo state before this run:

- `server/lib/websocket.ts` gates `poseFrame`, `targetIdentity`, and `vitalSigns`
  on `client.isAI`.
- AI identity/vitals are relayed as `advisoryIdentity` / `advisoryVitalSigns`.
- Deterministic `currentTargetIdentity` / `currentVitalSigns` are no longer written
  from client messages.
- `server/lib/websocket.test.ts` covers the non-AI reject path and deterministic snapshot behavior.

#### WP-3 close-out (this session)

**Fix A — tracked finding `PS-REMED-WP3-FOLLOWUP-01`, status OPEN.** Dashboard has no handler
for `advisoryIdentity` / `advisoryVitalSigns` (`client/src/hooks/use-websocket.ts` has no case
for either type); AI advisory output is non-rendering until a client handler is added. This is
a stricter-safe default than the pre-fix state (where AI output rendered by sharing the
authoritative channel) — tracked for the UI backlog, not implemented here.

**Fix B — `poseFrame` verdict-inertness, VERIFIED (not assumed).** Traced every downstream
reader of `currentPoseFrame`/`poseFrame`:
- Server (`server/lib/websocket.ts:346,1221,1312`): stores, relays to clients, resets to
  null — no computation reads it.
- Client WS hook (`client/src/hooks/use-websocket.ts:390-393`): stores in React state only.
- Prop chain (`dashboard.tsx:155` → `point-cloud-3d.tsx:37` → `RadialScene.tsx:498`): passed
  through unchanged, gated only by a cosmetic visibility toggle.
- Terminal consumer (`client/src/components/dashboard/HumanMesh.tsx:86,141-142,158-173`): a
  Three.js rendering component that uses `poseFrame.keypoints` to choose between an
  AI-reconstructed vs. procedural skeleton and to position keypoint meshes, anchored at the
  already-computed deterministic `target` position — never the reverse.

No reader on either side writes to `targetState`, the classifier, or any verdict field.
`poseFrame` is confirmed verdict-inert; no code action required.

Also carried forward from the WP-2 close-out session (evidence unchanged, restated here since
this report section was rewritten): **`PS-REMED-WP2-FOLLOWUP-01`, status OPEN.** The
autocorrelation-based respiratory periodicity estimator
(`firmware/esp32-csi-node/main/edge_dsp_pure.c`) can alias a clean, highly periodic non-human
vibration (e.g. a fan/HVAC unit at a stable RPM) into the 6-30 BPM band via integer
sub-harmonics of the autocorrelation. Evidence:
`firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c`'s
`demo_known_limitation_tonal_aliasing` (printed, not asserted) — a clean 2.2 Hz tone with no
noise produces `resp_conf = 1.000`, in-band `breathing_bpm = 26.4`. Real broadband/non-tonal
motion does not reproduce this (`test_broadband_motion_alone_is_not_human`). Not fixed;
requires a harmonic-purity/peak-sharpness check in the estimator itself, out of scope for the
respiratory-gate fix that introduced it.

### WP-4 — Retire Legacy 20-Byte CSI from Live Path (`PS-AUDIT-004`)

Status: FIXED

Changed:

- `server/lib/udp-server.ts`
- `server/lib/udp-server.test.ts`
- `scripts/calibrate-threshold.ts`

What changed:

- `parseCsiPacket()` now rejects legacy 20-byte CSI by default.
- Legacy parsing is available only through explicit compatibility opt-in
  (`allowLegacy` / `PHANTOM_ALLOW_LEGACY_CSI`).
- Offline calibration tooling can still opt in deliberately.

Validation:

- TS tests assert live-mode rejection and compat-mode acceptance.

### WP-5 — Node Identity vs Canonical Hardware IDs (`PS-AUDIT-005`)

Status: FIXED

Changed:

- `shared/schema.ts`
- `server/lib/udp-server.ts`

What changed:

- Added canonical mapping source of truth:
  - runtime node `1` -> hardware ID `29052`
  - runtime node `2` -> hardware ID `44260`
- Added `hardwareId` on `CSISample`.
- Live authority now resolves runtime node IDs to canonical hardware IDs at ingest.
- Unmapped runtime node IDs are rejected in the live authority.

Validation:

- TS suite remained green after the mapping change.

### WP-6 — Python Stale Geometry and Sample Rate (`PS-AUDIT-006`)

Status: FIXED

Changed:

- `phantom/dsp.py`
- `phantom/runtime.py`
- `tests/test_invariants.py`

What changed:

- Python reference baseline changed from `5.0 m` to `3.0 m`.
- `dual_node_on_axis_position()` now returns centered coordinates with midpoint `x_m = 0.0`.
- Python reference sample-rate defaults changed from `20.0` to `5.0` to stop encoding the stale
  20 Hz assumption in the reference path.
- Invariant test now asserts midpoint `x_m = 0.0`, not `2.5`.

Validation:

- Python tests passed with the corrected geometry.

### WP-7 — Replay / Out-of-Order Enforcement (`PS-AUDIT-007`)

Status: FIXED

Changed:

- `server/lib/udp-server.ts`
- `server/lib/udp-server.test.ts`

What changed:

- Added `PacketOrderGuard` in the live TS authority.
- Replays (`delta == 0`) are rejected.
- Clearly old/out-of-order sequences are rejected.
- Sequence rollover is accepted.
- Device timestamps are used to fail closed on repeated/non-advancing device time.

Validation:

- TS tests cover in-order, replay, out-of-order, and rollover cases.

### WP-8 — Source Pinning Hardening and Windows Bind Safety (`PS-AUDIT-008`, `PS-AUDIT-013`)

Status: FIXED

Changed:

- `server/lib/udp-server.ts`
- `server/lib/udp-server.test.ts`
- `phantom/ingest.py`
- `phantom/runtime.py`
- `tests/test_phantom_runtime.py`

What changed:

- Added optional static source pinning in the live TS authority via
  `PHANTOM_STATIC_NODE_SOURCES` JSON mapping.
- For statically pinned nodes, foreign IPs are rejected even before first claim and after silence.
- Retired Python live ingest no longer sets `SO_REUSEADDR`.
- Retired Python live mode now refuses to start unless
  `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1` is explicitly set.
- Python source pinning now fails closed on missing source info instead of silently skipping.

Validation:

- TS tests cover static pre-pin rejection and static post-silence rejection.
- Python tests cover missing-source rejection.

### WP-9 — First-Operator Bootstrap (`PS-AUDIT-015`)

Status: FIXED

Changed:

- `server/auth/service.ts`
- `server/auth/service.test.ts`

What changed:

- First-operator bootstrap is allowed only from loopback, or with a valid
  `PHANTOM_BOOTSTRAP_TOKEN`.
- Non-loopback first-login attempts without token return `403`.
- Failure is audit-logged as `operator_bootstrap_failure`.

Validation:

- TS tests cover successful loopback bootstrap and rejected forwarded non-loopback bootstrap.

### WP-10 — Live Fusion Math Alignment (`PS-AUDIT-003`)

Status: DEFERRED

Not changed in this run:

- The live path still contains nonlinear balance shaping and display bias in
  `server/lib/node-fusion.ts`.
- README truth was improved, but this report does not claim canonical-linear restoration.

Reason deferred:

- This is a separate behavioral choice and would require explicit alignment of
  authority math vs display transform semantics, plus updated tests/docs.

### WP-11 — Documentation Truth Pass (`PS-AUDIT-009`, `PS-AUDIT-011`, `PS-AUDIT-017`, `PS-AUDIT-018`)

Status: FIXED / PARTIAL

Changed:

- `README.md`
- `DETECTION_REPORT.md`
- `TEST_REPORT.md`
- `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`
- `ai model and densepose/model/README.md`

What changed:

- Removed stale root-level claims that Python was becoming the live authority.
- Updated root reports from stale 5 m geometry to centered 3 m geometry.
- Downgraded unmeasured “✅ Validated” claims in the preliminary deliverable to
  `Target — [TO BE MEASURED]`.
- Labeled legacy 20-byte and `2π / λ` references in the preliminary deliverable as superseded.
- Reworded model README “100% accuracy” claims to honest placeholder language.

Partial / deferred (as of July 19, 2026 — closed below in WP-13/WP-15, July 20, 2026):

- `docs/ruview-2node-full-analysis-report.md` was not updated in this run. **Closed by WP-13.**
- README/documentation for WP-10’s authoritative-linear vs display-transform split is still incomplete. **Closed by WP-15.**

## Files Changed In This Run (July 19, 2026)

- `README.md`
- `DETECTION_REPORT.md`
- `TEST_REPORT.md`
- `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`
- `ai model and densepose/model/README.md`
- `shared/schema.ts`
- `server/lib/udp-server.ts`
- `server/lib/udp-server.test.ts`
- `server/auth/service.ts`
- `server/auth/service.test.ts`
- `scripts/calibrate-threshold.ts`
- `phantom/ingest.py`
- `phantom/dsp.py`
- `phantom/runtime.py`
- `tests/test_invariants.py`
- `tests/test_phantom_runtime.py`

## WP-12 — Dashboard AI Advisory Surface (`PS-REMED-WP3-FOLLOWUP-01`)

Status: FIXED (July 20, 2026)

Changed:

- `client/src/hooks/use-websocket.ts`
- `client/src/components/dashboard/ai-advisory-panel.tsx` (new)
- `client/src/pages/dashboard.tsx`

What changed:

- Added `advisoryIdentity`/`advisoryVitalSigns` state and switch-case handling to the
  client WS hook, mirroring the existing `targetIdentity`/`vitalSigns` handling exactly.
  Both fields are cleared by `buildClearedSceneState()` on stop/disconnect/source-change
  so a dead AI sidecar cannot leave a ghost advisory reading on screen.
- Added a new `AIAdvisoryPanel` component: visually distinct (dashed border,
  amber/purple accent, permanent "AI ADVISORY · NON-AUTHORITATIVE" badge), renders
  nothing when no AI sidecar is connected.
- Wired into `dashboard.tsx` after the existing `NodeFeaturesCard`.

Validation: manual smoke-test procedure only (open a second WS connection as an
`isAI`-registered client, send `targetIdentity`/`vitalSigns`, confirm render and
clear-on-stop) — no client-side automated test harness exists in this repo (confirmed:
zero `client/src/**/*.test.*` files), and standing one up was explicitly deferred by the
operator to keep this change small.

## WP-13 — Collapse Stale RuView Analysis Report (`PS-AUDIT-010`)

Status: FIXED (July 20, 2026)

Changed:

- `docs/ruview-2node-full-analysis-report.md`

What changed:

- Collapsed the 567-line report (which had only a correction banner over an otherwise
  unchanged bridge-as-live narrative, with stale `[4.0,0,6.0]`/`[16.0,0,6.0]` coordinates
  throughout) to a ~90-line archived-note stub: strengthened ARCHIVED banner, a "what
  this document was" summary, a "what is canonical now" section pointing to ADR-051,
  README's fusion section, and `shared/schema.ts` geometry, a few preserved
  still-useful historical points (CSI self-ping starvation mitigation, the 1-D
  balance-ratio ancestry, node-health supervision), and the "Honest Limits" list kept
  verbatim. Confirmed via repo-wide grep that no other file links into this doc, so no
  dangling references were created.

## WP-14 — Regression Test for Python Cross-Node Correlation (`PS-AUDIT-016`)

Status: FIXED, confirmed already correct in code — test coverage added (July 20, 2026)

Changed:

- `tests/test_phantom_cross_node_correlation.py` (new)

What changed:

- Verified `phantom/runtime.py`'s `_build_derived_frame()` already feeds
  `cross_node_correlation()` with real multi-frame `NodeDspPipeline.dynamic_history()`
  (a 128-sample deque accumulated across `.process()` calls), not a single sample, and
  that `dual_node_on_axis_position()` is fed `motion_energy`, not raw mean amplitude —
  the `PS-AUDIT-016` finding's underlying code issue does not exist in the current tree.
- Added three tests driving the real `PhantomRuntime.ingest_packet()` pipeline (not the
  pure functions in isolation): correlation is not the structural `0.0` that single-sample
  input would produce, correlated two-node motion scores higher than independent motion,
  and `on_axis_position` reflects the centered 3 m geometry through the real pipeline
  wiring.

Validation: `python -m pytest tests/test_phantom_cross_node_correlation.py -v` -> 3 passed.

## WP-15 — Fusion Authoritative/Display Split (`PS-AUDIT-003`, `PS-AUDIT-011`)

Status: FIXED — additive telemetry + doc correction; live display math unchanged (July 20, 2026)

Changed:

- `server/lib/node-fusion.ts`
- `shared/schema.ts`
- `server/lib/websocket.ts`
- `server/lib/node-fusion.test.ts`
- `README.md`
- `docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md` (new)

What changed:

- Added `computeLinearBalance(r1, r2)` — the canonical, undecorated `r2/(r1+r2)` ratio —
  and a new `balanceLinear` field on `FusedTarget`/`radialTarget`, computed alongside
  (never replacing) the existing contrast+bias-shaped `balance` that drives the on-screen
  target position. Purely additive: no existing consumer reads the new field, and neither
  the on-screen position nor the trend/distance computation changed.
- Corrected two confirmed README documentation errors: the fusion section previously
  described a bare linear `balance` formula and a "3-second" window; the code has always
  used a contrast exponent (`BALANCE_CONTRAST_EXPONENT`, default 2.0) plus a separate
  display bias (`BALANCE_BIAS_EXPONENT`, default 0.72), and a `PHANTOM_MOTION_WINDOW_MS`
  default of 1500ms, not 3000ms. Per operator decision, the docs were corrected to match
  the code — the live runtime window/behavior was NOT changed.
- Added `docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md`, documenting the
  decision to keep the tuned display transform as intentional and add the authoritative
  value alongside it, rather than changing live display behavior (which would require
  real-hardware re-validation this pass cannot perform).

Validation: `npx tsx --test server/lib/node-fusion.test.ts` -> 23 pass, 0 fail (3 new
`balanceLinear` tests: invariant to contrast exponent, correct at the midpoint, matches
the plain ratio).

## WP-16 — Harmonic-Purity/Sub-Harmonic-Multiplicity Gate (`PS-AUDIT-002` follow-up, `PS-REMED-WP2-FOLLOWUP-01`)

Status: FIXED — mitigation landed with a placeholder threshold; real-hardware validation
still required (July 20, 2026)

Changed:

- `firmware/esp32-csi-node/main/edge_dsp_pure.h`
- `firmware/esp32-csi-node/main/edge_dsp_pure.c`
- `firmware/esp32-csi-node/main/edge_processing.c`
- `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c`

What changed:

- Added `estimate_period_regularity_cv()`, combining two signals: (1) coefficient of
  variation of interpolated (sub-sample) zero-crossing intervals — real breathing has
  natural cycle-to-cycle rate jitter that a clean mechanical tone lacks; and (2) a
  sub-harmonic-aliasing multiplicity check — comparing the raw zero-crossing count
  against what the claimed/accepted BPM implies, since a sub-harmonic-aliased tone
  oscillates far more often than its reported slow BPM suggests. **The multiplicity
  check, not the raw CV, is what actually rejects the documented exploit** — the raw CV
  alone proved insufficient during implementation (a clean 2.2 Hz tone under-sampled at
  15 Hz has only ~7 samples/cycle, so integer-quantized zero-crossing CV was *higher* for
  the tone than for genuine jittered breathing; even after sub-sample interpolation the
  two were statistically indistinguishable). This is recorded here rather than silently
  discarded, since the original plan specified a pure jitter-CV design.
- Extended `edge_evaluate_human_presence()` with a new `period_cv` parameter (indeterminate
  sentinel `-1.0f`, fewer than 3 crossings, PASSES per operator decision — consistent with
  the existing conservative-on-missed-detection stance at the low-BPM edge).
- `edge_processing.c` computes `s_resp_period_cv` in Step 7 (after the breathing-BPM
  sanity clamp, so the multiplicity check compares against the same value Step 9 evaluates)
  and threads it into the existing single production call site (line ~801).
- `test_edge_dsp_pure.c`: converted `demo_known_limitation_tonal_aliasing` (previously
  printed-but-unasserted) into a real, asserted `test_tonal_aliasing_is_rejected`; added
  realistic ±4% cycle-to-cycle rate jitter to the breathing-band test signals (needed so
  genuinely biological signals clear the new gate); added period_cv boundary tests
  (at/above/below `EDGE_RESP_PERIOD_CV_MIN`, and the indeterminate-sentinel pass-through).
- `EDGE_RESP_PERIOD_CV_MIN` set to a low placeholder (`0.002`) — a higher floor was tried
  and measurably increased the Monte Carlo missed-detection rate (from ~20% to over 30%)
  by rejecting genuinely jittered breathing near the low-cycle-count band edges, without
  improving tonal-aliasing rejection (which the multiplicity check already handles).
  **Still calibrated only against synthetic data** — real-hardware breathing captures and
  a real fan/HVAC negative control are required before this threshold (or the multiplicity
  ratio `1.6`) can be considered final.

Validation: host-compiled via
`gcc -std=c99 -O2 -Wall -Wextra -I. test/test_edge_dsp_pure.c edge_dsp_pure.c -lm -o test/test_edge_dsp_pure.exe`
(MSYS2 mingw64 gcc 15.2.0, requires `mingw64/bin` on `PATH` for runtime DLLs) -> all
assertions pass, including `test_tonal_aliasing_is_rejected` (period_cv=0.000, verdict
correctly false) and `test_breathing_band_sets_human_present` (period_cv=0.036, verdict
correctly true). Monte Carlo missed-detection rate measured at 20.4% (within noise of the
pre-WP-16 19.8% baseline — the new gate does not meaningfully worsen real detection once
tuned), noise false-positive rate unchanged at 0.2%.

## Remaining Operator Actions (not agent-executable — tracked explicitly, not silently closed)

1. **Real two-board hardware end-to-end verification** (live capture on current firmware,
   empty-room and fan/HVAC negative controls) remains unverified. No agent action in this
   or the prior remediation pass substitutes for it.
2. **Real-hardware calibration** of `EDGE_RESP_PERIOD_CV_MIN` (WP-16) and the pre-existing
   `DEFAULT_MOTION_THRESHOLD`/`TREND_DEADBAND_MPS` placeholders in `server/lib/node-fusion.ts`
   — all three are synthetic-only placeholders per their own docstrings.
3. **Router-side Wi-Fi password rotation and git-history scrub**: real credentials were
   removed from tracked firmware config files (WP-0, `PS-AUDIT-012`), but the original
   password remains recoverable from git history until history is rewritten/rotated
   out-of-band — an operator action outside this repo's remediation scope.

## Verification Results (July 19, 2026)

Executed after code changes in this run:

```text
npm test
```

Observed result:

```text
112 pass, 0 fail
```

```text
C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests -q
```

Observed result:

```text
83 passed, 1 skipped in 52.84s
```

## Remaining Unverified / Deferred Items (as of July 19, 2026 — updated below)

- Live hardware behavior remains unverified in this run:
  - real two-board UDP ingest,
  - live midpoint behavior,
  - empty-room negative control,
  - fan/curtain negative control,
  - real replay/spoof injection on hardware.
  **Still unverified as of July 20, 2026 — see "Remaining Operator Actions" above.**
- ~~`PS-AUDIT-003` remains open: live nonlinear fusion math has not been reconciled to a
  canonical linear authority path.~~ **Closed by WP-15** (additive `balanceLinear` +
  ADR-054; live display math intentionally left unchanged).
- ~~`PS-AUDIT-010` remains open in practice: `docs/ruview-2node-full-analysis-report.md`
  was not banner-corrected here.~~ **Closed by WP-13** (collapsed to an archived-note stub).
- ~~`PS-AUDIT-011` is only partial: README truth is corrected, but authoritative-linear vs
  display-transform documentation is not fully settled.~~ **Closed by WP-15.**
- This report does not claim any accuracy target is met; those remain
  `[TO BE MEASURED]`. **Still true as of July 20, 2026** — WP-12 through WP-16 added
  code-level mitigations and test coverage, not hardware-measured accuracy figures.

## Files Changed In This Run (July 20, 2026 — WP-12 through WP-16)

- `client/src/hooks/use-websocket.ts`
- `client/src/components/dashboard/ai-advisory-panel.tsx` (new)
- `client/src/pages/dashboard.tsx`
- `docs/ruview-2node-full-analysis-report.md`
- `tests/test_phantom_cross_node_correlation.py` (new)
- `server/lib/node-fusion.ts`
- `shared/schema.ts`
- `server/lib/websocket.ts`
- `server/lib/node-fusion.test.ts`
- `README.md`
- `docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md` (new)
- `firmware/esp32-csi-node/main/edge_dsp_pure.h`
- `firmware/esp32-csi-node/main/edge_dsp_pure.c`
- `firmware/esp32-csi-node/main/edge_processing.c`
- `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c`
- `PHANTOM_SCAN_REMEDIATION_REPORT.md` (this file)

## WP-12 through WP-16 Verification Results (July 20, 2026)

```text
npm test
```

Observed result:

```text
132 pass, 0 fail
```

```text
python -m pytest tests -q -rs
```

Observed result:

```text
81 passed, 6 skipped in 37.61s
```

The 6 skips are environmental, not regressions: 1 missing `torch` dependency
(`test_ai_smoke.py`) and 5 requiring the dev server on port 5000
(`test_esp_capture_e2e.py`), neither of which were running/installed during this
verification pass. The July 19, 2026 run recorded "83 passed, 1 skipped" with those
prerequisites available; the underlying test count increased (this run added 3 new tests
in `tests/test_phantom_cross_node_correlation.py`), and no previously-passing test
started failing.

Firmware host DSP test (`test_edge_dsp_pure.exe`, not part of `npm test`/`pytest`, no
ESP-IDF toolchain available in this environment):

```text
gcc -std=c99 -O2 -Wall -Wextra -I. test/test_edge_dsp_pure.c edge_dsp_pure.c -lm -o test/test_edge_dsp_pure.exe
```

(MSYS2 mingw64 gcc 15.2.0; requires `mingw64/bin` on `PATH` for runtime DLLs since the
compiler was invoked by absolute path.) Result: all assertions pass, 0 failures — see
WP-16 above for the specific measured figures (missed-detection rate, tonal-aliasing
rejection).

## Worktree Notes

This remediation was done in a dirty worktree. Unrelated existing changes were left untouched,
including:

- `.vscode/settings.json`
- `data/sessions/_index.json`
- nested git state under `ai model and densepose/model`
- untracked `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
- untracked `generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md`

No commit was created in this run.
