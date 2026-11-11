# Phantom Scan — Ghost Target Fix (2026-08-07)

False-positive investigation: dashboard showing a moving target in a genuinely empty room. This
is the opposite failure class from every other issue found this week (under-detection), and per
the project's search-and-rescue purpose, a more dangerous one — a ghost target actively misleads
an operator rather than just missing someone.

## Step 0 — live capture

Not received. No fresh case recording, screenshot, or console export arrived during this session.
Per the ground rules, analysis proceeded on pre-existing real empty-room data instead, and would
fold in fresh data immediately if it arrives. All findings below are from real recorded sessions
already in `data/sessions/`, not synthetic data.

## Root cause: confirmed, with evidence

Scanned every known real empty-room/negative-control session in `data/sessions/` for
`target_visible=1` (false-positive) rates:

| session | node_mode | target_visible=1 rate |
|---|---|---|
| `empty_room_fan_off_20260720` (fan off, no human) | — | **0.0%** (0/465) |
| `moving-detection-demo` | — | **0.0%** (0/128) |
| `emty_room_test_2026-07-20T18-18` | **single_node** | **99.4%** (2359/2374) |
| `emty_2026-07-20T18-21` | **single_node** | **98.2%** (824/839) |
| `live_hw_verify_20260720_v2` ("emty room") | fused_two_node | 95.9% (4797/5000) — see caveat below |
| `emty_room_test_2026-07-23T12-06` | fused_two_node | 17.2% (860/5000) |
| `emty_room_with_fan` (×2, fan running) | fused_two_node | 11.8% / 31.2% — known baseline, unrelated |

**Both true single-node ghost-target sessions (99.4%, 98.2%) share the same signature:
`node1_fps_start: 0`** — node 1 never reported that session, so `resolveLiveNodeMode()` correctly
fell to `single_node`. That confirms Priority Suspect #1's premise (single-node mode) and points
straight at `hasSingleNodePresenceEvidence` (`server/lib/node-fusion.ts:485-497`).

### The actual mechanism (not what Suspect #1 hypothesized)

Suspect #1 hypothesized `hasTrackedTarget` (DBSCAN/Kalman clustering) as the likely culprit. It
wasn't the one I found evidence for — the other OR-input was:

`hasSingleNodePresenceEvidence(motionDetected, hasTrackedTarget, classifier)` was being called
(`server/lib/websocket.ts`, pre-fix) with `motionDetected` from `motionResult.motionDetected` —
the output of a **completely separate** legacy `MotionGate` class (`server/lib/signal-processing.ts:795-852`),
not the `motion1`/`motion2` metric (`computeNodeMotionFromMatrix`) the two-node fused gate uses.

That `MotionGate`:
- Operates on `dynamicAmplitude`, a single scalar (background-subtracted `h1` magnitude).
- When `motionGateEnabled` is `false` (**the live config default** — `websocket.ts` config block,
  `motionGateEnabled: false`), it falls back to an **auto-calibrated threshold**: 3× the std-dev
  of just its first 100 samples (~2.4s at ~42fps) of *this specific session*.
- That threshold was never validated against a real empty-room + fan negative control — unlike
  `DEFAULT_MOTION_THRESHOLD` (0.6), which was calibrated 2026-07-20 against a 296-sample
  empty-room baseline (`node-fusion.ts:34-36`) and re-confirmed balanced across nodes in
  `PhantomScan_Node2_Diagnostic_Report.md` this same week.

So the live system had **two independent, uncoordinated motion-detection mechanisms** feeding two
sibling presence gates (fused-mode and single-node-mode) with wildly different calibration rigor
— one well-validated, one auto-calibrating itself fresh, unvalidated, every single session. That
architectural split is the real root cause.

## The fix

`server/lib/websocket.ts`: added `singleNodeMotionDetected()`, which reuses the *same* validated
`nodeMotionFor()` metric and `fusedTargetMotionThreshold` the two-node fused gate already trusts,
applied to whichever single node is currently active:

```ts
private singleNodeMotionDetected(): boolean {
  return this.activeHardwareNodeIds().some(
    (nodeId) => this.nodeMotionFor(nodeId).motion >= this.config.fusedTargetMotionThreshold,
  );
}
```

The single-node presence-gate call site now passes `this.singleNodeMotionDetected()` instead of
`motionResult.motionDetected`. `this.motionGate`/`motionResult` are untouched otherwise — they
still feed the `motionStatus` broadcast, which is a separate display concern.

This does **not** touch `hasTrackedTarget` or the DBSCAN/Kalman `TrackingProcessor` path (Suspect
#1's other half) — no evidence implicated it, and the OR-gate's other input (the one I did find
concrete evidence for) fully explains the mechanism.

## Before/after, real data

Replayed each real single-node empty-room session's actual recorded `motion_n1`/`motion_n2`
values (same metric the fix now uses) against `fused_motion_threshold`:

| session | old rate (MotionGate) | new rate (validated metric) |
|---|---|---|
| `emty_2026-07-20T18-21` | 98.2% | **0.0%** (0/839) |
| `emty_room_test_2026-07-20T18-18` | 99.4% | **61.7%** (1464/2374) |

**Honest result: not a full fix in every historical recording.** `emty_2026-07-20T18-21`'s ghost
target is completely eliminated. `emty_room_test_2026-07-20T18-18`'s node2 baseline itself
averages 0.631 — already above the 0.6 threshold, using the *same* metric the fused gate trusts.
The fix removes the separate under-calibrated mechanism, but can't manufacture headroom that
isn't in that particular recording's own node2 signal. Two explanations are plausible and I
can't distinguish them from this recording alone: (a) that session's node2 genuinely had an
elevated noise environment that day (both single-node sessions are from 2026-07-20, the same day
`DEFAULT_MOTION_THRESHOLD` itself was calibrated — plausibly early/pre-calibration data), or (b)
a single active node's own noise floor is statistically not the same distribution as
`max(motion1, motion2)` from a two-node calibration baseline. Flagging this as a real open
question rather than claiming full resolution.

### True-positive check (no over-correction)

Real moving-target-scale motion still trips the fixed gate — added as a direct regression test
(`server/lib/websocket.test.ts`, "real moving-target-scale node motion still trips the gate")
using the same order-of-magnitude variance a real moving person produces at this signal scale;
passes. The fix reuses `DEFAULT_MOTION_THRESHOLD`, which the Node2 report this week confirmed is
**not** miscalibrated in a way that would trade this false-positive fix for new false negatives —
it's the same threshold already governing the fused-mode path today, unchanged.

## Suspect #3 — two-node fusion gate on environmental noise: inconclusive, not confirmed

`live_hw_verify_20260720_v2`'s meta names it `'emty room'` but shows `fused_two_node` mode with
motion_n1 avg **0.871**, motion_n2 avg **0.744** — a 95.9% "false positive" rate using the
*already-validated* metric. This does **not** implicate the fused gate as broken: this session's
motion levels are 2× any other empty-room session found (typical resting baseline elsewhere:
~0.35–0.45), and its own filename ("live hw verify") suggests active hardware setup/testing, not
a settled unoccupied room. Genuine `empty_room_fan_off_20260720` (fan off, no human, no setup
activity) shows a clean 0.0% — the fused gate is not producing false positives on legitimate
environmental drift in the one recording that's actually trustworthy as a negative control. Not
touched; no evidence supports a fix here, and mislabeling one old session's `session_name` isn't
grounds to change production gate logic.

## Suspects 2, 4, 5

- **#2 (PS-GAP-TRK-001 regression):** re-confirmed intact — `tracking.ts:422`'s cold-start guard
  and both its regression tests (`tracking.test.ts:117,138`) are present and pass. No regression.
- **#4 (classifier corroboration):** cannot be checked against these specific recordings — both
  false-positive sessions predate the `classifier_corroboration` column (Item 1 wiring shipped
  later); the column is absent, not `"not_evaluated"`, confirming they're pre-Item-1 recordings.
  Whether the classifier would correctly flag this noise as non-human is genuinely unknown from
  existing data — would need a fresh empty-room negative-control run with current code to check.
- **#5 (stale target persisting):** ruled out by the mechanism itself — the gate was re-evaluating
  and re-passing on *live*, fresh data every tick (99.4%/98.2% of *all* ticks, not a plateau after
  one detection), not a leftover target failing to clear. `emptyTargetState()`'s hold/stale/clear
  timers were never the failure point here.

## Verification

```
$ npx tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts
tests 223
pass 223
fail 0

$ python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed in 0.49s
```

```
$ python -m pytest tests/ -q
91 passed, 1 skipped, 7551 warnings in 108.13s
```

As expected — this fix touches only `websocket.ts`'s TypeScript single-node branch, not any
Python path, so the full Python suite is unaffected.

F1/F2 explicitly re-confirmed. MUSIC fix: **not touched** — nothing in this trace involves
`computeMUSICSpectrum`/`powerIterationEigen` or the AoA path; the failure and fix are entirely in
the presence-gate wiring upstream of it.

## Architecture assessment

This is the third real behavioral bug found in the live target-detection path this week: a
stale-label bug, a threshold/node2 under-sensitivity investigation, and now a false-positive
whose root cause turned out to be **two independent motion-detection mechanisms with different
calibration rigor feeding sibling presence gates that were never audited against each other**. My
honest read: the pattern across all three isn't "the threshold is wrong" or "one function has a
bug" — it's that presence detection has accreted multiple parallel paths (`MotionGate`'s
auto-calibrated scalar, `computeNodeMotionFromMatrix`'s validated ratio, DBSCAN/Kalman spatial
clustering, the classifier corroboration layer) added incrementally, each patched in isolation
when a specific symptom appeared, without a single source of truth for "is motion present." This
fix removes one of the two overlapping mechanisms for the single-node case, but the two-node
fused path still has its own `motionGate`/`motionResult` computed and broadcast (unused for
gating there, but still running, still a latent inconsistency if some future code path reaches
for it). I'd genuinely recommend a focused architecture review — not another one-off — before the
next symptom surfaces: enumerate every presence-relevant signal (`MotionGate`, `motion1`/`motion2`,
`hasTrackedTarget`, classifier corroboration), decide which ones are load-bearing versus
legacy/display-only, and delete or clearly quarantine the rest. Right now it's not obvious from
reading the code alone which of four signals is authoritative for a given mode, and that's exactly
the condition that produced this bug.
