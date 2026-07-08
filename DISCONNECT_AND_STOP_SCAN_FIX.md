> **Note (2026-07-08):** written before this session's changes — the firmware now caches node_id pre-WiFi (`csi_collector_set_node_id`) and the dashboard also ingests `0xC5110006` feature-state packets (Board DSP card).

# Fix: Ghost Target on ESP32 Disconnect + Stop-Scan Quiesce + Reconnect Hardening

Status: **implemented** in the working tree (branch `feat/two-node-radar-live-detection`).
All changes live in `server/lib/websocket.ts`, `server/lib/udp-server.ts`, `server/lib/target-state.ts`.

## Problem 1 — Ghost target after ESP32 disconnect

Bench repro: unplugging both ESP32 nodes left the dashboard showing a target long after the
1.5 s stale / 5 s clear windows.

Root causes (all in `server/lib/websocket.ts`):

1. **Backlog drain masquerading as live data.** `hardwareSampleQueue` (cap 1000) was dequeued
   one sample per 50 ms tick — up to ~50 s of stale samples processed as "live", each refreshing
   `lastTruthfulTargetUpdateMs`, so the stale/clear timers never fired.
2. **Frozen motion window.** `nodeAmpWindow` evicted >3 s entries only on ingest
   (`recordNodeAmplitude`). Silent nodes kept their last motion energy, so
   `computeFusedTarget()` kept returning a target.
3. **Single-node fallback bypassed the gate.** With silent nodes `resolveLiveNodeMode()`
   degraded to `single_node`, skipping the fused empty-room motion gate.

### Fixes

- `isSampleFresh(sample, nowMs)` in `server/lib/target-state.ts`: a sample is fresh only if
  `nowMs - timestamp <= LIVE_TARGET_STALE_TIMEOUT_MS` (1500 ms). The dequeue loop in
  `websocket.ts` drops stale queued samples until it finds a fresh one or empties the queue
  → live-gap handling → 5 s clear.
- Motion reads (`nodeMotionFor`) apply a wall-clock filter (`t >= now - 3000`) so a silent
  node's motion decays to 0; ingest-side eviction kept for memory bounds.
- When `activeHardwareNodeIds()` is empty in esp32 mode, the tick is treated as a live gap —
  no target computation from backlog.

## Problem 2 — Stop scan left the radar "live"

After Stop, beacons kept their last motion glow, `distanceM`/`trend` labels persisted, and
`ingestSample()` kept broadcasting `updateTargetDebug()` per UDP packet (~80/s).

### Fixes (`server/lib/websocket.ts`)

- `buildSensorNodes()` when not processing: anchors with `motion: 0`, no `distanceM`,
  `trend: "stable"`; real `active`/`rssi` kept so node presence stays honest.
- `stopProcessing()` calls `broadcastNodes()` once after `clearTargetArtifacts("processing_stopped")`
  so clients immediately get the quiesced beacons.
- Idle debug throttled via `lastIdleDebugMs`: at most one `updateTargetDebug()` per second
  while stopped.

## Problem 3 — Reconnect flood (`[UDP][SEC] node_source_mismatch` spam)

On reboot an ESP32 uses a new ephemeral UDP source port; the source-pinning guard rejected
the node per-packet. A DHCP IP change would lock the node out permanently.

### Fixes (`server/lib/udp-server.ts`, `SourcePinningGuard`)

- **Same-IP port rebind**: a new port from the pinned IP rebinds silently (the reboot case).
- **Stale-binding rebind (DHCP case)**: `lastAcceptedMs` tracked per binding; a new IP is
  accepted (one `node_source_rebound` info line) only if the pinned source has been silent
  longer than `STALE_BINDING_MS` (10 s). A conflicting source while the pinned one is still
  actively sending remains rejected — that is the real spoof signal.
- Mismatch warnings rate-limited to one console line per node per 5 s (events still counted).
- `securityEvents` bounded to the last 200 entries.

## Tests

- `server/lib/target-state.test.ts` — `isSampleFresh` boundary cases (fresh, exactly at the
  1500 ms window, one ms past it).
- `server/lib/udp-server.test.ts` — guard suite with injectable clock
  (`check(nodeId, source, nowMs)`): same-IP new-port accepted; new IP vs. active pin rejected;
  new IP after >10 s silence accepted + binding updated; securityEvents capped.
- `server/lib/node-fusion.test.ts` — fusion/gate/trend regression suite unchanged (17 tests).

## Hardware verification checklist

1. Start scan → target visible while a person moves between the nodes.
2. **Unplug both nodes** → target goes stale ≈1.5 s, cleared ≤5 s; beacons dim; no ghost.
3. **Stop scan** → target dot gone AND beacons idle-dim with no distance/trend labels within
   one broadcast; server console quiet (no per-packet debug spam).
4. **Unplug + replug one node mid-scan** → no `[UDP][SEC]` flood (≤1 line per 5 s); node
   rejoins automatically (same IP instantly; changed IP within ~10 s).
5. Log results in `REAL_TEST_REPORT.md` Stage 6(c).
