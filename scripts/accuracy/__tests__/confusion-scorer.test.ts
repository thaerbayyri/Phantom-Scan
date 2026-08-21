import test from "node:test";
import assert from "node:assert/strict";
import { buildBins, computeConfusion, computeDerivedMetrics } from "../confusion-scorer";
import type { SystemSample, SystemStateKind } from "../system-state-adapter";
import { isHumanVerdict } from "../system-state-adapter";
import type { GroundTruthLog, GroundTruthRow } from "../ground-truth-adapter";
import { resolveAlignment } from "../time-aligner";

const IDENTITY_ALIGNMENT = resolveAlignment([{ groundTruthMs: 0, systemMs: 0 }]);

function gtLog(rows: GroundTruthRow[]): GroundTruthLog {
  return { rows, syncMarkerMs: null };
}

function sample(sessionTsMs: number, state: SystemStateKind): SystemSample {
  return {
    sessionTsMs,
    state,
    isHumanVerdict: isHumanVerdict(state),
    targetVisible: state !== "none",
    nodeMode: "fused_two_node",
    node1Fps: 25,
    node2Fps: 25,
  };
}

test("A1 — synthetic perfect match: matched present+absent regions score recall=1, FPR=0, F1=1", () => {
  const groundTruth = gtLog([{ tStartMs: 0, tEndMs: 5_000, label: "present", subjectId: "s1" }]);
  const samples: SystemSample[] = [];
  for (let t = 0; t < 5_000; t += 200) samples.push(sample(t, "moving"));
  for (let t = 5_000; t < 10_000; t += 200) samples.push(sample(t, "none"));

  const bins = buildBins(samples, groundTruth, IDENTITY_ALIGNMENT, 0, 10_000);
  const counts = computeConfusion(bins);
  const metrics = computeDerivedMetrics(bins, counts);

  assert.equal(counts.fp, 0);
  assert.equal(counts.fn, 0);
  assert.equal(metrics.recall.status, "MEASURED");
  assert.equal(metrics.recall.value, 1);
  assert.equal(metrics.falsePositiveRateFraction.status, "MEASURED");
  assert.equal(metrics.falsePositiveRateFraction.value, 0);
  assert.equal(metrics.f1.value, 1);
});

test("A2 — synthetic all-miss: system stays negative throughout a ground-truth-positive interval", () => {
  const groundTruth = gtLog([{ tStartMs: 0, tEndMs: 5_000, label: "present", subjectId: "s1" }]);
  const samples: SystemSample[] = [];
  for (let t = 0; t < 5_000; t += 200) samples.push(sample(t, "none"));

  const bins = buildBins(samples, groundTruth, IDENTITY_ALIGNMENT, 0, 5_000);
  const counts = computeConfusion(bins);
  const metrics = computeDerivedMetrics(bins, counts);

  assert.equal(counts.tp, 0);
  assert.equal(metrics.recall.value, 0);
});

test("A3 — a stale-demotion bin during ground-truth-positive scores FN, not excluded", () => {
  const groundTruth = gtLog([{ tStartMs: 0, tEndMs: 5_000, label: "present", subjectId: "s1" }]);
  const samples: SystemSample[] = [];
  for (let t = 0; t < 3_000; t += 200) samples.push(sample(t, "moving"));
  // 1.5s-3s aged out: system demotes to "stale" per target-state.ts's
  // LIVE_TARGET_STALE_TIMEOUT_MS window, well before the 5s hard-clear.
  for (let t = 3_000; t < 5_000; t += 200) samples.push(sample(t, "stale"));

  const bins = buildBins(samples, groundTruth, IDENTITY_ALIGNMENT, 0, 5_000);
  const counts = computeConfusion(bins);

  // All 5 bins present in the scored set — none excluded for being "stale".
  assert.equal(bins.length, 5);
  const staleBins = bins.filter((b) => b.systemStates.includes("stale"));
  assert.ok(staleBins.length > 0, "expected at least one bin observing the stale state");
  for (const bin of staleBins) {
    assert.equal(bin.groundTruthPositive, true);
    assert.equal(bin.systemPositive, false);
  }
  assert.equal(counts.fn, staleBins.length);
});

test("A6 — a ground-truth log with zero present rows can never produce a TP, by construction", () => {
  const negativeOnlyLog = gtLog([{ tStartMs: 0, tEndMs: 60_000, label: "absent" }]);
  const stateOptions: SystemStateKind[] = ["none", "stale", "idle", "moving", "degraded"];

  for (let trial = 0; trial < 20; trial++) {
    const samples: SystemSample[] = [];
    for (let t = 0; t < 60_000; t += 500) {
      const state = stateOptions[Math.floor(Math.random() * stateOptions.length)];
      samples.push(sample(t, state));
    }
    const bins = buildBins(samples, negativeOnlyLog, IDENTITY_ALIGNMENT, 0, 60_000);
    const counts = computeConfusion(bins);
    assert.equal(counts.tp, 0, `trial ${trial}: TP must be structurally 0 when ground truth has no present rows`);
  }
});
