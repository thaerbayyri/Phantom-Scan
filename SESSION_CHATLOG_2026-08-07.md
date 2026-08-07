# Phantom Scan — Session Log (2026-08-06 → 2026-08-07)

**Note on what this is:** a structured summary of this multi-turn Claude Code session, organized
by task/phase with the key requests, actions, findings, and file changes for each — not a raw
verbatim transcript (no mechanism exports the literal chat text), but everything material that
happened is captured below in order.

---

## Phase 1 — Research-to-repo gap analysis

**Request:** Analyze the codebase against an attached external research report ("CNN-LSTM Deep
Learning for Wi-Fi CSI Human Detection") — analysis only, no code changes.

**What happened:** Read the full research report (pasted after an initial round where it was
missing and had to be requested). Dispatched 5 parallel research agents to verify repo state
against the report's assumptions (motion/presence detection, ACF/periodicity vibration
rejection, ML/AI-firewall wiring, sampling rate, test coverage, and known open items). Produced
`PhantomScan_Research_Gap_Analysis.md`: recommendation was that the CNN-LSTM upgrade is not
currently justified — higher priority is wiring the existing deterministic classifier into the
live presence gate, running a real hardware negative control, and closing test-coverage gaps.

## Phase 2 — ADR-048 reconciliation

**Request:** Reconcile ADR-048 (documents a Rust "override capable" classifier that was never
built) with the actually-implemented advisory-only AI firewall invariant.

**What happened:** Verified no `crates/`/Rust implementation exists, confirmed the real
advisory-only guard (`server/lib/websocket.ts`, F1/PS-AUDIT-014) and its tests. Amended
`docs/adr/ADR-048-adaptive-csi-classifier.md` in place with a "Status Update: Superseded" section
— did not delete the original content (ADRs are historical record).

**Follow-up:** user asked to push all changes to GitHub. Confirmed scope with the user (staged
everything except a suspicious `data/sessions/_index.json` diff and an unrelated submodule),
committed, and pushed to `main` (commit `920595d`, merged via PR #1 to `9177ad3`).

## Phase 3 — "Fix-all" session (Items 1–8 from the gap analysis)

**Request:** Work through the gap analysis's prioritized list, item by item, tests required at
each step, never weakening the F1/F2 invariants.

**Outcomes, by item:**
1. Wired the deterministic `MicroDopplerClassifier` into the presence gate as a *corroborating*
   signal (`evaluateClassifierCorroboration`, `node-fusion.ts`) — can only suppress a presence
   claim the energy gate already made, never assert one alone. 17 new tests.
2. Built negative-control tooling: `docs/NEGATIVE_CONTROL_CHECKLIST.md`,
   `scripts/analyze_negative_control.py` (real-recordings-only analysis). Measured real pre-fix
   baselines from existing recordings (fan false-positive rate 11.8%/31.2%).
3. Reviewed/prepped the P0–S8 positional-fidelity campaign tooling; filled in the underspecified
   S2 stage.
4. Added spatial/DBSCAN noise-floor calibration (`calibrateEnergyThreshold`,
   `DEFAULT_SPATIAL_ENERGY_THRESHOLD`) — default left unchanged pending a real calibration run.
5. Added `server/lib/signal-processing.test.ts` and `server/lib/tracking.test.ts` — the
   project's first coverage for these two files. **Found and fixed a real pre-existing bug**
   (PS-GAP-TRK-001): `TrackingProcessor` could return a fabricated ghost target on a cold start
   with only sub-threshold noise. Also **discovered but did not yet fix** PS-GAP-MUSIC-001: MUSIC
   spectrum output was mathematically independent of its input (bit-for-bit identical for
   unrelated inputs).
6. Corrected the stale "~20 Hz" CSI sampling-rate claim to the measured ~41–43 pps across
   README/firmware docs, leaving historical ADR records untouched.
7. Evaluated the firmware SFO/PDD gap; formally deferred it via `docs/adr/ADR-058-...md` since
   the live path already cancels SFO/PDD and firmware phase isn't authoritative today.
8. Re-verified ADR-048's reconciliation still held.

Delivered `PhantomScan_FixAll_Session_Report.md`. Full suite green throughout (189/189 TS by
session end, 86+1-skip Python).

## Phase 4 — Follow-up session (Items A–D)

**Request:** Close out several loose ends the fix-all report flagged as needing Thaer's decision
or further investigation, rather than resolving them unilaterally.

**Outcomes:**
- **A:** Investigated PS-GAP-MUSIC-001's severity — confirmed it reaches the live dashboard by
  default (`isarEnabled: true`), and is worse than first scoped (entire spectrum frozen, not just
  the peak). Proposed but did **not** apply a UI honesty-caveat fix, pending sign-off.
- **B:** Re-confirmed `REAL_TEST_REPORT.md`'s self-contradictory "HISTORICAL" flag; drafted two
  resolution options (un-flag in place vs. a successor doc) without applying either.
- **C:** Verified ADR-058's factual foundation against `docs/research/csi-phase-in-wifi-sensing.md`
  on `main` — confirmed solid, no mismatch.
- **D:** Found and fixed the actual root cause of stray `.jsonl` files landing in the repo root
  (`tests/test_phantom_cross_node_correlation.py` was passing `output_dir=""`) — fixed to use
  `tmp_path`, verified with a double test run, added a root-anchored `.gitignore` rule. Also
  corrected the prior report's assumption that 12 legacy `.jsonl` files were "untracked" — they
  turned out to be tracked (committed accidentally in an old release commit); left them alone
  rather than unilaterally `git rm`-ing tracked files.

Delivered `PhantomScan_FollowUp_Session_Report.md`.

## Phase 5 — PS-GAP-MUSIC-001 proper fix

**Request:** Investigate and properly fix the MUSIC input-independence bug (not just a UI
workaround) — mandated a "Task 0" investigation into what `sampleBuffer` actually contains before
choosing a fix path.

**Task 0 finding:** `sampleBuffer` is 16 time-sequential single-antenna CSI scalars, interleaved
from two clock-unsynchronized nodes — not spatial antenna channels. No eigen-math fix could
recover a real angle-of-arrival from this input.

**Fix applied (temporal-signature path):**
- `powerIterationEigen`: added Gram-Schmidt orthogonalization in the deflation step, so
  degenerate/rank-deficient cases produce a genuine (input-dependent) orthogonal-complement basis
  instead of silently substituting the fixed random seed vector.
- `computeMUSICSpectrum`: now genuinely averages over multiple forward sub-window snapshots
  (previously claimed to but didn't); returns an honest empty spectrum for truly degenerate input.
- Relabeled the UI (`aoa-spectrum.tsx`, `metrics-panel.tsx`) from "AoA Spectrum"/"Peak AoA (deg)"
  to "Signal Signature (temporal MUSIC)" with a permanent "NOT SPATIAL ANGLE" caveat — a
  false-precision fix, not data-hiding.
- Replaced the old pinned "known-broken" test with 3 regression tests for the fixed behavior.

Verified with a real before/after demonstration (two unrelated random buffers went from a
3.6e-15 spectrum difference to 14.8 dB). Full suite green (191 TS, 86+1-skip Python). Delivered
`PhantomScan_MUSIC_Fix_Session_Report.md`.

## Phase 6 — Target-node regression investigations

**Request 1 (recorded-replay investigation):** Thaer reported the live target marker was no
longer showing up after the MUSIC fix. Investigated via synchronous replay of 5 real recorded
sessions (11,244 ticks) through the exact functions the MUSIC fix touched. **Could not
reproduce** — zero empty spectra, zero null-tracked-target ticks, app boots/typechecks clean, all
consumers already null-guarded. Delivered `PhantomScan_TargetNode_Regression_Fix.md` with an
explicit "here's what I tried, here's what would help" writeup rather than a speculative fix.

**Request 2 (live-replay investigation):** Thaer clarified the bug was observed live, in the
browser, against real hardware — a materially different reproduction condition. Built a genuine
live-conditions test: killed a stray leftover process squatting on UDP :5005, started the real
dev server, opened the real dashboard via Chrome DevTools browser automation, started a scan, and
replayed a large real captured wire-packet dataset (62,344 frames) over an actual UDP socket in
real time. **The target rendered correctly** — "Between N1 and N2", "MOVING", coherent
distance/bearing, zero console errors. Still could not reproduce the reported symptom. Delivered
`PhantomScan_LiveTarget_Regression_Fix.md`, including a precise live-test procedure for Thaer to
run against real hardware himself, since this environment has none.

One loose end surfaced and deliberately not chased without evidence: the live-replay test showed
fused-two-node display behavior despite only node-2 packets being sent.

## Phase 7 — Node-mode staleness investigation (in progress at time of this log)

**Request:** Determine whether that loose end is a real staleness/liveness bug in
`resolveLiveNodeMode()`, or a benign artifact of the previous test's session setup — with
evidence, not assumption.

**Progress so far:** Located and read `resolveLiveNodeMode()`/`activeHardwareNodeIds()` in full
(`server/lib/websocket.ts`) — on inspection, the staleness logic looks correct (1.5 s window,
requires both nodes active for fused mode). Traced `nodeId` end-to-end from `udp-server.ts`'s
packet parsing through to `ingestSample()` — no evident loss or misattribution. Was mid-way
through setting up a clean-session empirical test (fresh dev server, fresh browser tab, node-2
packets only, from a true cold start) to distinguish "real bug" from "session-leftover artifact"
when this log file was requested. **Noted but not yet explained:** the fresh dev server's log
showed an `[ESP32] Queue: 1 | h1=(-32.00, 10.00) h2=(-32.00, 10.00) rssi=-26` line appearing
*before* any replay traffic was sent this round — under investigation next.

---

## Cumulative file-change footprint (as of this log)

Code: `server/lib/node-fusion.ts`, `server/lib/websocket.ts`, `server/lib/tracking.ts`,
`server/lib/signal-processing.ts`, `server/lib/recording-export.ts`, `shared/schema.ts`,
`scripts/calibrate-threshold.ts`, `client/src/components/dashboard/aoa-spectrum.tsx`,
`client/src/components/dashboard/metrics-panel.tsx`, `tests/test_phantom_cross_node_correlation.py`.

New tests: `server/lib/signal-processing.test.ts`, `server/lib/tracking.test.ts`, plus additions
to `server/lib/node-fusion.test.ts`.

New tooling/docs: `scripts/analyze_negative_control.py`, `docs/NEGATIVE_CONTROL_CHECKLIST.md`,
`docs/SPATIAL_CALIBRATION.md`, `docs/adr/ADR-058-firmware-sfo-pdd-out-of-scope.md`, and this file.

New reports (all in repo root): `PhantomScan_Research_Gap_Analysis.md`,
`PhantomScan_FixAll_Session_Report.md`, `PhantomScan_FollowUp_Session_Report.md`,
`PhantomScan_MUSIC_Fix_Session_Report.md`, `PhantomScan_TargetNode_Regression_Fix.md`,
`PhantomScan_LiveTarget_Regression_Fix.md`.

Nothing beyond the Phase 2 push has been committed/pushed to git — everything from Phase 3
onward remains uncommitted working-tree changes.
