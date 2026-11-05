# 10 — PS-FIX-12 design note: rate-scaled timing (DESIGN ONLY; no production code written)

**Provenance.** 2026-11-04, HEAD `0f2db12`, dirty tree. Every `file:line` below was read this session. Rates used: **11 fps** (a degraded link), **41–43 fps** (the figure in the firmware comment and the dashboard; 42 used for arithmetic) and **65 fps** (measured median per node in the 14 recordings, `12-PS-FIX-07.md`). Nothing here changes a threshold, a tier constant or a setting; this note proposes, the owner decides at Gate 3.

## 1. The problem in one paragraph

Several time constants are counted in **frames or samples** and so silently assume a frame rate. The same constant means a 0.46 s window at 65 fps, a 0.71 s window at 42 fps and a 2.7 s window at 11 fps. When a node's rate changes inside a session (a link-state change such as the s7 step, node 1: 63 → 44 fps, `08-WAVE2-addendum.md`), the window silently stretches by 43 % mid-session. The fused detector's own window is already defined in time, which is the pattern to follow.

## 2. Already time-based (no change proposed)

| where | definition |
|--|--|
| `server/lib/websocket.ts:41-44, 2048, 2062` | per-node motion window `MOTION_WINDOW_MS = 1500` by timestamp ("yield-independent"): holds ~16 frames at 11 fps, ~63 at 42, ~98 at 65 |
| `server/lib/node-baseline.ts:145` | tier debounce 0.4 s |
| `server/lib/target-state.ts` (`LIVE_TARGET_STALE_TIMEOUT_MS`, `LIVE_TARGET_CLEAR_TIMEOUT_MS`) | target ageing in ms |
| `server/lib/dataset-recorder.ts:139` | summary window 10 s |
| `scripts/accuracy/calibration-soak.ts` | 10 s blocks, minutes-based soak rules |

One residual rate dependence even there: the statistic over the 1.5 s window (a standard deviation across frames) is noisier with fewer frames (16 at 11 fps against 98 at 65 fps). That is estimator variance, not a window-length error.

## 3. Constants counted in frames or samples (the list)

| # | where (`file:line`) | constant | assumed rate | meaning in seconds at **11 / 42 / 65 fps** |
|--|--|--|--|--|
| 1 | `server/lib/signal-processing.ts:804` | `MotionGate.bufferSize = 30` | 20 Hz tick | 2.73 / 0.71 / 0.46 s (if fed per frame; fed per 50 ms tick it is 1.5 s regardless) |
| 2 | `server/lib/signal-processing.ts:808-809, 828` | `MotionGate.calibrationCount = 100` (auto-calibration of the 3 sigma floor) | 20 Hz tick | 9.09 / 2.38 / 1.54 s per frame; 5 s per tick |
| 3 | `server/lib/signal-processing.ts:439-441` | `MicroDopplerClassifier(bufferSize 40, sampleRate 20)`; `highFreqRatio` band above 5 Hz | 20 Hz | 3.64 / 0.95 / 0.62 s per frame; 2 s per tick; the 5 Hz edge moves with the real rate |
| 4 | `server/lib/vitals.ts:86-88` | `VitalsComputer(20, 10)` buffer 200; DFT mapped at `sampleRate` 20 (`:121`) | 20 Hz | 18.18 / 4.76 / 3.08 s per frame; 10 s per tick; every band edge scales with the real rate |
| 5 | `server/lib/vitals.ts` (Hampel filter, window 7) | 7 samples | 20 Hz | 0.64 / 0.17 / 0.11 s |
| 6 | `server/lib/websocket.ts:806-809` | `setInterval(processFrame, 50)` + one dequeue per tick | 20 Hz | the per-tick path decimates to 20 Hz (PS-FIX-43) whatever the frame rate |
| 7 | `server/lib/websocket.ts:1105, 2722` | queue cap 1000 samples (all nodes) | — | 4 nodes: 22.7 / 5.95 / 3.85 s of backlog; 2 nodes: 45.5 / 11.9 / 7.7 s |
| 8 | `server/lib/websocket.ts:1078, 1097, 1174, 1648, 1653` | `framesProcessed % 20 / 3 / 10 / 20` broadcast cadences | 20 Hz tick | tick-based: 1 s, 0.15 s, 0.5 s, 1 s |
| 9 | `server/lib/websocket.ts:1483, 1490, 1854, 1639`; `server/lib/tracking.ts:386` | caps of 200 report samples, 200 point-cloud entries, 50 recording flush, 50 point buffer | 20 Hz tick | 10 s / 10 s / 2.5 s / 2.5 s at the tick; per frame 4.5-18 s at 11 fps |
| 10 | `server/lib/fused-position-kalman.ts:70` | `MAX_CONSECUTIVE_REJECTIONS = 5` | per tick | 0.45 / 0.12 / 0.08 s per frame; 0.25 s per tick |
| 11 | `server/lib/websocket.ts:2507-2518` | health warning "`(<20) … motion window assumes ~40 fps`" | 40 fps | text assumes 40; measured 65 |
| 12 | `scripts/ai_inference.py:201` | `HISTORY_LEN = 100` frames feeding `estimate_vitals` (`fs` is measured: `_estimate_fs`, `:492`) | measured mean | 9.09 / 2.38 / 1.54 s: at 65 fps the FFT bin spacing is 0.65 Hz, so **no bin lies inside the 0.1-0.5 Hz respiration band** |
| 13 | `scripts/ai_inference.py:258, 262, 269` | `ACTIVITY_HISTORY_LEN 6`, `CALIBRATION_HISTORY_LEN 50`, `EMBED_HISTORY_LEN 50` | the 5 Hz inference throttle | tick-based (1.2 s, 10 s, 10 s) |
| 14 | `phantom/count_model.py:31` | `WINDOW_FRAMES = 40` (the model's input shape; comment "~0.8-1 s at 40-50 fps") | 40-50 fps | 3.64 / 0.95 / 0.62 s; **the trained model has this shape fixed** |
| 15 | `phantom/features.py:50` | `MIN_FRAMES = 8` | — | 0.73 / 0.19 / 0.12 s |
| 16 | `phantom/runtime.py:72`, `phantom/dsp.py:84, 181` | `sample_rate_hz = 5.0` (`RespirationBandFilter`) | 5 Hz | reference runtime, not the live path |
| 17 | `firmware/esp32-csi-node/main/edge_processing.h:42` | `EDGE_CALIB_FRAMES = 1200` ("~60 s at 20 Hz") | 20 Hz | **109 / 28.6 / 18.5 s**; the 3 sigma baseline is fitted on an 18 s sample at 65 fps |
| 18 | `firmware/esp32-csi-node/main/edge_processing.h:34, 32` | `EDGE_PHASE_HISTORY_LEN 256`, `EDGE_RING_SLOTS 16` | — | 23.3 / 6.10 / 3.94 s; 1.5 / 0.38 / 0.25 s of ring buffer |

(Rows 1-6 and 8-10 act on the legacy per-tick path; rows 12-15 are the sidecar and the count model; rows 17-18 are firmware. The Python reference runtime and the evaluation tooling are listed for completeness.)

## 4. Proposed scaling rule, per class of constant

1. **Time-defined constants** (the design intent): store the constant in **seconds**; the count is `round(seconds × fs_node)`, clamped to `[min_count, max_count]`, where `fs_node` is the node's measured rate. Rows 1-5, 7, 9, 10, 12, 15.
2. **Tick-defined constants** (rows 6, 8, 13): leave as they are, because the tick is a clock; but the **decimation** that feeds them (row 6) is a separate decision (PS-FIX-43).
3. **Model-defined constants** (row 14): the input shape is a property of the trained network. Options: resample each window to the training rate with an anti-alias filter (as in PS-FIX-40), or retrain at the deployed rate. Not a simple rescale.
4. **Firmware constants** (rows 17-18): scale on board from the measured callback rate, or define in milliseconds. Host-tested logic only; **never flashed without the owner's say-so**.
5. **The rate estimate** (`fs_node`): the median inter-arrival over the last 5 s of **accepted** frames, clamped to [10, 100] Hz, updated at most once per second, with a reset at a link-state epoch boundary. Everything is computed per node; the fused detector already combines per-node values. **Fail closed:** below a floor (the calibration tool uses 20 fps) the node reports no usable rate and the output shows NO DATA (Item E), never EMPTY.

## 5. Failure cases (what happens when the rate is wrong or changes)

| case | effect on windows if counted in frames (today) | effect with the rule above |
|--|--|--|
| rate **change** inside a session, s7 node 1: 63 → 44 fps | a 100-frame window grows 1.59 s → 2.27 s (+43 %); a 1200-frame firmware baseline 19.0 s → 27.3 s | window stays at its time length; the count follows the rate estimate with a lag of up to 5 s (the estimator's window) |
| rate **collapse** to 11 fps | a 40-frame window is 3.6 s (5.8 times longer than at 65); the vitals buffer is 18 s | counts shrink; a time window of 1.5 s holds only ~16 frames, so the motion statistic gets noisy; below the floor the output is NO DATA |
| **wrong estimate** (a burst of duplicated or delayed frames) | n/a today | clamped, rate-limited, median-based; an estimate outside [10, 100] is ignored and the last good value is kept for a bounded time, then NO DATA |
| **node reboot / link-state epoch** (PS-FIX-32) | windows straddle the change | windows and the rate estimate reset at the epoch boundary; a settling period before any verdict (the SETTLING chip) |
| **mixed rates across nodes** (65, 44, 63, 62) | one fixed count is a different duration per node | per-node counts; the fusion consumes per-node values, so no cross-node alignment is needed |
| **both** the alias path and the rate (row 6) | 20 Hz decimation without an anti-alias filter | decided separately (PS-FIX-43) |

## 6. Test plan (to run only after the owner approves implementation)

1. **Unit, synthetic:** streams at 11, 42 and 65 fps with the same physical content: every converted window has the same duration in seconds (within one frame); a step 65 → 44 and 65 → 11 mid-stream changes counts within the estimator lag and never the duration by more than the lag; a missing or implausible rate fails closed.
2. **Property test:** the converted count is monotone in the rate and within the clamps.
3. **Shadow mode first** (as for the PHY guard): compute the scaled windows alongside the current ones, log the differences, **change no output**; run it live and over the recordings.
4. **Replay on the real sessions, both failure directions, counts per session** (s1-s10, using the recording-readiness validator once it exists): (a) **under-detection**: walking and two-person segments: the number of seconds with a marker, before and after, must not fall; (b) **ghost targets**: empty, fan and no-data segments: the number of seconds with a marker or an EMPTY verdict must not rise. Report the numbers per session; **do not touch `DEFAULT_MOTION_THRESHOLD`, the tier thresholds 4/7/14 or the 0.05 fallback** whatever the replay shows (PS-EVAL-010 / -013 stay with the owner).
5. F1/F2 and the AI-firewall tests run explicitly after every step; the sessions diff-guard before and after.

## 7. What this note does NOT do

No production file is changed. It does not choose the reference rate, the estimator constants (5 s, clamp 10-100, 1 s update), the floor (20 fps) or the acceptance numbers; those are the owner's. It does not decide PS-FIX-43 (the 20 Hz decimation) or the count model's retrain-or-resample question.

## 8. Questions the owner must answer at Gate 3

1. **Reference rate.** Were the existing frame-counted constants tuned at about 42 fps (the firmware comment) or at the measured 65? Should behaviour at 42 fps stay identical after the change (keep the old numbers as the reference), or is a small shift acceptable?
2. **Approval to implement** the shadow mode first (compute only, change nothing), and to then switch outputs over file by file? Which files are in scope (the legacy per-tick path, the sidecar, the count model, the firmware)?
3. **Estimator parameters:** median over the last 5 s, clamp [10, 100] Hz, update once per second: acceptable, or set your own `[OWNER TO SET]`.
4. **Rate floor** below which a node reports NO DATA: 20 fps (the calibration tool's value) or another number `[OWNER TO SET]`?
5. **PS-FIX-43:** should the legacy 20 Hz per-tick decimation be retired in favour of per-node, rate-scaled processing, or kept (and anti-aliased)? This decides how much of rows 1-6 change.
6. **Count model (row 14):** resample with an anti-alias filter, or retrain at the deployed rate?
7. **Firmware (rows 17-18):** scale on board (needs a flash, host-tested only until you say so) or leave and document?
8. **Replay acceptance:** what counts as "no worse" per session in each direction (for example, a walking segment may lose at most N seconds of marker; an empty segment may gain none) `[OWNER TO SET]`; and which sessions count as evaluation data, given that the new dashboard output has no recording sidecar.
9. **Room-level hysteresis** (named in the original PS-FIX-12): in scope for the same change, or separate?
