# 06 — Test report (T0 baseline and final state)

**Provenance.** Commands exactly as the repo documents them in `package.json` (`npm test` → `tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts scripts/accuracy/__tests__/**/*.test.ts`; `python -m pytest tests/ -q` with the repo `.venv`, Python 3.13.15, pytest 9.0.3). Run 2026-11-02 on branch `feat/two-node-radar-live-detection`, HEAD `744ce43` (dirty working tree: Thaer's uncommitted edits, unchanged by this task — see tracked-diff hash below). Outputs below are pasted verbatim from files saved at run time.

## Summary

| suite | before (T0) | after (this task's files added) |
|--|--|--|
| TypeScript, full (`npm test`) | **407 pass, 0 fail** (wall 18 s, reported duration 14.7 s) — matches the last known 407 | **407 pass, 0 fail** |
| Python, full (`pytest tests/`) | **cannot complete: 2 collection errors** (`tests/test_count_model.py`, `tests/test_train_activity.py`: `ModuleNotFoundError: No module named 'sklearn'`) | same 2 collection errors |
| Python, all collectable files (those 2 ignored) | **148 passed, 5 skipped** (58 s) | **190 passed, 5 skipped** (68 s) — +42 = 10 inventory, 15 features, 5 drift, 12 two-node tests |
| F1/F2 (`tests/test_invariants.py -k 'test_f1 or test_f2'`) | 3 passed | 3 passed |
| AI-firewall tests in `server/lib/websocket.test.ts` (name pattern `F1\|AI\|advisory\|firewall`) | 11 passed | 11 passed |

**Not as expected.** The last known Python result (163 passed / 5 skipped on 25 Oct) could not be reproduced: `scikit-learn` is installed in none of the three interpreters on this machine (`.venv` 3.13.15, system 3.13.15, WindowsApps 3.11.9) and installing packages was out of scope. The 15-test difference (163 − 148) is *probably* the two uncollectable files `[UNVERIFIED]`. **The slow count-CNN training test could not be run, so its duration is not measured** (PS-EVAL-001). Python results therefore cannot be called a green *full* suite.

**Side effect of running the repo's own TS suite:** it appended to the gitignored `data/audit/audit-current.jsonl` (auth tests; last line 18:50:27Z, i.e. during the final `npm test`). Not part of this task's code (PS-EVAL-019).

## git state

### `git status --short` before (38 lines)

```text
 M README.md
 m "ai model and densepose/model"
 M client/src/components/dashboard/RadialScene.tsx
 M client/src/components/dashboard/ai-advisory-panel.tsx
 M client/src/components/dashboard/point-cloud-3d.tsx
 M client/src/components/dashboard/top-bar.tsx
 M client/src/components/dashboard/vitals-monitor.tsx
 M client/src/hooks/use-websocket.ts
 M client/src/pages/dashboard.tsx
 M data/sessions/_index.json
 M firmware/esp32-csi-node/CMakeLists.txt
 M firmware/esp32-csi-node/main/Kconfig.projbuild
 M firmware/esp32-csi-node/main/csi_collector.c
 M firmware/esp32-csi-node/sdkconfig.defaults
 M server/lib/target-presentation.test.ts
 M server/lib/target-state.test.ts
 M server/lib/target-state.ts
 M server/lib/websocket.test.ts
 M server/lib/websocket.ts
 M shared/schema.ts
 M shared/target-presentation.ts
?? client/src/components/dashboard/demo-banner.tsx
?? client/src/hooks/use-persisted-flag.ts
?? client/src/lib/demo-banner.test.ts
?? client/src/lib/demo-banner.ts
?? client/src/lib/stored-flag.test.ts
?? client/src/lib/stored-flag.ts
?? client/src/lib/vitals-status.test.ts
?? client/src/lib/vitals-status.ts
?? docs/esp32s3-framework-comparison-report.md
?? firmware/esp32-csi-node/version.txt
?? server/lib/demo-replay.test.ts
?? server/lib/demo-replay.ts
?? server/lib/demo-session.test.ts
?? server/lib/demo-session.ts
?? server/lib/demo-walker.test.ts
?? server/lib/demo-walker.ts
?? server/lib/websocket-demo.test.ts
```

### `git status --short` after — diff against before

```text
@@ -31,0 +32,2 @@
+?? reports/
+?? scripts/presence_eval/
@@ -38,0 +41,4 @@
+?? tests/test_presence_eval_drift.py
+?? tests/test_presence_eval_features.py
+?? tests/test_presence_eval_inventory.py
+?? tests/test_presence_eval_twonode.py
```

Tracked-file integrity: `git diff | sha256sum` before = `b9887e0d73591d69c977008fd50ff4fb3552e584dda380aa43ee123d6499db2c`; after = `b9887e0d73591d69c977008fd50ff4fb3552e584dda380aa43ee123d6499db2c` (identical → no tracked file changed by this task, including by the test runs).

## T0 — before

### TypeScript full suite, before (`npm test`, complete output)

```text

> csi-signal-processing@1.2.0 test
> tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts scripts/accuracy/__tests__/**/*.test.ts

✔ no banner when the demo is idle or unknown (4.8255ms)
✔ simulated demo says it is scripted and not a measurement (4.1874ms)
✔ replay demo names the recording and warns it may show no target (0.5777ms)
✔ replay demo reports calibration progress while the baselines warm up (0.5794ms)
✔ loading a recording is shown as such (0.342ms)
✔ a failed demo start surfaces the reason as an error banner (0.2613ms)
✔ k = -ln(1-alpha)*60 table matches the tuned per-frame alphas (2.3761ms)
✔ DECAY_RATES.positionFusedNearScale approximates positionFar - positionFusedBase (0.2693ms)
✔ dampVector3 converges to the same result regardless of step count for a fixed elapsed time (0.7795ms)
✔ dampScalar and dampAngle share the same frame-rate-independence property (0.5073ms)
✔ a naive fixed-alpha-per-frame lerp is NOT frame-rate independent (the bug this file fixes) (0.2979ms)
✔ dampVector3 clamps large deltas so a multi-second stall does not snap instantly (0.2117ms)
✔ dampAngle wraps across the +-PI boundary the short way (0.2423ms)
✔ a missing key falls back to the default (2.2945ms)
✔ stored values round-trip (0.3611ms)
✔ an unrecognised stored value falls back to the default (0.2287ms)
✔ blocked or missing storage never throws and uses the default (0.3891ms)
✔ no target state at all reads NO TARGET (3.984ms)
✔ an invisible target reads NO TARGET even if stale vitals are still around (0.4381ms)
✔ a visible live target with no vitals yet reads CALIBRATING (0.3239ms)
✔ a visible live target with a vitals reading shows no badge (0.2673ms)
✔ simulated demo vitals are always flagged SIMULATED (0.2486ms)
✔ NO TARGET outranks SIMULATED when the simulated walker is not visible (0.2037ms)
✔ A1 — synthetic perfect match: matched present+absent regions score recall=1, FPR=0, F1=1 (2.4159ms)
✔ A2 — synthetic all-miss: system stays negative throughout a ground-truth-positive interval (3.8794ms)
✔ A3 — a stale-demotion bin during ground-truth-positive scores FN, not excluded (0.6455ms)
✔ A6 — a ground-truth log with zero present rows can never produce a TP, by construction (9.8931ms)
✔ parses present/absent/sync rows and resolves the sync marker (4.5084ms)
✔ rejects a row with an invalid label (0.8873ms)
✔ a log with zero present rows never reports positive at any sampled time (0.3842ms)
✔ groundTruthTimeBounds ignores sync rows and returns null when only sync rows exist (0.4378ms)
✔ A5 — a trial with node1 fps below the 20/node preflight is excluded from the campaign rollup with a named reason (15.3055ms)
✔ A5 — a degraded-only trial is excluded unless --allow-degraded is set (0.4229ms)
✔ A7 — every derived metric carries {value,status,evidence} (0.5886ms)
✔ A7 — assertMetricValueShape rejects a bare number or a status-less object (0.4475ms)
✔ A7 — buildTrialReport itself refuses a metrics object with a malformed field (0.4806ms)
✔ resolveAlignment recovers a known constant offset from a single sync event (1.9849ms)
✔ resolveAlignment recovers known offset and drift from two sync events (0.4818ms)
✔ A4 — resolveAlignment refuses with NoSyncMarkerError when no sync event exists (6.5325ms)
✔ generateOperatorSeed creates a verifiable scrypt hash (228.3389ms)
✔ AuditLogger writes and lists records in reverse chronological order (61.9522ms)
✔ AuditLogger accepts websocket-style request objects without req.get (24.1722ms)
✔ load path accepts operator files with npm banner noise before JSON (3371.1504ms)
✔ initializeAuth bootstraps first operator on loopback when seed file is missing (3232.1407ms)
✔ initializeAuth rejects first-operator bootstrap from non-loopback without token (12.1222ms)
✔ compassBearingRad: cardinal positions (3.111ms)
✔ bearingToCardinal: sector centers and boundaries (0.3931ms)
✔ bearingToCardinalLong matches short mapper sectors (0.2347ms)
✔ travelAngleToBearingRad: math angle to compass bearing (0.3473ms)
✔ headingVectorFromAngle: regression for motion-vector decode (0.2696ms)
✔ LLTF data index set excludes DC, the invalid first word, and the ±27..±32 guards (2.9996ms)
✔ reduceCsiFrame returns only data-subcarrier amplitudes from the LLTF block (0.9145ms)
✔ reduceCsiFrame keeps the subcarrier count constant across non-HT, HT and STBC frames (0.9123ms)
✔ reduceCsiFrame reads ESP-IDF imaginary-first byte order for the dominant subcarrier (1.3351ms)
✔ reduceCsiFrame falls back to every entry for short legacy/synthetic frames (0.3968ms)
✔ reduceCsiFrame uses the second antenna block for h2 when present (0.5133ms)
✔ parseDatasetStart accepts a valid request and derives the count from the label (1.6461ms)
✔ parseDatasetStart rejects unknown labels, unsafe ids and out-of-range counts (0.9615ms)
✔ recorder writes a header then frame rows under data/datasets/<room>/ (9.6506ms)
✔ recorder rotates to a new part file with its own header after maxFramesPerFile (50.0665ms)
✔ record is a no-op when not recording, and a second start is refused (17.2979ms)
✔ frames with non-finite amplitudes are skipped and counted, not written (34.3934ms)
✔ per-node frame counts are tracked for the operator (4.5544ms)
✔ stop() always closes the file and clears recording state even if the final flush fails (6.9978ms)
✔ a failed flush drops the pending buffer instead of growing without bound (3.7047ms)
✔ readClipHead keeps nodes 1-4, rebases time to the first frame and skips junk (116.7031ms)
✔ readClipHead stops after the requested number of seconds (12.7219ms)
✔ findDatasetFile matches the label and ignores .partN continuations (8.6052ms)
✔ loadReplayClip places the body after the calibration lead-in (21.8888ms)
✔ loadReplayClip reports a missing recording with an actionable error (10.7137ms)
✔ ReplayCursor emits each due frame exactly once, in order (0.5751ms)
✔ ReplayCursor loops back to the loop point instead of restarting calibration (0.5272ms)
✔ ReplayCursor reports a lap-local position for the progress display (0.377ms)
✔ sampleFromFrame stamps the sample with the current time and copies amplitudes (0.5695ms)
✔ synthetic demo publishes labelled walker frames and stops cleanly (11.6737ms)
✔ replay demo feeds recorded frames to ingest stamped with the current time (1.0583ms)
✔ replay demo reports running once calibration has elapsed and loops without re-calibrating (0.6431ms)
✔ replay demo exposes clip label and duration in its status (0.3152ms)
✔ a missing recording fails the start with a message and leaves the demo off (0.607ms)
✔ starting while a demo is already running is refused (0.3184ms)
✔ stopping while the recording is still loading discards the load (0.358ms)
✔ status updates are emitted on start, on phase change and about once per second (0.3578ms)
✔ walker stays inside the room for two full laps (4.9747ms)
✔ walker path is deterministic and loops seamlessly (1.4017ms)
✔ walker moves at the nominal speed and pauses at least once per lap (1.1819ms)
✔ walker frame is labelled synthetic end to end (2.3665ms)
✔ walker frame radialTarget is self-consistent with its position (1.8107ms)
✔ the node nearest the walker shows the most motion (0.7115ms)
✔ walker frame state follows the walker: moving while walking, idle while paused (33.6894ms)
✔ walker frame carries scripted vitals in a plausible, time-varying human range (27.6268ms)
✔ walker signal field covers the room grid with finite values (0.8432ms)
✔ FusedPositionKalman: repeated measurement at a fixed point converges near that point (2.7919ms)
✔ FusedPositionKalman: reports the origin with zero velocity before any update (1.2713ms)
✔ FusedPositionKalman: a single predict after a large gap is bounded by the dt ceiling, not the full elapsed time (0.5958ms)
✔ FusedPositionKalman: a single wild outlier tick is gated out, not applied (0.5093ms)
✔ FusedPositionKalman: getState always returns finite numbers (no NaN/Infinity propagation) (0.3856ms)
✔ FusedPositionKalman: reset returns to the zero-velocity origin state (0.5014ms)
✔ FusedPositionKalman: the first measurement initializes the state (no pull from the origin) (0.2287ms)
✔ FusedPositionKalman: process noise scales with gap length beyond the reference tick (0.3445ms)
✔ FusedPositionKalman: velocity variance shrinks by the PRE-update cross-covariance (0.3304ms)
✔ FusedPositionKalman: a real jump persisting 5+ ticks re-initializes instead of locking out (0.6034ms)
✔ FusedPositionKalman: filtering the real recorded session reduces mean tick-to-tick jitter on both axes (67.1872ms)
✔ FusedPositionKalman: filtering the real recorded session tracks the raw track tightly, except for rare gated outlier ticks (55.0066ms)
✔ FusedPositionKalman.constrain pulls an overshoot back into the box and removes outward velocity (0.7586ms)
✔ FusedPositionKalman.constrain caps speed while preserving direction (13.3786ms)
✔ join-groundtruth enriches live CSV rows via one sync marker and trace (4.7365ms)
✔ smoothing is time-constant based: same response after 0.6 s at 20 Hz and 50 Hz (5.1891ms)
✔ warm-up learns the empty-room level quickly, then rise ≈ 0 and tier absent (1.0094ms)
✔ motion well above the node's own baseline reaches present_moving only after the 0.4 s debounce (0.6705ms)
✔ rise is gain-invariant: a node with 3x amplitude gain produces the same rise (2.1843ms)
✔ baseline does not absorb a person while frozen (target held), so rise persists (3.7528ms)
✔ without freeze the slow baseline eventually adapts to a new static level (3.493ms)
✔ freeze is bounded: after the max freeze time the baseline adapts again (4.45ms)
✔ spikes above the smoothed level are excluded from the baseline update (9.7909ms)
✔ default tier thresholds are ordered still < moving < active (0.7417ms)
✔ room presence upgrades immediately but holds a downgrade for 1.5 s (0.9835ms)
✔ excess is the absolute rise above baseline, comparable across nodes with different baselines (0.7755ms)
✔ excess is never negative and is ~0 in a settled empty room (0.446ms)
✔ a noisy but empty room stays absent: the baseline must not sit at the lower noise edge (2.7921ms)
✔ a genuine sustained rise well above the noise is still detected (0.7851ms)
✔ z is the excess in units of the node's own empty-room fluctuation (1.5806ms)
✔ fuseNodeTargets: motion concentrated at node 3 centroids near node 3's anchor (14.5504ms)
✔ fuseNodeTargets: motion split evenly across all 4 nodes centroids near room center (1.3325ms)
✔ fuseNodeTargets: below-threshold motion at all nodes returns null (empty-room gate) (0.9309ms)
✔ fuseNodeTargets: confident mechanical classification suppresses an otherwise-passing energy gate (0.3215ms)
✔ r1 >> r2 places the target at node 1 (x ≈ -1.5) (0.7406ms)
✔ r1 ≈ r2 places the target at the midpoint (x ≈ 0, balance ≈ 0.5) (0.2276ms)
✔ r2 >> r1 places the target at node 2 (x ≈ +1.5) (0.2795ms)
✔ display bias preserves the midpoint exactly (0.1762ms)
✔ display bias pulls the target closer to node 1 when balance is low (0.2736ms)
✔ display bias pulls the target closer to node 2 when balance is high (1.337ms)
✔ empty room (motion below threshold) returns NO target — not a centered ghost (0.2527ms)
✔ fused target uses the configured presence threshold instead of the placeholder default (0.2019ms)
✔ zero perturbation returns NO target even if motion inputs are high (0.135ms)
✔ distToNearestNodeM is ~half the separation at the midpoint (0.1379ms)
✔ matrix motion: identical frames => zero motion (static room) (0.3463ms)
✔ matrix motion detects per-subcarrier oscillation the best-subcarrier scalar misses (0.2805ms)
✔ balance tracks the node with stronger per-subcarrier perturbation (0.3127ms)
✔ computeNodeMotionFromMatrix: constant amplitude => zero motion (0.2034ms)
✔ rising balance (positive axis velocity) => N2 approaching, N1 receding (0.1803ms)
✔ falling balance (negative axis velocity) => N1 approaching, N2 receding (0.1656ms)
✔ velocity inside the deadband keeps the previous trends (hysteresis) (0.6112ms)
✔ distanceM bookkeeping: balance splits the separation between the nodes (0.2136ms)
✔ contrast exponent widens balance vs the linear ratio; p=1 restores linear (0.3032ms)
✔ computeNodeMotionFromMatrix: saturates at 1.0 and uses the documented scale (0.1169ms)
✔ computeLinearBalance is the undecorated r2/(r1+r2) ratio (0.1496ms)
✔ balanceLinear on fuseTwoNodeTarget is invariant to the contrast exponent, unlike balance (0.1996ms)
✔ balanceLinear is 0.5 at the midpoint (0.1367ms)
✔ computeFallbackVelocity returns zero with no previous sample (first tick, never a spike) (0.1786ms)
✔ computeFallbackVelocity is linear in displacement for a fixed dt (no hidden multiplier) (0.1719ms)
✔ computeFallbackVelocity does not hardcode a 50ms tick — the same displacement over a longer real dt yields a smaller velocity (0.1526ms)
✔ computeFallbackVelocity floors dt so a near-zero interval cannot blow up velocity (0.1357ms)
✔ computeFallbackVelocity yields zero (never a spike) across a gap beyond the max threshold (0.1207ms)
✔ computeFallbackVelocity: invalidating prev (null) after a primary-tracker hit yields zero on the next fallback tick, not a diff across the skipped interval (0.14ms)
✔ computeGainNormalizedPerturbation cancels a per-node multiplicative gain (0.2527ms)
✔ computeGainNormalizedPerturbation returns 0 for a silent node without dividing by zero (0.1043ms)
✔ computeGainNormalizedPerturbation guards a non-finite or non-positive mean defensively (0.1651ms)
✔ FIXED (PS-BEHTEST-004): gain-normalizing r1/r2 restores balance ~= 0.5 under a 2x per-node gain asymmetry with identical real motion (0.3546ms)
✔ a COMMON gain applied equally to both nodes leaves balance unchanged (the bug was only the differential mismatch) (0.3277ms)
✔ hasSingleNodePresenceEvidence: no motion and no tracked cluster => no presence (empty room) (0.1326ms)
✔ hasSingleNodePresenceEvidence: real motion alone is sufficient evidence (0.1777ms)
✔ hasSingleNodePresenceEvidence: a tracked cluster alone is sufficient evidence (covers a real-but-stationary target) (0.1155ms)
✔ hasSingleNodePresenceEvidence: both signals present is still presence (0.0813ms)
✔ evaluateClassifierCorroboration: no classifier supplied => not_evaluated, never suppresses (0.1626ms)
✔ evaluateClassifierCorroboration: confident 'human' => confirmed, never suppresses (0.1557ms)
✔ evaluateClassifierCorroboration: confident 'mechanical' (humanProb <= threshold) => contradicted, suppresses (0.1422ms)
✔ evaluateClassifierCorroboration: borderline 'mechanical' (above the confident-reject bar) => inconclusive, does NOT suppress (0.1925ms)
✔ evaluateClassifierCorroboration: 'unknown' => inconclusive, does NOT suppress (0.0947ms)
✔ fuseTwoNodeTarget (a): energy gate passes + classifier 'human' => target present, corroboration confirmed (0.1704ms)
✔ fuseTwoNodeTarget (b): energy gate passes + confident 'mechanical' classifier => presence suppressed (null) (0.1216ms)
✔ fuseTwoNodeTarget (c): energy gate passes + 'unknown' classifier => target still present (not stricter than baseline) (0.1642ms)
✔ fuseTwoNodeTarget (c): borderline 'mechanical' (not confidently rejected) also falls back to baseline (0.1074ms)
✔ fuseTwoNodeTarget (d): energy gate fails => no target even with a confident 'human' classification (0.1346ms)
✔ fuseTwoNodeTarget: no classifier supplied at all => behavior is byte-for-byte the pre-Item-1 baseline (0.1217ms)
✔ wasSuppressedByClassifier: true only when energy gate passed AND classifier confidently vetoed (0.2066ms)
✔ hasSingleNodePresenceEvidence (a): energy evidence + 'human' classifier => presence (0.1059ms)
✔ hasSingleNodePresenceEvidence (b): energy evidence + confident 'mechanical' classifier => suppressed (0.0988ms)
✔ hasSingleNodePresenceEvidence (c): energy evidence + 'unknown' classifier => falls back to baseline (still present) (0.0824ms)
✔ hasSingleNodePresenceEvidence (d): no energy evidence => no presence even with a confident 'human' classifier (0.0953ms)
✔ hasSingleNodePresenceEvidence: omitting classifier entirely is unchanged from the pre-Item-1 signature (0.0978ms)
✔ computeAgcNormalizedPerturbation: a static pattern under per-frame gain swings reads as ~no motion (0.9778ms)
✔ computeAgcNormalizedPerturbation: a changing multipath shape reads as motion and is gain-invariant (0.3756ms)
✔ computeAgcNormalizedPerturbation: degenerate input returns 0 (0.1381ms)
✔ computeRadialTrends: walking toward node 3 approaches 3 and recedes from 1 (0.4036ms)
✔ computeRadialTrends: speed inside the deadband is stable for every node (0.3515ms)
✔ computePositionUncertaintyM shrinks with stronger evidence and grows when one node dominates (0.3681ms)
✔ computePositionUncertaintyM is bounded by the room size and never below a floor (0.3052ms)
✔ distanceToSegment: projects onto the segment and clamps at the ends (0.185ms)
✔ distanceToSegment: a zero-length link (node next to the router) is a point (0.0882ms)
✔ link model: person near node 1 or node 2 is placed on that side, not at nodes 3/4 (31.4856ms)
✔ link model: person near node 3 and node 4 is placed on the far wall (8.6331ms)
✔ link model: beats the plain anchor centroid for people near the router (7.3201ms)
✔ link model: position stays inside the room bounds even with degenerate input (3.5454ms)
✔ link model: without a router the result is exactly the old anchor centroid (1.1775ms)
✔ locateByLinkModel: returns null when there are no usable shares (0.5832ms)
✔ getAnatomicalRoot uses hip midpoint when both hips are present (2.4571ms)
✔ getAnatomicalRoot falls back to shoulder midpoint when hips are absent (0.3426ms)
✔ getAnatomicalRoot falls back to centroid when neither hips nor shoulders present (0.2386ms)
✔ getAnatomicalRoot handles a single keypoint without division error (0.2358ms)
✔ getAnatomicalRoot handles an empty keypoint array safely (0.2137ms)
✔ hip midpoint maps to exact target.x/z when all hips are on the root (0.31ms)
✔ nose joint offset is preserved relative to target root (0.2945ms)
✔ left wrist offset is correct and under clamp (0.5 m from root, within 0.8 m) (0.2286ms)
✔ outlier keypoint > POSE_CLAMP_M is clamped to POSE_CLAMP_M (0.3677ms)
✔ outlier in negative direction is clamped to -POSE_CLAMP_M (0.3005ms)
✔ y is never clamped — absolute height is preserved regardless of offset (0.2092ms)
✔ skeleton root equals target position at "near N1" (0.2955ms)
✔ skeleton root equals target position at "midpoint" (0.1403ms)
✔ skeleton root equals target position at "near N2" (0.1339ms)
✔ skeleton root equals target position at "off-axis" (0.144ms)
✔ skeleton root tracks target as it moves from N1 to N2 in 5 steps (0.2555ms)
✔ limb offset is stable across target positions (not amplified by movement) (0.2339ms)
✔ double-offset bug is NOT present: adding target.x twice would produce wrong position (0.2143ms)
✔ recording CSV header includes the positional fidelity columns (22.9484ms)
✔ raw_perturbation_nX is exported unclamped, unlike the saturated motion_nX it's derived from (6.5719ms)
✔ visible fused rows reuse the same displayed position contract (0.5594ms)
✔ gate-closed rows suppress position and distance fields atomically (0.348ms)
✔ serialized CSV carries metadata with the explicit x/x_disp contract (0.8778ms)
✔ recording rows carry the room tier, per-node excess, and real N3/N4 trends for fused_room (0.3597ms)
✔ recording rows without room extras keep the legacy trend source and leave the new columns empty (0.2864ms)
✔ defaults reproduce the historical 4 m x 6 m corner layout (25.2948ms)
✔ parseRoomGeometry accepts a valid config and keys anchors by numeric node id (4.6836ms)
✔ parseRoomGeometry rejects non-finite / oversized dimensions (2.7971ms)
✔ parseRoomGeometry rejects node ids outside the canonical 1-4 set (0.4424ms)
✔ parseRoomGeometry rejects anchors outside the room bounds (0.4248ms)
✔ parseRoomGeometry rejects 3+ collinear anchors (no 2-D localization possible) (0.3378ms)
✔ geometricDiversity is 1 for a square layout, ~0.8 for 4x6 corners, low when 3 nodes share a corner (0.5191ms)
✔ loadRoomGeometry falls back to defaults when no config file exists (0.2962ms)
✔ loadRoomGeometry reads PHANTOM_ROOM_CONFIG and fails fast when that file is missing (0.4912ms)
✔ loadRoomGeometry reports invalid JSON with the file path (0.6869ms)
✔ an optional router position is parsed and returned (0.4384ms)
✔ no router means no link model: router is undefined (0.3004ms)
✔ a router far outside the room is rejected with a clear message (0.9407ms)
✔ a router with an unknown field is rejected (strict schema) (0.6198ms)
✔ MUSIC: spectrum has the requested length and finite power at every bin (6.4925ms)
✔ MUSIC: fewer than 3 samples returns an empty spectrum (guard clause) (2.2824ms)
✔ MUSIC: identical covariance input yields an identical spectrum (deterministic eigen start) (1.9072ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): clean steering input resolves its true synthetic angle (21.0732ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): unrelated random inputs produce meaningfully different spectra (24.3221ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): all-zero (degenerate) input returns an empty spectrum, not a fake curve (0.7525ms)
✔ findSpectrumPeak: empty spectrum returns the documented sentinel (0.2657ms)
✔ HampelFilter: passes normal values through unchanged (0.4877ms)
✔ HampelFilter: replaces a hard outlier spike with the window median (0.263ms)
✔ HampelFilter: values before the window fills pass through untouched (0.3972ms)
✔ MicroDopplerClassifier: a strong periodic (mechanical) signal classifies as mechanical (8.5841ms)
✔ MicroDopplerClassifier: an aperiodic low-frequency signal does NOT classify as mechanical (6.9332ms)
✔ MicroDopplerClassifier: returns last state (label unknown) until the buffer fills (0.2657ms)
✔ PDPRanger: returns the RSSI path-loss fallback before the CSI buffer fills (0.6813ms)
✔ PDPRanger: RSSI fallback clamps to the documented [0.3m, 8m] bounds (1.6152ms)
✔ PDPRanger: steady CSI input produces a finite, bounded distance estimate (3.9764ms)
✔ BackgroundSubtractor: a constant (static) channel is fully suppressed (0.7543ms)
✔ BackgroundSubtractor: a step change appears in the dynamic residual (0.4159ms)
✔ BackgroundSubtractor: setWindowSize trims an over-full window without crashing (4.4502ms)
✔ MotionGate: constant amplitude (empty room) never reports motion (2.0356ms)
✔ MotionGate: auto-calibrates threshold = 3*sigma from the first 100 samples (1.3291ms)
✔ MotionGate: large amplitude swings after calibration trigger motionDetected (1.6925ms)
✔ MotionGate: a manual threshold overrides the calibrated one (1.3495ms)
✔ MotionGate: reset returns to the uncalibrated default threshold (6.1306ms)
✔ live esp32 degraded targets still present a live position marker (2.5075ms)
✔ truthful live targets remain fully visible (0.2893ms)
✔ stale or cleared targets do not present a live position (0.3152ms)
✔ fused live targets expose the on-axis honesty caveat (1.5062ms)
✔ single-node live targets expose the distinct bearing caveat (0.3183ms)
✔ caveat clears together with stale or missing live position (0.2714ms)
✔ live esp32 truthful targets stay on the abstract marker path (0.259ms)
✔ truthful live targets do not use volumetric presentation (0.3316ms)
✔ illustrative body is allowed only where the live position marker is allowed (0.3042ms)
✔ illustrative body is withheld for mechanical targets, empty rooms and aged-out targets (0.6354ms)
✔ illustrative body never re-enables the volumetric/AI-pose gate (0.1719ms)
✔ axis motion vector only renders when projected speed is present (0.1968ms)
✔ fused targets summarize the between-node position and destination node (2.3514ms)
✔ fused midpoint targets call out midpoint hold on the node axis (0.3956ms)
✔ fused targets near the second node identify the far-side destination (0.3488ms)
✔ single-node targets summarize as around the nearest node (0.2907ms)
✔ single-node moving label uses compass cardinal from travel angle (0.4194ms)
✔ isSampleFresh accepts a sample within the live stale window (1.8952ms)
✔ isSampleFresh drops backlog samples older than the stale window (0.2861ms)
✔ resolveSourceMode maps esp32 to live (0.2009ms)
✔ sourceMode override labels empty and built target states as replay/synthetic (0.5863ms)
✔ emptyTargetState reports none when no truthful target exists (0.3057ms)
✔ buildTargetState marks single-node live targets as degraded (0.2676ms)
✔ buildTargetState honors fused two-node live mode (0.247ms)
✔ buildTargetState keeps fused live targets moving (0.1877ms)
✔ buildTargetState demotes old targets to stale (0.2809ms)
✔ buildTargetState keeps low-confidence targets visible but not position-confident (0.4799ms)
✔ resolveLiveHoldState distinguishes startup, live, stale hold, and cleared (0.2654ms)
✔ emptyTargetState settles back to 'none' well past the clear timeout instead of reporting 'stale' forever (0.2044ms)
✔ bearing_deg uses the compass convention (x=1,z=0 -> 90 = east) (0.3077ms)
✔ calibrateEnergyThreshold: empty input returns a neutral zero result, not a crash (1.8851ms)
✔ calibrateEnergyThreshold: constant samples => zero sigma, threshold equals the constant (0.3377ms)
✔ calibrateEnergyThreshold: known mean/sigma from a hand-computable sample set (0.5278ms)
✔ calibrateEnergyThreshold: a higher kSigma produces a strictly higher (more conservative) threshold (0.3603ms)
✔ calibrateEnergyThreshold: non-finite samples are dropped, not propagated as NaN (0.2885ms)
✔ DEFAULT_SPATIAL_ENERGY_THRESHOLD is unchanged from the pre-Item-4 hardcoded literal (10) (0.2757ms)
✔ TrackingProcessor (default threshold): a dense cluster with total amplitude just above 10 is accepted (2.0079ms)
✔ TrackingProcessor (default threshold): a dense cluster with total amplitude just below 10 is rejected (0.4653ms)
✔ TrackingProcessor: a custom (calibrated) energyThreshold changes the accept/reject boundary (0.6942ms)
✔ TrackingProcessor: empty point cloud never produces a target (empty-room invariant) (0.3708ms)
✔ TrackingProcessor (PS-GAP-TRK-001): sub-threshold noise on a cold start never returns a coasted ghost target (7.3211ms)
✔ TrackingProcessor (PS-GAP-TRK-001): coasting through misses still works AFTER a real acquisition (1.2451ms)
✔ DBSCAN: two well-separated dense groups form two clusters (3.8341ms)
✔ DBSCAN: points below minPts density are noise (no cluster produced) (0.7342ms)
✔ DBSCAN: points farther apart than eps do not merge into one cluster (1.0978ms)
✔ DBSCAN: a chain of points within eps of their immediate neighbor forms one connected cluster (0.3488ms)
✔ KalmanFilter: repeated measurement at a fixed point converges the state near that point (67.5288ms)
✔ KalmanFilter: starts at the origin with zero velocity before any update (1.5943ms)
✔ KalmanFilter: velocity is clamped to the human sprint limit (10 m/s) even under an extreme single-tick jump (1.1987ms)
✔ KalmanFilter: getState always returns finite numbers (no NaN/Infinity propagation) (50.6371ms)
[UDP][SEC] {"record_type":"security_event","event_type":"node_source_mismatch","node_id":1,"expected_source":{"ip":"10.0.0.11","port":5005},"actual_source":{"ip":"10.0.0.99","port":5005},"packet_kind":"csi_frame"} (rejections for node 1: rate-limited log). If BOTH boards keep sending, they were likely provisioned with the same node_id — re-provision one with a unique id (firmware/esp32-csi-node/esp-flash.py).
[UDP] node 2 source rebound after silence: 10.0.0.20:5005 -> 10.0.0.99:6001
[UDP][SEC] {"record_type":"security_event","event_type":"node_source_mismatch","node_id":2,"expected_source":{"ip":"10.0.0.20","port":5005},"actual_source":{"ip":"10.0.0.99","port":5005},"packet_kind":"csi_frame"} (rejections for node 2: rate-limited log). If BOTH boards keep sending, they were likely provisioned with the same node_id — re-provision one with a unique id (firmware/esp32-csi-node/esp-flash.py).
✔ parseCsiPacket accepts ADR-018 32-byte CSI frames (3.5827ms)
✔ parseCsiPacket matches committed ADR-018 fixture fields (4.7494ms)
✔ parseCsiPacket ignores heartbeat packets (0.3131ms)
✔ parseCsiPacket ignores committed heartbeat fixture (0.5914ms)
✔ parseCsiPacket rejects legacy 20-byte packets in live mode (0.6659ms)
✔ parseCsiPacket accepts legacy 20-byte packets only in compat mode (0.4491ms)
✔ SourcePinningGuard rejects same node id from a foreign source (2.4176ms)
✔ SourcePinningGuard accepts same IP with a new ephemeral port (ESP32 reboot) (0.7639ms)
✔ SourcePinningGuard rejects a new IP while the pinned source is still active (0.329ms)
✔ SourcePinningGuard rebinds a new IP after the pinned source goes stale (DHCP renumber) (0.6753ms)
✔ SourcePinningGuard bounds the security-event history (0.6645ms)
✔ SourcePinningGuard rejects a foreign IP before first frame when statically pinned (0.2012ms)
✔ SourcePinningGuard rejects a foreign IP after silence when statically pinned (0.3964ms)
✔ PacketOrderGuard accepts in-order packets, rejects replay/out-of-order, and accepts rollover (0.3977ms)
✔ parseFeatureStatePacket decodes the RuView 0xC5110006 layout (0.3832ms)
✔ parseFeatureStatePacket rejects short packets and wrong magic (0.1941ms)
✔ parseEdgeVitalsPacket decodes the firmware 0xC5110002 layout (0.346ms)
✔ parseEdgeVitalsPacket zeroes confidence for zero BPM estimates (1.4735ms)
✔ parseEdgeVitalsPacket rejects short packets and wrong magic (0.7773ms)
✔ parseEdgeVitalsPacket propagates the board-reported RSSI (0.1976ms)
✔ parseFeatureStatePacket leaves rssi undefined (packet carries none) (0.1321ms)
✔ parseFeatureStatePacket accepts a full 60-byte packet with valid CRC32 (0.4718ms)
✔ parseFeatureStatePacket rejects a 60-byte packet with corrupted CRC32 (0.3031ms)
✔ classifyPacketMagic distinguishes every known packet type (0.4511ms)
✔ SourcePinningGuard accepts feature-state from the pinned source and tags events (1.2958ms)
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[WS] handleMessage from operator: startDemo
[DEMO] Live ESP32 nodes are streaming - demo mode is unavailable while live data is arriving
[WS] handleMessage from operator: startDemo
[DEMO] startDemo needs mode "synthetic" or "replay"
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: startDemo
[DEMO] A demo is already running - stop it first
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopProcessing
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[DEMO] Stop the scan before starting a demo
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
✔ synthetic demo labels every message synthetic and unwinds to live on stop (118.1191ms)
✔ external samples are dropped while a demo runs (27.1062ms)
✔ demo is refused while live ESP32 nodes are streaming (5.6023ms)
✔ startDemo rejects an unknown mode and a second concurrent start (26.3731ms)
✔ stopProcessing also ends a running demo (2.2145ms)
✔ the last client disconnecting ends the demo (1.9502ms)
✔ a demo is refused while a scan is already running (2.2316ms)
[ESP32] Queue: 1 | h1=(4.00, 0.00) h2=(4.00, 0.00) rssi=-40
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[DEMO] Demo replay needs a "empty" recording in C:\Users\thaer\AppData\Local\Temp\demo-ws-ssnfal (set PHANTOM_DEMO_DATASET_DIR)
✔ a demo never records and never saves a session into the real history (147.2089ms)
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
✔ replay demo with no recordings reports why and returns to live (24.0449ms)
[ESP32] Queue: 1 | h1=(4.00, 0.00) h2=(4.00, 0.00) rssi=-40
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
✔ replay demo feeds the real pipeline and labels the state replay (136.0769ms)
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: vitalSigns
[WS][SEC] non-AI client attacker sent vitalSigns — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: poseFrame
[WS][SEC] non-AI client attacker sent poseFrame — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: poseFrame
[WS] handleMessage from ai: registerAIClient
[WS] Registered AI Inference client: ai
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 2 live (active: 2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 2 live (active: 2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(20.00, 5.00) h2=(20.00, 5.00) rssi=-45
[NODES] node 1 live (active: 1,2)
[NODES] node 2 live (active: 1,2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] AI client ai sent malformed targetIdentity — dropped: Invalid enum value. Expected 'human' | 'mechanical' | 'unknown', received 'alien'
[WS] handleMessage from ai: targetIdentity
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[NODES] node 1 live (active: 1,2,3)
[NODES] node 2 live (active: 1,2,3)
[NODES] node 3 live (active: 1,2,3)
[NODES] node 2 stale >1.5s (active: 1,3)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] start refused: invalid roomId: use 1-64 letters, digits, '_' or '-'
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording walking (count=1) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-ws-Lo0T3H\lab\lab__s1__walking__20261102T181852Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: stopDatasetRecording
[DATASET] stopped: 5 frames (0 skipped) in 1 file(s)
[DATASET] write failed, stopping recording: ENOSPC: no space left on device
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording walking (count=1) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-progress-V8G5OK\lab\lab__s1__walking__20261102T181852Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording empty (count=0) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-progress-1ZCkG9\lab\lab__s1__empty__20261102T181852Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
✔ non-AI client's targetIdentity produces no state change and no broadcast (4.0332ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.7654ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.6478ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (2.305ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (2.946ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.9106ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.6412ms)
✔ new-client snapshot (sendLiveSnapshotToClient) always serves the deterministic value, never an injected one (1.8144ms)
✔ resolveLiveNodeMode: cold start with only node 2 reporting resolves single_node, not fused (1.8809ms)
✔ resolveLiveNodeMode: both nodes freshly reporting resolves fused_two_node (0.8064ms)
✔ resolveLiveNodeMode: node 1 going stale mid-session (dropout) falls back to single_node while node 2 keeps reporting (0.6161ms)
✔ resolveLiveNodeMode: both nodes stale resolves single_node (no separate 'no nodes' state) (0.6076ms)
✔ two-node fusion uses the active pair when nodes 3 and 4 are the live sensors (4.2667ms)
✔ singleNodeMotionDetected: realistic empty-room node2 noise (node1 silent) does not trip the gate (0.9859ms)
✔ singleNodeMotionDetected: real moving-target-scale node motion still trips the gate (no over-correction) (0.7597ms)
✔ motionStatus broadcast: known-unreliable MotionGate false positive does not reach the dashboard in an empty room (4.0458ms)
✔ motionStatus broadcast: manual motionGateEnabled threshold is not overridden (1.7024ms)
✔ fused_room: radialTarget broadcast and roomFusedSnapshot both reflect the Kalman-filtered position, not raw (32.3389ms)
✔ fused_room radialTarget is labeled fused_room_centroid, not the 1-D two-node basis (89.2348ms)
✔ fused_room localization still runs when ISAR/MUSIC is disabled (1.6991ms)
✔ micro-Doppler classifier is fed the per-node background-subtracted residual (40.9848ms)
✔ hardware queue is bounded per node so a 4-node burst cannot pin it at the global cap (5.2977ms)
✔ targetDebug reports fps and motion for every anchored node, not just 1 and 2 (0.8447ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (17.8223ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (2.3461ms)
✔ trackActiveNodeSet reports join/leave transitions exactly once (0.8265ms)
✔ fused_room: position is weighted by each node's rise above its own baseline (no centre pull) (2.0363ms)
✔ fused_room with a router: evidence on node 1 only is placed on node 1's link, not at a far corner (13.8327ms)
✔ fused_room: no target while the room tier is absent (2.5396ms)
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (1.7753ms)
✔ fused_room: present_still without a prior target never creates one (1.1071ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (1.9554ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (4.6239ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (22.9876ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (2.3747ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (4.1592ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (1.6697ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (1.4169ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (17.6313ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (3.9923ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (1.7244ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (3.1087ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (1.6951ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (21.3298ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (15.5396ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.5415ms)
✔ protected route returns 401 without a session (244.6303ms)
✔ protected route returns 401 with a garbage/forged cookie (61.1299ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (670.0451ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (245.2891ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (47.8003ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (production no longer does this) (2.4603ms)
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invariant for the exact same scenario above (0.9104ms)
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3771ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (55.7205ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (20.1287ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.751ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (2.2401ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.6154ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2652ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2523ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2066ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.3699ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.3075ms)
ℹ tests 407
ℹ suites 0
ℹ pass 407
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 14659.448
EXIT=0
```

### Python full suite, before (`python -m pytest tests/ -q --durations=10`, complete output)

```text

=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_count_model.py __________________
ImportError while importing test module 'D:\WIFI csi\phanotm\phantom scan\tests\test_count_model.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\thaer\AppData\Local\Programs\Python\Python313\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_count_model.py:7: in <module>
    from phantom.activity_train import TrainingRefused
phantom\activity_train.py:24: in <module>
    from sklearn.linear_model import LogisticRegression
E   ModuleNotFoundError: No module named 'sklearn'
________________ ERROR collecting tests/test_train_activity.py ________________
ImportError while importing test module 'D:\WIFI csi\phanotm\phantom scan\tests\test_train_activity.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\thaer\AppData\Local\Programs\Python\Python313\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_train_activity.py:8: in <module>
    from phantom.activity_train import TrainingRefused, train_activity
phantom\activity_train.py:24: in <module>
    from sklearn.linear_model import LogisticRegression
E   ModuleNotFoundError: No module named 'sklearn'
=========================== short test summary info ===========================
ERROR tests/test_count_model.py
ERROR tests/test_train_activity.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 14.42s
EXIT=2
```

### Python, collectable files only, before (`--ignore=tests/test_count_model.py --ignore=tests/test_train_activity.py`)

```text
.............................................sssss...................... [ 47%]
........................................................................ [ 94%]
.........                                                                [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py::TestDWTDenoiser::test_online_mode
tests/test_csi_pipeline.py::TestDBSCANClustering::test_pipeline_clustering
tests/test_csi_pipeline.py::TestFullPipeline::test_processes_real_data_without_crashing
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_all_recordings_process_cleanly
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_motion_detection_varies
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_distance_estimation_reasonable
  D:\WIFI csi\phanotm\phantom scan\.venv\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundary effects.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================ slowest 10 durations =============================
15.85s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_motion_detection_varies
8.92s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_all_recordings_process_cleanly
4.02s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_status_endpoint
4.02s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_ingest_batch_from_recording
4.01s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_ingest_single_sample
4.01s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_queue_status
4.01s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_health_endpoint
2.74s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_distance_estimation_reasonable
1.20s call     tests/test_csi_pipeline.py::TestFullPipeline::test_processes_real_data_without_crashing
0.59s call     tests/test_phantom_cross_node_correlation.py::test_correlated_motion_scores_higher_than_independent_motion
148 passed, 5 skipped, 6 warnings in 56.87s
EXIT=0
secs 58
```

### F1/F2 Python invariants, before

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\phantom scan\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.16s =======================
EXIT=0
```

### AI-firewall TS tests, before

```text
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: vitalSigns
[WS][SEC] non-AI client attacker sent vitalSigns — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: poseFrame
[WS][SEC] non-AI client attacker sent poseFrame — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: poseFrame
[WS] handleMessage from ai: registerAIClient
[WS] Registered AI Inference client: ai
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] AI client ai sent malformed targetIdentity — dropped: Invalid enum value. Expected 'human' | 'mechanical' | 'unknown', received 'alien'
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.9128ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3402ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3145ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.1672ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4578ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.336ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3513ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (15.5916ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.9747ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.9603ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.4058ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1072.803
EXIT=0
```

## Final state — after

### TypeScript full suite, after

```text

> csi-signal-processing@1.2.0 test
> tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts scripts/accuracy/__tests__/**/*.test.ts

✔ no banner when the demo is idle or unknown (1.9561ms)
✔ simulated demo says it is scripted and not a measurement (0.5355ms)
✔ replay demo names the recording and warns it may show no target (0.2432ms)
✔ replay demo reports calibration progress while the baselines warm up (0.2037ms)
✔ loading a recording is shown as such (0.2387ms)
✔ a failed demo start surfaces the reason as an error banner (0.4066ms)
✔ k = -ln(1-alpha)*60 table matches the tuned per-frame alphas (2.9586ms)
✔ DECAY_RATES.positionFusedNearScale approximates positionFar - positionFusedBase (0.2584ms)
✔ dampVector3 converges to the same result regardless of step count for a fixed elapsed time (0.6428ms)
✔ dampScalar and dampAngle share the same frame-rate-independence property (0.3879ms)
✔ a naive fixed-alpha-per-frame lerp is NOT frame-rate independent (the bug this file fixes) (0.229ms)
✔ dampVector3 clamps large deltas so a multi-second stall does not snap instantly (0.196ms)
✔ dampAngle wraps across the +-PI boundary the short way (0.2341ms)
✔ a missing key falls back to the default (1.5957ms)
✔ stored values round-trip (0.3799ms)
✔ an unrecognised stored value falls back to the default (0.2061ms)
✔ blocked or missing storage never throws and uses the default (0.4153ms)
✔ no target state at all reads NO TARGET (1.3169ms)
✔ an invisible target reads NO TARGET even if stale vitals are still around (0.5323ms)
✔ a visible live target with no vitals yet reads CALIBRATING (0.2241ms)
✔ a visible live target with a vitals reading shows no badge (0.1902ms)
✔ simulated demo vitals are always flagged SIMULATED (0.2161ms)
✔ NO TARGET outranks SIMULATED when the simulated walker is not visible (0.1763ms)
✔ A1 — synthetic perfect match: matched present+absent regions score recall=1, FPR=0, F1=1 (2.2931ms)
✔ A2 — synthetic all-miss: system stays negative throughout a ground-truth-positive interval (0.558ms)
✔ A3 — a stale-demotion bin during ground-truth-positive scores FN, not excluded (0.4394ms)
✔ A6 — a ground-truth log with zero present rows can never produce a TP, by construction (6.3608ms)
✔ parses present/absent/sync rows and resolves the sync marker (3.0181ms)
✔ rejects a row with an invalid label (0.7629ms)
✔ a log with zero present rows never reports positive at any sampled time (0.3195ms)
✔ groundTruthTimeBounds ignores sync rows and returns null when only sync rows exist (0.3994ms)
✔ A5 — a trial with node1 fps below the 20/node preflight is excluded from the campaign rollup with a named reason (4.6384ms)
✔ A5 — a degraded-only trial is excluded unless --allow-degraded is set (0.4031ms)
✔ A7 — every derived metric carries {value,status,evidence} (0.7533ms)
✔ A7 — assertMetricValueShape rejects a bare number or a status-less object (3.7439ms)
✔ A7 — buildTrialReport itself refuses a metrics object with a malformed field (1.0158ms)
✔ resolveAlignment recovers a known constant offset from a single sync event (2.4624ms)
✔ resolveAlignment recovers known offset and drift from two sync events (0.4866ms)
✔ A4 — resolveAlignment refuses with NoSyncMarkerError when no sync event exists (0.6937ms)
✔ generateOperatorSeed creates a verifiable scrypt hash (274.0876ms)
✔ AuditLogger writes and lists records in reverse chronological order (61.7311ms)
✔ AuditLogger accepts websocket-style request objects without req.get (6.8465ms)
✔ load path accepts operator files with npm banner noise before JSON (3494.2993ms)
✔ initializeAuth bootstraps first operator on loopback when seed file is missing (3125.5422ms)
✔ initializeAuth rejects first-operator bootstrap from non-loopback without token (7.9434ms)
✔ compassBearingRad: cardinal positions (1.4224ms)
✔ bearingToCardinal: sector centers and boundaries (0.3397ms)
✔ bearingToCardinalLong matches short mapper sectors (0.1859ms)
✔ travelAngleToBearingRad: math angle to compass bearing (0.3499ms)
✔ headingVectorFromAngle: regression for motion-vector decode (0.3011ms)
✔ LLTF data index set excludes DC, the invalid first word, and the ±27..±32 guards (1.4541ms)
✔ reduceCsiFrame returns only data-subcarrier amplitudes from the LLTF block (0.8544ms)
✔ reduceCsiFrame keeps the subcarrier count constant across non-HT, HT and STBC frames (0.7523ms)
✔ reduceCsiFrame reads ESP-IDF imaginary-first byte order for the dominant subcarrier (1.3842ms)
✔ reduceCsiFrame falls back to every entry for short legacy/synthetic frames (0.3432ms)
✔ reduceCsiFrame uses the second antenna block for h2 when present (0.4163ms)
✔ parseDatasetStart accepts a valid request and derives the count from the label (1.9368ms)
✔ parseDatasetStart rejects unknown labels, unsafe ids and out-of-range counts (1.0465ms)
✔ recorder writes a header then frame rows under data/datasets/<room>/ (8.5132ms)
✔ recorder rotates to a new part file with its own header after maxFramesPerFile (46.6442ms)
✔ record is a no-op when not recording, and a second start is refused (3.1039ms)
✔ frames with non-finite amplitudes are skipped and counted, not written (2.7618ms)
✔ per-node frame counts are tracked for the operator (2.3136ms)
✔ stop() always closes the file and clears recording state even if the final flush fails (4.3006ms)
✔ a failed flush drops the pending buffer instead of growing without bound (3.9189ms)
✔ readClipHead keeps nodes 1-4, rebases time to the first frame and skips junk (17.6709ms)
✔ readClipHead stops after the requested number of seconds (86.7993ms)
✔ findDatasetFile matches the label and ignores .partN continuations (5.1548ms)
✔ loadReplayClip places the body after the calibration lead-in (9.6932ms)
✔ loadReplayClip reports a missing recording with an actionable error (2.3341ms)
✔ ReplayCursor emits each due frame exactly once, in order (0.5036ms)
✔ ReplayCursor loops back to the loop point instead of restarting calibration (0.3639ms)
✔ ReplayCursor reports a lap-local position for the progress display (0.22ms)
✔ sampleFromFrame stamps the sample with the current time and copies amplitudes (0.3987ms)
✔ synthetic demo publishes labelled walker frames and stops cleanly (31.6693ms)
✔ replay demo feeds recorded frames to ingest stamped with the current time (0.8395ms)
✔ replay demo reports running once calibration has elapsed and loops without re-calibrating (0.9829ms)
✔ replay demo exposes clip label and duration in its status (0.318ms)
✔ a missing recording fails the start with a message and leaves the demo off (0.6458ms)
✔ starting while a demo is already running is refused (0.366ms)
✔ stopping while the recording is still loading discards the load (0.3775ms)
✔ status updates are emitted on start, on phase change and about once per second (0.3536ms)
✔ walker stays inside the room for two full laps (5.3616ms)
✔ walker path is deterministic and loops seamlessly (1.3037ms)
✔ walker moves at the nominal speed and pauses at least once per lap (1.0325ms)
✔ walker frame is labelled synthetic end to end (2.155ms)
✔ walker frame radialTarget is self-consistent with its position (1.4281ms)
✔ the node nearest the walker shows the most motion (1.0137ms)
✔ walker frame state follows the walker: moving while walking, idle while paused (24.3187ms)
✔ walker frame carries scripted vitals in a plausible, time-varying human range (17.8235ms)
✔ walker signal field covers the room grid with finite values (0.5182ms)
✔ FusedPositionKalman: repeated measurement at a fixed point converges near that point (2.6095ms)
✔ FusedPositionKalman: reports the origin with zero velocity before any update (1.2871ms)
✔ FusedPositionKalman: a single predict after a large gap is bounded by the dt ceiling, not the full elapsed time (0.5568ms)
✔ FusedPositionKalman: a single wild outlier tick is gated out, not applied (0.4798ms)
✔ FusedPositionKalman: getState always returns finite numbers (no NaN/Infinity propagation) (0.3788ms)
✔ FusedPositionKalman: reset returns to the zero-velocity origin state (0.3145ms)
✔ FusedPositionKalman: the first measurement initializes the state (no pull from the origin) (0.2716ms)
✔ FusedPositionKalman: process noise scales with gap length beyond the reference tick (0.3701ms)
✔ FusedPositionKalman: velocity variance shrinks by the PRE-update cross-covariance (0.3307ms)
✔ FusedPositionKalman: a real jump persisting 5+ ticks re-initializes instead of locking out (0.5498ms)
✔ FusedPositionKalman: filtering the real recorded session reduces mean tick-to-tick jitter on both axes (61.3012ms)
✔ FusedPositionKalman: filtering the real recorded session tracks the raw track tightly, except for rare gated outlier ticks (57.6478ms)
✔ FusedPositionKalman.constrain pulls an overshoot back into the box and removes outward velocity (0.6279ms)
✔ FusedPositionKalman.constrain caps speed while preserving direction (0.3677ms)
✔ join-groundtruth enriches live CSV rows via one sync marker and trace (2.3453ms)
✔ smoothing is time-constant based: same response after 0.6 s at 20 Hz and 50 Hz (3.6318ms)
✔ warm-up learns the empty-room level quickly, then rise ≈ 0 and tier absent (0.7418ms)
✔ motion well above the node's own baseline reaches present_moving only after the 0.4 s debounce (0.6002ms)
✔ rise is gain-invariant: a node with 3x amplitude gain produces the same rise (1.9476ms)
✔ baseline does not absorb a person while frozen (target held), so rise persists (1.6779ms)
✔ without freeze the slow baseline eventually adapts to a new static level (11.9212ms)
✔ freeze is bounded: after the max freeze time the baseline adapts again (2.8057ms)
✔ spikes above the smoothed level are excluded from the baseline update (0.6209ms)
✔ default tier thresholds are ordered still < moving < active (0.2109ms)
✔ room presence upgrades immediately but holds a downgrade for 1.5 s (0.4239ms)
✔ excess is the absolute rise above baseline, comparable across nodes with different baselines (0.6307ms)
✔ excess is never negative and is ~0 in a settled empty room (0.2372ms)
✔ a noisy but empty room stays absent: the baseline must not sit at the lower noise edge (2.6159ms)
✔ a genuine sustained rise well above the noise is still detected (0.6209ms)
✔ z is the excess in units of the node's own empty-room fluctuation (1.3358ms)
✔ fuseNodeTargets: motion concentrated at node 3 centroids near node 3's anchor (10.1917ms)
✔ fuseNodeTargets: motion split evenly across all 4 nodes centroids near room center (0.5543ms)
✔ fuseNodeTargets: below-threshold motion at all nodes returns null (empty-room gate) (0.3217ms)
✔ fuseNodeTargets: confident mechanical classification suppresses an otherwise-passing energy gate (0.1846ms)
✔ r1 >> r2 places the target at node 1 (x ≈ -1.5) (0.6106ms)
✔ r1 ≈ r2 places the target at the midpoint (x ≈ 0, balance ≈ 0.5) (0.2454ms)
✔ r2 >> r1 places the target at node 2 (x ≈ +1.5) (0.2311ms)
✔ display bias preserves the midpoint exactly (0.115ms)
✔ display bias pulls the target closer to node 1 when balance is low (0.2352ms)
✔ display bias pulls the target closer to node 2 when balance is high (0.6285ms)
✔ empty room (motion below threshold) returns NO target — not a centered ghost (0.4291ms)
✔ fused target uses the configured presence threshold instead of the placeholder default (0.2247ms)
✔ zero perturbation returns NO target even if motion inputs are high (0.822ms)
✔ distToNearestNodeM is ~half the separation at the midpoint (0.2083ms)
✔ matrix motion: identical frames => zero motion (static room) (0.3594ms)
✔ matrix motion detects per-subcarrier oscillation the best-subcarrier scalar misses (0.4297ms)
✔ balance tracks the node with stronger per-subcarrier perturbation (0.4769ms)
✔ computeNodeMotionFromMatrix: constant amplitude => zero motion (0.148ms)
✔ rising balance (positive axis velocity) => N2 approaching, N1 receding (0.1865ms)
✔ falling balance (negative axis velocity) => N1 approaching, N2 receding (0.4787ms)
✔ velocity inside the deadband keeps the previous trends (hysteresis) (0.963ms)
✔ distanceM bookkeeping: balance splits the separation between the nodes (0.2051ms)
✔ contrast exponent widens balance vs the linear ratio; p=1 restores linear (0.2028ms)
✔ computeNodeMotionFromMatrix: saturates at 1.0 and uses the documented scale (0.1243ms)
✔ computeLinearBalance is the undecorated r2/(r1+r2) ratio (0.5734ms)
✔ balanceLinear on fuseTwoNodeTarget is invariant to the contrast exponent, unlike balance (0.6298ms)
✔ balanceLinear is 0.5 at the midpoint (0.1634ms)
✔ computeFallbackVelocity returns zero with no previous sample (first tick, never a spike) (0.4906ms)
✔ computeFallbackVelocity is linear in displacement for a fixed dt (no hidden multiplier) (0.2089ms)
✔ computeFallbackVelocity does not hardcode a 50ms tick — the same displacement over a longer real dt yields a smaller velocity (0.1462ms)
✔ computeFallbackVelocity floors dt so a near-zero interval cannot blow up velocity (0.1587ms)
✔ computeFallbackVelocity yields zero (never a spike) across a gap beyond the max threshold (0.1658ms)
✔ computeFallbackVelocity: invalidating prev (null) after a primary-tracker hit yields zero on the next fallback tick, not a diff across the skipped interval (0.1539ms)
✔ computeGainNormalizedPerturbation cancels a per-node multiplicative gain (0.2089ms)
✔ computeGainNormalizedPerturbation returns 0 for a silent node without dividing by zero (0.1111ms)
✔ computeGainNormalizedPerturbation guards a non-finite or non-positive mean defensively (0.2417ms)
✔ FIXED (PS-BEHTEST-004): gain-normalizing r1/r2 restores balance ~= 0.5 under a 2x per-node gain asymmetry with identical real motion (0.2963ms)
✔ a COMMON gain applied equally to both nodes leaves balance unchanged (the bug was only the differential mismatch) (0.3542ms)
✔ hasSingleNodePresenceEvidence: no motion and no tracked cluster => no presence (empty room) (0.1367ms)
✔ hasSingleNodePresenceEvidence: real motion alone is sufficient evidence (0.1403ms)
✔ hasSingleNodePresenceEvidence: a tracked cluster alone is sufficient evidence (covers a real-but-stationary target) (0.1077ms)
✔ hasSingleNodePresenceEvidence: both signals present is still presence (0.1446ms)
✔ evaluateClassifierCorroboration: no classifier supplied => not_evaluated, never suppresses (0.1141ms)
✔ evaluateClassifierCorroboration: confident 'human' => confirmed, never suppresses (0.1182ms)
✔ evaluateClassifierCorroboration: confident 'mechanical' (humanProb <= threshold) => contradicted, suppresses (0.1049ms)
✔ evaluateClassifierCorroboration: borderline 'mechanical' (above the confident-reject bar) => inconclusive, does NOT suppress (0.0996ms)
✔ evaluateClassifierCorroboration: 'unknown' => inconclusive, does NOT suppress (0.0914ms)
✔ fuseTwoNodeTarget (a): energy gate passes + classifier 'human' => target present, corroboration confirmed (0.1656ms)
✔ fuseTwoNodeTarget (b): energy gate passes + confident 'mechanical' classifier => presence suppressed (null) (0.1175ms)
✔ fuseTwoNodeTarget (c): energy gate passes + 'unknown' classifier => target still present (not stricter than baseline) (0.1468ms)
✔ fuseTwoNodeTarget (c): borderline 'mechanical' (not confidently rejected) also falls back to baseline (0.1229ms)
✔ fuseTwoNodeTarget (d): energy gate fails => no target even with a confident 'human' classification (0.1347ms)
✔ fuseTwoNodeTarget: no classifier supplied at all => behavior is byte-for-byte the pre-Item-1 baseline (0.1189ms)
✔ wasSuppressedByClassifier: true only when energy gate passed AND classifier confidently vetoed (0.2784ms)
✔ hasSingleNodePresenceEvidence (a): energy evidence + 'human' classifier => presence (0.1319ms)
✔ hasSingleNodePresenceEvidence (b): energy evidence + confident 'mechanical' classifier => suppressed (0.1015ms)
✔ hasSingleNodePresenceEvidence (c): energy evidence + 'unknown' classifier => falls back to baseline (still present) (0.0687ms)
✔ hasSingleNodePresenceEvidence (d): no energy evidence => no presence even with a confident 'human' classifier (0.0671ms)
✔ hasSingleNodePresenceEvidence: omitting classifier entirely is unchanged from the pre-Item-1 signature (2.0254ms)
✔ computeAgcNormalizedPerturbation: a static pattern under per-frame gain swings reads as ~no motion (0.628ms)
✔ computeAgcNormalizedPerturbation: a changing multipath shape reads as motion and is gain-invariant (0.3553ms)
✔ computeAgcNormalizedPerturbation: degenerate input returns 0 (0.1607ms)
✔ computeRadialTrends: walking toward node 3 approaches 3 and recedes from 1 (0.2417ms)
✔ computeRadialTrends: speed inside the deadband is stable for every node (0.2748ms)
✔ computePositionUncertaintyM shrinks with stronger evidence and grows when one node dominates (0.2285ms)
✔ computePositionUncertaintyM is bounded by the room size and never below a floor (0.1715ms)
✔ distanceToSegment: projects onto the segment and clamps at the ends (0.1429ms)
✔ distanceToSegment: a zero-length link (node next to the router) is a point (0.0771ms)
✔ link model: person near node 1 or node 2 is placed on that side, not at nodes 3/4 (23.3087ms)
✔ link model: person near node 3 and node 4 is placed on the far wall (13.0396ms)
✔ link model: beats the plain anchor centroid for people near the router (4.3228ms)
✔ link model: position stays inside the room bounds even with degenerate input (4.1233ms)
✔ link model: without a router the result is exactly the old anchor centroid (1.2148ms)
✔ locateByLinkModel: returns null when there are no usable shares (0.2911ms)
✔ getAnatomicalRoot uses hip midpoint when both hips are present (2.2503ms)
✔ getAnatomicalRoot falls back to shoulder midpoint when hips are absent (0.3818ms)
✔ getAnatomicalRoot falls back to centroid when neither hips nor shoulders present (0.2562ms)
✔ getAnatomicalRoot handles a single keypoint without division error (0.2517ms)
✔ getAnatomicalRoot handles an empty keypoint array safely (0.1976ms)
✔ hip midpoint maps to exact target.x/z when all hips are on the root (0.294ms)
✔ nose joint offset is preserved relative to target root (0.2973ms)
✔ left wrist offset is correct and under clamp (0.5 m from root, within 0.8 m) (0.2166ms)
✔ outlier keypoint > POSE_CLAMP_M is clamped to POSE_CLAMP_M (0.2471ms)
✔ outlier in negative direction is clamped to -POSE_CLAMP_M (0.3217ms)
✔ y is never clamped — absolute height is preserved regardless of offset (0.2621ms)
✔ skeleton root equals target position at "near N1" (0.2547ms)
✔ skeleton root equals target position at "midpoint" (0.109ms)
✔ skeleton root equals target position at "near N2" (0.0985ms)
✔ skeleton root equals target position at "off-axis" (0.2576ms)
✔ skeleton root tracks target as it moves from N1 to N2 in 5 steps (0.2525ms)
✔ limb offset is stable across target positions (not amplified by movement) (0.2615ms)
✔ double-offset bug is NOT present: adding target.x twice would produce wrong position (0.204ms)
✔ recording CSV header includes the positional fidelity columns (1.6472ms)
✔ raw_perturbation_nX is exported unclamped, unlike the saturated motion_nX it's derived from (4.4767ms)
✔ visible fused rows reuse the same displayed position contract (0.453ms)
✔ gate-closed rows suppress position and distance fields atomically (0.3462ms)
✔ serialized CSV carries metadata with the explicit x/x_disp contract (0.9482ms)
✔ recording rows carry the room tier, per-node excess, and real N3/N4 trends for fused_room (0.3848ms)
✔ recording rows without room extras keep the legacy trend source and leave the new columns empty (0.4461ms)
✔ defaults reproduce the historical 4 m x 6 m corner layout (2.7589ms)
✔ parseRoomGeometry accepts a valid config and keys anchors by numeric node id (2.9846ms)
✔ parseRoomGeometry rejects non-finite / oversized dimensions (3.1584ms)
✔ parseRoomGeometry rejects node ids outside the canonical 1-4 set (0.5042ms)
✔ parseRoomGeometry rejects anchors outside the room bounds (0.4108ms)
✔ parseRoomGeometry rejects 3+ collinear anchors (no 2-D localization possible) (0.4004ms)
✔ geometricDiversity is 1 for a square layout, ~0.8 for 4x6 corners, low when 3 nodes share a corner (0.5551ms)
✔ loadRoomGeometry falls back to defaults when no config file exists (0.2657ms)
✔ loadRoomGeometry reads PHANTOM_ROOM_CONFIG and fails fast when that file is missing (0.4746ms)
✔ loadRoomGeometry reports invalid JSON with the file path (0.4209ms)
✔ an optional router position is parsed and returned (0.5882ms)
✔ no router means no link model: router is undefined (0.2106ms)
✔ a router far outside the room is rejected with a clear message (0.4333ms)
✔ a router with an unknown field is rejected (strict schema) (0.5188ms)
✔ MUSIC: spectrum has the requested length and finite power at every bin (5.987ms)
✔ MUSIC: fewer than 3 samples returns an empty spectrum (guard clause) (10.2047ms)
✔ MUSIC: identical covariance input yields an identical spectrum (deterministic eigen start) (9.5294ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): clean steering input resolves its true synthetic angle (13.1043ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): unrelated random inputs produce meaningfully different spectra (19.5852ms)
✔ MUSIC (PS-GAP-MUSIC-001 fixed): all-zero (degenerate) input returns an empty spectrum, not a fake curve (0.611ms)
✔ findSpectrumPeak: empty spectrum returns the documented sentinel (0.3362ms)
✔ HampelFilter: passes normal values through unchanged (0.4103ms)
✔ HampelFilter: replaces a hard outlier spike with the window median (0.2251ms)
✔ HampelFilter: values before the window fills pass through untouched (0.3237ms)
✔ MicroDopplerClassifier: a strong periodic (mechanical) signal classifies as mechanical (16.4724ms)
✔ MicroDopplerClassifier: an aperiodic low-frequency signal does NOT classify as mechanical (6.4501ms)
✔ MicroDopplerClassifier: returns last state (label unknown) until the buffer fills (0.5752ms)
✔ PDPRanger: returns the RSSI path-loss fallback before the CSI buffer fills (0.742ms)
✔ PDPRanger: RSSI fallback clamps to the documented [0.3m, 8m] bounds (0.2375ms)
✔ PDPRanger: steady CSI input produces a finite, bounded distance estimate (4.4931ms)
✔ BackgroundSubtractor: a constant (static) channel is fully suppressed (0.8277ms)
✔ BackgroundSubtractor: a step change appears in the dynamic residual (0.3342ms)
✔ BackgroundSubtractor: setWindowSize trims an over-full window without crashing (0.6443ms)
✔ MotionGate: constant amplitude (empty room) never reports motion (0.7693ms)
✔ MotionGate: auto-calibrates threshold = 3*sigma from the first 100 samples (0.5675ms)
✔ MotionGate: large amplitude swings after calibration trigger motionDetected (0.4654ms)
✔ MotionGate: a manual threshold overrides the calibrated one (0.4155ms)
✔ MotionGate: reset returns to the uncalibrated default threshold (0.4417ms)
✔ live esp32 degraded targets still present a live position marker (1.9799ms)
✔ truthful live targets remain fully visible (0.3115ms)
✔ stale or cleared targets do not present a live position (0.2145ms)
✔ fused live targets expose the on-axis honesty caveat (1.309ms)
✔ single-node live targets expose the distinct bearing caveat (0.2633ms)
✔ caveat clears together with stale or missing live position (0.2259ms)
✔ live esp32 truthful targets stay on the abstract marker path (0.2311ms)
✔ truthful live targets do not use volumetric presentation (0.1763ms)
✔ illustrative body is allowed only where the live position marker is allowed (0.2937ms)
✔ illustrative body is withheld for mechanical targets, empty rooms and aged-out targets (0.4241ms)
✔ illustrative body never re-enables the volumetric/AI-pose gate (0.1935ms)
✔ axis motion vector only renders when projected speed is present (0.1969ms)
✔ fused targets summarize the between-node position and destination node (2.0929ms)
✔ fused midpoint targets call out midpoint hold on the node axis (0.4334ms)
✔ fused targets near the second node identify the far-side destination (2.5996ms)
✔ single-node targets summarize as around the nearest node (0.5354ms)
✔ single-node moving label uses compass cardinal from travel angle (0.4882ms)
✔ isSampleFresh accepts a sample within the live stale window (4.9126ms)
✔ isSampleFresh drops backlog samples older than the stale window (0.3714ms)
✔ resolveSourceMode maps esp32 to live (0.2026ms)
✔ sourceMode override labels empty and built target states as replay/synthetic (0.5854ms)
✔ emptyTargetState reports none when no truthful target exists (0.2454ms)
✔ buildTargetState marks single-node live targets as degraded (0.7301ms)
✔ buildTargetState honors fused two-node live mode (0.2779ms)
✔ buildTargetState keeps fused live targets moving (0.2663ms)
✔ buildTargetState demotes old targets to stale (0.29ms)
✔ buildTargetState keeps low-confidence targets visible but not position-confident (0.9825ms)
✔ resolveLiveHoldState distinguishes startup, live, stale hold, and cleared (0.5203ms)
✔ emptyTargetState settles back to 'none' well past the clear timeout instead of reporting 'stale' forever (0.2586ms)
✔ bearing_deg uses the compass convention (x=1,z=0 -> 90 = east) (0.4053ms)
✔ calibrateEnergyThreshold: empty input returns a neutral zero result, not a crash (1.9275ms)
✔ calibrateEnergyThreshold: constant samples => zero sigma, threshold equals the constant (0.6201ms)
✔ calibrateEnergyThreshold: known mean/sigma from a hand-computable sample set (0.5143ms)
✔ calibrateEnergyThreshold: a higher kSigma produces a strictly higher (more conservative) threshold (0.2489ms)
✔ calibrateEnergyThreshold: non-finite samples are dropped, not propagated as NaN (0.304ms)
✔ DEFAULT_SPATIAL_ENERGY_THRESHOLD is unchanged from the pre-Item-4 hardcoded literal (10) (0.1842ms)
✔ TrackingProcessor (default threshold): a dense cluster with total amplitude just above 10 is accepted (1.9332ms)
✔ TrackingProcessor (default threshold): a dense cluster with total amplitude just below 10 is rejected (0.4887ms)
✔ TrackingProcessor: a custom (calibrated) energyThreshold changes the accept/reject boundary (0.7498ms)
✔ TrackingProcessor: empty point cloud never produces a target (empty-room invariant) (0.4799ms)
✔ TrackingProcessor (PS-GAP-TRK-001): sub-threshold noise on a cold start never returns a coasted ghost target (14.2834ms)
✔ TrackingProcessor (PS-GAP-TRK-001): coasting through misses still works AFTER a real acquisition (1.0233ms)
✔ DBSCAN: two well-separated dense groups form two clusters (1.7759ms)
✔ DBSCAN: points below minPts density are noise (no cluster produced) (0.2675ms)
✔ DBSCAN: points farther apart than eps do not merge into one cluster (0.2565ms)
✔ DBSCAN: a chain of points within eps of their immediate neighbor forms one connected cluster (0.25ms)
✔ KalmanFilter: repeated measurement at a fixed point converges the state near that point (4.1328ms)
✔ KalmanFilter: starts at the origin with zero velocity before any update (0.2173ms)
✔ KalmanFilter: velocity is clamped to the human sprint limit (10 m/s) even under an extreme single-tick jump (0.3421ms)
✔ KalmanFilter: getState always returns finite numbers (no NaN/Infinity propagation) (0.8179ms)
[UDP][SEC] {"record_type":"security_event","event_type":"node_source_mismatch","node_id":1,"expected_source":{"ip":"10.0.0.11","port":5005},"actual_source":{"ip":"10.0.0.99","port":5005},"packet_kind":"csi_frame"} (rejections for node 1: rate-limited log). If BOTH boards keep sending, they were likely provisioned with the same node_id — re-provision one with a unique id (firmware/esp32-csi-node/esp-flash.py).
[UDP] node 2 source rebound after silence: 10.0.0.20:5005 -> 10.0.0.99:6001
[UDP][SEC] {"record_type":"security_event","event_type":"node_source_mismatch","node_id":2,"expected_source":{"ip":"10.0.0.20","port":5005},"actual_source":{"ip":"10.0.0.99","port":5005},"packet_kind":"csi_frame"} (rejections for node 2: rate-limited log). If BOTH boards keep sending, they were likely provisioned with the same node_id — re-provision one with a unique id (firmware/esp32-csi-node/esp-flash.py).
✔ parseCsiPacket accepts ADR-018 32-byte CSI frames (2.289ms)
✔ parseCsiPacket matches committed ADR-018 fixture fields (1.7723ms)
✔ parseCsiPacket ignores heartbeat packets (0.2954ms)
✔ parseCsiPacket ignores committed heartbeat fixture (0.4401ms)
✔ parseCsiPacket rejects legacy 20-byte packets in live mode (1.173ms)
✔ parseCsiPacket accepts legacy 20-byte packets only in compat mode (0.5751ms)
✔ SourcePinningGuard rejects same node id from a foreign source (2.0344ms)
✔ SourcePinningGuard accepts same IP with a new ephemeral port (ESP32 reboot) (0.2568ms)
✔ SourcePinningGuard rejects a new IP while the pinned source is still active (0.236ms)
✔ SourcePinningGuard rebinds a new IP after the pinned source goes stale (DHCP renumber) (0.5427ms)
✔ SourcePinningGuard bounds the security-event history (0.6845ms)
✔ SourcePinningGuard rejects a foreign IP before first frame when statically pinned (0.2127ms)
✔ SourcePinningGuard rejects a foreign IP after silence when statically pinned (0.5505ms)
✔ PacketOrderGuard accepts in-order packets, rejects replay/out-of-order, and accepts rollover (0.3276ms)
✔ parseFeatureStatePacket decodes the RuView 0xC5110006 layout (0.357ms)
✔ parseFeatureStatePacket rejects short packets and wrong magic (0.1762ms)
✔ parseEdgeVitalsPacket decodes the firmware 0xC5110002 layout (0.3077ms)
✔ parseEdgeVitalsPacket zeroes confidence for zero BPM estimates (0.2392ms)
✔ parseEdgeVitalsPacket rejects short packets and wrong magic (0.1662ms)
✔ parseEdgeVitalsPacket propagates the board-reported RSSI (0.1212ms)
✔ parseFeatureStatePacket leaves rssi undefined (packet carries none) (0.1225ms)
✔ parseFeatureStatePacket accepts a full 60-byte packet with valid CRC32 (0.5262ms)
✔ parseFeatureStatePacket rejects a 60-byte packet with corrupted CRC32 (0.2016ms)
✔ classifyPacketMagic distinguishes every known packet type (0.2725ms)
✔ SourcePinningGuard accepts feature-state from the pinned source and tags events (0.1685ms)
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[WS] handleMessage from operator: startDemo
[DEMO] Live ESP32 nodes are streaming - demo mode is unavailable while live data is arriving
[WS] handleMessage from operator: startDemo
[DEMO] startDemo needs mode "synthetic" or "replay"
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: startDemo
[DEMO] A demo is already running - stop it first
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopProcessing
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[DEMO] Stop the scan before starting a demo
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
✔ synthetic demo labels every message synthetic and unwinds to live on stop (72.1576ms)
✔ external samples are dropped while a demo runs (2.3009ms)
✔ demo is refused while live ESP32 nodes are streaming (2.0581ms)
✔ startDemo rejects an unknown mode and a second concurrent start (2.0901ms)
✔ stopProcessing also ends a running demo (1.9535ms)
✔ the last client disconnecting ends the demo (5.8454ms)
✔ a demo is refused while a scan is already running (1.1493ms)
[ESP32] Queue: 1 | h1=(4.00, 0.00) h2=(4.00, 0.00) rssi=-40
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[DEMO] Demo replay needs a "empty" recording in C:\Users\thaer\AppData\Local\Temp\demo-ws-3MLdri (set PHANTOM_DEMO_DATASET_DIR)
✔ a demo never records and never saves a session into the real history (136.7995ms)
[WS] handleMessage from operator: startDemo
[WS] startProcessing called, isProcessing=false, interval=false
[NODES] anchors N1=(-2,-3) N2=(2,-3) N3=(2,3) N4=(-2,3) room=4x6m sep(N1-N2)=4.00m source=config/room.json router=(2,-3) position=link-model
[WS] Processing started, interval created
✔ replay demo with no recordings reports why and returns to live (24.552ms)
[ESP32] Queue: 1 | h1=(4.00, 0.00) h2=(4.00, 0.00) rssi=-40
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=true, interval=true
[WS] Interval cleared
[WS] Processing stopped, isProcessing=false broadcast sent
[WS] handleMessage from operator: stopDemo
[WS] stopProcessing called, isProcessing=false, interval=false
[WS] Processing stopped, isProcessing=false broadcast sent
✔ replay demo feeds the real pipeline and labels the state replay (125.6302ms)
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: vitalSigns
[WS][SEC] non-AI client attacker sent vitalSigns — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: poseFrame
[WS][SEC] non-AI client attacker sent poseFrame — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: poseFrame
[WS] handleMessage from ai: registerAIClient
[WS] Registered AI Inference client: ai
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 2 live (active: 2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 2 live (active: 2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(20.00, 5.00) h2=(20.00, 5.00) rssi=-45
[NODES] node 1 live (active: 1,2)
[NODES] node 2 live (active: 1,2)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] AI client ai sent malformed targetIdentity — dropped: Invalid enum value. Expected 'human' | 'mechanical' | 'unknown', received 'alien'
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-40
[NODES] node 1 live (active: 1,2,3)
[NODES] node 2 live (active: 1,2,3)
[NODES] node 3 live (active: 1,2,3)
[NODES] node 2 stale >1.5s (active: 1,3)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] start refused: invalid roomId: use 1-64 letters, digits, '_' or '-'
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording walking (count=1) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-ws-8EzdHx\lab\lab__s1__walking__20261102T185026Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: stopDatasetRecording
[DATASET] stopped: 5 frames (0 skipped) in 1 file(s)
[DATASET] write failed, stopping recording: ENOSPC: no space left on device
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording walking (count=1) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-progress-aYvd2r\lab\lab__s1__walking__20261102T185026Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: startDatasetRecording
[DATASET] recording empty (count=0) room=lab -> C:\Users\thaer\AppData\Local\Temp\phantom-ds-progress-Vztqgu\lab\lab__s1__empty__20261102T185026Z.jsonl
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
✔ non-AI client's targetIdentity produces no state change and no broadcast (3.4762ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.7051ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.6873ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (2.0957ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.9235ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.7204ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.7096ms)
✔ new-client snapshot (sendLiveSnapshotToClient) always serves the deterministic value, never an injected one (1.4722ms)
✔ resolveLiveNodeMode: cold start with only node 2 reporting resolves single_node, not fused (1.7933ms)
✔ resolveLiveNodeMode: both nodes freshly reporting resolves fused_two_node (0.9318ms)
✔ resolveLiveNodeMode: node 1 going stale mid-session (dropout) falls back to single_node while node 2 keeps reporting (0.5965ms)
✔ resolveLiveNodeMode: both nodes stale resolves single_node (no separate 'no nodes' state) (0.7525ms)
✔ two-node fusion uses the active pair when nodes 3 and 4 are the live sensors (2.0508ms)
✔ singleNodeMotionDetected: realistic empty-room node2 noise (node1 silent) does not trip the gate (1.0254ms)
✔ singleNodeMotionDetected: real moving-target-scale node motion still trips the gate (no over-correction) (0.6366ms)
✔ motionStatus broadcast: known-unreliable MotionGate false positive does not reach the dashboard in an empty room (2.3592ms)
✔ motionStatus broadcast: manual motionGateEnabled threshold is not overridden (1.0209ms)
✔ fused_room: radialTarget broadcast and roomFusedSnapshot both reflect the Kalman-filtered position, not raw (15.8298ms)
✔ fused_room radialTarget is labeled fused_room_centroid, not the 1-D two-node basis (9.4117ms)
✔ fused_room localization still runs when ISAR/MUSIC is disabled (2.1474ms)
✔ micro-Doppler classifier is fed the per-node background-subtracted residual (6.5698ms)
✔ hardware queue is bounded per node so a 4-node burst cannot pin it at the global cap (6.56ms)
✔ targetDebug reports fps and motion for every anchored node, not just 1 and 2 (1.0321ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (22.8007ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (2.129ms)
✔ trackActiveNodeSet reports join/leave transitions exactly once (0.6994ms)
✔ fused_room: position is weighted by each node's rise above its own baseline (no centre pull) (1.6367ms)
✔ fused_room with a router: evidence on node 1 only is placed on node 1's link, not at a far corner (6.2768ms)
✔ fused_room: no target while the room tier is absent (1.0792ms)
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (1.0339ms)
✔ fused_room: present_still without a prior target never creates one (0.7272ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (1.3877ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.9302ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (19.0052ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.9426ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (2.2061ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (1.8488ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.8304ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (9.0874ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.4282ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.4234ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (1.8467ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (1.2935ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (14.089ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (10.6256ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.3658ms)
✔ protected route returns 401 without a session (102.5293ms)
✔ protected route returns 401 with a garbage/forged cookie (33.1369ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (468.3616ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (184.4225ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (22.3648ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (production no longer does this) (2.4086ms)
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invariant for the exact same scenario above (0.5007ms)
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3494ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (54.0029ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (7.8315ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.2518ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.2461ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.3235ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.1435ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2002ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.1298ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.342ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.2727ms)
ℹ tests 407
ℹ suites 0
ℹ pass 407
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9420.0994
EXIT=0
```

### Python full suite, after (same collection errors)

```text

=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_count_model.py __________________
ImportError while importing test module 'D:\WIFI csi\phanotm\phantom scan\tests\test_count_model.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\thaer\AppData\Local\Programs\Python\Python313\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_count_model.py:7: in <module>
    from phantom.activity_train import TrainingRefused
phantom\activity_train.py:24: in <module>
    from sklearn.linear_model import LogisticRegression
E   ModuleNotFoundError: No module named 'sklearn'
________________ ERROR collecting tests/test_train_activity.py ________________
ImportError while importing test module 'D:\WIFI csi\phanotm\phantom scan\tests\test_train_activity.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\thaer\AppData\Local\Programs\Python\Python313\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_train_activity.py:8: in <module>
    from phantom.activity_train import TrainingRefused, train_activity
phantom\activity_train.py:24: in <module>
    from sklearn.linear_model import LogisticRegression
E   ModuleNotFoundError: No module named 'sklearn'
=========================== short test summary info ===========================
ERROR tests/test_count_model.py
ERROR tests/test_train_activity.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 4.35s
EXIT=2
```

### Python, collectable files only, after (includes the 42 new tests)

```text
.............................................sssss...................... [ 36%]
........................................................................ [ 73%]
...................................................                      [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py::TestDWTDenoiser::test_online_mode
tests/test_csi_pipeline.py::TestDBSCANClustering::test_pipeline_clustering
tests/test_csi_pipeline.py::TestFullPipeline::test_processes_real_data_without_crashing
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_all_recordings_process_cleanly
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_motion_detection_varies
tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_distance_estimation_reasonable
  D:\WIFI csi\phanotm\phantom scan\.venv\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundary effects.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================ slowest 10 durations =============================
15.22s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_motion_detection_varies
7.65s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_all_recordings_process_cleanly
4.11s call     tests/test_presence_eval_inventory.py::test_real_folder_counts_match_inventory_json
4.03s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_ingest_batch_from_recording
4.02s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_health_endpoint
4.02s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_ingest_single_sample
4.01s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_status_endpoint
4.01s call     tests/test_esp_capture_e2e.py::TestServerIngestion::test_queue_status
2.91s call     tests/test_esp_capture_e2e.py::TestPipelineWithRecordings::test_distance_estimation_reasonable
1.85s call     tests/test_presence_eval_twonode.py::test_rules_on_synthetic_world_where_only_node_1_sees_the_person
190 passed, 5 skipped, 6 warnings in 67.72s (0:01:07)
EXIT=0
```

### F1/F2 Python invariants, after

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\phantom scan\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.16s =======================
EXIT=0
```

### AI-firewall TS tests, after

```text
[WS] handleMessage from attacker: targetIdentity
[WS][SEC] non-AI client attacker sent targetIdentity — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: vitalSigns
[WS][SEC] non-AI client attacker sent vitalSigns — ignored (PS-AUDIT-014)
[WS] handleMessage from attacker: poseFrame
[WS][SEC] non-AI client attacker sent poseFrame — ignored (PS-AUDIT-014)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: poseFrame
[WS] handleMessage from ai: registerAIClient
[WS] Registered AI Inference client: ai
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[NODES] node 1 live (active: 1,2,3,4)
[NODES] node 2 live (active: 1,2,3,4)
[NODES] node 3 live (active: 1,2,3,4)
[NODES] node 4 live (active: 1,2,3,4)
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: targetIdentity
[WS] AI client ai sent malformed targetIdentity — dropped: Invalid enum value. Expected 'human' | 'mechanical' | 'unknown', received 'alien'
[WS] handleMessage from ai: targetIdentity
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (2.1702ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.6181ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.4811ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.1941ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.5011ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3354ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3765ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (17.2266ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.1783ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.8198ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3229ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1071.4307
EXIT=0
```

## Notes

* `tests/test_presence_eval_twonode.py` was modified on disk by something other than me during the session (a leading space appeared on line 1, making it a syntax error that would abort collection of the whole run). That single character was removed; nothing else in the file differs from what I wrote. If the leading space was intentional, tell me.
* The real-folder test `test_real_folder_counts_match_inventory_json` runs (not skipped) here because the dataset and `results/inventory.json` exist; it is skipped automatically elsewhere.
