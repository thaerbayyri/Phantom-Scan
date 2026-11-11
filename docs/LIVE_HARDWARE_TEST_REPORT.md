# Live Two-Board Hardware Test Report

Date: 2026-07-20
Boards: ESP32-S3 on COM5/COM6, reflashed same day with WP-16 firmware (tonal-aliasing
respiratory-gate mitigation). Test run against the user's own `npm run dev` session,
authenticated via the existing operator account, driven via a WebSocket observer/sender
pair (throwaway scripts, removed after the test) that mirrors what the dashboard UI does.

## Summary

This was the first real-hardware verification of the two-node live detection pipeline
(previously an open item in `PHANTOM_SCAN_REMEDIATION_REPORT.md`, "Remaining Operator
Actions" #1/#2). It found and fixed one critical miscalibration, confirmed presence
detection works once corrected, and surfaced a new, previously undocumented gap: the
two-node fusion motion gate has no fan/mechanical-motion rejection, unlike the firmware's
separate WP-16 respiratory gate.

## Findings

### 1. CRITICAL — `PHANTOM_MOTION_THRESHOLD` default (0.12) was drastically miscalibrated — FIXED

- With the dashboard running at the default threshold, the empty-room negative control
  failed: `targetState.state` showed `"moving"`/`"idle"` with confidence up to 0.84 with
  nobody in the room.
- Ran `scripts/calibrate-threshold.ts --seconds 60` with the room confirmed empty:
  `max(motion1, motion2)` measured **mean=0.49, sigma=0.027, max=0.58** over 296 samples
  — roughly **4x the 0.12 default**, confirming the code comment in `node-fusion.ts`
  that this value is an uncalibrated placeholder was accurate, and the actual ambient
  noise floor in this room is far higher than assumed.
- Restarted the server with `PHANTOM_MOTION_THRESHOLD=0.6` (~mean+4·sigma margin above
  the measured empty-room ceiling). This is **only set for the current process via env
  var** — not yet persisted to any config/startup script, so it will revert to the 0.12
  default on the next `npm run dev` unless the operator sets it explicitly (see
  Recommendations).

### 2. Static presence detection — CONFIRMED WORKING (with corrected threshold)

- With the user standing near the boards, `targetState.target_visible=true`,
  `state="moving"`→settling, `confidence` up to ~0.92, `node_mode="fused_two_node"`
  (both boards live and fusing).

### 3. Movement tracking — PARTIALLY OBSERVED, not a clean deliberate test

- `radialTarget.balance` was observed oscillating continuously between ~0.32 and ~0.62
  over an extended period while the user was near the desk — consistent with the fusion
  math responding to real motion — but this was incidental movement, not a deliberate
  walk-the-full-axis test. **Not yet cleanly verified end-to-end.**

### 4. Vitals gate (new WP-16 firmware path) — NOT VERIFIED

- `vitalSigns.vitalsReliable` stayed `false`/absent throughout the session.
- Inconclusive rather than a failure: the test never included a genuine sustained-stillness
  window (the room had ongoing motion — see finding 5 — and no deliberate 60s-still
  segment was completed before the test was cut short per operator decision).
- **The WP-16 firmware gate itself remains unverified against real hardware.**

### 5. NEW FINDING — Fan in the room defeats the two-node motion gate (fusion layer, not firmware)

- After the threshold fix, a second empty-room check (user confirmed out of the room)
  *still* showed a confident false target (`state="moving"`, `confidence≈0.87`).
- Verified the server was genuinely running the corrected threshold (live `config`
  broadcast confirmed `fusedTargetMotionThreshold: 0.6`), ruling out a config-revert bug.
- User confirmed a fan was running in the room. This is a real, reproducible false
  positive: **`server/lib/node-fusion.ts`'s presence gate (`fuseTwoNodeTarget`) is purely
  a raw amplitude-perturbation threshold with no periodicity/tonal-motion discrimination**
  — unlike the firmware's WP-16 gate, which only judges respiratory periodicity for the
  *vitals* path, not the two-node target/motion detection itself.
- This means `DEFAULT_MOTION_THRESHOLD`'s own docstring requirement — *"validated
  against a negative control: a fan/curtain must be REJECTED"* — has **never actually
  passed**, and now has live evidence of failing. This is a distinct, additional gap from
  the WP-16 firmware mitigation (which only applies once a target/presence is already
  established and vitals are being evaluated).
- **Retested with the fan turned off**: ran a bounded 25-second sample of `targetState`
  with the room otherwise empty. Result: **clean** — `states_seen: ["none"]`,
  `non_none_samples: 0` (0%), `max_confidence: 0` for the entire window. This confirms
  the fan was the actual source of the false positive, not a residual threshold or
  config problem — with it off, the recalibrated `PHANTOM_MOTION_THRESHOLD=0.6` gives a
  genuinely clean empty-room negative control.
- The underlying gap remains real and unfixed: the two-node fusion gate still has no
  fan/tonal-motion rejection of its own. This test only confirms the *current* room is
  clean *without* the fan running — a fan (or similar periodic mechanical vibration)
  anywhere in range would still defeat detection, since nothing in `node-fusion.ts`
  discriminates it from a real person. See Recommendation 2 below.

## Artifacts

- Session recording: `data/sessions/live_hw_verify_20260720_v2_2026-07-20T12-04-29-536Z.csv`
- Auto-generated session report: `data/sessions/live_hw_verify_20260720_v2_2026-07-20T12-04-29-536Z.json`
  / `.pdf`
- Empty-room calibration run: 296 samples / 60s, mean=0.49 sigma=0.027 max=0.58 (not
  separately saved to a file — captured in this report and in this session's transcript).

## Recommendations / Follow-ups

1. **Persist the corrected motion threshold.** Set `PHANTOM_MOTION_THRESHOLD=0.6` (or
   re-calibrate per-deployment) in whatever startup mechanism is actually used
   (`.env`, launch script, or documented operator step) — the current fix is
   process-local and will be lost on the next restart.
2. **Add fan/tonal-motion rejection to the two-node fusion gate**, not just the firmware
   respiratory gate. This is a new, distinct finding from WP-16 — the motion-only
   presence gate in `node-fusion.ts` needs its own negative-control-passing mechanism
   (e.g. periodicity/regularity discrimination analogous to WP-16, or requiring
   corroboration from the firmware's own presence flag rather than raw motion alone).
3. **Complete the deliberate movement + vitals tests** that this session didn't finish:
   a clean walk-the-axis test with the room otherwise controlled, and a genuine 60s
   stillness window (with the fan off) to verify the WP-16 vitals gate against real
   hardware for the first time.
4. ~~Re-run the empty-room negative control with the fan off~~ **DONE** — confirmed
   clean (see Finding 5 retest above). Still outstanding: a longer/repeat clean-room
   confirmation over more than 25s, and Recommendation 2 (actual fan rejection in the
   fusion gate) remains unimplemented — this retest only proves today's room is clean
   *without* the fan, not that the gate is robust to one in general.
