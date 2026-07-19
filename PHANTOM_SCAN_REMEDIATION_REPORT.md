# Phantom Scan Remediation Report

Date: July 19, 2026
Source audit: `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
Runtime authority: Node/TS server per `docs/adr/ADR-051-runtime-authority.md`

## Scope

This report summarizes the remediation work present in the current working tree as of
July 19, 2026. It covers the secret-removal work already landed in the firmware tree, the
runtime-authority decision already recorded in ADR-051, the WebSocket F1 presentation fix
already present in `server/lib/websocket.ts`, and the additional code and documentation
changes completed in this run.

Verification for this report:

- `npm test` -> `112 pass, 0 fail`
- `C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests -q`
  -> `83 passed, 1 skipped in 52.84s`

## Findings Summary

| Finding | Status | Notes |
|---|---|---|
| `PS-AUDIT-001` | DECISION / FIXED | Node/TS live authority recorded in ADR-051 and README. |
| `PS-AUDIT-002` | FIXED | Firmware sovereign respiratory gate already present in repo state. |
| `PS-AUDIT-003` | DEFERRED | Live nonlinear fusion/display split not changed in this run. |
| `PS-AUDIT-004` | FIXED | Legacy 20-byte CSI retired from live path; compat-only gate added. |
| `PS-AUDIT-005` | FIXED | Canonical hardware-ID mapping layer added at authority ingest. |
| `PS-AUDIT-006` | FIXED | Python reference geometry/sample-rate corrected. |
| `PS-AUDIT-007` | FIXED | Live authority now rejects replay/out-of-order packets. |
| `PS-AUDIT-008` | FIXED | Retired Python live bind now fail-closed; `SO_REUSEADDR` removed. |
| `PS-AUDIT-009` | FIXED | Stale 20-byte / draft protocol text labeled superseded in deliverable. |
| `PS-AUDIT-010` | DEFERRED | `docs/ruview-2node-full-analysis-report.md` banner not changed in this run. |
| `PS-AUDIT-011` | PARTIAL | README truth corrected; live fusion math doc split still incomplete. |
| `PS-AUDIT-012` | FIXED | Credential placeholders + gitignore/provisioning already present. |
| `PS-AUDIT-013` | FIXED | Static source pinning support added to live authority. |
| `PS-AUDIT-014` | FIXED | Non-AI verdict-adjacent WS writes blocked; advisory channel split already present. |
| `PS-AUDIT-015` | FIXED | First-operator bootstrap restricted to loopback or token. |
| `PS-AUDIT-016` | FIXED | Python fused reference uses motion histories/metrics instead of stale path. |
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

Partial / deferred:

- `docs/ruview-2node-full-analysis-report.md` was not updated in this run.
- README/documentation for WP-10’s authoritative-linear vs display-transform split is still incomplete.

## Files Changed In This Run

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

## Verification Results

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

## Remaining Unverified / Deferred Items

- Live hardware behavior remains unverified in this run:
  - real two-board UDP ingest,
  - live midpoint behavior,
  - empty-room negative control,
  - fan/curtain negative control,
  - real replay/spoof injection on hardware.
- `PS-AUDIT-003` remains open: live nonlinear fusion math has not been reconciled to a
  canonical linear authority path.
- `PS-AUDIT-010` remains open in practice: `docs/ruview-2node-full-analysis-report.md`
  was not banner-corrected here.
- `PS-AUDIT-011` is only partial: README truth is corrected, but authoritative-linear vs
  display-transform documentation is not fully settled.
- This report does not claim any accuracy target is met; those remain
  `[TO BE MEASURED]`.

## Worktree Notes

This remediation was done in a dirty worktree. Unrelated existing changes were left untouched,
including:

- `.vscode/settings.json`
- `data/sessions/_index.json`
- nested git state under `ai model and densepose/model`
- untracked `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
- untracked `generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md`

No commit was created in this run.
