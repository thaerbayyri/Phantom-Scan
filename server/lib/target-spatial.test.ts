import test from "node:test";
import assert from "node:assert/strict";
import type { RadialTarget, SensorNode, TargetState } from "@shared/schema";
import { summarizeTargetSpatial } from "@shared/target-spatial";

const fusedNodes: SensorNode[] = [
  { node_id: 1, x: -1.5, z: 0, motion: 0.7, active: true, rssi: -45, source: "live", distanceM: 0.6, trend: "receding" },
  { node_id: 2, x: 1.5, z: 0, motion: 0.8, active: true, rssi: -43, source: "live", distanceM: 2.4, trend: "approaching" },
];

function buildTargetState(overrides: Partial<TargetState> = {}): TargetState {
  return {
    state: "moving",
    source_mode: "live",
    node_mode: "fused_two_node",
    target_visible: true,
    position_confident: true,
    position: { x: 0, y: 0, z: 0 },
    bearing_deg: 0,
    range_m: 1,
    motion_score: 0.8,
    confidence: 0.9,
    last_update_ms: 1_000,
    data_age_ms: 0,
    stale: false,
    reason: "live_target",
    ...overrides,
  };
}

test("fused targets summarize the between-node position and destination node", () => {
  const target: RadialTarget = {
    x: -0.9,
    z: 0,
    r: 0.9,
    theta: 0,
    vx: 0.2,
    vz: 0,
    isMoving: true,
    angle: 0,
    speed: 0.4,
    confidence: 0.8,
    label: "human",
    humanProb: 0.9,
    distanceCm: 90,
    wallDistance: 4.2,
    balance: 0.2,
  };

  const summary = summarizeTargetSpatial(target, fusedNodes, buildTargetState());
  assert(summary);
  assert.equal(summary.zoneLabel, "Projected Near N1");
  assert.equal(summary.motionLabel, "Projected motion toward N2");
  assert.equal(summary.presentationMode, "fused_axis");
  assert.equal(summary.balanceZone, "near_n1");
  assert.equal(summary.projectionLabel, "front / behind / beside collapses to this axis projection");
  assert.match(summary.detailLabel, /to N1/);
  assert.match(summary.detailLabel, /to N2/);
});

test("fused midpoint targets call out midpoint hold on the node axis", () => {
  const target: RadialTarget = {
    x: 0,
    z: 0,
    r: 0,
    theta: 0,
    vx: 0,
    vz: 0,
    isMoving: false,
    angle: 0,
    speed: 0,
    confidence: 0.6,
    label: "unknown",
    humanProb: 0.5,
    distanceCm: 150,
    wallDistance: 4,
    balance: 0.5,
  };

  const summary = summarizeTargetSpatial(target, fusedNodes, buildTargetState({
    state: "degraded",
    position_confident: false,
    target_visible: false,
  }));
  assert(summary);
  assert.equal(summary.zoneLabel, "Projected Between N1 and N2");
  assert.equal(summary.motionLabel, "Projected hold at the midpoint");
  assert.equal(summary.presentationMode, "fused_axis");
  assert.equal(summary.balanceZone, "midpoint");
});

test("fused targets near the second node identify the far-side destination", () => {
  const target: RadialTarget = {
    x: 1.2,
    z: 0,
    r: 1.2,
    theta: 0,
    vx: -0.12,
    vz: 0,
    isMoving: true,
    angle: Math.PI,
    speed: 0.25,
    confidence: 0.72,
    label: "human",
    humanProb: 0.82,
    distanceCm: 120,
    wallDistance: 4.4,
    balance: 0.9,
  };

  const summary = summarizeTargetSpatial(
    target,
    [
      { ...fusedNodes[0], trend: "approaching", distanceM: 2.7 },
      { ...fusedNodes[1], trend: "receding", distanceM: 0.3 },
    ],
    buildTargetState(),
  );
  assert(summary);
  assert.equal(summary.zoneLabel, "Projected Near N2");
  assert.equal(summary.motionLabel, "Projected motion toward N1");
  assert.equal(summary.presentationMode, "fused_axis");
  assert.equal(summary.balanceZone, "near_n2");
});

test("single-node targets summarize as around the nearest node", () => {
  const target: RadialTarget = {
    x: -1.0,
    z: 1.2,
    r: 1.56,
    theta: -0.6,
    vx: 0,
    vz: 0,
    isMoving: false,
    angle: Math.PI / 2,
    speed: 0,
    confidence: 0.35,
    label: "unknown",
    humanProb: 0.5,
    distanceCm: 156,
    wallDistance: 4.2,
  };

  const summary = summarizeTargetSpatial(
    target,
    fusedNodes,
    buildTargetState({ node_mode: "single_node", state: "degraded", position_confident: false }),
  );
  assert(summary);
  assert.equal(summary.zoneLabel, "Around N1");
  assert.equal(summary.motionLabel, "Holding near N1");
  assert.equal(summary.presentationMode, "single_node");
});

test("single-node moving label uses compass cardinal from travel angle", () => {
  const target: RadialTarget = {
    x: -1.0,
    z: 1.2,
    r: 1.56,
    theta: -0.6,
    vx: 0.3,
    vz: 0,
    isMoving: true,
    angle: 0, // math convention: 0 = east
    speed: 0.3,
    confidence: 0.35,
    label: "unknown",
    humanProb: 0.5,
    distanceCm: 156,
    wallDistance: 4.2,
  };

  const summary = summarizeTargetSpatial(
    target,
    fusedNodes,
    buildTargetState({ node_mode: "single_node", state: "moving", position_confident: false }),
  );
  assert(summary);
  assert.equal(summary.motionLabel, "Moving east around the node field");

  const north = summarizeTargetSpatial(
    { ...target, angle: Math.PI / 2 }, // +90° = north
    fusedNodes,
    buildTargetState({ node_mode: "single_node", state: "moving", position_confident: false }),
  );
  assert(north);
  assert.equal(north.motionLabel, "Moving north around the node field");
});
