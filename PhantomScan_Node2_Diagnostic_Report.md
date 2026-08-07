# Phantom Scan — Node 2 Diagnostic Report (2026-08-07)

Follow-up to `PhantomScan_RealLiveFailure_Analysis.md`, which found that in one real 21-minute
session (`dsgdfsg`), node 2's motion signal never exceeded 0.398 against a 0.6 presence
threshold — effectively silent. This session asks the harder question that report didn't answer:
**is that a software bug, or a physical/hardware problem?** Short answer up front: **neither** —
it's normal session-to-session variance, and `dsgdfsg` was a one-off. See below for the evidence.

---

## Task 0 — Software-side causes: ruled out

Checked, with evidence, in this order:

1. **Per-node math asymmetry.** `computeNodeMotionFromMatrix` (`server/lib/node-fusion.ts:198-238`)
   is one function called identically for both nodes via `nodeMotionFor(1)` / `nodeMotionFor(2)`
   (`server/lib/websocket.ts:1507-1513, 1533-1534`) — no `nodeId`-specific branch exists anywhere
   in that path. `grep -rn "nodeId === 2"` across `server/` returns nothing. The `motion` value
   itself is already a gain-normalized ratio (`absStd/mean * MOTION_SATURATION_SCALE`, clamped to
   1 — `node-fusion.ts:236`), the same normalization family as the gain-normalized `r1`/`r2`
   balance inputs added in PS-BEHTEST-004 — there's no missing normalization step for node 2.
2. **Raw signal comparison.** This turned up a real gap, not a bug: the recording format
   (`RecordingRow` in `server/lib/recording-export.ts:46-84`) stores `h1_re/h1_im/h2_re/h2_im/rssi`
   per *packet* (whichever node's packet triggered that tick), with no `node_id` column — so
   per-node raw amplitude/RSSI cannot be reconstructed from existing recordings at all, for any
   session. `motion_n1`/`motion_n2` (already-normalized, but per-node) are the only per-node
   signal available. This is now documented as a known limitation in
   `scripts/node_health_diagnostic.py`'s docstring (Task 3) rather than worked around.
3. **Firmware.** `firmware/esp32-csi-node/main/nvs_config.c` stores no gain/TX-power/calibration
   field at all (only `presence_thresh`, unrelated) — there's no per-device NVS setting that could
   make one board's math diverge from the other's. `csi_collector.c` computes `n_subcarriers`
   generically from `iq_len` and reads `info->rx_ctrl.rssi` directly from the driver — both boards
   run the identical generic path, no node-specific code exists in firmware source.
4. **Data-plumbing path.** `udp-server.ts`'s packet handler (`startUDPServer`, already fully
   audited in the prior report) has no `nodeId`-conditional logic in the parse/dispatch path.
   `node1_fps`/`node2_fps` in the `dsgdfsg` CSV itself are 43.0 vs 42.6 (ratio 0.99) — packet
   arrival rate for both nodes was essentially identical during the very session where the motion
   asymmetry appeared, ruling out a packet-loss/plumbing explanation for that session specifically.

**Task 0 conclusion: no software bug found.** Every stage from firmware capture through the
motion-gate math treats node 1 and node 2 identically. (The one real finding — recordings can't
carry raw per-node amplitude — is a genuine gap, addressed as a documented limitation rather than
a fix, since closing it means extending the recording schema, which is out of scope here.)

## Task 1 — Cross-session comparison: `dsgdfsg` is the outlier, not the norm

This is the finding that reframes the prior report. Built `scripts/node_health_diagnostic.py`
(Task 3) and ran it across every real session CSV in `data/sessions/` with the recording-export
schema (48 files had the `# phantom_session_meta` header + `motion_n1`/`motion_n2` columns; 71
older files predate that format and were correctly skipped, not guessed at).

Moving-state motion ratio (node2's average ÷ node1's average, while the presence gate was
actually firing) across all 48 sessions ranges **51.3% – 150.2%**, clustering close to 100% (most
sessions land 80–130%). `dsgdfsg` at **51.3% is the single lowest value in the entire history** —
next-lowest is 71.0% (`emty room test`).

Same-week (2026-08-02 through 2026-08-07) sessions, which best represent the *current* physical
rig placement, make this unambiguous:

| session | date | node2/node1 ratio |
|---|---|---|
| case0099 | 08-06 | 131.4% |
| test scan | 08-06 | 139.1% |
| scan_01_test | 08-06 | 106.9% |
| scan | 08-06 | 100.2% |
| dddddddd | 08-06 | 101.5% |
| fix test | 08-06 | 103.1% |
| new test | 08-06 | 95.2% |
| case300 | 08-06 | 85.7% |
| **dsgdfsg** | **08-07, 17:27** | **51.3%** |
| **new test scan sesion 43** | **08-07, 17:36** | **78.8%** |
| case001 | 08-07, 12:15 | n/a (gate never fired this session) |
| joddb test | 08-05 | 96.3% |
| last test | 08-04 | 99.5% |
| testtt | 08-04 | 130.5% |
| sss / final test / aaaaaaaaaaaaa / dr test | 08-02 | 126.4% / 99.2% / 116.6% / 81.9% |

The decisive data point: **`new_test_scan_sesion_43`, recorded 9 minutes after `dsgdfsg` on the
same day (17:36 vs 17:27), on presumably the same physical setup, shows a completely normal
78.8% ratio.** A genuine hardware fault (bad connector, damaged antenna element, structurally
poor placement) would not resolve itself in 9 minutes without physical intervention. Nothing in
`data/sessions/` indicates the rig was touched between those two recordings.

Negative-control reference points (empty room / fan, no human) also show near-symmetric node1/
node2 resting behavior (`empty_room_fan_off_20260720`: 0.397 vs 0.410; `emty_room_with_fan`
sessions: 74–93% ratio during fan motion) — consistent with a rig that is, in general, physically
balanced.

**Revised interpretation of the original finding:** node 2 wasn't "essentially inert in this
room" as a structural property (that was an overreach in the prior report, based on a single
session — corrected here). What actually happened in `dsgdfsg`: during that specific ~4.6-minute
window, whoever was moving happened to couple weakly to *both* nodes simultaneously (node 1 also
only averaged 0.581 during "moving" ticks, itself marginal against the 0.6 gate) — most
consistent with a person's real movement path/orientation that session (e.g. moving mostly
parallel to the node axis, or concentrated near the room's center rather than favoring either
node) rather than any node being faulty. The **root cause identified in the prior report — the
gate threshold sitting too close to real signal levels — still fully explains why the marker
rarely appeared**; what's corrected here is only the "node 2 is broken" framing.

## Task 2 — Physical-check procedure: not warranted right now

Per the ground rules, Task 2's procedure only gets built out if Task 0/1 point to a physical
cause. They don't — the same-day before/after comparison is strong evidence against a persistent
placement or hardware fault. Producing a full prioritized swap-test procedure here would be
solving a problem the data doesn't show exists.

**What I'd actually recommend instead:** treat this as closed unless it recurs. If a future
session run through `scripts/node_health_diagnostic.py` shows a node2/node1 ratio persistently
low (multiple sessions in a row under ~60%, not just one), *then* run the swap test (physically
exchange the two ESP32 units between the N1/N2 mounting positions and re-check) as the
single highest-value next step — it cleanly separates "placement" from "this specific unit" in
one test. No need to pre-build that procedure now for a problem that isn't currently recurring.

## Task 3 — Standing diagnostic tool

Added `scripts/node_health_diagnostic.py`: given one or more real session CSVs (positional paths
or `--glob`), it reports per-node motion-statistic distributions split into `moving` vs
`resting` buckets (matching `target_state`), fps parity, and a single "node2/node1 moving-state
ratio" headline number, flagging anything under 25%. A `--summary-only` cross-session table mode
is what produced Task 1's table above. Its docstring documents the raw-amplitude schema
limitation found in Task 0 rather than silently ignoring it.

Usage:
```
python scripts/node_health_diagnostic.py data/sessions/<name>_<timestamp>.csv
python scripts/node_health_diagnostic.py --glob "data/sessions/*.csv" --summary-only
```

Tests: `tests/test_node_health_diagnostic.py`, 5 tests on synthetic input (symmetric nodes ≈100%,
a known-asymmetric case mirroring the real `dsgdfsg` numbers reports <25%, moving/resting rows
bucket correctly, a missing-meta-header file is skipped rather than fabricated, a no-moving-rows
session reports the ratio as `None` rather than crashing or reporting 0%).

## Verification

```
$ python -m pytest tests/ -q
91 passed, 1 skipped, 7551 warnings in 153.61s

$ python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed in 0.38s

$ npx tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts
tests 221
pass 221
fail 0
```

F1 (AI advisory-only) and F2 (no upstream hardware control surface) invariants explicitly
re-confirmed passing, unchanged.

## Confirmations

- **`DEFAULT_MOTION_THRESHOLD` was not touched** this session, per the ground rules.
- **The MUSIC fix was not touched.**
- **Should Thaer run `calibrate-threshold.ts` before or after this?** After — but for a different
  reason than originally guessed. It's not that recalibrating against a node2-silent session
  would wrongly bake in motion1-only behavior (that concern doesn't apply — `dsgdfsg` was atypical,
  not representative). The real reason to wait: `calibrate-threshold.ts` needs a fresh empty-room
  + fan-on-axis soak on the real rig, and that's an independent, unrelated hardware session. Doing
  it now versus later doesn't depend on anything found here — go ahead whenever convenient. If
  anything, this session is good news for that recalibration: since node1 and node2 are normally
  balanced (not one structurally weak), there's no asymmetry to design around — the recalibration
  can proceed as a standard single empty-room/fan soak, same as the script already assumes.
