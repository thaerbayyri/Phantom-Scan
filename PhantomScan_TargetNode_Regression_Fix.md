# Phantom Scan — Target-Node Regression Investigation

**Date:** 2026-08-07
**Scope:** Investigate a reported regression ("the target node that should be visible on the live dashboard is no longer showing up") suspected to follow the PS-GAP-MUSIC-001 fix session.
**Outcome: could not reproduce.** No code change was made. This report documents exactly what was tried and why each of the four prime suspects was ruled out with evidence, per the explicit instruction to report honestly rather than patch a guess.

---

## 1. Baseline

```
> npx tsx --test server/**/*.test.ts
ℹ tests 191 / pass 191 / fail 0

> python -m pytest tests/
========== 86 passed, 1 skipped, 7551 warnings in 76.17s (0:01:16) ===========
```
Identical to the MUSIC fix session's exit state — no drift since that session ended.

## 2. Bisection note

Nothing is committed yet — the fix-all, follow-up, and MUSIC-fix sessions are all still uncommitted working-tree changes stacked on `git log`'s `920595d`. `git log` therefore has no commit boundary to bisect against. Instead I bisected by *file*: I know exactly which files the MUSIC session touched (`server/lib/signal-processing.ts`, `server/lib/signal-processing.test.ts`, `client/src/components/dashboard/aoa-spectrum.tsx`, `client/src/components/dashboard/metrics-panel.tsx`) versus everything else (from earlier sessions, already exercised through two subsequent full test-suite passes with no reported issue). The investigation below focuses on the MUSIC session's diff specifically, as instructed.

## 3. Reproduction attempts (all real data, no synthetic substitutes)

**App boot check:** `npm run dev` started cleanly (`serving on port 5001`, no crash, no unhandled exception) — ruled out a startup-level break. `npx tsc` (project-wide typecheck) passes with no errors.

**Real-data pipeline replay:** Since no live ESP32 hardware or browser session was available, I wrote a script that replays real recorded CSI (`h1_re/h1_im/h2_re/h2_im` — genuine ESP32 captures, not synthetic) row-by-row through the **exact production functions** the MUSIC session touched, in the exact order `processFrame()` calls them: `BackgroundSubtractor.process()` → rolling 16-sample `sampleBuffer` → `computeMUSICSpectrum()` → the point-cloud generation block (`websocket.ts`'s `maxPower`/`pThreshold` logic, reproduced verbatim) → `TrackingProcessor.process()`. This exercises the entire MUSIC→point-cloud→tracked-target chain a live tick actually runs.

Replayed against **5 diverse real sessions** — fused-two-node and single-node modes, busy and quiet, fan-present and fan-off — covering **11,244 ticks total**:

| Session | Mode(s) | Ticks | Empty MUSIC spectra | Tracked target = null |
|---|---|---|---|---|
| `test_scan_csi_data_from_esp_2026-07-17T16-48-16-206Z.csv` | fused_two_node | 4,985 | 0 | 0 |
| `emty_room_with_fan_2026-07-23T12-17-51-741Z.csv` | fused_two_node | 4,985 | 0 | 1 |
| `empty_room_fan_off_20260720_2026-07-20T14-13-48-842Z.csv` | fused_two_node | 450 | 0 | 0 |
| `scan_01_test_2026-07-07T18-34-19-672Z.csv` | single_node | 4,985 | 0 | 0 |
| `emty_2026-07-20T18-21-17-566Z.csv` | single_node | 824 | 0 | 0 |

**Zero empty spectra across all 11,244 ticks.** Measured `inputPower` (the quantity Fix 3's `< 1e-12` degenerate-input guard checks) ranged from ~21,000 to ~68,900 across every session — roughly 16 orders of magnitude above the guard's threshold. Real ESP32 raw I/Q amplitude values (roughly ±127, int8) squared and summed over a 16-sample window never come remotely close to triggering the degenerate-empty path, even in the quietest fan-off empty-room capture. **The empty-spectrum path added by the MUSIC fix does not appear to be reachable by real hardware data at all**, at least not in any of the 5 sessions tried.

I specifically included single-node-mode sessions because that's the one place `computeMUSICSpectrum`'s downstream output (`hasTrackedTarget`) is load-bearing for *presence itself* (ADR-057's gate), not just position — fused-two-node mode's primary target position doesn't depend on the MUSIC/tracking chain at all (`fuseTwoNodeTarget` uses amplitude-balance, unrelated math). Even there, tracked target was null in only 1 tick out of 5,809 single-node ticks replayed, and that one null tick has no connection to the empty-spectrum path (spectrum was non-empty; it was an ordinary `maxEnergy` miss, the same mechanism that existed long before this session).

## 4. Suspects checked

1. **Empty-spectrum handling downstream (`peak.angle`, `spectrum[0]`, etc.)** — grepped every consumer of `isarFrame`/`spectrum`/`peakAngle` in the client: only `aoa-spectrum.tsx` and `metrics-panel.tsx`. Both already guard correctly (`!frame || frame.spectrum.length === 0` and `isarFrame ? ... : "0.0"` respectively) — pre-existing guards, unmodified by the relabeling. No unguarded access found anywhere. **Ruled out** — both by code inspection and by the empirical finding that the empty case never actually triggers on real data.
2. **Multi-snapshot buffer sizing / minimum fill level** — the fill-level gate (`sampleBuffer.length >= config.arrayLength`, still 16) is unchanged by the MUSIC fix; only what happens *after* the buffer is full changed. Replay confirms `computeMUSICSpectrum` produces real (non-empty) output from the very first eligible tick in every session tested (`firstNonEmptyTick: 1` in every run). **Ruled out.**
3. **UI relabeling side effects** — re-read the exact diff: text, color, marker size/symbol, axis title, and hover template strings changed; no prop names, conditional render logic, or `data-testid` values changed (`metric-peak-aoa` preserved). `npx tsc` passes. **Ruled out** as a structural break; it's cosmetic-only.
4. **Which element is actually missing** — could not get clarification on whether "target node" means the position marker, a node-online badge, or something else, since no live session/screenshot was available this round. Searched the client for a dedicated node-status/badge component (`grep -rln "N1.*online\|NodeStatus\|node-status"`) and found none by that name — "target" terminology in this codebase consistently refers to the detected-person position marker (`radialTarget`/`TrackedTarget`/`currentTargetIdentity`), which is what the reproduction above tested end-to-end.

## 5. Conclusion

**I could not reproduce the reported symptom.** Five real recorded sessions, both node modes, 11,244 replayed ticks through the exact production functions the MUSIC session modified, zero instances of the failure mode any of the four suspects predicted. The app boots and typechecks cleanly. No code was changed this session — there is nothing to verify with a before/after test, and adding a "fix" for an unconfirmed defect would risk masking a real but different problem, or introducing an unnecessary change to code that just went through heavy scrutiny in the MUSIC fix session.

**What would help find the actual cause:**
- A screenshot or exact description of which dashboard element is missing (position marker vs. a status badge vs. something else), and whether it's missing always or intermittently.
- Browser console output at the time of the symptom (a client-side exception wouldn't show up in any of my server-side/pipeline-level checks).
- Whether this was observed on live ESP32 hardware or in the browser against replayed/demo data, and if the latter, which session/demo path was used — that would let me replay the *exact* same data rather than a representative sample.
- If it's reproducible, the simplest next step is `npm run dev` plus a browser open to `localhost:5001` (or whichever port it binds — `5000` was busy in this environment) while watching the browser console, since that's the one thing this investigation couldn't do in this environment.

**Explicit confirmation:** the MUSIC correctness fix from the prior session (Gram-Schmidt deflation orthogonalization, multi-snapshot covariance averaging, honest empty-spectrum handling) was **not reverted, weakened, or otherwise touched** in this investigation.
