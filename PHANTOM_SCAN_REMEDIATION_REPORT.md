# Phantom Scan Remediation Report

Tracks remediation of findings from `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`. Entries are
added as work packages close. This report currently covers **WP-0, WP-1, WP-2 (including
WP-2 close-out), WP-3**. WP-4 onward are not yet started.

## WP-0 — Secret rotation (PS-AUDIT-012)

**Status: FIXED.** Commit `6096db8`. SSID/password placeholders in `sdkconfig.defaults`;
`sdkconfig`, `sdkconfig.old`, `nvs_node1.bin`, `nvs_node2.bin` untracked and gitignored;
`firmware/esp32-csi-node/PROVISIONING.md` documents the NVS flow. The real WPA2 password
remains in git history — history scrub is an operator action, not automated here.

## WP-1 — Runtime authority decision (PS-AUDIT-001)

**Status: DECISION RECORDED.** Commit `438b1f3`. Operator chose Option B (bless shipped
reality): the Node/TS server is THE AUTHORITY for Milestone-1 live operation. Recorded in
`docs/adr/ADR-051-runtime-authority.md` (ADR-019 was already taken) and `README.md`.
`phantom/` is reference/replay/test tooling only.

## WP-2 — Firmware sovereign is_human respiratory gate (PS-AUDIT-002)

**Status: FIXED**, with one intentional canon correction and one documented residual
limitation. Commit `0cf351d` (initial), plus this close-out session's follow-up commit.

### Original fix (commit `0cf351d`)

`edge_processing.c`'s presence bit was `motion_energy > threshold` with no respiratory
check. Extracted the pure DSP math (biquad, phase unwrap, BPM estimators) into
`edge_dsp_pure.c/.h` (ESP-IDF-free, host-testable) and added
`edge_evaluate_human_presence(motion_present, breathing_data_ready, breathing_bpm, resp_conf)`,
called from `process_frame` Step 9. Cardiac-band data has no parameter in that function by
construction (F1 compile-time guarantee).

### Close-out review — Fix 1: single source of truth

**Status: CONFIRMED, no code change needed.** Verified `edge_processing.c` contains zero
function *definitions* matching the pure-module signatures (grep for
`^(void|float|bool) (biquad_bandpass_design|biquad_process|unwrap_phase|extract_phase|
estimate_bpm_zero_crossing|estimate_periodicity_autocorr|edge_evaluate_human_presence)`
returns no matches). `edge_processing.h:70` includes `edge_dsp_pure.h`. Call sites in
`edge_processing.c`: `extract_phase` (:454,654), `unwrap_phase` (:465,657),
`biquad_process` (:473-474,686-687), `biquad_bandpass_design` (:639-643,1003-1009),
`estimate_bpm_zero_crossing` (:494,714), `estimate_periodicity_autocorr` (:495-500,716-720),
and the verdict itself at `edge_processing.c:788` →
`s_presence_detected = edge_evaluate_human_presence(...)`. The firmware target and the host
test (`main/test/test_edge_dsp_pure.c`) both compile `edge_dsp_pure.c` — same code, both
places.

### Close-out review — Fix 2: sample-rate contract

**Status: CONTRACT CLEAN, no code change needed.** `edge_dsp_pure.c`'s `fs`/`sample_rate`
are function parameters, not constants — confirmed no hardcoded frequency literal inside
`edge_dsp_pure.c` (grep for `sample_rate|SAMPLE_RATE|fs\b|FS\b|dt\b|interval|hz|Hz|BPM`
shows only parameter names and derived math). The caller, `edge_processing.c:617-631`,
measures the real inter-frame timestamp delta (`dt`), EMA-smooths it into
`s_sample_rate_hz` (`:626`), clamps to `[8, 30]` Hz (`:627-628`) — a band matching this
firmware's own documented self-ping-driven reality ("callback rate is variable (self-ping +
ambient traffic, ~13-19 Hz)", comment at `:618`) — and passes that measured value into every
`edge_dsp_pure` call (`:639-643,649,714-720,1003-1009`). Biquads are re-tuned whenever the
measured rate drifts >15% from their design frequency (`:638-646`). WP-6/WP-10 inherit this
clean contract; no action required there for the fs axis itself.

Note: `main/test/test_edge_dsp_pure.c` uses a **fixed** `FS 15.0f` for reproducibility — that
is a deliberate, disclosed host-test parameter (matching the firmware's own
`s_sample_rate_hz` reset default at `edge_processing.c:983`), not evidence of a hardcoded
production constant.

### Close-out review — Fix 3: band-edge reconciliation

**Status: FIXED — Option A (clamp to canon).** No clinical rationale for tachypnea coverage
(BPM > 30) exists anywhere in this codebase or the canonical spec. The pre-existing firmware
sanity clamp used `6.0f, 40.0f` (0.667 Hz upper edge), exceeding canon's 0.1-0.5 Hz (6-30
BPM) — an undocumented drift never checked against canon before this close-out, not an
intentional design choice.

Changed `EDGE_BREATHING_BPM_MAX` from `40.0f` to `30.0f` in `edge_dsp_pure.h`. This single
constant is now the sole source of truth for THREE call sites that previously used
independent literals:
- `edge_processing.c:716-717` (single-target Step 7 breathing search band) — already used
  the constants from the original WP-2 commit.
- `edge_processing.c:723` (single-target sanity clamp) — already used the constants.
- `edge_processing.c:495-496,503` (multi-person vitals path) — **found during close-out**,
  this path had its own independent `6.0f, 40.0f` literals that WP-2's original commit
  missed (it only touched the single-target Step 7/9 path). Updated to use
  `EDGE_BREATHING_BPM_MIN/MAX`.
- `main/test/test_edge_dsp_pure.c:180` — boundary test literal `40.1f` changed to
  `EDGE_BREATHING_BPM_MAX + 0.1f` (self-adjusting to the constant).

`git grep` for `6-40|6\.0f.*40\.0f` in `firmware/esp32-csi-node/main` now returns no matches
outside historical/comment references that were also corrected.

### Recalibration required by Fix 3 (band changed → threshold re-verified)

Fix 3 narrowed the search band from 6-30 BPM (was 6-40); this could invalidate the WP-2
`EDGE_RESP_CONF_MIN = 0.5` calibration, which was originally validated only against an 8-32
BPM synthetic sweep (not the full 6-30 canonical band). Re-ran the Monte Carlo calibration
against the corrected 6-30 BPM band (500 trials each, real `edge_dsp_pure.c`, scratch driver
described in the Appendix):

- **Noise**: unchanged from the original run (noise generation doesn't depend on the
  breathing band) — P(resp_conf ≥ 0.5) = 0.2% (1/500), max observed 0.53.
- **Breathing, full 6-30 BPM band**: mean resp_conf = 0.894, **min resp_conf = 0.379** (down
  from the earlier 8-32 BPM sweep's 0.589 minimum). The weaker cases cluster near the 6 BPM
  edge, where only ~1.7 respiratory cycles fit in the 256-sample (~17 s at 15 Hz) analysis
  window — a genuinely weaker autocorrelation signal at that edge, not a bug.
- At `EDGE_RESP_CONF_MIN = 0.5`: **8% missed-detection rate (40/500)** on the full-band sweep,
  concentrated at low BPM, vs. 0.2% noise false-positive rate.

**Decision: kept `EDGE_RESP_CONF_MIN = 0.5`**, not lowered. Rationale: this is a firewall
gate (F1) where a false "human present" claim is the worse failure mode than a delayed one;
Step 9 re-evaluates every frame, so a single miss delays registration by one analysis window
rather than permanently losing a continuously-present target. This trade-off is itself
`[TO BE MEASURED]` against real slow-breather captures — see UNVERIFIED register below.
`edge_dsp_pure.h`'s `EDGE_RESP_CONF_MIN` docstring documents both figures (noise FP and
breathing miss rate) so a future recalibration has the real numbers, not a rounded summary.

### Known limitation — tonal aliasing (tracked, not fixed)

**ID: `PS-REMED-WP2-FOLLOWUP-01`. Status: OPEN, tracked.**

The autocorrelation-based periodicity estimator (`estimate_periodicity_autocorr`,
`edge_dsp_pure.c`) can alias a clean, highly periodic non-human vibration into the
respiratory band, because a band-limited pure tone's autocorrelation retains strong peaks at
integer sub-harmonics of its true period. Operational vector: a fan or HVAC unit running at a
stable RPM (not the broadband, non-tonal flutter of real ambient air movement) could produce
a near-pure mechanical oscillation whose sub-harmonic lands in the 6-30 BPM band and reads as
confident "breathing."

Evidence (`main/test/test_edge_dsp_pure.c`, `demo_known_limitation_tonal_aliasing`, printed
not asserted): a clean 2.2 Hz tone with no noise produces `resp_conf = 1.000`,
`breathing_bpm = 26.4` (in-band) — a false positive by construction. By contrast, realistic
broadband/non-tonal motion (`test_broadband_motion_alone_is_not_human`) reliably stays below
`EDGE_RESP_CONF_MIN` (`resp_conf = 0.137` in that run; ≤0.2% chance of exceeding 0.5 across
500 independent noise trials).

**Not fixed in WP-2** because closing it requires a harmonic-purity or peak-sharpness check
in the estimator itself — a distinct algorithmic change from "add a gate," and out of WP-2's
scope per the standing rule against batching unrelated findings into one work package.
Recommended follow-up: reject a breathing-band candidate whose peak profile is too sharp/pure
relative to real (slightly irregular) human breathing, or cross-check against a
simultaneously-computed broadband spectral-flatness measure.

### Verification-status caveats (measured vs. pending, rule 6)

- All WP-2 calibration figures (noise false-positive rate, breathing missed-detection rate)
  are from **synthetic signals only** — no real CSI captures were used, because none showing
  a clean respiratory-only vs. non-human-motion-only ground truth are available in this
  environment. These figures are `[TO BE MEASURED]` against real captures before being cited
  as production accuracy claims.
- The ESP-IDF/xtensa cross-build of the modified firmware is **`UNVERIFIED`** — no ESP-IDF
  toolchain is available in this environment. The moved DSP functions are byte-identical in
  body to their pre-WP-2 counterparts (only relocated + de-`static`'d), and
  `main/CMakeLists.txt` was updated to compile `edge_dsp_pure.c` into the firmware target, but
  an actual on-device or ESP-IDF-toolchain build has not been run.
- The host test (`main/test/test_edge_dsp_pure.c`) and calibration driver both compile
  cleanly with `-Wall -Wextra` (zero warnings) on GCC 15.2.0 (MSYS2 mingw64) and exit 0.

## WP-3 — F1 WebSocket presentation gap (PS-AUDIT-014)

**Status: FIXED.** Commit `096f611`.

`server/lib/websocket.ts`'s `handleMessage()` accepted `poseFrame`/`targetIdentity`/
`vitalSigns` from any authenticated client (gated only on `this.status.isProcessing`), and
`targetIdentity`/`vitalSigns` wrote directly into `currentTargetIdentity`/`currentVitalSigns`
— the same fields the deterministic pipeline (micro-Doppler classifier, VitalsComputer/board
fallback) writes every processing tick. This let the AI sidecar's model-derived `humanProb`
transiently occupy the verdict-adjacent authoritative channel, and let any non-AI
authenticated client inject fake identity/vitals/pose data visible to every dashboard.

Fix: all three message types now require `client?.isAI` (set only via a prior
`registerAIClient` message); a rejected non-AI message is logged
(`console.warn(...PS-AUDIT-014)`), matching the `SourcePinningGuard` logging convention
already used in `server/lib/udp-server.ts`. `targetIdentity`/`vitalSigns` from an AI client no
longer write the authoritative fields at all — they are relayed under distinct types
(`advisoryIdentity`, `advisoryVitalSigns`) instead, so AI output structurally cannot occupy
the same channel as the deterministic verdict. `poseFrame` keeps writing
`currentPoseFrame` (no deterministic source exists for skeletal keypoints, and it was never a
verdict channel) — now correctly gated on `isAI`.

F1 static re-trace (`git grep 'this\.currentTargetIdentity\s*=|this\.currentVitalSigns\s*='`
in `server/lib/websocket.ts`): each field has exactly two writers — the deterministic pipeline
(`:963` classifier assignment, `:1166` vitals assignment) and the artifact-clear reset
(`:1310-1311`). No client-message writer remains for either field.

Verified `scripts/ai_inference.py` needs no change: `on_open` (`:614-618`) sends
`registerAIClient` before any inference message, so its existing messages are correctly gated
and now arrive as the new advisory types without any sidecar-side edit.

**Disclosed side effect, not silently absorbed:** `client/src/hooks/use-websocket.ts` has no
handler for `advisoryIdentity`/`advisoryVitalSigns` yet, so the AI sidecar's advisory output
will not render on the dashboard until that UI work is added — out of scope for this security
fix, and a strictly safer state than before (where it rendered by sharing the authoritative
channel).

New coverage: `server/lib/websocket.test.ts` (new file, 8 tests) — non-AI client's
`targetIdentity`/`vitalSigns`/`poseFrame` produce no state change and no broadcast; AI
client's `targetIdentity`/`vitalSigns` relay under the new advisory types and never write the
authoritative fields; AI `poseFrame` still works; `registerAIClient` unblocks the gate;
`sendLiveSnapshotToClient` always serves the deterministic value even after both an injection
attempt and a legitimate AI message arrive first.

`npm test`: 107/107 pass (99 prior + 8 new). `npm run check` (tsc): clean, no errors.
`pytest`: 82 passed, 1 skipped (unaffected — TS-only change).

## UNVERIFIED register (WP-2 additions)

- `UNVERIFIED — ESP-IDF/xtensa firmware build of the WP-2 changes`. Needed: ESP-IDF toolchain
  (not present in this environment) to confirm `edge_dsp_pure.c` compiles and links into the
  actual firmware image, and ideally an on-device smoke test.
- `UNVERIFIED — EDGE_RESP_CONF_MIN = 0.5's real-world missed-detection rate for slow (near-6
  BPM) breathers`. Needed: real CSI captures of a stationary subject breathing at the low end
  of the physiological range, to confirm the "re-evaluated every frame, so a miss just
  delays" mitigation actually holds in practice rather than causing intermittent verdict
  flicker.
- `UNVERIFIED — PS-REMED-WP2-FOLLOWUP-01 real-world exposure`. Needed: a real recording near
  a running fan/HVAC unit at a stable RPM, replayed through the firmware/host-test pipeline,
  to confirm (or rule out) the tonal-aliasing false positive occurs with real hardware noise
  characteristics, not just an idealized synthetic tone.

## Appendix — commands run this close-out session

```
grep -n "edge_dsp_pure" firmware/esp32-csi-node/main/edge_processing.c
grep -n "^(void|float|bool) (biquad_bandpass_design|biquad_process|unwrap_phase|
  extract_phase|estimate_bpm_zero_crossing|estimate_periodicity_autocorr|
  edge_evaluate_human_presence)" firmware/esp32-csi-node/main/edge_processing.c
grep -n "sample_rate|SAMPLE_RATE|fs\b|FS\b|dt\b|interval|hz|Hz|BPM" \
  firmware/esp32-csi-node/main/edge_dsp_pure.c
grep -n "s_sample_rate_hz|s_filter_design_fs|const float sample_rate" \
  firmware/esp32-csi-node/main/edge_processing.c
grep -n "6-40|6\.0f.*40\.0f|breathing.*40|40.*[Bb]reathing" firmware/esp32-csi-node/main
```

Host-test rebuild/run (from `firmware/esp32-csi-node/main`, GCC 15.2.0 MSYS2 mingw64):
```
gcc -std=c99 -O2 -Wall -Wextra -I. test/test_edge_dsp_pure.c edge_dsp_pure.c -lm \
    -o test/test_edge_dsp_pure.exe
./test/test_edge_dsp_pure.exe
```
Result: 0 compiler warnings, all assertions passed, exit 0 (full transcript in the commit
message).

Monte Carlo recalibration (scratch driver `calibrate.c`, not committed — reproduces the
`resp_conf` distribution for pure-noise vs. synthetic-breathing inputs across 500 trials
each, linking the real `edge_dsp_pure.c`):
```
gcc -std=c99 -O2 -Wall -I<firmware>/main calibrate.c <firmware>/main/edge_dsp_pure.c -lm \
    -o calibrate.exe
./calibrate.exe
```
Output reproduced in the "Recalibration required by Fix 3" section above.

Full-suite re-verification after this close-out session:
```
npm test
```
→ `99 tests, 99 pass, 0 fail`.
```
python -m pytest tests -q
```
→ `82 passed, 1 skipped` (total 83, unchanged from the original WP-2 session's `77 passed, 6
skipped`; the skip/pass split shift is environment-dependent — e.g. an optional AI-stack
dependency's availability — and unrelated to this firmware-only close-out, which touched no
Python files. Reported as observed, not silently reconciled to the stale figure.)
