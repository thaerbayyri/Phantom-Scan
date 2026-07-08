import test from "node:test";
import assert from "node:assert/strict";
import {
  fuseTwoNodeTarget,
  computeNodeMotion,
  computeNodeMotionFromMatrix,
  computeNodeTrends,
  MOTION_SATURATION_SCALE,
  type NodeTrend,
} from "./node-fusion";

const ANCHORS = { 1: { x: -1.5, z: 0 }, 2: { x: 1.5, z: 0 } } as const;
// Motion well above threshold so these tests isolate the localization math.
const MOVING = { motion1: 1, motion2: 1, motionThreshold: 0.12 } as const;

test("r1 >> r2 places the target at node 1 (x ≈ -1.5)", () => {
  const t = fuseTwoNodeTarget({ r1: 100, r2: 1, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.ok(t!.balance < 0.05, `balance ${t!.balance}`);
  assert.ok(Math.abs(t!.x - -1.5) < 0.1, `x ${t!.x}`);
  assert.equal(t!.z, 0);
});

test("r1 ≈ r2 places the target at the midpoint (x ≈ 0, balance ≈ 0.5)", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.ok(Math.abs(t!.balance - 0.5) < 1e-9);
  assert.ok(Math.abs(t!.x) < 1e-9, `x ${t!.x}`);
});

test("r2 >> r1 places the target at node 2 (x ≈ +1.5)", () => {
  const t = fuseTwoNodeTarget({ r1: 1, r2: 100, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.ok(t!.balance > 0.95, `balance ${t!.balance}`);
  assert.ok(Math.abs(t!.x - 1.5) < 0.1, `x ${t!.x}`);
});

test("empty room (motion below threshold) returns NO target — not a centered ghost", () => {
  const t = fuseTwoNodeTarget({
    r1: 0.001,
    r2: 0.001,
    motion1: 0.01,
    motion2: 0.01,
    anchors: ANCHORS,
    motionThreshold: 0.12,
  });
  assert.equal(t, null);
});

test("fused target uses the configured presence threshold instead of the placeholder default", () => {
  const belowCustom = fuseTwoNodeTarget({
    r1: 0.3,
    r2: 0.25,
    motion1: 0.4,
    motion2: 0.35,
    anchors: ANCHORS,
    motionThreshold: 0.5,
  });
  assert.equal(belowCustom, null);

  const aboveCustom = fuseTwoNodeTarget({
    r1: 0.3,
    r2: 0.25,
    motion1: 0.6,
    motion2: 0.35,
    anchors: ANCHORS,
    motionThreshold: 0.5,
  });
  assert.ok(aboveCustom);
});

test("zero perturbation returns NO target even if motion inputs are high", () => {
  const t = fuseTwoNodeTarget({
    r1: 0,
    r2: 0,
    motion1: 1,
    motion2: 1,
    anchors: ANCHORS,
    motionThreshold: 0.12,
  });
  assert.equal(t, null);
});

test("distToNearestNodeM is ~half the separation at the midpoint", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  // Midpoint of a 3 m axis is 1.5 m from each node.
  assert.ok(Math.abs(t!.distToNearestNodeM - 1.5) < 1e-9);
});

test("matrix motion: identical frames => zero motion (static room)", () => {
  const m = computeNodeMotionFromMatrix([
    [10, 20, 15],
    [10, 20, 15],
    [10, 20, 15],
  ]);
  assert.equal(m.absStd, 0);
  assert.equal(m.motion, 0);
});

test("matrix motion detects per-subcarrier oscillation the best-subcarrier scalar misses", () => {
  // Alternating [10,20] / [20,10]: the max-power scalar is 20 in EVERY frame
  // (std 0 — sees nothing), but each subcarrier oscillates strongly.
  const frames = [
    [10, 20],
    [20, 10],
    [10, 20],
    [20, 10],
  ];
  const matrix = computeNodeMotionFromMatrix(frames);
  const scalar = computeNodeMotion(frames.map((f) => Math.max(...f)));
  assert.equal(scalar.motion, 0, "scalar path blind to this motion");
  assert.ok(matrix.absStd > 4, `matrix absStd ${matrix.absStd}`);
  assert.ok(matrix.motion > 0.5, `matrix motion ${matrix.motion}`);
});

test("balance tracks the node with stronger per-subcarrier perturbation", () => {
  // Node 1: strongly oscillating subcarriers; node 2: nearly static.
  const perturbed = computeNodeMotionFromMatrix([
    [10, 30, 20],
    [30, 10, 25],
    [12, 28, 18],
    [28, 12, 26],
  ]);
  const still = computeNodeMotionFromMatrix([
    [15, 15, 15],
    [15.2, 14.9, 15.1],
    [14.9, 15.1, 15],
    [15.1, 15, 14.9],
  ]);
  const t = fuseTwoNodeTarget({
    r1: perturbed.absStd,
    r2: still.absStd,
    motion1: perturbed.motion,
    motion2: still.motion,
    anchors: ANCHORS,
    motionThreshold: 0.12,
  });
  assert.ok(t, "target must exist");
  assert.ok(t!.balance < 0.1, `balance ${t!.balance} should sit near node 1`);
  assert.ok(t!.x < -1.2, `x ${t!.x} should be near N1 (-1.5)`);
});

test("computeNodeMotion: constant amplitude => zero motion", () => {
  const m = computeNodeMotion([10, 10, 10, 10]);
  assert.equal(m.absStd, 0);
  assert.equal(m.motion, 0);
});

test("rising balance (positive axis velocity) => N2 approaching, N1 receding", () => {
  const prev = { 1: "stable", 2: "stable" } as { 1: NodeTrend; 2: NodeTrend };
  const t = computeNodeTrends(0.4, prev, 0.05);
  assert.equal(t[1], "receding");
  assert.equal(t[2], "approaching");
});

test("falling balance (negative axis velocity) => N1 approaching, N2 receding", () => {
  const prev = { 1: "stable", 2: "stable" } as { 1: NodeTrend; 2: NodeTrend };
  const t = computeNodeTrends(-0.4, prev, 0.05);
  assert.equal(t[1], "approaching");
  assert.equal(t[2], "receding");
});

test("velocity inside the deadband keeps the previous trends (hysteresis)", () => {
  const prev = { 1: "approaching", 2: "receding" } as { 1: NodeTrend; 2: NodeTrend };
  const t = computeNodeTrends(0.01, prev, 0.05);
  assert.deepEqual(t, prev);
});

test("distanceM bookkeeping: balance splits the separation between the nodes", () => {
  // balance 0.25 on a 3 m axis => 0.75 m from N1, 2.25 m from N2.
  const t = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.ok(Math.abs(t!.balance - 0.25) < 1e-9);
  const dN1 = Math.abs(t!.x - ANCHORS[1].x);
  const dN2 = Math.abs(t!.x - ANCHORS[2].x);
  assert.ok(Math.abs(dN1 - 0.75) < 1e-9, `dN1 ${dN1}`);
  assert.ok(Math.abs(dN2 - 2.25) < 1e-9, `dN2 ${dN2}`);
});

test("computeNodeMotion: saturates at 1.0 and uses the documented scale", () => {
  // absStd/mean * SCALE >= 1 must clamp to 1.
  const m = computeNodeMotion([0, 20]); // mean 10, absStd 10 => 10/10*4 = 4 -> clamp 1
  assert.equal(m.motion, 1);
  assert.ok(m.absStd > 0);
  assert.equal(MOTION_SATURATION_SCALE, 4);
});
