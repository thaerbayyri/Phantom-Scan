# ADR-057: Single-Node Mode Needs a Presence Gate

**Status:** Accepted
**Date:** 2026-08-05
**Closes:** genuinely new finding (no prior PS-AUDIT-*/PS-BEHTEST-* item names this)
**Related:** ADR-056 (gain-normalized node balance, same bug-fix session), ADR-055 (endpoint velocity boost, measured)
**Decision maker:** Operator (bug report: target still shown when the room is empty)

## Context

The operator reported a phantom/ghost target still appearing on the
dashboard when the room is empty. Read-only investigation traced the full
single-node pipeline in `server/lib/websocket.ts` and found **no
presence/empty-room gate at all** in single-node mode:

1. The MUSIC-spectrum point cloud (`pThreshold = maxPower - 10`) is a
   *relative* threshold with no absolute noise floor — an empty room's
   ambient noise/multipath still has a max and a spread, so it reliably
   produces a non-empty point cloud with nobody present.
2. `TrackingProcessor` (DBSCAN+Kalman, `server/lib/tracking.ts`) clusters
   whatever points arrive using only a bare energy threshold
   (`maxEnergy > 10`) — no reference to `MotionGate`/`motionDetected`/any
   presence signal. It clusters noise and real people indistinguishably.
3. The broadcast-decision block only special-cased
   `nodeMode === "fused_two_node" && !fused` (the fused path's own presence
   gate, `present = max(motion1,motion2) >= threshold`). In `single_node`
   mode that condition is structurally always false, so `radialTarget` was
   broadcast **every tick** with a full sample buffer, regardless of
   `motionResult.motionDetected` or whether `trackedTarget` was null.
4. `MotionGate.motionDetected` was deliberately decoupled from rendering — an
   explicit prior comment states: *"Motion-gate now affects motion
   classification only. A stationary but truthful target should remain
   visible as idle/degraded, not disappear entirely."* This was an
   intentional design choice to avoid hiding a real-but-stationary person,
   which any fix must preserve rather than override with a blunt motion gate.
5. `buildTargetState` sets `state = "degraded"` unconditionally for
   `single_node` mode (no presence check), and `"degraded"` is neither
   `"none"` nor `"stale"`, so the client's `canRenderTarget` renders it.

This is a genuinely new finding — the existing audit/behavioral-test reports
only flag "we lack empty-room test data to measure a false-positive rate,"
never the code-level absence of a single-node presence gate.

## Decision

Added `hasSingleNodePresenceEvidence(motionDetected, hasTrackedTarget)` in
`server/lib/node-fusion.ts`:

```ts
export function hasSingleNodePresenceEvidence(motionDetected: boolean, hasTrackedTarget: boolean): boolean {
  return motionDetected || hasTrackedTarget;
}
```

Wired into the broadcast-decision block in `server/lib/websocket.ts`,
alongside (not replacing) the existing fused-mode branch:

```ts
} else if (
  nodeMode === "single_node" &&
  !hasSingleNodePresenceEvidence(motionResult.motionDetected, Boolean(trackedTarget))
) {
  this.holdOrClearTarget({
    hold: "single_node_no_detection_hold",
    staleHold: "single_node_no_detection_stale_hold",
    cleared: "single_node_no_detection_cleared",
    empty: "single_node_no_detection",
  });
} else {
  // existing broadcast — unchanged
}
```

**Why OR, not motion alone:** using `motionDetected || Boolean(trackedTarget)`
(rather than reintroducing a hard motion-only gate) preserves as much of the
original stationary-target-stays-visible intent as this pipeline allows — a
still person may not trip the temporal `MotionGate`, but can still form a
spatial DBSCAN cluster, so `trackedTarget` being non-null is independently
sufficient evidence.

**Why the hold/clear lifecycle, not an instant clear:** reuses the exact
`holdOrClearTarget` mechanism the fused path already uses for its own
"detection dropped this tick, don't instantly wipe a real target" case (5s
hard clear / 1.5s stale hold). A momentary motion-gate flicker or a single
tick where DBSCAN didn't cluster does not immediately hide a real target —
only a sustained absence (>5s) of any real evidence clears it, identical to
how any other live-data gap is already handled.

## Consequences

- Single-node mode now requires at least one real evidence signal
  (motion OR a tracked cluster) before ever acquiring or continuing to hold a
  target — an empty room with neither signal is held/cleared instead of
  broadcasting a fresh noise-derived `radialTarget` every tick.
- This does **not** fully solve detecting a perfectly stationary person via
  spatial clustering alone — that requires a calibrated absolute noise floor
  for the point-cloud/tracking stage, which needs real hardware capture to
  establish and is out of scope here. It solves the concrete reported bug: a
  continuous ghost target with nobody in the room.
- **UNVERIFIED ON REAL HARDWARE.** No calibrated empty-room capture currently
  exists in this repo's session data (a gap already flagged in
  `PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md`). Recommend the operator test by
  leaving the room empty for >5s in single-node mode and confirming the
  target clears, then re-entering and confirming a real target still shows
  normally — including surviving a few seconds of standing still.
- No integration test exercises this decision inside the actual
  `PhantomWebSocketServer` class end-to-end — no harness for driving its
  per-tick CSI processing pipeline exists in this codebase (confirmed when
  scoping the earlier fallback-velocity fix this session). The pure
  `hasSingleNodePresenceEvidence` decision function is fully unit-tested; the
  two-line wiring at the call site is a visually-verifiable diff, not
  independently integration-tested. This is a residual gap, not fabricated
  coverage.
- Checkpoint: `checkpoint/pre-target-presentation-fix` git tag (pushed to
  `origin`) marks the commit immediately before this change and ADR-056's
  gain-normalization fix, for rollback if either doesn't hold up on real
  hardware.
