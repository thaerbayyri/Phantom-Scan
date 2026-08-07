# Phantom Scan — `resolveLiveNodeMode()` Staleness Investigation

**Date:** 2026-08-07
**Scope:** Determine whether the fused-two-node display observed in the prior live-UDP-replay session (while only node 2's packets were being replayed) was a real staleness bug in mode resolution, or a benign artifact.
**Outcome: explanation (2) confirmed — no bug.** One regression test file extended (4 new tests); no production code changed. A separate, more important environmental finding surfaced along the way — see §4.

---

## 1. The actual function, read in full

`server/lib/websocket.ts`:

```ts
/** Node IDs whose last UDP packet is ≤1.5 s old — the definition of a "live" node. */
private activeHardwareNodeIds(nowMs = Date.now()): number[] {
  const active: number[] = [];
  for (const [nodeId, lastSeenMs] of Array.from(this.hardwareNodeLastSeenMs.entries())) {
    if (nowMs - lastSeenMs <= 1500) {
      active.push(nodeId);
    }
  }
  return active.sort((a, b) => a - b);
}

/** fused_two_node only when BOTH boards are live; otherwise single_node (UI shows "degraded"). */
private resolveLiveNodeMode(): TargetState["node_mode"] {
  return this.activeHardwareNodeIds().length >= 2 ? "fused_two_node" : "single_node";
}
```

`hardwareNodeLastSeenMs` is a `Map<number, number>`, updated on every ingested sample:
`ingestSample(): this.hardwareNodeLastSeenMs.set(sample.nodeId ?? 1, Date.now())` — genuinely a
recency-based check, not an "ever seen since process start" check. Traced `nodeId` end-to-end
from `udp-server.ts`'s wire parsing (`sample: CSISample = { ..., nodeId: parsed.nodeId, ... }`)
through to `ingestSample` — no loss or misattribution found in the code.

**On inspection, this looks correct.** The investigation moved to empirical confirmation.

## 2. Empirical test — in-process, deliberately no network

The task's Step 3 called for a clean UDP-replay test (fresh browser, fresh server, node-2-only
from cold start). I started building that, but discovered mid-setup that this environment has
**persistent, unidentified UDP traffic already arriving at :5005 independent of anything I run**
(detailed in §4) — which would have made any "clean" *network*-based test unreliable regardless
of how carefully I isolated my own processes. Since the actual question ("does
`resolveLiveNodeMode()` correctly age out stale nodes") doesn't require the network at all —
`ingestSample()` is a plain public method — I tested it directly, in-process, with no UDP socket
involved:

```
=== Test A: cold start, node 2 only ===
mode after node2 only: single_node

=== Test B: both nodes fresh ===
mode after node1+node2 fresh: fused_two_node

=== Test C: node 1 goes stale (2s old), node 2 still fresh ===
mode after node1 stale: single_node

=== Test D: both stale ===
mode after both stale: single_node
```

All four outcomes are correct. Test A directly answers the task's core question: **a genuinely
cold start with only node 2 ever having sent a sample resolves `single_node`, never
`fused_two_node`.** Test C directly answers the mid-session-dropout question: once node 1's last
sample crosses the 1.5 s staleness window, mode correctly falls back to `single_node` while node
2 keeps reporting.

**Explanation (2) confirmed, explanation (1) ruled out.** There is no staleness/liveness bug in
`resolveLiveNodeMode()`. The prior session's fused-mode observation while replaying only node 2
was not caused by this function mishandling stale state.

## 3. Regression tests added

Formalized the four probe scenarios as permanent tests in `server/lib/websocket.test.ts`
(reusing the file's existing `newProcessingServer()` `as any` pattern, since
`resolveLiveNodeMode`/`hardwareNodeLastSeenMs` are private):

- cold start, node 2 only → `single_node`
- both nodes fresh → `fused_two_node`
- node 1 stale mid-session (dropout) while node 2 keeps reporting → falls back to `single_node`
- both nodes stale → `single_node` (documents that there's no distinct "no nodes" enum value —
  zero active nodes and one active node both resolve to `single_node`; not a bug, just noting
  the actual contract for future readers)

This wasn't required by the task's own branching logic (which only mandates a test if a bug is
*found*), but since the exact verified-correct scenarios were already built and validated, adding
them costs little and locks in this specific mode-resolution guarantee for the future.

## 4. The more important finding: unidentified ambient UDP traffic

While setting up the "clean" test, `netstat`/`Get-Process` revealed **three separate leftover
`npm run dev` process trees** still running from earlier phases of this multi-hour session
(spanning 2:14 AM to 2:59 PM the same day) — my own `Stop-Process` calls in earlier turns had
only killed the specific PID holding the UDP port at that moment, not each `npm run dev`'s full
process tree (`npm-cli.js` → `dev-full.cjs` → `tsx` loader → `server/index.ts`, several
processes per invocation). Killed all of them explicitly by PID (keeping only the
`chrome-devtools-mcp` tooling alive) and restarted with a verified-clean process list.

**Even then**, within seconds of a freshly-started, singly-owned server binding :5005, the log
showed continuous, realistic-looking CSI traffic (~85 packets/s — roughly double a single node's
measured ~41-43 pps, consistent with *two* nodes; varied h1/h2 magnitudes with the genuine
single-antenna h1=h2 duplicate pattern; plausible RSSI values) that I did not send. This is
**not explained by anything in my own process tree** — it was present with a process list
containing nothing but the browser tooling and the one freshly-started server.

**I did not chase this further** — it's outside this task's scope, and identifying the actual
source (real ESP32 hardware genuinely reachable on this network? some other service? a
scheduled/leftover process outside what `Get-Process`/`netstat` on this account can see?) needs
its own investigation. But it directly recontextualizes the *previous* session's finding: the
fused-two-node display observed while replaying only node 2's packets was very likely this same
ambient traffic supplying genuine (or at least genuine-looking) node-1 samples in the background
— not a bug in my replay method, not a bug in mode resolution, and not "session-leftover
artifact" in the browser-state sense the task's explanation (2) originally described. It's a
third possibility neither explanation fully named: **an independent, unidentified live traffic
source in this environment**, present throughout recent testing.

**This deserves your attention independent of this specific investigation:** if that's real
ESP32-S3 hardware genuinely broadcasting to this network right now, that changes the "no hardware
available in this environment" premise every prior investigation in this thread operated under —
worth confirming what it actually is before trusting or discounting any earlier "live" test
result in this session's reports.

## 5. Full verification (real output)

```
> npx tsx --test server/lib/websocket.test.ts
ℹ tests 12 / pass 12 / fail 0   (8 existing F1 tests + 4 new)

> npx tsx --test server/**/*.test.ts
ℹ tests 195 / pass 195 / fail 0   (191 + 4 new)

> python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed
```

No regression; only the intentional +4 new tests. F1/F2 invariants explicitly re-run and green.
MUSIC fix untouched, as instructed.

## 6. Does this connect to Thaer's original "missing target" report?

**Honest assessment: no direct connection, and this investigation found no bug to connect.**
`resolveLiveNodeMode()` is correct. If anything, §4's finding is the more relevant thread to pull
for the *original* report — if unidentified real-looking traffic has been present in this
environment, it's worth confirming whether that traffic (or its absence at the time of the
original report) has any bearing on what Thaer actually saw, though that's speculation, not
evidence; I have none linking the two.

## 7. Current status of the original missing-target investigation

**Unchanged: still unreproduced, pending a real hands-on hardware session**, exactly as the two
prior reports (`PhantomScan_TargetNode_Regression_Fix.md`,
`PhantomScan_LiveTarget_Regression_Fix.md`) concluded. This session neither reproduced it nor
found a connected root cause — it closed one specific loose end (mode-resolution staleness, now
confirmed not a bug) and surfaced one new, unrelated-but-worth-investigating environmental
question (§4).

## Unrelated fix made mid-session (user-directed interrupt)

`firmware/esp32-csi-node/main/CMakeLists.txt:23` — `set(REQUIRES esp_lcd esp_lcd_touch lvgl)`
inside the `CONFIG_DISPLAY_ENABLE` block was overwriting the base `REQUIRES` list (losing
`esp_wifi`, `lwip`, `esp_netif`, `nvs_flash`, etc.) instead of appending to it, unlike the `SRCS`
list two lines above which correctly uses `list(APPEND ...)`. Fixed to
`list(APPEND REQUIRES esp_lcd esp_lcd_touch lvgl)`. This is firmware/CMake, unrelated to this
investigation or the test suites above (no server/lib test exercises firmware CMake), noted here
for completeness of this session's change log.
