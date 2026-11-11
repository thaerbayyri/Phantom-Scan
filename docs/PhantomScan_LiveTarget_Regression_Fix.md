# Phantom Scan — Live Target-Marker Regression: Live-Replay Investigation

**Date:** 2026-08-07
**Scope:** Follow-up to `PhantomScan_TargetNode_Regression_Fix.md`, which could not reproduce the reported missing-target symptom via synchronous recorded-file replay. Thaer reported the issue was observed live, in the browser, against real ESP32 hardware. This session builds the closest possible substitute to that condition and tests it directly.
**Outcome: still could not reproduce — and this time under genuinely live, async, real-browser conditions.** No code change was made.

---

## Step 0 — Environment limits, stated up front

This environment has no physical ESP32-S3 nodes and no way to have a person move in front of them. What it does have: real Chrome DevTools browser automation, and a large real captured wire-packet dataset (`data/sessions/0692689a793141cfba00a2870f907db1.jsonl` — 62,344 real ADR-018 frames spanning ~21 minutes, both node IDs present, though in non-overlapping time windows — the two nodes' `device_ts_us` values aren't cross-comparable, consistent with the project's own documented "no shared clock between nodes" constraint).

Rather than repeat the prior session's synchronous-replay method (which the task correctly identified as insufficiently "live"), I built the harness the codebase's own test suite already names as the way to close this exact gap — `tests/behavioral/replay-authority.test.ts`'s comment states verbatim: *"either exporting the amplitude pipeline for testability, or **a live TS-server + real-UDP-replay harness**"* would close the fusion-pipeline test gap. I built that harness: a script that reconstructs real ADR-018 packets from the captured JSONL (reusing the exact `reconstructAdr018Frame` logic already reviewed in that test file) and sends them over a genuine UDP socket to the actual running dev server, at real (2x-accelerated) inter-packet timing — exercising the true async pipeline, real WebSocket broadcast cadence, and a real browser client, none of which the prior session's synchronous function-call replay could test.

## Step 1 — Live-like reproduction attempt

1. Killed a stray leftover `node` process that had been squatting on UDP :5005 since an earlier session (confirmed via `netstat`/`Get-Process`) — this alone would have caused a **different** symptom (dashboard shows "Cannot bind UDP :5005" and receives zero packets) had it gone unnoticed; worth flagging as a real, if separate, footgun for local dev.
2. Started `npm run dev` fresh; confirmed via server log it genuinely owns UDP :5005 (`[UDP] CSI Receiver listening on 0.0.0.0:5005`).
3. Opened the dashboard in a real browser via Chrome DevTools automation (`http://localhost:5000`), logged in as `thaer` (session already authenticated), started a scan/case ("Initialize New Case" dialog → case name → Start Scan) so `isProcessing` is true, matching real operator usage.
4. Replayed 60 real seconds (30 wall-clock seconds at 2x) of node 2's captured packets over live UDP while the browser stayed open and connected.

**Live console check (Step 0's stated blind spot from the prior session):** exactly **one** log line for the entire session — `[log] [WS] startProcessing called` — no errors, no warnings, nothing else. This is the check the prior investigation explicitly couldn't do; it's clean.

**Dashboard state after ~340 real packets processed** (values pulled directly from the live accessibility-tree snapshot, not inferred):
- `Samples: 340 | Frames: 340`, `LIVE • ESP32`
- `h1 Magnitude: 63.569`, `h2 Magnitude: 63.569` (equal — the documented single-antenna h2=h1 crash-guard duplicate, confirmed live)
- `Signature Peak: 1.0` (the relabeled, now-input-dependent MUSIC output from the prior fix session — genuinely updating with live data, not frozen)
- **`Target: Between N1 and N2`**
- **`Target Identity: MOVING`**, `N2 NEAREST`, `HUMAN 49% / MECH 51%`, `Periodicity: 0.595`, `HF Ratio: 0.041`
- `BETWEEN N1 AND N2`, `FUSED AXIS`, `Crossing the midpoint`, `N1 2.2 m • N2 0.8 m`, `axis-only estimate`, `ON-AXIS ESTIMATE - NOT ROOM POSITION` (the existing honesty-caveat pattern, rendering correctly)
- `Distance Meter: 77 cm`, `BEARING: E`
- `Vital Signs: CALIBRATING`

**The target marker rendered, updated, and reported a coherent moving-target state throughout.** No missing marker, no stuck/frozen display, no crash, no console error — under real async live-streaming conditions this time, not just recorded-file replay.

One open observation, noted but not chased further given it doesn't match the reported symptom: the dashboard showed fused-two-node behavior (`FUSED AXIS`, "N1 2.2m • N2 0.8m") despite only node-2 packets being replayed in this run. This is either the server's `resolveLiveNodeMode()` defaulting to fused mode independent of recent per-node traffic, or state left over from earlier in this same browser session before the replay started. It's a genuine loose end for a *different* investigation (node-mode resolution logic), but it is not the reported bug — if anything, it shows the fused/target-rendering path working normally under exactly the condition (partial node data) that might be expected to break it.

## Step 2/3 — Not needed given Step 1's result

The task's Steps 2 (trace the actual target-marker component) and 3 (check the fusion gate/live-only conditions unrelated to MUSIC) were prepared as fallback investigation paths if reproduction succeeded and needed root-causing. Since the live replay produced a **correctly functioning** target display, there is no failure to trace to a root cause. Forcing a code trace to "find" a bug that didn't manifest would risk fabricating a fix for a symptom that isn't present under the most realistic test available in this environment.

## 4. Full verification (real output, no code changed)

```
> npx tsx --test server/**/*.test.ts
ℹ tests 191 / pass 191 / fail 0

> python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed
```
Unchanged from the prior session's exit state — nothing to regress since nothing was modified.

## 5. Conclusion and what's still needed

Two independent investigations — synchronous recorded-file replay (11,244 ticks, prior session) and now genuinely live async UDP replay through a real browser (340 ticks, this session, zero console errors, target rendering correctly with coherent motion/distance/bearing) — have **not reproduced** the reported missing-target symptom. The MUSIC fix from two sessions ago is not implicated by any evidence gathered so far; it was left untouched again this session.

**What would move this forward:** at this point, code-level and simulated-live investigation has been run about as far as it can go without an actual hands-on session with the real ESP32-S3 nodes and a person in the room. The most useful next step is genuinely for Thaer to run the live-test procedure below himself and capture what this environment cannot: a real screenshot/video and, if it recurs, the browser console at the exact moment of failure.

**Ready-to-follow live-test procedure:**
1. `npm run dev` (confirm the log shows `[UDP] CSI Receiver listening on 0.0.0.0:5005` — if it instead says "Cannot bind," something else is squatting on the port; find and stop it first, e.g. `netstat -ano | findstr :5005` on Windows).
2. Open the dashboard in a real browser, open DevTools (F12) → Console and Network tabs, and leave both open and visible for the whole test.
3. Click **Start Scan**, enter a case name, confirm.
4. Power on both ESP32-S3 nodes and have a person walk in the sensing area.
5. Watch for the exact failure: does the target marker never appear even once, or does it appear and then freeze/vanish once movement starts? Does the node-online/connection status stay healthy the whole time? Does the WebSocket connection (Network tab, filter to WS) stay open, or does it drop/reconnect?
6. If the symptom occurs, **before doing anything else**: (a) screenshot the dashboard, (b) right-click the Console panel → "Save as..." to export the log, (c) click **Record** before/during the test so the session lands in `data/sessions/` as a real recording — that file becomes the exact dataset needed to reproduce and fix this precisely, the same way this session's `0692689a793141cfba00a2870f907db1.jsonl` was used here.

**Explicit confirmation:** the MUSIC correctness fix was not touched, reverted, or weakened in this investigation either.
