import test from "node:test";
import assert from "node:assert/strict";
import {
  DBSCAN,
  KalmanFilter,
  TrackingProcessor,
  calibrateEnergyThreshold,
  DEFAULT_SPATIAL_ENERGY_THRESHOLD,
} from "./tracking";
import type { PointCloudPoint } from "@shared/schema";

// ── calibrateEnergyThreshold (Item 4) ──────────────────────────────────────
// Same mean+k*sigma statistical method as scripts/calibrate-threshold.ts's
// motion-gate calibration; here applied to a pure array of synthetic
// empty-room energy samples (no live UDP capture — that's the real,
// hardware-gated calibration run, tracked as [TO BE MEASURED]).

test("calibrateEnergyThreshold: empty input returns a neutral zero result, not a crash", () => {
  const r = calibrateEnergyThreshold([]);
  assert.equal(r.sampleCount, 0);
  assert.equal(r.mean, 0);
  assert.equal(r.sigma, 0);
  assert.equal(r.suggestedThreshold, 0);
});

test("calibrateEnergyThreshold: constant samples => zero sigma, threshold equals the constant", () => {
  const r = calibrateEnergyThreshold([5, 5, 5, 5, 5]);
  assert.equal(r.mean, 5);
  assert.equal(r.sigma, 0);
  assert.equal(r.suggestedThreshold, 5);
});

test("calibrateEnergyThreshold: known mean/sigma from a hand-computable sample set", () => {
  // Samples: 1,2,3,4,5 -> mean=3, population variance=2, sigma=sqrt(2).
  const r = calibrateEnergyThreshold([1, 2, 3, 4, 5], 3);
  assert.equal(r.sampleCount, 5);
  assert.ok(Math.abs(r.mean - 3) < 1e-9);
  assert.ok(Math.abs(r.sigma - Math.sqrt(2)) < 1e-9, `sigma ${r.sigma}`);
  assert.ok(Math.abs(r.suggestedThreshold - (3 + 3 * Math.sqrt(2))) < 1e-9);
});

test("calibrateEnergyThreshold: a higher kSigma produces a strictly higher (more conservative) threshold", () => {
  const samples = [2, 3, 4, 3, 2, 5, 3];
  const loose = calibrateEnergyThreshold(samples, 2);
  const strict = calibrateEnergyThreshold(samples, 4);
  assert.ok(strict.suggestedThreshold > loose.suggestedThreshold);
});

test("calibrateEnergyThreshold: non-finite samples are dropped, not propagated as NaN", () => {
  const r = calibrateEnergyThreshold([1, 2, NaN, 3, Infinity, -Infinity, 4]);
  assert.equal(r.sampleCount, 4);
  assert.ok(Number.isFinite(r.mean));
  assert.ok(Number.isFinite(r.suggestedThreshold));
});

// ── TrackingProcessor: default-threshold regression (Item 4) ──────────────
// The energyThreshold is now configurable, but the DEFAULT must remain
// byte-for-byte the old hardcoded `10` until a real calibration run
// replaces it — this is the "no behavior change without a real calibration
// run" requirement.

test("DEFAULT_SPATIAL_ENERGY_THRESHOLD is unchanged from the pre-Item-4 hardcoded literal (10)", () => {
  // Only true when PHANTOM_SPATIAL_ENERGY_THRESHOLD is unset, exactly like
  // production until an operator explicitly opts into a calibrated value.
  if (!process.env.PHANTOM_SPATIAL_ENERGY_THRESHOLD) {
    assert.equal(DEFAULT_SPATIAL_ENERGY_THRESHOLD, 10);
  }
});

function densePointsAt(x: number, z: number, amplitude: number, count = 5): PointCloudPoint[] {
  // Tightly packed so they fall within DBSCAN's eps=0.8m and clear minPts=4.
  const pts: PointCloudPoint[] = [];
  for (let i = 0; i < count; i++) {
    pts.push({ x: x + i * 0.01, y: 0, z: z + i * 0.01, amplitude, timestamp: Date.now() });
  }
  return pts;
}

test("TrackingProcessor (default threshold): a dense cluster with total amplitude just above 10 is accepted", () => {
  const tp = new TrackingProcessor(); // default = DEFAULT_SPATIAL_ENERGY_THRESHOLD (10)
  // 5 points * amplitude 2.1 = 10.5 total energy > 10.
  const target = tp.process(densePointsAt(1, 1, 2.1));
  assert.ok(target, "cluster energy 10.5 must clear the default threshold of 10");
});

test("TrackingProcessor (default threshold): a dense cluster with total amplitude just below 10 is rejected", () => {
  const tp = new TrackingProcessor();
  // 5 points * amplitude 1.9 = 9.5 total energy < 10.
  const target = tp.process(densePointsAt(1, 1, 1.9));
  assert.equal(target, null, "cluster energy 9.5 must NOT clear the default threshold of 10");
});

test("TrackingProcessor: a custom (calibrated) energyThreshold changes the accept/reject boundary", () => {
  // Same 9.5-energy cluster that the default threshold rejects...
  const strict = new TrackingProcessor(10);
  assert.equal(strict.process(densePointsAt(1, 1, 1.9)), null);

  // ...is accepted once a calibration lowers the threshold below 9.5.
  const calibrated = new TrackingProcessor(5);
  assert.ok(calibrated.process(densePointsAt(1, 1, 1.9)));
});

test("TrackingProcessor: empty point cloud never produces a target (empty-room invariant)", () => {
  const tp = new TrackingProcessor();
  assert.equal(tp.process([]), null);
});

// PS-GAP-TRK-001 regression (found by this test file during Item 4/5 work):
// before the fix, a cold start with only sub-threshold noise clusters
// returned a fabricated target at the Kalman origin (confidence 0.9) for up
// to 10 ticks — the exact `hasTrackedTarget` evidence ADR-057's single-node
// presence gate trusts. Coasting must require a prior real acquisition.
// NOTE on buffer semantics: TrackingProcessor.pointBuffer ACCUMULATES the
// last 50 points across process() calls, so per-tick energies add up within
// a persistent cluster. The tests below pick amplitudes so the accumulated
// 50-point ceiling stays below (or above) the threshold as intended.
test("TrackingProcessor (PS-GAP-TRK-001): sub-threshold noise on a cold start never returns a coasted ghost target", () => {
  const tp = new TrackingProcessor();
  // 5 pts/tick at amplitude 0.15: even at the full 50-point buffer ceiling
  // the cluster's total energy is 50 * 0.15 = 7.5 < 10 — never acquirable.
  for (let tick = 0; tick < 12; tick++) {
    const result = tp.process(densePointsAt(1, 1, 0.15));
    assert.equal(result, null, `tick ${tick}: no target was ever acquired, so nothing may coast`);
  }
});

function scatteredNoise(count: number): PointCloudPoint[] {
  // Far-apart isolated points: no DBSCAN cluster can form (each has no
  // neighbor within eps), so pushing 50 of them flushes the buffer and
  // forces a genuine miss tick.
  const pts: PointCloudPoint[] = [];
  for (let i = 0; i < count; i++) {
    pts.push({ x: i * 17, y: 0, z: -i * 13, amplitude: 0.01, timestamp: Date.now() });
  }
  return pts;
}

test("TrackingProcessor (PS-GAP-TRK-001): coasting through misses still works AFTER a real acquisition", () => {
  const tp = new TrackingProcessor();
  // Real acquisition first (5 * 2.1 = 10.5 energy > 10).
  assert.ok(tp.process(densePointsAt(1, 1, 2.1)), "initial acquisition must succeed");
  // Force a true miss: flood the 50-point buffer with unclusterable noise.
  const coasted = tp.process(scatteredNoise(50));
  assert.ok(coasted, "a previously-acquired target must survive a brief miss (~0.5s coast window)");
  // Confidence must degrade on the miss, reflecting reduced certainty.
  assert.ok(coasted!.confidence < 1.0, `confidence ${coasted!.confidence} must drop below 1 on a miss`);
});

// ── DBSCAN (Item 5) ─────────────────────────────────────────────────────────

test("DBSCAN: two well-separated dense groups form two clusters", () => {
  const dbscan = new DBSCAN(0.5, 3);
  const groupA = densePointsAt(0, 0, 1, 4);
  const groupB = densePointsAt(10, 10, 1, 4); // far outside eps of group A
  const clusters = dbscan.cluster([...groupA, ...groupB]);
  assert.equal(clusters.length, 2, `expected 2 clusters, got ${clusters.length}`);
  const sizes = clusters.map((c) => c.length).sort((a, b) => a - b);
  assert.deepEqual(sizes, [4, 4]);
});

test("DBSCAN: points below minPts density are noise (no cluster produced)", () => {
  const dbscan = new DBSCAN(0.5, 5); // requires 5 neighbors, only 3 points given
  const clusters = dbscan.cluster(densePointsAt(0, 0, 1, 3));
  assert.equal(clusters.length, 0);
});

test("DBSCAN: points farther apart than eps do not merge into one cluster", () => {
  const dbscan = new DBSCAN(0.3, 2);
  const scattered: PointCloudPoint[] = [
    { x: 0, y: 0, z: 0, amplitude: 1, timestamp: 0 },
    { x: 5, y: 0, z: 0, amplitude: 1, timestamp: 0 },
    { x: 10, y: 0, z: 0, amplitude: 1, timestamp: 0 },
  ];
  const clusters = dbscan.cluster(scattered);
  assert.equal(clusters.length, 0, "each point is isolated (no neighbor within eps) so none reach minPts");
});

test("DBSCAN: a chain of points within eps of their immediate neighbor forms one connected cluster", () => {
  const dbscan = new DBSCAN(0.5, 2);
  // Each point 0.3m from the next — within eps of its neighbors, forming a
  // density-connected chain even though the endpoints are 1.2m apart.
  const chain: PointCloudPoint[] = [0, 1, 2, 3, 4].map((i) => ({
    x: i * 0.3,
    y: 0,
    z: 0,
    amplitude: 1,
    timestamp: 0,
  }));
  const clusters = dbscan.cluster(chain);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].length, 5);
});

// ── KalmanFilter (Item 5) ────────────────────────────────────────────────────

test("KalmanFilter: repeated measurement at a fixed point converges the state near that point", () => {
  const kf = new KalmanFilter();
  for (let i = 0; i < 50; i++) {
    kf.predict();
    kf.update([2, 0, 3]);
  }
  const state = kf.getState();
  assert.ok(Math.abs(state.x - 2) < 0.2, `x ${state.x} should converge near 2`);
  assert.ok(Math.abs(state.z - 3) < 0.2, `z ${state.z} should converge near 3`);
});

test("KalmanFilter: starts at the origin with zero velocity before any update", () => {
  const kf = new KalmanFilter();
  const state = kf.getState();
  assert.deepEqual(state, { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0 });
});

test("KalmanFilter: velocity is clamped to the human sprint limit (10 m/s) even under an extreme single-tick jump", () => {
  const kf = new KalmanFilter();
  kf.predict();
  kf.update([0, 0, 0]);
  // An absurd 1000m jump in one update must not produce an absurd velocity.
  kf.predict();
  kf.update([1000, 0, 0]);
  const state = kf.getState();
  assert.ok(state.vx <= 10.0001, `vx ${state.vx} must be clamped to <= 10 m/s`);
  assert.ok(state.vx >= -10.0001);
});

test("KalmanFilter: getState always returns finite numbers (no NaN/Infinity propagation)", () => {
  const kf = new KalmanFilter();
  for (let i = 0; i < 10; i++) {
    kf.predict();
    kf.update([i * 0.1, 0, 0]);
  }
  const state = kf.getState();
  for (const v of Object.values(state)) {
    assert.ok(Number.isFinite(v), `state value ${v} must be finite`);
  }
});
