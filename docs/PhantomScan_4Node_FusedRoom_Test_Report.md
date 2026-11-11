# Verification & Stress-Test: 4-Node `fused_room` Implementation

**Scope:** Independent verification of `PhantomScan_4Node_Fusion_Report.md` (2026-08-24) against current repo state on `feat/two-node-radar-live-detection`.
**Method:** Static/code-level verification + full automated test suites. **No live hardware was exercised in this session** — see "What was not tested" below. Every claim below is either reproduced directly or explicitly marked unverified.

---

## Prominent flag — geometry change needs your sign-off

The report moved node geometry from the centered 3 m N1–N2 baseline (`(-1.5,0)`/`(1.5,0)`) to four room corners on a 4 m × 6 m footprint (`(-2,-3)`/`(2,-3)`/`(2,3)`/`(-2,3)`). This is confirmed present in `shared/schema.ts:320-329` exactly as claimed. It is **not** a pure addition — N1–N2 separation grew from 3 m to 4 m and the origin shifted, which changes `fuseTwoNodeTarget` output even though that function's code is untouched (its inputs changed). This project's convention treats anchor geometry as a ground-truth constant requiring your confirmation, not something to silently adopt from a report. Flagging for your explicit sign-off before treating `(±2, ±3)` as final.

---

## Step 0 — Claim reconciliation

| Report claim | Status | Evidence |
|---|---|---|
| Branch `feat/two-node-radar-live-detection` | ✅ Verified | `git branch --show-current` |
| `NODE_ANCHORS` = 4 room corners, `ROOM_WIDTH_M=4`/`ROOM_DEPTH_M=6` | ✅ Verified | `shared/schema.ts:320-329`, exact match |
| `CANONICAL_NODE_HARDWARE_IDS` covers nodes 1-4 (29052/44260/51234/67891) | ✅ Verified | `shared/schema.ts:32-37` |
| `node_mode` enum includes `fused_room` | ✅ Verified | `shared/schema.ts:291` |
| `fuseTwoNodeTarget` byte-for-byte unchanged, still 2-node-only | ✅ Verified (structurally) | `server/lib/node-fusion.ts:371-414` — still takes exactly `anchors[1]`/`anchors[2]`, no N-node awareness |
| New `fuseNodeTargets` exists, additive | ✅ Verified | `server/lib/node-fusion.ts:533-597` |
| Ingest accepts node IDs 1-4, no silent cap | ✅ Verified | `server/lib/udp-server.ts:619-624` uses `mapRuntimeNodeIdToHardwareId` (generic map lookup), no hardcoded `1`/`2` check remains |
| "243 tests passing, 0 type errors" | ✅ Reproduced exactly | `npx tsc --noEmit` → 0 errors; `npx tsx --test ...` → `pass 243, fail 0` |
| F1/F2 invariants hold | ✅ Verified | `pytest tests/test_invariants.py` → 5/5 passed, including both F1 tests and the F2 test |
| Docs not yet updated | ✅ Confirmed still true | `docs/WINDOWS_ESP32_SETUP.md` — zero matches for COM8/COM9/node-id 3/4 |
| No stale references to the old 3 m/centered baseline remain in live code/docs | ✅ Confirmed | Grep for the old coordinate literals and "2-node hardware reality" phrasing returns matches only inside the two report `.md` files themselves (correctly describing history), nothing in code or active docs |

Everything the prior report claimed about static repo state reproduces exactly. No discrepancies found at this level.

---

## Step 1 — Functional matrix (code-trace verified; live rows marked)

| Nodes live | Expected `node_mode` | Result |
|---|---|---|
| 1 (any single) | `single_node` | Isolated correctly — `resolveLiveNodeMode` returns `single_node` whenever active count < 2; single-node path (`singleNodeMotionDetected`, `hasSingleNodePresenceEvidence`) has no fused-path coupling. |
| 2, N1+N2 | `fused_two_node` | Mode label correct. Fusion computation correct — this is the only pair the hardcoded path (below) actually serves. |
| **2, any other pair (e.g. N3+N4, N1+N3)** | `fused_two_node` (label) | **🔴 CONFIRMED DEFECT.** `computeFusedTarget`'s non-room branch (`server/lib/websocket.ts:1661-1677`) unconditionally reads `this.nodeMotionFor(1)`, `this.nodeMotionFor(2)`, and `anchors: {1: NODE_ANCHORS[1], 2: NODE_ANCHORS[2]}` — **it never looks at `activeIds`**, the list `resolveLiveNodeMode` itself just computed. If N1/N2 are offline and N3+N4 are the two live, motion-detecting nodes, `resolveLiveNodeMode()` correctly reports `fused_two_node`, but the fusion math runs against N1/N2's empty/stale amplitude windows (`nodeMotionFor` returns `{absStd:0, motion:0}` once their window ages out past 1.5s). `fuseTwoNodeTarget`'s energy gate (`max(motion1,motion2) >= threshold`) then fails on every tick, so **the system silently reports no target while two live nodes are actively sensing a real person.** `buildSensorNodes`'s `distanceM` (fed from the same `fusedSnapshot`) is `undefined` too, while N3/N4 still show `active:true` with real motion glow — an inconsistent, misleading UI state (beacons look live, target vanishes). This is a false-negative/under-detection bug, not cosmetic, and directly relevant to this project's search-and-rescue framing. |
| 3 (any combination) | `fused_room` | ✅ Generic — `activeIds.length >= 3` branch maps every active id through `fuseNodeTargets`, no fixed-pair assumption. Code-verified correct for any 3-of-4 combination. |
| 4 (all live) | `fused_room` | ✅ Same generic path. Perimeter order (1→2→3→4) is correctly encoded in `NODE_ANCHORS`' declaration order, which `RoomBoundary` consumes — confirmed the anchors form a non-crossed quad by construction (each edge shares exactly one coordinate with the next). |
| 4→3→4 live dropout/rejoin | Should transition cleanly | ✅ **for the room↔room transition** (3-4 nodes, generic path). **⚠️ NOT safe** for a transition that lands on exactly 2 nodes unless that pair happens to be {1,2} — see the confirmed defect above. A drop from 4 active nodes straight to {3,4} (skipping through 3) reproduces the same false-negative. |
| Mode *label* vs. underlying data consistency | — | Re-checked the class of bug the report's own §04 found twice (stale ternaries). `target-identity-card.tsx` and `shared/target-presentation.ts` both correctly branch on `fused_room` now (read in full — no remaining two-way ternary found in either file). No other stale-label site found via grep for `fused_two_node`/`fused_axis` ternary patterns outside these two already-fixed files. |

**Net assessment of Step 1:** the room-mode work (3-4 nodes) is solid and generic. The regression is specifically in the *2-node* path now that "2 active nodes" no longer implies "nodes 1 and 2" — a case that did not exist before this session's change and was never exercised by the prior report's own testing (it only ever ran N1+N2 together).

**Suggested fix (not applied — flagging per this task's scope, which is verification not remediation):** `computeFusedTarget`'s 2-node branch should build `anchors`/motion samples from `activeIds` the same way the room branch does, calling `fuseTwoNodeTarget` with whichever two ids are actually active (in `NODE_ANCHORS` id order, matching `activeIds`' existing sort) instead of the literal `{1,2}`. `updateFusedSnapshot`, `computeNodeTrends`, and `buildSensorNodes`'s `snap.trends[key as 1|2]` lookup are all keyed to literal ids `1`/`2` downstream of this and would need the same generalization — this is a larger, non-trivial change than a one-line fix, since `FusedTarget.balance`/`trends` are inherently a 2-endpoint concept currently pinned to ids 1 and 2 specifically.

---

## Step 2 — Ground-truth location walk

**Not executed.** No live ESP32 hardware or active UDP stream was reachable in this tool session (no dev server / browser / physically-connected boards in scope here). Fabricating accuracy numbers would violate this project's own honesty discipline, so none are reported.

Ready-to-run procedure for you to execute and paste results back:

1. Start the dev server (`npm run dev`), confirm all 4 boards show `active` in the Board DSP panel.
2. Walk to each of: room center, 4 corners (near each node), 4 wall midpoints (9 points total). At each, stand still ~10-15s and record: nearest-node badge, room-centroid `(x,z)` from the dashboard, and the `SignalFieldGrid`'s visual peak location, against your true position.
3. Walk a continuous corner→corner→corner→corner path; confirm the nearest-node sequence matches true walk order without freezing or backward jumps.
4. Save the session via the existing recording mechanism into `data/sessions/` with a clear label (e.g. `groundtruth_4node_walk_<date>`).
5. Score only: nearest-node classification accuracy, transition latency (frames/seconds behind true position), directional consistency. **Do not** compute a meter-level position error — `fuseNodeTargets` is a perturbation-weighted centroid, not RF ranging; a meter-accuracy figure would be dishonest given the method.
6. Separately test standing near room center (all 4 nodes roughly equidistant) — this is where the centroid weighting is most likely to drift or feel unstable, since no node dominates.

---

## Step 3 — Empty-room negative control (`fused_room`)

**Not executed** — same hardware-reachability reason as Step 2. This is confirmed to be a genuine, currently-unmeasured gap: the prior report's §04 verification was a qualitative walk-through, not a negative control, and grepping the repo turns up no existing empty-room recording tagged for 3-4-node operation the way `PhantomScan_GhostTarget_Fix.md`'s 2-node baseline was validated.

Procedure to run, mirroring the existing 2-node negative-control checklist (`docs/NEGATIVE_CONTROL_CHECKLIST.md`):

1. Empty room, all 4 nodes live, record several minutes. Compute `target_visible=1` rate from the recorded CSV's `node_mode`/target-visibility column — this is the room-mode false-positive rate (currently unmeasured; existing 2-node baseline is 0.0–17.2% per prior sessions).
2. Repeat with exactly 3 nodes live (unplug/power down one), simulating the report's own node-2-dropout incident deliberately rather than accidentally.
3. Repeat once with a fan or other non-human vibration source on-axis with one node pair, per the existing checklist, now against room geometry.
4. Confirm the `SignalFieldGrid` does not render a false hot spot during any empty-room run — a visually convincing but spurious intensity peak is a worse failure mode for an operator than a missing marker.
5. If any run shows a false-positive rate meaningfully outside the existing 2-node range, treat it as a real defect requiring root-cause, not an averaged-away artifact of "it's a new mode."

---

## Step 4 — Open items investigated

**Trend arrows inert in room mode** — ✅ Confirmed still true. `computeNodeTrends` (`node-fusion.ts:159-170`) is still hard-typed to `{1: NodeTrend, 2: NodeTrend}`, and `buildSensorNodes`'s trend field explicitly falls back to `"stable"` under `roomSnap` (`websocket.ts:1774-1776`, comment confirms this is deliberate). **Assessment: not a quick fix.** A correct room-mode trend needs per-node radial velocity (rate of change of distance to *that specific* anchor), which requires tracking each node's own distance history independently rather than one shared axis velocity — a real design/testing pass, not a coarse patch. Left as a genuine follow-up item, correctly characterized by the original report.

**Node 2 dropped out mid-verification** — ⚠️ Root cause **not reproducible from server-side evidence, and this is itself a gap.** Traced the ingest/liveness path (`hardwareNodeLastSeenMs`, `activeHardwareNodeIds`): a node aging out past the 1.5s window is handled entirely silently — there is no log line anywhere for "node N went stale" or "node N reassociated," only the passive age check on read. So the original report's own question ("worth a power/WiFi check") is currently unanswerable after the fact from logs alone; the only forward-looking options are (a) reproduce live with the boards and watch serial output directly for WiFi disassociation, or (b) add a stale-transition log line first (`activeHardwareNodeIds` or the ingest handler), then reproduce. Not attempted here since it needs live boards. **This also matters for Step 3**: an unlogged node dropping mid-empty-room-soak would be indistinguishable from a legitimate mode-transition artifact without such logging — recommend adding the log line before running the Step 3 procedure above.

**Docs not yet updated** — ✅ Confirmed still true, zero COM8/COM9/node-id-3/4 references in `docs/WINDOWS_ESP32_SETUP.md`. Not updated in this pass — prioritized the functional-matrix and audit work per this task's own instruction not to let doc updates take priority over testing.

---

## Step 5 — Honesty & geometry-drift audit

- No stale references to the old centered 3 m baseline (`(-1.5,0)`/`(1.5,0)`) or "2-node hardware reality" language found anywhere in live code or active docs — only inside the two historical/current report `.md` files themselves, which correctly describe it as history. No drift found.
- `getLivePositionCaveat` (`shared/target-presentation.ts:57-82`) correctly branches on `fused_room` with the claimed caveat text, using the same single mechanism as the 2-node caveat (no parallel/inconsistent mechanism introduced) — confirmed by full file read.
- `target-identity-card.tsx` correctly surfaces `presentationCaveat` for all three modes via the shared mechanism — confirmed by full file read, no separate room-mode-only caveat path exists to drift independently.
- CSV export (`server/lib/recording-export.ts`) carries `node_mode` per row (line 78/142/249) but no textual caveat string — this matches the pre-existing pattern for `fused_two_node` (which also never had a textual caveat in CSV) and is **not a room-mode-specific regression**; a downstream analyst can still filter by `node_mode` to apply correct interpretation. Not flagged as a new defect, but noting it as an existing limitation that now also applies to the new mode.

---

## Step 6 — F1/F2 invariant re-verification

```
tests/test_invariants.py::test_dual_node_equal_balance_midpoint PASSED
tests/test_invariants.py::test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
tests/test_invariants.py::test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed in 1.83s
```

TS-side AI-firewall tests (subset of the 243, `server/lib/websocket.test.ts`) also passed: non-AI client's `targetIdentity`/`vitalSigns`/`poseFrame` produce no state change/broadcast; AI client's equivalents are relayed as `advisory*` and never write `currentTargetIdentity`/`currentVitalSigns`.

`signalField` reasoning: it is registered only in the outbound `wsMessageTypeSchema`/`streamFrameSchema` union and is broadcast server→client from `buildSignalField()`/`broadcastNodes()`; no inbound handler exists for it in the message-dispatch switch (confirmed by inspecting the same dispatch block the AI-firewall tests exercise — `targetIdentity`/`vitalSigns`/`poseFrame`/`registerAIClient` are the only inbound-handled types). It remains strictly observational — F2 preserved. The room-mode fusion path (`fuseNodeTargets`, `computeFusedTarget`'s room branch) writes only to `roomFusedSnapshot`/the `radialTarget`/`nodes` broadcasts, never to `currentTargetIdentity`/`currentVitalSigns` — F1 preserved.

---

## Full before/after test suite output

No code was modified during this verification pass (report-only + defect discovery), so "before" and "after" are identical:

- **TypeScript:** `npx tsc --noEmit` → 0 errors.
- **TypeScript tests:** `npx tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts scripts/accuracy/__tests__/**/*.test.ts` → `243 pass, 0 fail`.
- **Python:** `pytest tests/test_invariants.py -v` → `5 passed`.
- **Firmware host-DSP:** not touched by this session's changes (nothing in the firmware path was modified), not re-run.

---

## Summary

| Area | Verdict |
|---|---|
| Static claims (Step 0) | All reproduce exactly — no drift |
| Room-mode fusion (3-4 nodes) | Solid, generic, code-verified correct |
| 2-node fusion for non-{1,2} pairs | **Confirmed defect — false negative when N1/N2 offline but another pair is live** |
| Ground-truth accuracy / empty-room false-positive rate | Not measured — requires live hardware, procedures provided |
| Trend arrows | Confirmed still inert, correctly deferred (real design work, not a quick fix) |
| Node dropout root cause | Unanswerable from current logs — recommend adding stale-transition logging before the next live session |
| Docs | Confirmed still not updated |
| Honesty/geometry audit | Clean — no stale references, caveat correctly wired |
| F1/F2 | Both hold |

**Geometry change (3 m→4 m baseline) still needs your explicit sign-off — see the flag at the top of this report.**
