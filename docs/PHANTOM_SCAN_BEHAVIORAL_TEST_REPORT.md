# Phantom Scan Behavioral Test Report

Date: 2026-07-20. Authority: Node/TS server (`docs/adr/ADR-051-runtime-authority.md`).
Scope: prove runtime behavior against canon, with real command output and file:line
evidence. This is a test-only pass — no product behavior was changed. Findings that
surfaced are recorded as `PS-BEHTEST-###` and left unfixed per the task's rules.

## 1. Coverage matrix

Legend: PASS = asserted and green. CITED = already proven by pre-existing coverage
(verified present before writing new tests, not duplicated). UNVERIFIED = stated with
the exact artifact needed.

| # | Canon property | Test ID(s) | Result |
|---|---|---|---|
| B1.1 | ADR-018 32-byte round-trip, all ~12 fields | `udp-server.test.ts:67-82` (TS), `tests/test_udp_ad018.py:87-101` (Python) | CITED |
| B1.2 | Heartbeat `0xC51100A1` excluded from CSI in both TS and Python | `udp-server.test.ts:84-92`, `tests/test_udp_ad018.py:104-117` | CITED |
| B1.3 | Fix C: ADR-018 4-byte magic checked before legacy interpretation, byte-0=`0x01` collision | `udp-server.test.ts:94-106` (byte-0 collision explicit, per `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:19`) | CITED |
| B1.4 | Legacy 20-byte gating (`allowLegacy` on/off) | `udp-server.test.ts:94-106` | CITED |
| B1.5 | Truncated frame rejected | `tests/behavioral/wire-protocol.test.ts` `"rejects a truncated frame..."` | **PASS (new)** |
| B1.6 | Declared-vs-actual IQ length mismatch rejected | `wire-protocol.test.ts` `"rejects a 32-byte header that declares more IQ bytes..."` | **PASS (new)** |
| B1.7 | Oversized frame: no crash | `wire-protocol.test.ts` `"accepts an oversized frame without crashing..."` | **PASS (new)**, see finding `PS-BEHTEST-001` |
| B1.8 | Non-1 schema version, live mode | `wire-protocol.test.ts` `"...falls through and is rejected in live mode"` | **PASS (new)** |
| B1.9 | Non-1 schema version, compat mode | `wire-protocol.test.ts` `"...is safely rejected (not silently misparsed as legacy garbage)"` | **PASS (new)** — see analysis below (initial hypothesis wrong, verified) |
| B1.10 | Garbage/unknown magic rejected directly | `wire-protocol.test.ts` `"rejects a garbage/unknown magic directly"` | **PASS (new)** |
| B1.11 | NaN/Inf poisoning in vitals/feature-state floats doesn't crash the parser | `wire-protocol.test.ts` (2 tests) | **PASS (new)**, see finding `PS-BEHTEST-002` |
| B2.1 | Respiratory gate positive (6/15/30 BPM synthetic) | `test_edge_dsp_pure.c: test_breathing_band_sets_human_present`, `test_bpm_estimate_consistent_across_measured_csi_rates` | CITED + PASS |
| B2.2 | Respiratory gate negative control (broadband/non-tonal motion) | `test_edge_dsp_pure.c: test_broadband_motion_alone_is_not_human` | CITED |
| B2.3 | Cardiac cannot set/flip verdict | `test_edge_dsp_pure.c: test_cardiac_only_cannot_flip_negative_respiratory_verdict` (structural: no cardiac parameter exists) | CITED |
| B2.4 | Empty-room/noise false-positive rate, ≥500 trials, committed | `test_edge_dsp_pure.c: test_monte_carlo_calibration_bounds` (**new, promoted from an uncommitted scratch run**) | **PASS (new)** — 0.2% FP rate, `[MEASURED-ON-SYNTHETIC]` |
| B2.5 | Sample-rate correctness across 3/5/7 Hz | `test_edge_dsp_pure.c: test_bpm_estimate_consistent_across_measured_csi_rates` (new) | **PASS (new)** |
| B2.6 | Sub-harmonic aliasing probe (tracked, not asserted) | `test_edge_dsp_pure.c: demo_known_limitation_tonal_aliasing` | CITED (`PS-REMED-WP2-FOLLOWUP-01`, still open) |
| B2.7 | Missed-detection rate on synthetic breathing across full 6-30 BPM band | `test_edge_dsp_pure.c: test_monte_carlo_calibration_bounds` | **PASS (new)** — 19.8%, see finding `PS-BEHTEST-003` |
| B3.1 | Midpoint (equal motion → balance≈0.5, x≈0.0) | `node-fusion.test.ts:24-29` | CITED |
| B3.2 | Endpoints (x→±1.5) | `node-fusion.test.ts:16-22,31-36` | CITED |
| B3.3 | Bounds/invariants over a real replayed session | `tests/behavioral/replay-authority.test.ts` (parse fidelity only, see B6) + historical Python-path replay (`PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`, 16,741 derived frames, zero violations) | CITED (historical, superseded path) + PASS (new, parse-only) |
| B3.4 | Divide-by-zero (r1+r2→0 / r1^p+r2^p→0 with `present` true) | `tests/behavioral/fusion-invariants.test.ts` `"hits the r1^p+r2^p<=EPS fallback..."` | **PASS (new)** |
| B3.5 | Gain-asymmetry sensitivity (static per-node gain, no real motion difference) | `tests/behavioral/fusion-invariants.test.ts` `"FINDING: a static multiplicative gain asymmetry..."` | **PASS (new)** — but the finding itself is `PS-BEHTEST-004` |
| B3.6 | Current live fusion (1500ms window + contrast + display bias) documented as non-canon baseline | `server/lib/websocket.ts:29-32`, `server/lib/node-fusion.ts:64-81,204-216`; called at `websocket.ts:1393-1400` with no `contrastExponent` override | CITED (analysis below) |
| B4.1 | F1: client message cannot write authoritative verdict fields | `server/lib/websocket.test.ts` (8 tests) | CITED |
| B4.2 | F1 mode integrity (AI stack absent) | grep evidence: zero matches for `deterministic_only`/`ai_status`/`torch`/`safetensors` under `server/` | CITED (analysis below — not a meaningful TS-side test target) |
| B4.3 | F2: `/api/esp32/configure` always 403, even authenticated | `tests/behavioral/firewall-f2.test.ts` (2 tests) | **PASS (new)** |
| B4.4 | F2: UI invariant, no node-config controls in dashboard source | `tests/test_invariants.py:39-45` | CITED |
| B5.1 | Source-IP pinning (TOFU, stale-rebind, static pin, foreign-IP reject) | `udp-server.test.ts:108-184,350-359` (8 cases) | CITED |
| B5.2 | Replay/out-of-order (`PacketOrderGuard`) | `udp-server.test.ts:186-202` | CITED |
| B5.3 | Auth: protected route 401 without session | `tests/behavioral/auth-security.test.ts` (2 tests) | **PASS (new)** |
| B5.4 | Auth: login rate-limiting (429) | `tests/behavioral/auth-security.test.ts` | **PASS (new)** |
| B5.5 | Auth: first-operator bootstrap restriction | `server/auth/service.test.ts:152-188` | CITED |
| B5.6 | Log-injection: adversarial content cannot corrupt JSONL structure | `tests/behavioral/log-injection.test.ts` | **PASS (new)** |
| B6.1 | Real captured frames parse through THE AUTHORITY with exact field fidelity | `tests/behavioral/replay-authority.test.ts` | **PASS (new)** |
| B6.2 | Full fusion-invariant replay on real captured bytes through THE AUTHORITY | — | `UNVERIFIED — see §4` (scope decision, not attempted this pass) |
| B6.3 | Empty-room negative control | — | `UNVERIFIED — see §4` |

## 2. New tests added

- `tests/behavioral/wire-protocol.test.ts` (8 tests) — B1 malformed-input hardening gaps.
- `tests/behavioral/fusion-invariants.test.ts` (2 tests) — gain-asymmetry finding, divide-by-zero direct hit.
- `tests/behavioral/auth-security.test.ts` (3 tests) — 401-without-session (×2), 429 rate-limit.
- `tests/behavioral/firewall-f2.test.ts` (2 tests) — `/api/esp32/configure` 403-always and 401-pre-auth.
- `tests/behavioral/log-injection.test.ts` (1 test) — adversarial JSONL content.
- `tests/behavioral/replay-authority.test.ts` (1 test) — real-capture parse fidelity through THE AUTHORITY.
- `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c` — added `test_bpm_estimate_consistent_across_measured_csi_rates` (3/5/7 Hz sweep) and `test_monte_carlo_calibration_bounds` (500-trial committed, asserted regression test — promotes the previously-uncommitted scratch calibration cited in `edge_dsp_pure.h`'s docstring into a real, reproducible test).
- `package.json:14` — `test` script now globs `tests/behavioral/**/*.test.ts` alongside `server/**/*.test.ts`, so these run under plain `npm test`, not as a side channel.

17 new TS tests + 2 new C tests = 19 new assertions across the campaign, all passing.

## 3. Findings

### PS-BEHTEST-001 — Severity LOW
**Problem:** `parseCsiPacket` has no upper bound on IQ payload length; an oversized datagram is parsed successfully rather than rejected.
**Analysis:** `server/lib/udp-server.ts:452-490` — the ADR-018 branch validates `iqData.length >= expectedIqBytes` (a lower bound) but never checks an upper bound. Confirmed via `tests/behavioral/wire-protocol.test.ts`: a 50,000-byte IQ payload against a header declaring 8 bytes parses without error.
**Impact:** Bounded by the UDP MTU (~65,507 bytes max per datagram) — a malicious/buggy sender cannot exceed that regardless. Low real exposure; noted for completeness, not urgent.
**Validation (proposed, not implemented):** cap `iqData` at a sane maximum (e.g. `EDGE_MAX_SUBCARRIERS * 8 * 2` bytes) and reject longer payloads.

### PS-BEHTEST-002 — Severity LOW
**Problem:** `parseFeatureStatePacket`/`parseEdgeVitalsPacket` pass NaN/Infinity through structurally from crafted float fields; the parser performs no float sanity check.
**Analysis:** `server/lib/udp-server.ts:369-426` — `readFloatLE` calls have no `Number.isFinite` guard. Confirmed via `tests/behavioral/wire-protocol.test.ts`: both parsers return `NaN`/`Infinity` fields unchanged from crafted input.
**Impact:** These fields feed the board-vitals-fallback path (`server/lib/websocket.ts` ~1153-1175, "board vitals fallback when host vitals unreliable"). A NaN/Inf board vitals reading could propagate to the `vitalSigns` broadcast. Not a verdict/F1 issue (vitals are not `is_human`), but worth a downstream guard.
**Validation (proposed):** add `Number.isFinite` checks at the parse boundary or the board-vitals-fallback consumer, rejecting non-finite readings.

### PS-BEHTEST-003 — Severity MEDIUM
**Problem:** The firmware respiratory gate's true combined missed-detection rate (motion **and** respiratory confidence both required) is ~20% across the full canonical 6-30 BPM band at low BPM — nearly 2.5x the 8% figure previously calculated during WP-2 close-out.
**Analysis:** `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c: test_monte_carlo_calibration_bounds`, 500 trials, real `edge_dsp_pure.c`. Output: `breathing_missed_detection_rate=0.198`. The WP-2 close-out's 8% figure (recorded in `edge_dsp_pure.h`'s docstring) was calculated by checking `resp_conf` in isolation; it did not account for `motion_energy` also independently failing to clear its 0.05 threshold at some low-amplitude/low-BPM synthetic combinations. This test uses the full `edge_evaluate_human_presence(motion_present, ...)` verdict path, which is the more representative number.
**Impact:** At the low end of the physiological breathing range (near 6 BPM, ~1.7 cycles fit in the 256-sample/~17s analysis window at 15 Hz), a real slow-breathing stationary subject has a meaningfully higher chance of a single analysis window failing to register presence than previously documented. Since Step 9 re-evaluates every frame, a miss delays registration rather than losing the target permanently — but this mitigation is itself `UNVERIFIED` against real captures.
**Validation (proposed):** real capture of a subject breathing at 6-10 BPM, replayed through the firmware pipeline, measuring actual time-to-first-detection rather than per-window miss rate.

### PS-BEHTEST-004 — Severity MEDIUM
**Problem:** A static multiplicative gain asymmetry between the two nodes (e.g. antenna/RSSI hardware mismatch between boards 29052/44260), with **no difference in real target motion**, measurably biases the reported `balance` away from 0.5.
**Analysis:** `tests/behavioral/fusion-invariants.test.ts`, `"FINDING: a static multiplicative gain asymmetry..."`. `computeNodeMotionFromMatrix`'s `motion` field (display value) IS gain-normalized (`absStd/base`), but `absStd` itself — the value `fuseTwoNodeTarget` actually receives as `r1`/`r2` and uses in the `balance = r2^p/(r1^p+r2^p)` ratio — is not. A 2x gain difference with identical relative motion depth at both nodes produced `|balance - 0.5| > 0.1` in the test. Root cause: `std(g·X) = g·std(X)` — the raw per-node standard deviation scales linearly with any multiplicative gain on the input amplitudes, and `base` (the mean-amplitude normalizer) is divided into the *display* `motion` value but never into `absStd`/`r1`/`r2` before they reach the balance ratio.
**Impact:** If nodes 29052 and 44260 have any real-world RSSI/gain mismatch (different antenna characteristics, different distances to typical multipath, firmware AGC differences), the displayed position would be systematically biased toward whichever node has higher gain, independent of where the target actually is. This is a design assumption ("RuView-faithful", `node-fusion.ts:117-130`) that both nodes have matched gain/normalization — never verified against real hardware.
**Validation (proposed):** normalize `r1`/`r2` by each node's own `base` (mean amplitude) before computing `balance`, then re-run this exact test to confirm gain-invariance; separately, measure real per-node gain differences between the two boards from a real capture.

## 4. Measured-on-synthetic vs UNVERIFIED-on-hardware register

**Measured-on-synthetic (real math, real compiler/runtime, synthetic input — not accuracy claims):**
- Noise false-positive rate: 0.2% (1/500 trials), max observed confidence 0.53 — `test_monte_carlo_calibration_bounds`.
- Breathing missed-detection rate: 19.8% (99/500 trials) across the full 6-30 BPM band — same test, see `PS-BEHTEST-003`.
- Sample-rate BPM estimation error: <1 BPM at 3, 5, and 7 Hz for a 15 BPM synthetic signal — `test_bpm_estimate_consistent_across_measured_csi_rates`.
- Gain-asymmetry balance drift: >0.1 balance units at 2x gain, synthetic per-subcarrier matrix — `fusion-invariants.test.ts`.

None of these are accuracy claims about detecting real humans. They measure whether the deterministic logic behaves as specified against synthetic inputs.

**UNVERIFIED — with the exact artifact needed:**
- `UNVERIFIED — empty-room negative control`. No capture in `data/sessions/` is labeled or verifiable as an empty room / no-occupant session (checked all 7 committed `.jsonl` files' headers and the three smallest files' full contents — none qualify; confirmed consistent with `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:439`, which flagged this same gap). Needed: a recorded session with a verified-empty room, replayed through THE AUTHORITY, to measure a REAL (not synthetic) false-positive rate.
- `UNVERIFIED — full fusion-invariant replay on real captured bytes through THE AUTHORITY`. `tests/behavioral/replay-authority.test.ts` proves real bytes parse correctly (B6.1) but does not re-run the amplitude-extraction/fusion pipeline on that real data, because that logic is private to `SignalProcessingServer`'s processing loop and isn't exported for reuse — exporting it would be a product change, out of scope for a test-only pass. The historical evidence in `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md` (16,741 derived frames replayed with zero invariant violations) used the **superseded Python path** (`phantom/runtime.py`), not THE AUTHORITY. Needed: either export the amplitude pipeline for testability, or a live TS-server-plus-real-UDP-replay harness.
- `UNVERIFIED — ESP-IDF/xtensa on-device firmware build`. No ESP-IDF toolchain is available in this environment (same gap noted in the WP-2 close-out report); the host-compiled `edge_dsp_pure.c` tests prove the math, not the cross-compiled firmware image.
- `UNVERIFIED — real per-node hardware gain difference between boards 29052/44260`. `PS-BEHTEST-004` is proven on synthetic matrices; the actual real-world magnitude of any gain mismatch between the two physical boards has never been measured.
- Accuracy figures (respiration/cardiac BPM accuracy, occupancy count accuracy, AoA/PDP ranging accuracy) remain `[TO BE MEASURED]` — this campaign did not produce or attempt any such claim, consistent with rule 2.

## 5. Reproduction

```powershell
# Full TS + new behavioral suite (129 tests)
npm test

# Typecheck
npm run check

# Python suite (unaffected by this pass)
& 'C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe' -m pytest tests -q

# Firmware host DSP tests (GCC 15.2.0, MSYS2 mingw64; not part of the ESP-IDF build)
cd firmware/esp32-csi-node/main
gcc -std=c99 -O2 -Wall -Wextra -I. test/test_edge_dsp_pure.c edge_dsp_pure.c -lm -o test/test_edge_dsp_pure.exe
./test/test_edge_dsp_pure.exe
```

Seeds: all synthetic-signal tests use a fixed linear-congruential generator (`s_rng = s_rng * 1103515245 + 12345`) seeded per-trial from a deterministic formula (e.g. `1000 + i*7919`), never wall-clock or OS entropy — reproducible bit-for-bit across runs and platforms with the same toolchain.

Fixtures used: `tests/fixtures/adr018_frame.hex`, `tests/fixtures/heartbeat_frame.hex` (pre-existing, cited not duplicated); `data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl` (pre-existing committed capture, 135 KB, read directly — no new fixture file created).

## 6. Suite status (verbatim)

### `npm test`
```
tests 129
pass 129
fail 0
cancelled 0
skipped 0
todo 0
duration_ms 8051.4609
```

### `npm run check`
```
> csi-signal-processing@1.1.0 check
> tsc
```
(no output = clean, zero type errors)

### `python -m pytest tests -q`
```
.s...................................................................... [ 85%]
............                                                             [100%]
83 passed, 1 skipped in 45.92s
```

### Firmware host DSP test (`test_edge_dsp_pure.exe`)
```
[broadband motion] motion_energy=0.19513 resp_conf=0.137 breathing_bpm=7.4 verdict=0
[breathing 15bpm]  motion_energy=0.31228 resp_conf=0.969 breathing_bpm=15.2 verdict=1
[cardiac-only]     motion_present=1 breathing_bpm=0.0 resp_conf=0.000 (hr_bpm=72.0 hr_conf=0.95 computed but NOT passed to gate) verdict=0
[sample-rate sweep] fs=3.0Hz truth=15.0BPM est=15.02BPM ratio=0.959
[sample-rate sweep] fs=5.0Hz truth=15.0BPM est=15.05BPM ratio=0.932
[sample-rate sweep] fs=7.0Hz truth=15.0BPM est=15.07BPM ratio=0.902
[Monte Carlo, N=500] noise_false_positive_rate=0.002 breathing_missed_detection_rate=0.198
[KNOWN LIMITATION, not asserted] clean 2.2Hz tone: motion_energy=0.12818 resp_conf=1.000 breathing_bpm=26.4 verdict=1

All assertions passed.
exit=0
```
Compiled with `-Wall -Wextra`: zero warnings.

---

**Scope note on this campaign itself:** given the size of the full B1-B6 specification and the amount of pre-existing coverage already proven by prior WP-0 through WP-9/13/16 work, this pass prioritized (a) citing existing coverage precisely rather than duplicating it, and (b) building genuinely new tests only where a real gap existed. Two items were explicitly scoped down rather than silently skipped: B6's full real-data fusion replay (would require exporting private pipeline internals — a product change) and a deeper F1-mode-integrity test (the underlying AI-absent concept doesn't exist on the TS authority side to test against). Both are named in §4 with what would close them.
