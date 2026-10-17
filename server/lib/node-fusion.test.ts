import test from "node:test";
import assert from "node:assert/strict";
import {
  fuseTwoNodeTarget,
  fuseNodeTargets,
  biasBalanceTowardNearestNode,
  computeLinearBalance,
  computeNodeMotionFromMatrix,
  computeNodeTrends,
  computeFallbackVelocity,
  computeGainNormalizedPerturbation,
  computeAgcNormalizedPerturbation,
  computeRadialTrends,
  computePositionUncertaintyM,
  hasSingleNodePresenceEvidence,
  evaluateClassifierCorroboration,
  wasSuppressedByClassifier,
  MOTION_SATURATION_SCALE,
  FALLBACK_VELOCITY_MAX_GAP_S,
  DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX,
  type NodeTrend,
  type ClassifierGateInput,
} from "./node-fusion";

// 4m x 6m room, one anchor per corner, perimeter order 1->2->3->4->1 —
// mirrors shared/schema.ts's NODE_ANCHORS.
const ROOM_ANCHORS = {
  1: { x: -2, z: -3 },
  2: { x: 2, z: -3 },
  3: { x: 2, z: 3 },
  4: { x: -2, z: 3 },
} as const;
const ROOM_MOVING_THRESHOLD = 0.12;

test("fuseNodeTargets: motion concentrated at node 3 centroids near node 3's anchor", () => {
  const t = fuseNodeTargets(
    [
      { id: 1, r: 1, motion: 1, anchor: ROOM_ANCHORS[1] },
      { id: 2, r: 1, motion: 1, anchor: ROOM_ANCHORS[2] },
      { id: 3, r: 100, motion: 1, anchor: ROOM_ANCHORS[3] },
      { id: 4, r: 1, motion: 1, anchor: ROOM_ANCHORS[4] },
    ],
    { motionThreshold: ROOM_MOVING_THRESHOLD },
  );
  assert.ok(t);
  assert.ok(Math.abs(t!.x - ROOM_ANCHORS[3].x) < 0.5, `x ${t!.x}`);
  assert.ok(Math.abs(t!.z - ROOM_ANCHORS[3].z) < 0.5, `z ${t!.z}`);
  assert.equal(t!.nearestNodeId, 3);
});

test("fuseNodeTargets: motion split evenly across all 4 nodes centroids near room center", () => {
  const t = fuseNodeTargets(
    [
      { id: 1, r: 10, motion: 1, anchor: ROOM_ANCHORS[1] },
      { id: 2, r: 10, motion: 1, anchor: ROOM_ANCHORS[2] },
      { id: 3, r: 10, motion: 1, anchor: ROOM_ANCHORS[3] },
      { id: 4, r: 10, motion: 1, anchor: ROOM_ANCHORS[4] },
    ],
    { motionThreshold: ROOM_MOVING_THRESHOLD },
  );
  assert.ok(t);
  assert.ok(Math.abs(t!.x) < 1e-9, `x ${t!.x} should be at room center`);
  assert.ok(Math.abs(t!.z) < 1e-9, `z ${t!.z} should be at room center`);
});

test("fuseNodeTargets: below-threshold motion at all nodes returns null (empty-room gate)", () => {
  const t = fuseNodeTargets(
    [
      { id: 1, r: 0.01, motion: 0.02, anchor: ROOM_ANCHORS[1] },
      { id: 2, r: 0.01, motion: 0.02, anchor: ROOM_ANCHORS[2] },
      { id: 3, r: 0.01, motion: 0.02, anchor: ROOM_ANCHORS[3] },
      { id: 4, r: 0.01, motion: 0.02, anchor: ROOM_ANCHORS[4] },
    ],
    { motionThreshold: ROOM_MOVING_THRESHOLD },
  );
  assert.equal(t, null);
});

test("fuseNodeTargets: confident mechanical classification suppresses an otherwise-passing energy gate", () => {
  const t = fuseNodeTargets(
    [
      { id: 1, r: 1, motion: 1, anchor: ROOM_ANCHORS[1] },
      { id: 3, r: 1, motion: 1, anchor: ROOM_ANCHORS[3] },
    ],
    {
      motionThreshold: ROOM_MOVING_THRESHOLD,
      classifier: { label: "mechanical", humanProb: 0.05 },
    },
  );
  assert.equal(t, null);
});

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

// ── balanceLinear: authoritative/canonical cross-check (PS-AUDIT-003/011, ADR-054) ──

test("computeLinearBalance is the undecorated r2/(r1+r2) ratio", () => {
  assert.ok(Math.abs(computeLinearBalance(30, 10) - 0.25) < 1e-9);
  assert.equal(computeLinearBalance(0, 0), 0.5);
  assert.equal(computeLinearBalance(10, 10), 0.5);
});

test("balanceLinear on fuseTwoNodeTarget is invariant to the contrast exponent, unlike balance", () => {
  const p1 = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING, contrastExponent: 1 });
  const p2 = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING, contrastExponent: 2 });
  const p3 = fuseTwoNodeTarget({ r1: 30, r2: 10, anchors: ANCHORS, ...MOVING, contrastExponent: 3 });
  assert.ok(p1 && p2 && p3);
  // Always the plain linear ratio regardless of contrast shaping.
  for (const t of [p1!, p2!, p3!]) {
    assert.ok(Math.abs(t.balanceLinear - 0.25) < 1e-9, `balanceLinear ${t.balanceLinear}`);
  }
  // `balance` (display value), by contrast, DOES vary with the exponent.
  assert.ok(Math.abs(p1!.balance - 0.25) < 1e-9);
  assert.ok(p2!.balance < p1!.balance);
  assert.ok(p3!.balance < p2!.balance);
});

test("balanceLinear is 0.5 at the midpoint", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.ok(Math.abs(t!.balanceLinear - 0.5) < 1e-9);
});

// ── computeFallbackVelocity (Area 5/NEW-1) — contract tests, not accuracy tests ──

test("computeFallbackVelocity returns zero with no previous sample (first tick, never a spike)", () => {
  const r = computeFallbackVelocity(null, { x: 5, z: 5 }, 1000);
  assert.equal(r.vx, 0);
  assert.equal(r.vz, 0);
  assert.equal(r.speed, 0);
});

test("computeFallbackVelocity is linear in displacement for a fixed dt (no hidden multiplier)", () => {
  const prev = { x: 0, z: 0, atMs: 1000 };
  const dtMs = 50;
  const a = computeFallbackVelocity(prev, { x: 0.1, z: 0 }, 1000 + dtMs);
  const b = computeFallbackVelocity(prev, { x: 0.2, z: 0 }, 1000 + dtMs);
  // Doubling displacement over the same dt must exactly double velocity —
  // this fails against any position-dependent multiplier (e.g. the 1.35x
  // endpoint boost that must NEVER leak into this unrelated fallback path).
  assert.ok(Math.abs(b.vx - 2 * a.vx) < 1e-9, `a.vx=${a.vx} b.vx=${b.vx}`);
});

test("computeFallbackVelocity does not hardcode a 50ms tick — the same displacement over a longer real dt yields a smaller velocity", () => {
  const prev = { x: 0, z: 0, atMs: 1000 };
  const fast = computeFallbackVelocity(prev, { x: 0.1, z: 0 }, 1000 + 50); // 50ms
  const slow = computeFallbackVelocity(prev, { x: 0.1, z: 0 }, 1000 + 200); // 200ms
  assert.ok(slow.vx < fast.vx, `fast.vx=${fast.vx} slow.vx=${slow.vx}`);
  // The old bug (targetVx = dx * 20) is exactly "assume dt=50ms always" —
  // confirm the 50ms case matches dx/dt algebra, not a fixed dx*20 constant.
  assert.ok(Math.abs(fast.vx - 0.1 / 0.05) < 1e-9, `fast.vx=${fast.vx}`);
});

test("computeFallbackVelocity floors dt so a near-zero interval cannot blow up velocity", () => {
  const prev = { x: 0, z: 0, atMs: 1000 };
  const r = computeFallbackVelocity(prev, { x: 0.05, z: 0 }, 1000 + 1); // 1ms real gap
  assert.ok(Number.isFinite(r.vx));
  // Floored to FALLBACK_VELOCITY_MIN_DT_S (0.02s), not the true 0.001s gap.
  assert.ok(Math.abs(r.vx - 0.05 / 0.02) < 1e-6, `vx=${r.vx}`);
});

test("computeFallbackVelocity yields zero (never a spike) across a gap beyond the max threshold", () => {
  const prev = { x: 0, z: 0, atMs: 1000 };
  const gapMs = (FALLBACK_VELOCITY_MAX_GAP_S + 0.1) * 1000;
  // A 1.6m displacement across a 2s gap would be 0.8 m/s if naively diffed —
  // this must report zero instead, matching NEW-1's corrected-fix rationale.
  const r = computeFallbackVelocity(prev, { x: 1.6, z: 0 }, 1000 + gapMs);
  assert.equal(r.vx, 0);
  assert.equal(r.vz, 0);
  assert.equal(r.speed, 0);
});

test("computeFallbackVelocity: invalidating prev (null) after a primary-tracker hit yields zero on the next fallback tick, not a diff across the skipped interval", () => {
  // Simulates: a fallback sample at t=1000 (seeds prev), then a primary-hit
  // tick 100ms later — WITHIN the max-gap window, so without invalidation
  // the fallback path would happily diff across it and report real motion.
  // Per NEW-1's 5th reset condition, a primary-tracker success must
  // invalidate prev (pass null) so the *next* primary-miss tick starts fresh.
  const seeded = { x: 0, z: 0, atMs: 1000 };
  const shortGapMs = 100;
  const raw = { x: 3, z: 0 };

  const withoutInvalidation = computeFallbackVelocity(seeded, raw, 1000 + shortGapMs);
  assert.ok(withoutInvalidation.speed > 1, `expected a real spike without invalidation, got ${withoutInvalidation.speed}`);

  const afterPrimaryHitInvalidation: typeof seeded | null = null; // caller invalidated on the primary-hit tick
  const withInvalidation = computeFallbackVelocity(afterPrimaryHitInvalidation, raw, 1000 + shortGapMs);
  assert.equal(withInvalidation.vx, 0, "must not diff the 3m displacement across the primary-tracked gap");
  assert.equal(withInvalidation.speed, 0);
});

// ── computeGainNormalizedPerturbation (PS-BEHTEST-004 / ADR-056) ──────────────

test("computeGainNormalizedPerturbation cancels a per-node multiplicative gain", () => {
  const absStd = 5;
  const mean = 15;
  const base = computeGainNormalizedPerturbation(absStd, mean);
  for (const gain of [2.0, 0.5, 3.7]) {
    const scaled = computeGainNormalizedPerturbation(absStd * gain, mean * gain);
    assert.ok(Math.abs(scaled - base) < 1e-9, `gain=${gain}: base=${base} scaled=${scaled}`);
  }
});

test("computeGainNormalizedPerturbation returns 0 for a silent node without dividing by zero", () => {
  const r = computeGainNormalizedPerturbation(0, 0);
  assert.equal(r, 0);
  assert.ok(Number.isFinite(r));
});

test("computeGainNormalizedPerturbation guards a non-finite or non-positive mean defensively", () => {
  assert.ok(Number.isFinite(computeGainNormalizedPerturbation(5, NaN)));
  assert.ok(Number.isFinite(computeGainNormalizedPerturbation(5, -1)));
  assert.ok(Number.isFinite(computeGainNormalizedPerturbation(5, 0)));
  // Falls back to divisor 1.0, so absStd passes through unchanged.
  assert.equal(computeGainNormalizedPerturbation(5, NaN), 5);
});

test("FIXED (PS-BEHTEST-004): gain-normalizing r1/r2 restores balance ~= 0.5 under a 2x per-node gain asymmetry with identical real motion", () => {
  // Same synthetic scenario as tests/behavioral/fusion-invariants.test.ts's
  // FINDING test, but run through the REAL fixed composition production now
  // uses (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation ->
  // fuseTwoNodeTarget) instead of feeding raw absStd directly.
  const base = [
    [10, 12, 9, 11],
    [11, 9, 12, 10],
    [9, 11, 10, 12],
    [12, 10, 11, 9],
  ];
  const gain = 2.0;
  const scaled = base.map((frame) => frame.map((v) => v * gain));

  const m1 = computeNodeMotionFromMatrix(base);
  const m2 = computeNodeMotionFromMatrix(scaled);

  const t = fuseTwoNodeTarget({
    r1: computeGainNormalizedPerturbation(m1.absStd, m1.mean),
    r2: computeGainNormalizedPerturbation(m2.absStd, m2.mean),
    motion1: 1,
    motion2: 1,
    motionThreshold: 0.12,
    anchors: ANCHORS,
  });
  assert.ok(t);
  assert.ok(Math.abs(t!.balance - 0.5) < 0.02, `expected balance near 0.5 (gain-invariant), got ${t!.balance}`);
});

test("a COMMON gain applied equally to both nodes leaves balance unchanged (the bug was only the differential mismatch)", () => {
  const m1Frames = [
    [10, 12, 9, 11],
    [11, 9, 12, 10],
  ];
  const m2Frames = [
    [20, 15, 25, 18],
    [22, 14, 24, 19],
  ];
  const commonGain = 3.0;

  const balanceFor = (gain: number) => {
    const m1 = computeNodeMotionFromMatrix(m1Frames.map((f) => f.map((v) => v * gain)));
    const m2 = computeNodeMotionFromMatrix(m2Frames.map((f) => f.map((v) => v * gain)));
    const t = fuseTwoNodeTarget({
      r1: computeGainNormalizedPerturbation(m1.absStd, m1.mean),
      r2: computeGainNormalizedPerturbation(m2.absStd, m2.mean),
      motion1: 1,
      motion2: 1,
      motionThreshold: 0.12,
      anchors: ANCHORS,
    });
    assert.ok(t);
    return t!.balance;
  };

  const balanceAt1x = balanceFor(1);
  const balanceAtCommonGain = balanceFor(commonGain);
  assert.ok(
    Math.abs(balanceAt1x - balanceAtCommonGain) < 1e-9,
    `balanceAt1x=${balanceAt1x} balanceAtCommonGain=${balanceAtCommonGain}`,
  );
});

// ── hasSingleNodePresenceEvidence (ADR-057, empty-room ghost target) ──────────

test("hasSingleNodePresenceEvidence: no motion and no tracked cluster => no presence (empty room)", () => {
  assert.equal(hasSingleNodePresenceEvidence(false, false), false);
});

test("hasSingleNodePresenceEvidence: real motion alone is sufficient evidence", () => {
  assert.equal(hasSingleNodePresenceEvidence(true, false), true);
});

test("hasSingleNodePresenceEvidence: a tracked cluster alone is sufficient evidence (covers a real-but-stationary target)", () => {
  assert.equal(hasSingleNodePresenceEvidence(false, true), true);
});

test("hasSingleNodePresenceEvidence: both signals present is still presence", () => {
  assert.equal(hasSingleNodePresenceEvidence(true, true), true);
});

// ── Item 1: classifier corroboration gate ──────────────────────────────────
// MicroDopplerClassifier (server/lib/signal-processing.ts) is deterministic
// DFT+autocorrelation DSP, not an ML/AI model — these tests confirm it acts
// as a CORROBORATING signal only (can suppress, never assert presence alone)
// and does not touch the advisory-only AI firewall (F1/PS-AUDIT-014), which
// is a completely separate mechanism gating scripts/ai_inference.py output.

const HUMAN: ClassifierGateInput = { label: "human", humanProb: 0.9 };
const CONFIDENT_MECHANICAL: ClassifierGateInput = { label: "mechanical", humanProb: 0.05 };
const BORDERLINE_MECHANICAL: ClassifierGateInput = { label: "mechanical", humanProb: 0.34 };
const UNKNOWN: ClassifierGateInput = { label: "unknown", humanProb: 0.5 };

test("evaluateClassifierCorroboration: no classifier supplied => not_evaluated, never suppresses", () => {
  const r = evaluateClassifierCorroboration(undefined);
  assert.equal(r.suppress, false);
  assert.equal(r.corroboration, "not_evaluated");
});

test("evaluateClassifierCorroboration: confident 'human' => confirmed, never suppresses", () => {
  const r = evaluateClassifierCorroboration(HUMAN);
  assert.equal(r.suppress, false);
  assert.equal(r.corroboration, "confirmed");
});

test("evaluateClassifierCorroboration: confident 'mechanical' (humanProb <= threshold) => contradicted, suppresses", () => {
  const r = evaluateClassifierCorroboration(CONFIDENT_MECHANICAL);
  assert.equal(r.suppress, true);
  assert.equal(r.corroboration, "contradicted");
});

test("evaluateClassifierCorroboration: borderline 'mechanical' (above the confident-reject bar) => inconclusive, does NOT suppress", () => {
  // humanProb 0.34 is below MicroDopplerClassifier's own 0.35 "mechanical"
  // label boundary but above DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX (0.2) —
  // must not become stricter than the energy-gate-only baseline for a merely
  // borderline call.
  assert.ok(BORDERLINE_MECHANICAL.humanProb > DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX);
  const r = evaluateClassifierCorroboration(BORDERLINE_MECHANICAL);
  assert.equal(r.suppress, false);
  assert.equal(r.corroboration, "inconclusive");
});

test("evaluateClassifierCorroboration: 'unknown' => inconclusive, does NOT suppress", () => {
  const r = evaluateClassifierCorroboration(UNKNOWN);
  assert.equal(r.suppress, false);
  assert.equal(r.corroboration, "inconclusive");
});

// (a) energy gate passes + classifier says "human" => presence confirmed
test("fuseTwoNodeTarget (a): energy gate passes + classifier 'human' => target present, corroboration confirmed", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: HUMAN });
  assert.ok(t, "target must be present");
  assert.equal(t!.classifierCorroboration, "confirmed");
});

// (b) energy gate passes + classifier confidently says "mechanical" => suppressed
test("fuseTwoNodeTarget (b): energy gate passes + confident 'mechanical' classifier => presence suppressed (null)", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: CONFIDENT_MECHANICAL });
  assert.equal(t, null, "confident mechanical classification must suppress an otherwise-passing energy gate");
});

// (c) energy gate passes + classifier "unknown"/low-confidence => falls back to energy-gate-only baseline
test("fuseTwoNodeTarget (c): energy gate passes + 'unknown' classifier => target still present (not stricter than baseline)", () => {
  const withClassifier = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: UNKNOWN });
  const withoutClassifier = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(withClassifier, "ambiguous classifier output must not suppress presence");
  assert.ok(withoutClassifier);
  assert.equal(withClassifier!.classifierCorroboration, "inconclusive");
  // Ambiguous classifier evidence must not change the position/balance math either.
  assert.equal(withClassifier!.balance, withoutClassifier!.balance);
});

test("fuseTwoNodeTarget (c): borderline 'mechanical' (not confidently rejected) also falls back to baseline", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: BORDERLINE_MECHANICAL });
  assert.ok(t, "borderline mechanical call must not suppress presence");
  assert.equal(t!.classifierCorroboration, "inconclusive");
});

// (d) energy gate fails => no target regardless of classifier output (empty-room invariant)
test("fuseTwoNodeTarget (d): energy gate fails => no target even with a confident 'human' classification", () => {
  const t = fuseTwoNodeTarget({
    r1: 0.001,
    r2: 0.001,
    motion1: 0.01,
    motion2: 0.01,
    anchors: ANCHORS,
    motionThreshold: 0.12,
    classifier: HUMAN,
  });
  assert.equal(t, null, "empty-room gate must hold regardless of classifier output");
});

test("fuseTwoNodeTarget: no classifier supplied at all => behavior is byte-for-byte the pre-Item-1 baseline", () => {
  const t = fuseTwoNodeTarget({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING });
  assert.ok(t);
  assert.equal(t!.classifierCorroboration, "not_evaluated");
});

test("wasSuppressedByClassifier: true only when energy gate passed AND classifier confidently vetoed", () => {
  assert.equal(
    wasSuppressedByClassifier({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: CONFIDENT_MECHANICAL }),
    true,
  );
  // Energy gate never fired — must not be reported as classifier-vetoed even
  // though the classifier also says "mechanical" (avoids a misleading log).
  assert.equal(
    wasSuppressedByClassifier({
      r1: 0.001,
      r2: 0.001,
      motion1: 0.01,
      motion2: 0.01,
      anchors: ANCHORS,
      motionThreshold: 0.12,
      classifier: CONFIDENT_MECHANICAL,
    }),
    false,
  );
  // Energy gate passed, classifier didn't confidently veto.
  assert.equal(
    wasSuppressedByClassifier({ r1: 10, r2: 10, anchors: ANCHORS, ...MOVING, classifier: HUMAN }),
    false,
  );
});

// Same (a)-(d) matrix for the single-node gate.
test("hasSingleNodePresenceEvidence (a): energy evidence + 'human' classifier => presence", () => {
  assert.equal(hasSingleNodePresenceEvidence(true, false, HUMAN), true);
});

test("hasSingleNodePresenceEvidence (b): energy evidence + confident 'mechanical' classifier => suppressed", () => {
  assert.equal(hasSingleNodePresenceEvidence(true, false, CONFIDENT_MECHANICAL), false);
  assert.equal(hasSingleNodePresenceEvidence(false, true, CONFIDENT_MECHANICAL), false);
});

test("hasSingleNodePresenceEvidence (c): energy evidence + 'unknown' classifier => falls back to baseline (still present)", () => {
  assert.equal(hasSingleNodePresenceEvidence(true, false, UNKNOWN), true);
});

test("hasSingleNodePresenceEvidence (d): no energy evidence => no presence even with a confident 'human' classifier", () => {
  assert.equal(hasSingleNodePresenceEvidence(false, false, HUMAN), false);
});

test("hasSingleNodePresenceEvidence: omitting classifier entirely is unchanged from the pre-Item-1 signature", () => {
  // Existing 2-arg call sites (and this repo's existing tests above) must
  // keep behaving identically — classifier is opt-in, not opt-out.
  assert.equal(hasSingleNodePresenceEvidence(true, false), true);
  assert.equal(hasSingleNodePresenceEvidence(false, false), false);
});

// ── AGC-normalized perturbation (RuView ADR-345 link-motion metric) ─────────

function frames(rows: number[][]): number[][] {
  return rows.map((r) => [...r]);
}

test("computeAgcNormalizedPerturbation: a static pattern under per-frame gain swings reads as ~no motion", () => {
  const pattern = [10, 14, 8, 12, 9, 11];
  const gains = [1, 1.3, 0.8, 1.15, 0.9, 1.25, 0.85, 1.1];
  const agcOnly = gains.map((g) => pattern.map((a) => a * g));
  const r = computeAgcNormalizedPerturbation(frames(agcOnly));
  assert.ok(r < 1e-12, `pure AGC/gain fluctuation must not read as motion, got ${r}`);
  // The old gain-normalized metric DOES read the same frames as motion.
  const old = computeNodeMotionFromMatrix(frames(agcOnly));
  assert.ok(computeGainNormalizedPerturbation(old.absStd, old.mean) > 0.05);
});

test("computeAgcNormalizedPerturbation: a changing multipath shape reads as motion and is gain-invariant", () => {
  const moving = [
    [10, 14, 8, 12],
    [12, 10, 11, 9],
    [8, 15, 9, 13],
    [13, 9, 12, 8],
  ];
  const base = computeAgcNormalizedPerturbation(frames(moving));
  const scaled = computeAgcNormalizedPerturbation(frames(moving.map((f) => f.map((a) => a * 4))));
  assert.ok(base > 0.05, `shape change must read as motion, got ${base}`);
  assert.ok(Math.abs(base - scaled) < 1e-12, "a constant node gain must cancel exactly");
});

test("computeAgcNormalizedPerturbation: degenerate input returns 0", () => {
  assert.equal(computeAgcNormalizedPerturbation([]), 0);
  assert.equal(computeAgcNormalizedPerturbation([[1, 2, 3]]), 0);
  assert.equal(computeAgcNormalizedPerturbation([[0, 0], [0, 0]]), 0);
});

// ── Per-node radial trends for fused_room ───────────────────────────────────

test("computeRadialTrends: walking toward node 3 approaches 3 and recedes from 1", () => {
  const trends = computeRadialTrends({ x: 0, z: 0 }, { vx: 0.4, vz: 0.6 }, ROOM_ANCHORS);
  assert.equal(trends[3], "approaching");
  assert.equal(trends[1], "receding");
});

test("computeRadialTrends: speed inside the deadband is stable for every node", () => {
  const trends = computeRadialTrends({ x: 0.5, z: -1 }, { vx: 0.01, vz: -0.02 }, ROOM_ANCHORS);
  for (const id of [1, 2, 3, 4]) assert.equal(trends[id], "stable");
});

// ── Position uncertainty (display radius for the fused_room centroid) ───────

test("computePositionUncertaintyM shrinks with stronger evidence and grows when one node dominates", () => {
  const spread = { 1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25 };
  const dominated = { 1: 0.85, 2: 0.05, 3: 0.05, 4: 0.05 };
  const weak = computePositionUncertaintyM(spread, 0.1, 4);
  const strong = computePositionUncertaintyM(spread, 1.0, 4);
  const snapped = computePositionUncertaintyM(dominated, 1.0, 4);
  assert.ok(strong < weak, `strong ${strong} should be < weak ${weak}`);
  assert.ok(snapped > strong, `one dominant node (${snapped}) is less trustworthy than a spread (${strong})`);
});

test("computePositionUncertaintyM is bounded by the room size and never below a floor", () => {
  const lo = computePositionUncertaintyM({ 1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25 }, 5, 4);
  const hi = computePositionUncertaintyM({ 1: 1 }, 0, 4);
  assert.ok(lo >= 0.3, `floor, got ${lo}`);
  assert.ok(hi <= 0.6 * 4 + 1e-9, `cap, got ${hi}`);
  assert.ok(Number.isFinite(computePositionUncertaintyM({}, Number.NaN, 0)));
});
