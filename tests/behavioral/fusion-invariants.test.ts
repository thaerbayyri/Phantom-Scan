import test from "node:test";
import assert from "node:assert/strict";
import {
  fuseTwoNodeTarget,
  computeNodeMotionFromMatrix,
  computeGainNormalizedPerturbation,
} from "../../server/lib/node-fusion";

/**
 * B3 — fusion/localization behavior gaps not already covered by
 * server/lib/node-fusion.test.ts's 20+ existing tests (midpoint, endpoints,
 * display bias, empty-room gate, matrix motion, trends/hysteresis, contrast
 * exponent, saturation — all verified present before writing this file).
 * This file covers two specific gaps: (1) whether a purely multiplicative
 * per-node gain asymmetry (no real motion difference) biases `balance` away
 * from 0.5, and (2) a direct hit on the r1^p+r2^p<=EPS fallback branch that
 * the existing zero-perturbation test doesn't reach (it's gated off by the
 * `present` check before division happens).
 *
 * UPDATE (ADR-056): gap (1)'s finding, PS-BEHTEST-004, is now FIXED upstream
 * — server/lib/websocket.ts's computeFusedTarget() gain-normalizes r1/r2 via
 * computeGainNormalizedPerturbation() before calling fuseTwoNodeTarget, so
 * production no longer feeds it raw absStd. The FINDING test below is kept,
 * renamed, and its assertions are UNCHANGED — it still correctly documents
 * that fuseTwoNodeTarget's own math drifts under gain asymmetry IF fed raw
 * absStd directly (by design: the fix lives entirely in the caller, not in
 * fuseTwoNodeTarget's contract). Its sibling immediately below proves the
 * real production composition is gain-invariant.
 */

const ANCHORS = { 1: { x: -1.5, z: 0 }, 2: { x: 1.5, z: 0 } } as const;

test("[HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (production no longer does this)", () => {
  // Both nodes see the IDENTICAL relative perturbation pattern (same
  // physical motion depth) — node 2's raw amplitude is just uniformly
  // scaled by a constant gain factor (proxy for antenna/RSSI hardware
  // mismatch between boards 29052/44260), not a difference in the target's
  // actual proximity or motion.
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

  // computeNodeMotionFromMatrix's own `motion` (display) field IS
  // gain-normalized (absStd/base), so it correctly reports equal relative
  // perturbation for both nodes:
  assert.ok(Math.abs(m1.motion - m2.motion) < 1e-9, "normalized `motion` should be gain-invariant");

  // But `absStd` (the RAW value fuseTwoNodeTarget's balance ratio actually
  // uses as r1/r2) is NOT gain-normalized, and scales linearly with the
  // gain factor:
  assert.ok(Math.abs(m2.absStd / m1.absStd - gain) < 1e-6, "absStd should scale linearly with the applied gain");

  const t = fuseTwoNodeTarget({
    r1: m1.absStd,
    r2: m2.absStd,
    motion1: 1,
    motion2: 1,
    motionThreshold: 0.12,
    anchors: ANCHORS,
  });
  assert.ok(t);
  // If balance were gain-invariant (as intended for "equal real motion"),
  // it would stay at ~0.5. It does not — this is the finding: a 2x
  // node-to-node gain mismatch with EQUAL real motion depth pulls the
  // reported position measurably toward the higher-gain node.
  assert.ok(Math.abs(t!.balance - 0.5) > 0.1, `expected balance to drift from 0.5 under gain asymmetry, got ${t!.balance}`);
});

test("FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invariant for the exact same scenario above", () => {
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
  assert.ok(
    Math.abs(t!.balance - 0.5) < 0.02,
    `expected balance to stay near 0.5 once production normalizes by each node's own gain, got ${t!.balance}`,
  );
});

test("fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows", () => {
  // r1+r2 = 2e-4, comfortably above the `present` gate's EPS=1e-6 threshold.
  // But with the default contrast exponent p=2, r1^2+r2^2 = 2e-8, which is
  // BELOW EPS — a narrow path the existing "zero perturbation returns NO
  // target" test never reaches, since that test uses r1=r2=0 and never gets
  // past the `present` gate at all.
  const t = fuseTwoNodeTarget({
    r1: 1e-4,
    r2: 1e-4,
    motion1: 1, // clears the default 0.12 threshold, so `present` is true
    motion2: 0,
    motionThreshold: 0.12,
    anchors: ANCHORS,
  });
  assert.ok(t, "present gate should pass (r1+r2 > EPS and motion1 clears threshold)");
  assert.equal(t!.balance, 0.5, "contrast-sum underflow must fall back to the midpoint, not NaN/divide-by-zero");
  assert.ok(Number.isFinite(t!.x) && Number.isFinite(t!.z), "x/z must stay finite through the fallback");
});
