import test from "node:test";
import assert from "node:assert/strict";
import {
  fuseTwoNodeTarget,
  biasBalanceTowardNearestNode,
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

test("display bias preserves the midpoint exactly", () => {
  assert.equal(biasBalanceTowardNearestNode(0.5), 0.5);
});

test("display bias pulls the target closer to node 1 when balance is low", () => {
  const linearX = ANCHORS[1].x + (ANCHORS[2].x - ANCHORS[1].x) * 0.25;
  const t = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  // Contrast p=2: 10² / (30² + 10²) = 100/1000 = 0.1.
  assert.ok(Math.abs(t!.balance - 0.1) < 1e-9, `balance ${t!.balance}`);
  assert.ok(t!.x < linearX, `biased x ${t!.x} should be closer to N1 than linear ${linearX}`);
  assert.ok(t!.x < -0.9, `x ${t!.x} should land aggressively near N1`);
});

test("display bias pulls the target closer to node 2 when balance is high", () => {
  const linearX = ANCHORS[1].x + (ANCHORS[2].x - ANCHORS[1].x) * 0.75;
  const t = fuseTwoNodeTarget({ r1: 10, r2: 30, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  // Contrast p=2: 30² / (10² + 30²) = 900/1000 = 0.9.
  assert.ok(Math.abs(t!.balance - 0.9) < 1e-9, `balance ${t!.balance}`);
  assert.ok(t!.x > linearX, `biased x ${t!.x} should be closer to N2 than linear ${linearX}`);
  assert.ok(t!.x > 0.9, `x ${t!.x} should land aggressively near N2`);
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
  // The max-power scalar per frame is constant 20 → 1-element frames, std 0.
  const scalar = computeNodeMotionFromMatrix(frames.map((f) => [Math.max(...f)]));
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

test("computeNodeMotionFromMatrix: constant amplitude => zero motion", () => {
  const m = computeNodeMotionFromMatrix([
    [10, 10],
    [10, 10],
    [10, 10],
  ]);
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
  // Raw balance still reflects the motion ratio even though display x is biased.
  const t = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  // Contrast p=2 sharpens the raw ratio: 0.25 linear → 0.1.
  assert.ok(Math.abs(t!.balance - 0.1) < 1e-9);
  assert.ok(t!.distToNearestNodeM < 0.75, `nearest distance ${t!.distToNearestNodeM} should be closer than linear`);
});

test("contrast exponent widens balance vs the linear ratio; p=1 restores linear", () => {
  const sharp = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING });
  const linear = fuseTwoNodeTarget({
    r1: 30,
    r2: 10,
    anchors: ANCHORS,
    ...MOVING,
    contrastExponent: 1,
  });
  assert.ok(sharp && linear);
  assert.ok(Math.abs(linear!.balance - 0.25) < 1e-9, `linear balance ${linear!.balance}`);
  assert.ok(sharp!.balance < linear!.balance, "p=2 must pull balance further toward N1");
  // Midpoint is invariant under any exponent.
  const mid = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, contrastExponent: 3 });
  assert.ok(Math.abs(mid!.balance - 0.5) < 1e-9);
});

test("computeNodeMotionFromMatrix: saturates at 1.0 and uses the documented scale", () => {
  // Temporal std per subcarrier: [0,20] -> std 10, mean 10 => 10/10*4 = 4 -> clamp 1.
  const m = computeNodeMotionFromMatrix([
    [0, 0],
    [20, 20],
  ]);
  assert.equal(m.motion, 1);
  assert.ok(m.absStd > 0);
  assert.equal(MOTION_SATURATION_SCALE, 4);
});
