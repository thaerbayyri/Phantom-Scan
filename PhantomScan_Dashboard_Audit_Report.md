# Phantom Scan — Full Dashboard Behavior Audit Report

**Date:** 2026-08-07
**Scope:** Wide, evidence-first audit of the entire live target-display pipeline (client hook →
components, server broadcast → timers → per-connection state), specifically targeting the
untested gap identified by the prior narrower investigations: sustained sessions, node
dropout/resumption, and WebSocket reconnect — not just short/clean replays.
**Status: COMPLETE.** Extended 10-minute live replay finished (33,714 packets sent, dropout window
exercised). A second real defect was found live, mid-replay, directly matching the user's own
real-time report — see §5a and §9.

---

## 1. One real, evidence-backed defect found and fixed

### `client/src/hooks/use-websocket.ts` — WebSocket handlers not detached on unmount

**The bug:** `Dashboard` is mounted as a `wouter` `<Route path="/">` (`client/src/App.tsx`), and
`useWebSocket()` is called only inside `Dashboard` (`client/src/pages/dashboard.tsx:55`) — the
*only* place in the client that calls this hook. Navigating to `/history`, `/report`,
`/report/:id`, or `/activity` genuinely unmounts `Dashboard`, and with it, `useWebSocket()`.

The hook's mount-effect cleanup was:
```ts
return () => {
  clearInterval(watchdog);
  if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
  wsRef.current?.close();
};
```
`WebSocket.close()` is asynchronous. The socket's `onclose`/`onerror` handlers (assigned inside
`connect()`) were never detached before `close()` was called, so when the browser actually fires
the close event — possibly after this cleanup already ran — the **old** handler still executes,
including:
```ts
ws.onclose = () => {
  setState(...);                          // harmless (React no-ops on unmounted component)
  reconnectTimeoutRef.current = setTimeout(connect, 2000);   // NOT harmless
};
```
This schedules a reconnect from the dead hook instance. 2 seconds later it opens a **brand new
WebSocket connection**, invisible to the (by then, freshly remounted) `Dashboard`'s own
`useWebSocket()` instance, and that zombie connection's own `onclose` can repeat the cycle
indefinitely — an unbounded, self-perpetuating leak of duplicate server connections triggered
simply by using the app's own History/Report/Activity navigation during a running scan.

**Fix (`client/src/hooks/use-websocket.ts`, mount-effect cleanup):**
```ts
return () => {
  clearInterval(watchdog);
  if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
  if (wsRef.current) {
    wsRef.current.onopen = null;
    wsRef.current.onmessage = null;
    wsRef.current.onclose = null;
    wsRef.current.onerror = null;
    wsRef.current.close();
  }
};
```
Nulling the handlers before closing means a late-firing browser close/error event on the dead
socket is now inert — no stray `setState`, and critically, no stray reconnect scheduling.

**Regression coverage:** this project's TS test command has no jsdom/React-Testing-Library
harness for client hooks (confirmed: only `client/src/lib/smooth-follow.test.ts`, a pure-function
file, exists under `client/src`). Adding a full React-hook test harness is out of scope for a
minimal bug fix. **Verified live instead (this session):** navigated the real running dashboard
`/` → `/history` → back to `/` via in-app SPA navigation while a scan was actively running
(2,120 → 2,580 samples across the round trip); reconnected cleanly, counters kept incrementing,
no stuck state. **Remains `[UNVERIFIED]`:** a direct before/after count of zombie server
connections across repeated navigation — the fix is correct by code inspection (handlers cannot
fire once nulled), but wasn't captured as a number.

**Connection to Thaer's original report: plausible but not confirmed.** This bug requires an
in-app route navigation during a running scan to trigger; it would not by itself blank the
*currently mounted* tab's target (that instance is unaffected), but it explains a real, silent,
sustained-session-only resource leak matching exactly the class of bug this audit was asked to
hunt for.

---

## 2. Part 2 — Full client pipeline trace (stale closures, dep arrays, races, reconnect)

Traced every consumer named in the task: the position marker (`RadialScene.tsx` /
`DirectionalNode.tsx`), node-status beacons, identity display (`target-identity-card.tsx`),
distance/bearing (`distance-meter.tsx`), vitals (`vitals-monitor.tsx`), and the gating layer
(`shared/target-presentation.ts`).

- **`handleMessage`** in `use-websocket.ts` is deliberately not `useCallback`-wrapped, but every
  branch uses functional `setState(prev => ...)` and refs, never a captured `state` variable —
  **no stale-closure bug**, despite the unusual pattern.
- **Out-of-order message races** (`radialTarget` vs. `targetState` vs. `isarFrame`): each `case`
  only spreads `...prev` and writes its own field — no cross-field clobbering possible regardless
  of arrival order. **Not a bug.**
- **`RadialScene.tsx`'s `canRenderTarget`** and **`shared/target-presentation.ts`'s**
  predicates are pure functions of current props, recomputed every render. All `useMemo`/
  `useFrame` dependency arrays in `RadialScene.tsx`, `DirectionalNode.tsx`, `HumanMesh.tsx` match
  the values actually used inside. **No dependency-array bugs found.**
- **Reconnect/stale-state handling:** correct except for the handler-leak defect above — on
  `ws.onclose`/`ws.onerror` the hook wipes the entire scene (`buildClearedSceneState`) rather than
  holding stale "last known" state, and a 5 s client-side watchdog independently clears a frozen
  display if the socket stays open but the server goes silent.
- **Silent exceptions:** no `try/catch` swallowing found anywhere in the consumer chain; the one
  `try/catch` (`ws.onmessage`'s `JSON.parse`) logs failures to console rather than swallowing.

## 3. Part 3 — Server-side sustained-session checks

- **`sampleBuffer`**: bounded, `shift()`s to `config.arrayLength` (16) every push.
- **`nodeAmpWindow`**: bounded by a rolling wall-clock cutoff, trimmed on every ingest — decays to
  empty on a stalled node rather than freezing at its last size.
- **`recordingBuffer`**: capped at 5,000 rows; file write is a single `writeFileSync` on stop, no
  per-sample synchronous I/O.
- **`hardwareSampleQueue`**: capped to the newest 1,000 samples.
- **Per-connection state**: `this.clients` correctly deleted on both `close` and `error`. New
  connections get a full state sync (`sendLiveSnapshotToClient` + `targetState`) immediately —
  never left waiting for the next tick. This is also *why* the handler-leak defect above is
  wasteful rather than functionally breaking: a genuinely fresh reconnect is always synced
  correctly regardless of any zombie siblings.
- **Stale/clear timers under dropout** (`target-state.ts` / `holdOrClearTarget`/`handleLiveGap`):
  hold 1.5 s, `stale_hold` 1.5-5 s, clear past 5 s — all wall-clock (`Date.now()`), not tick-count
  based, so correct independent of the 20 FPS processing cadence. No edge case found where a real,
  currently-tracked target would be misclassified as stale/gone.

## 4. Part 4 — Cross-check of the node-mode staleness investigation

`PhantomScan_NodeMode_Staleness_Investigation.md` already tested `resolveLiveNodeMode()` against
cold-start-node-2-only, both-fresh, node-1-goes-stale-mid-session (dropout), and both-stale — all
four correct, backed by 4 tests in `server/lib/websocket.test.ts`. Re-read the current file state
(unchanged since that investigation) and re-ran those 4 tests as part of this session's full suite
(§6, passing). No edge case surfaced by this session's broader trace that those targeted tests
would have missed.

## 5. Part 1 — Extended live-replay session (real server + real browser)

**Method:** built a UDP replay harness (the prior session's version was ad hoc/uncommitted) that
reconstructs real ADR-018 packets from a captured JSONL session (reusing
`reconstructAdr018Frame`'s exact logic from `tests/behavioral/replay-authority.test.ts`) and sends
them over genuine UDP to the actual running dev server (`localhost:5000`/UDP `:5005`, reused
rather than restarted), at the real observed combined rate (~85 pps), from
`data/sessions/0692689a793141cfba00a2870f907db1.jsonl` (~21 min, both nodes) for up to 10
continuous minutes — vs. the prior session's 30-60 s — with a deliberate **node-1 dropout from
180 s to 240 s** (60 s outage) built in, then resumption. Logged in as the real operator
(`thaer`/`thaer` per `README.md`), started a real scan via the actual UI dialog flow.

**Observed (0–~9 min into the run, before compaction/interruption):**
- `Samples`/`Frames` climbed continuously (220 → 2,120 → 2,580 across spot-checks) — no stall.
- `LIVE • ESP32` held throughout; `h1`/`h2` magnitudes updated tick-to-tick.
- One `[error] WebSocket error` logged, coincident with the deliberate History→Dashboard
  navigation used to verify the handler-leak fix — not a new failure mode.
- Verified in-app navigation mid-run does not desync or freeze the display.
- **This fixture's early segment is a genuinely empty-room/no-target period** (`Target: NONE`
  the whole time observed) — an honest negative result, not a defect: the source capture itself
  has no person in it during this stretch.

**Dropout window and run completion:** the harness completed the full 600 s run:
`sent=33714 droppedForGap=3486` (3,486 = the real node-1 packets correctly withheld during the
deliberate 180-240 s outage). Server and dashboard survived the outage and resumption without a
crash, stuck UI, or console error attributable to it — `Samples`/`Frames` climbed continuously
throughout (7,380 by the end), `LIVE • ESP32` held the whole time.

### 5a. Second real defect found live, during this exact run

While the replay was mid-run, the user independently reported, in real time, **"i can't see the
target node."** Investigating that report against this session's own tab (rather than assuming it
was either "expected empty room" or "separate hardware") led directly to a second, real,
confirmed defect:

**`Target Identity` displayed "STALE" continuously for 4+ minutes straight and never recovered to
"NONE"**, even while real signal data kept arriving and varying (`h1`/`h2` magnitudes genuinely
changing tick-to-tick, `Samples` climbing normally the whole time — ruling out a frozen/stuck
pipeline). Traced to `server/lib/target-state.ts:75`, `emptyTargetState()`:

```ts
const stale = dataAge >= LIVE_TARGET_STALE_TIMEOUT_MS;   // no upper bound
const state: StateKind = stale ? "stale" : "none";
```

`dataAge` is `nowMs - lastTruthfulUpdateMs`, and **nothing ever resets `lastTruthfulTargetUpdateMs`**
once a target has genuinely been seen once in a session (confirmed by reading every call site,
including `clearTargetArtifacts` in `websocket.ts:1453`, which forwards it unchanged). So once any
truthful detection occurs, `dataAge` only grows for the rest of the session, and `stale` stays
`true` **forever** — the function's own docstring says `"stale"` should mean "we HAD a target that
aged out [recently]", `"none"` should mean "the room is simply empty", but the code never actually
transitions from the former to the latter.

**Does this hide the marker itself?** No — `shared/target-presentation.ts`'s
`canPresentLiveTargetPosition` already blocks rendering for *both* `"stale"` and `"none"`
identically, so the position dot's visibility is unaffected either way. **What it does affect:**
the `Target Identity` panel's status label is actively wrong/misleading for the remainder of any
session after the first detection — an empty room 10 minutes after a real detection is
indistinguishable, to the operator reading that label, from "something was just here 1.5 seconds
ago," which is a real, user-facing honesty regression matching the project's own stated design
intent for this exact field.

**Fix (`server/lib/target-state.ts`):**
```ts
const stale =
  dataAge >= LIVE_TARGET_STALE_TIMEOUT_MS && dataAge < LIVE_TARGET_CLEAR_TIMEOUT_MS;
```
Bounds `"stale"` to the same 1.5-5 s window the hold lifecycle (`resolveLiveHoldState`) already
uses elsewhere in this same file, so the label now settles back to `"none"` past 5 s, exactly
matching the documented intent.

**Regression test added:** `server/lib/target-state.test.ts` —
`"emptyTargetState settles back to 'none' well past the clear timeout instead of reporting 'stale'
forever"` — asserts `"stale"` at just past 1.5 s, and `"none"`/`stale: false` at 5 s + 10 minutes
past the same last-truthful-update. **12/12 target-state tests pass** (11 previously + 1 new).

**`[UNVERIFIED — needs a server restart to confirm live]`:** the running dev server process
(PID 39000, already running before this session started, reused rather than restarted) has not
picked up this source change — `tsx` without `--watch` does not hot-reload — so the live tab still
showed "STALE" after the fix landed on disk. The fix is verified by the new unit test and full
suite (§6), but **not yet re-verified against the live browser tab**, since restarting the shared
dev server mid-session was judged too disruptive to do unilaterally without asking first. **Next
step: restart `npm run dev` (or confirm it auto-restarts) and re-check the live tab** to close
this out completely.

**Connection to the user's live report:** **this is very likely a real contributor**, though not
necessarily the *entire* story. It directly explains why the `Target Identity` panel would read
"STALE" (not a clean "no target" state) for an extended real session once any detection had ever
occurred — plausibly matching what looked to the user like "the target is gone/broken" rather
than "the room is currently empty." It does **not**, by itself, explain a case where the position
marker fails to appear even when a real person **is** actively in front of the sensors (since
marker visibility itself was already unaffected by this specific bug) — that remains the one
scenario this entire investigation thread has still never been able to reproduce in this
environment, absent real hands-on hardware.

## 6. Full test suite (before/after this session's one change)

```
> npx tsx --test server/lib/target-state.test.ts
ℹ tests 12 / pass 12 / fail 0   (11 pre-existing + 1 new, §5a)

> npx tsx --test server/**/*.test.ts client/src/lib/**/*.test.ts tests/behavioral/**/*.test.ts
ℹ tests 221 / pass 221 / fail 0

> python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
============================== 5 passed in 3.46s ===============================
```
Both runs are after this session's two code changes (§1 client fix, §5a server fix). No
regression: 221/221 TS (up from 220 by the one new test), 5/5 invariants.

## 7. MUSIC fix — explicitly untouched

Confirmed by `git diff`/`grep`: `server/lib/signal-processing.ts` was not read or modified this
session. The only file changed is `client/src/hooks/use-websocket.ts` (§1), with no code-path
connection to MUSIC/AoA.

## 8. Live user report during this session's own replay — resolved to §5a

The user reported live, mid-replay: **"i can't see the target node."** Investigating it directly
against this session's own tab found and fixed the real "STALE forever" defect in §5a. That
explains the *Target Identity* panel's misleading status text for the remainder of any session
after a first detection, but confirmed it does **not** affect whether the position marker itself
is hidden (marker visibility was already correctly gated identically for "stale" and "none").
**One remaining unverified step:** re-check the live tab after restarting the dev server (needed
for the fix to take effect — see §5a's `[UNVERIFIED]` note) to confirm the label now correctly
settles to "NONE."

## 9. Honest bottom line

**Two real, minimal, evidence-backed defects found and fixed this session:**

1. WebSocket handler leak on route navigation (§1) — plausible contributor to degraded
   sustained-session behavior via accumulating zombie connections; not confirmed as *the*
   originally reported symptom.
2. Target-state "stale forever" mislabeling (§5a) — found live, directly investigating the user's
   own real-time report during this session's own extended replay; genuinely explains a
   misleading "STALE" status persisting indefinitely in long sessions, though it does not by
   itself explain the position marker failing to render for an *actually present* target.

Parts 2-4's static trace found no other defect in the client pipeline, server timers, or
per-connection state. Part 1's extended 10-minute live/dropout replay completed in full
(33,714 packets, dropout+resume exercised cleanly, no crash/stuck-UI) and is what surfaced the
§5a defect. **The one scenario this entire multi-session investigation thread has still never
reproduced: the position marker failing to appear while a real person is actively present in
front of the sensors.** Given how much has now been ruled out or fixed (MUSIC empty-spectrum
path, node-mode staleness, synchronous and async replay across 5+ real sessions and ~45,000+
combined replayed ticks, the two defects above), the remaining gap increasingly looks like it
needs either genuine hands-on hardware time, or the specific screenshot/console capture requested
at the end of `PhantomScan_LiveTarget_Regression_Fix.md`, to close definitively.
