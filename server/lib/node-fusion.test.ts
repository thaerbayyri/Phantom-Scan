import test from "node:test";
import assert from "node:assert/strict";
import {
  fuseTwoNodeTarget,
  computeNodeMotion,
  MOTION_SATURATION_SCALE,
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

test("computeNodeMotion: constant amplitude => zero motion", () => {
  const m = computeNodeMotion([10, 10, 10, 10]);
  assert.equal(m.absStd, 0);
  assert.equal(m.motion, 0);
});

test("computeNodeMotion: saturates at 1.0 and uses the documented scale", () => {
  // absStd/mean * SCALE >= 1 must clamp to 1.
  const m = computeNodeMotion([0, 20]); // mean 10, absStd 10 => 10/10*4 = 4 -> clamp 1
  assert.equal(m.motion, 1);
  assert.ok(m.absStd > 0);
  assert.equal(MOTION_SATURATION_SCALE, 4);
});
