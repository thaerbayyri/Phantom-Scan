import test from "node:test";
import assert from "node:assert/strict";
import type { MotionStatus, RadialTarget } from "@shared/schema";
import {
  buildTargetState,
  emptyTargetState,
  LIVE_TARGET_CLEAR_TIMEOUT_MS,
  LIVE_TARGET_STALE_TIMEOUT_MS,
  resolveLiveHoldState,
  resolveSourceMode,
} from "./target-state";

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

test("resolveSourceMode maps file replay and demo synthetic", () => {
  assert.equal(resolveSourceMode("demo"), "synthetic");
  assert.equal(resolveSourceMode("file"), "replay");
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

test("buildTargetState keeps demo targets synthetic and moving", () => {
  const state = buildTargetState({
    dataSource: "demo",
    nowMs: 3_000,
    lastTruthfulUpdateMs: 3_000,
    radialTarget,
    motionStatus: movingMotion,
  });

  assert.equal(state.state, "moving");
  assert.equal(state.source_mode, "synthetic");
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
