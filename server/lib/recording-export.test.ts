import test from "node:test";
import assert from "node:assert/strict";
import type { CSISample, RadialTarget, TargetState } from "@shared/schema";
import {
  RECORDING_COLUMNS,
  RECORDING_POSITION_CONTRACT,
  buildRecordingRow,
  buildRecordingSessionMeta,
  serializeRecordingCsv,
} from "./recording-export";

const sample: CSISample = {
  timestamp: 10_500,
  h1: { re: 1, im: 2 },
  h2: { re: 3, im: 4 },
  rssi: -47,
  subcarrierIndex: 12,
};

const radialTarget: RadialTarget = {
  x: 0.75,
  z: 0,
  r: 0.75,
  theta: 0,
  vx: 0.1,
  vz: 0,
  isMoving: true,
  angle: 0,
  speed: 0.2,
  confidence: 0.8,
  label: "human",
  humanProb: 0.9,
  distanceCm: 75,
  wallDistance: 4.5,
  balance: 0.75,
};

const fusedTargetState: TargetState = {
  state: "moving",
  source_mode: "live",
  node_mode: "fused_two_node",
  target_visible: true,
  position_confident: true,
  position: { x: 0.75, y: 0, z: 0 },
  bearing_deg: 0,
  range_m: 0.75,
  motion_score: 0.4,
  confidence: 0.8,
  last_update_ms: 10_500,
  data_age_ms: 0,
  stale: false,
  reason: "live_target",
};

test("recording CSV header includes the positional fidelity columns", () => {
  assert.ok(RECORDING_COLUMNS.includes("session_ts_ms"));
  assert.ok(RECORDING_COLUMNS.includes("sync_marker"));
  assert.ok(RECORDING_COLUMNS.includes("x_disp_m"));
  assert.ok(RECORDING_COLUMNS.includes("distance_n1_m"));
  assert.ok(RECORDING_COLUMNS.includes("target_visible"));
  assert.ok(RECORDING_COLUMNS.includes("node1_fps"));
  assert.ok(RECORDING_COLUMNS.includes("gt_x_m"));
});

test("visible fused rows reuse the same displayed position contract", () => {
  const row = buildRecordingRow({
    sample,
    sessionStartMs: 10_000,
    radialTarget,
    targetState: fusedTargetState,
    fusedSnapshot: {
      balance: 0.75,
      x: 0.75,
      velMps: 0.2,
      trends: { 1: "receding", 2: "approaching" },
      atMs: 10_500,
    },
    nodeMotion: { 1: 0.3, 2: 0.4 },
    nodeFps: { 1: 24, 2: 25 },
  });

  assert.equal(row.session_ts_ms, 500);
  assert.equal(row.x_disp_m, radialTarget.x);
  assert.equal(row.z_disp_m, radialTarget.z);
  assert.equal(row.x, row.x_disp_m);
  assert.equal(row.z, row.z_disp_m);
  // NODE_ANCHORS[1].x = -2, NODE_ANCHORS[2].x = 2 (4m x 6m room corners).
  assert.equal(row.distance_n1_m, 2.75);
  assert.equal(row.distance_n2_m, 1.25);
  assert.equal(row.trend_n1, "receding");
  assert.equal(row.trend_n2, "approaching");
  assert.equal(row.target_visible, 1);
});

test("gate-closed rows suppress position and distance fields atomically", () => {
  const row = buildRecordingRow({
    sample,
    sessionStartMs: 10_000,
    radialTarget,
    targetState: {
      ...fusedTargetState,
      state: "stale",
      target_visible: false,
      stale: true,
    },
    fusedSnapshot: {
      balance: 0.75,
      x: 0.75,
      velMps: 0.2,
      trends: { 1: "receding", 2: "approaching" },
      atMs: 10_500,
    },
    nodeMotion: { 1: 0.3, 2: 0.4 },
    nodeFps: { 1: 24, 2: 25 },
  });

  assert.equal(row.x_disp_m, undefined);
  assert.equal(row.z_disp_m, undefined);
  assert.equal(row.distance_n1_m, undefined);
  assert.equal(row.distance_n2_m, undefined);
  assert.equal(row.trend_n1, "stable");
  assert.equal(row.trend_n2, "stable");
  assert.equal(row.target_visible, 0);
});

test("serialized CSV carries metadata with the explicit x/x_disp contract", () => {
  const meta = buildRecordingSessionMeta({
    sessionName: "case-a",
    recordingStartMs: 10_000,
    node1Fps: 23,
    node2Fps: 24,
    scalarMotionThreshold: 0.05,
    fusedMotionThreshold: 0.42,
  });
  const csv = serializeRecordingCsv([], meta);

  assert.match(csv, /^# phantom_session_meta /);
  assert.match(csv, new RegExp(RECORDING_POSITION_CONTRACT.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(csv, /"fused_motion_threshold":0\.42/);
});
