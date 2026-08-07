import test from "node:test";
import assert from "node:assert/strict";
import type { MotionStatus, RadialTarget } from "@shared/schema";
import {
  buildTargetState,
  emptyTargetState,
  LIVE_TARGET_CLEAR_TIMEOUT_MS,
  LIVE_TARGET_STALE_TIMEOUT_MS,
  isSampleFresh,
  resolveLiveHoldState,
  resolveSourceMode,
} from "./target-state";

test("isSampleFresh accepts a sample within the live stale window", () => {
  const now = 1_000_000;
  assert.equal(isSampleFresh({ timestamp: now - 100 }, now), true);
  assert.equal(isSampleFresh({ timestamp: now }, now), true);
});

test("isSampleFresh drops backlog samples older than the stale window", () => {
  const now = 1_000_000;
  // 2 s old — the disconnect-backlog case that painted ghost targets.
  assert.equal(isSampleFresh({ timestamp: now - 2_000 }, now), false);
  // Boundary: exactly at the window edge is still fresh.
  assert.equal(
    isSampleFresh({ timestamp: now - LIVE_TARGET_STALE_TIMEOUT_MS }, now),
    true,
  );
  assert.equal(
    isSampleFresh({ timestamp: now - LIVE_TARGET_STALE_TIMEOUT_MS - 1 }, now),
    false,
  );
});

const movingMotion: MotionStatus = {
  motionDetected: true,
  variance: 0.42,
  threshold: 0.05,
};

const radialTarget: RadialTarget = {
  x: 1.2,
  z: 2.4,
  r: 2.68,
  theta: Math.PI / 6,
  vx: 0.1,
  vz: 0.2,
  isMoving: true,
  angle: Math.PI / 8,
  speed: 0.3,
  confidence: 0.82,
  label: "human",
  humanProb: 0.91,
  distanceCm: 268,
  wallDistance: 4.6,
};

test("resolveSourceMode maps esp32 to live", () => {
  assert.equal(resolveSourceMode("esp32"), "live");
});

test("emptyTargetState reports none when no truthful target exists", () => {
  const state = emptyTargetState({
    dataSource: "esp32",
    nowMs: 1_000,
    reason: "awaiting_live_samples",
  });

  assert.equal(state.state, "none");
  assert.equal(state.target_visible, false);
  assert.equal(state.node_mode, "single_node");
  assert.equal(state.source_mode, "live");
  assert.equal(state.reason, "awaiting_live_samples");
});

test("buildTargetState marks single-node live targets as degraded", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 2_000,
    lastTruthfulUpdateMs: 2_000,
    radialTarget,
    motionStatus: movingMotion,
  });

  assert.equal(state.state, "degraded");
  assert.equal(state.target_visible, true);
  assert.equal(state.position_confident, true);
  assert.equal(state.node_mode, "single_node");
  assert.equal(state.source_mode, "live");
  assert.equal(state.range_m, radialTarget.r);
});

test("buildTargetState honors fused two-node live mode", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 2_000,
    lastTruthfulUpdateMs: 2_000,
    nodeMode: "fused_two_node",
    radialTarget,
    motionStatus: movingMotion,
  });

  assert.equal(state.state, "moving");
  assert.equal(state.target_visible, true);
  assert.equal(state.node_mode, "fused_two_node");
  assert.equal(state.source_mode, "live");
});

test("buildTargetState keeps fused live targets moving", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 3_000,
    lastTruthfulUpdateMs: 3_000,
    nodeMode: "fused_two_node",
    radialTarget,
    motionStatus: movingMotion,
  });

  assert.equal(state.state, "moving");
  assert.equal(state.source_mode, "live");
  assert.equal(state.node_mode, "fused_two_node");
});

test("buildTargetState demotes old targets to stale", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 10_000,
    lastTruthfulUpdateMs: 8_000,
    radialTarget,
    motionStatus: movingMotion,
  });

  assert.equal(state.state, "stale");
  assert.equal(state.target_visible, false);
  assert.equal(state.stale, true);
});

test("buildTargetState keeps low-confidence targets visible but not position-confident", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 4_000,
    lastTruthfulUpdateMs: 4_000,
    radialTarget: {
      ...radialTarget,
      confidence: 0.2,
      label: "human",
    },
    motionStatus: movingMotion,
  });

  assert.equal(state.target_visible, true);
  assert.equal(state.position_confident, false);
  assert.equal(state.state, "degraded");
});

test("resolveLiveHoldState distinguishes startup, live, stale hold, and cleared", () => {
  assert.equal(resolveLiveHoldState(null, 1_000), "startup");
  assert.equal(resolveLiveHoldState(1_000, 1_000 + LIVE_TARGET_STALE_TIMEOUT_MS - 1), "live");
  assert.equal(resolveLiveHoldState(1_000, 1_000 + LIVE_TARGET_STALE_TIMEOUT_MS), "stale_hold");
  assert.equal(resolveLiveHoldState(1_000, 1_000 + LIVE_TARGET_CLEAR_TIMEOUT_MS), "cleared");
});

test("emptyTargetState settles back to 'none' well past the clear timeout instead of reporting 'stale' forever", () => {
  const lastTruthful = 1_000;
  // Just inside the stale window: genuinely recently aged out.
  const recentlyLost = emptyTargetState({
    dataSource: "esp32",
    nowMs: lastTruthful + LIVE_TARGET_STALE_TIMEOUT_MS + 1,
    lastTruthfulUpdateMs: lastTruthful,
  });
  assert.equal(recentlyLost.state, "stale");

  // Long after the clear timeout (e.g. minutes into an otherwise-empty room
  // later in the same long session) — must read as an ordinary empty room,
  // not "stale" forever just because a target was truthfully seen once.
  const longAfter = emptyTargetState({
    dataSource: "esp32",
    nowMs: lastTruthful + LIVE_TARGET_CLEAR_TIMEOUT_MS + 10 * 60_000,
    lastTruthfulUpdateMs: lastTruthful,
  });
  assert.equal(longAfter.state, "none");
  assert.equal(longAfter.stale, false);
});

test("bearing_deg uses the compass convention (x=1,z=0 -> 90 = east)", () => {
  const state = buildTargetState({
    dataSource: "esp32",
    nowMs: 10_000,
    lastTruthfulUpdateMs: 10_000,
    nodeMode: "fused_two_node",
    radialTarget: { ...radialTarget, x: 1, z: 0, theta: Math.PI / 2 },
    motionStatus: movingMotion,
  });
  assert.equal(state.target_visible, true);
  assert.ok(Math.abs((state.bearing_deg ?? 0) - 90) < 1e-9);
});
