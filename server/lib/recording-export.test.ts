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
  assert.ok(RECORDING_COLUMNS.includes("raw_perturbation_n1"));
  assert.ok(RECORDING_COLUMNS.includes("raw_perturbation_n4"));
});

test("raw_perturbation_nX is exported unclamped, unlike the saturated motion_nX it's derived from", () => {
  // A ratio far past the saturation ceiling (motion_nX clamps at 1.0) must
  // still come through raw_perturbation_nX at its real, uncensored value --
  // that's the whole point of this field (see its doc comment on RecordingRow).
  const row = buildRecordingRow({
    sample,
    sessionStartMs: 10_000,
    radialTarget,
    targetState: fusedTargetState,
    fusedSnapshot: null,
    nodeMotion: { 1: 1.0, 2: 0.3 },
    nodeRawPerturbation: { 1: 3.7, 2: 0.075 },
    nodeFps: { 1: 24, 2: 25 },
  });

  assert.equal(row.motion_n1, 1.0, "sanity: motion_n1 is the clamped/saturated value");
  assert.equal(
    row.raw_perturbation_n1,
    3.7,
    "raw_perturbation_n1 must preserve the real ratio, not the clamped 1.0",
  );
  assert.equal(row.raw_perturbation_n2, 0.075);
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
      z: 0,
      velMps: 0.2,
      endpointIds: [1, 2],
      trends: { 1: "receding", 2: "approaching" },
      atMs: 10_500,
    },
    nodeMotion: { 1: 0.3, 2: 0.4 },
    nodeRawPerturbation: { 1: 0.03, 2: 0.04 },
    nodeFps: { 1: 24, 2: 25 },
  });

  assert.equal(row.session_ts_ms, 500);
  assert.equal(row.x_disp_m, radialTarget.x);
  assert.equal(row.z_disp_m, radialTarget.z);
  assert.equal(row.x, row.x_disp_m);
  assert.equal(row.z, row.z_disp_m);
  // Distances use the full 4m x 6m room geometry.
  assert.equal(row.distance_n1_m, Math.hypot(2.75, 3));
  assert.equal(row.distance_n2_m, Math.hypot(1.25, 3));
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
      z: 0,
      velMps: 0.2,
      endpointIds: [1, 2],
      trends: { 1: "receding", 2: "approaching" },
      atMs: 10_500,
    },
    nodeMotion: { 1: 0.3, 2: 0.4 },
    nodeRawPerturbation: { 1: 0.03, 2: 0.04 },
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

test("recording rows carry the room tier, per-node excess, and real N3/N4 trends for fused_room", () => {
  for (const col of ["room_tier", "excess_n1", "excess_n2", "excess_n3", "excess_n4", "trend_n3", "trend_n4", "position_uncertainty_m"]) {
    assert.ok(RECORDING_COLUMNS.includes(col as never), `missing column ${col}`);
  }
  const row = buildRecordingRow({
    sample,
    sessionStartMs: 10_000,
    radialTarget,
    targetState: fusedTargetState,
    fusedSnapshot: null,
    nodeMotion: { 1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5 },
    nodeRawPerturbation: { 1: 0.05, 2: 0.06, 3: 0.07, 4: 0.08 },
    nodeFps: { 1: 20, 2: 20, 3: 20, 4: 20 },
    roomExtras: {
      tier: "present_moving",
      excess: { 1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04 },
      trends: { 1: "approaching", 2: "receding", 3: "approaching", 4: "stable" },
      positionUncertaintyM: 1.25,
    },
  });
  assert.equal(row.room_tier, "present_moving");
  assert.equal(row.excess_n3, 0.03);
  assert.equal(row.trend_n1, "approaching");
  assert.equal(row.trend_n3, "approaching");
  assert.equal(row.trend_n4, "stable");
  assert.equal(row.position_uncertainty_m, 1.25);
});

test("recording rows without room extras keep the legacy trend source and leave the new columns empty", () => {
  const row = buildRecordingRow({
    sample,
    sessionStartMs: 10_000,
    radialTarget,
    targetState: fusedTargetState,
    fusedSnapshot: null,
    nodeMotion: { 1: 0.2, 2: 0.3 },
    nodeRawPerturbation: { 1: 0.05, 2: 0.06 },
    nodeFps: { 1: 20, 2: 20 },
  });
  assert.equal(row.room_tier, undefined);
  assert.equal(row.excess_n1, undefined);
  assert.equal(row.trend_n3, "stable");
});
