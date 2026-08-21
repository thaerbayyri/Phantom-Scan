import test from "node:test";
import assert from "node:assert/strict";
import { evaluatePreconditions, buildCampaignReport, buildTrialReport } from "../report-generator";
import { assertMetricValueShape } from "../types";
import { buildBins, computeConfusion, computeDerivedMetrics } from "../confusion-scorer";
import { resolveAlignment } from "../time-aligner";
import type { SystemSample } from "../system-state-adapter";
import { isHumanVerdict } from "../system-state-adapter";
import type { GroundTruthLog } from "../ground-truth-adapter";

const alignment = resolveAlignment([{ groundTruthMs: 0, systemMs: 0 }]);

function baseTrialInputs() {
  const groundTruth: GroundTruthLog = {
    rows: [{ tStartMs: 0, tEndMs: 1_000, label: "present", subjectId: "s1" }],
    syncMarkerMs: 0,
  };
  const samples: SystemSample[] = [
    {
      sessionTsMs: 0,
      state: "moving",
      isHumanVerdict: isHumanVerdict("moving"),
      targetVisible: true,
      nodeMode: "fused_two_node",
      node1Fps: 12,
      node2Fps: 24,
    },
  ];
  const bins = buildBins(samples, groundTruth, alignment, 0, 1_000);
  const counts = computeConfusion(bins);
  const metrics = computeDerivedMetrics(bins, counts);
  return { bins, counts, metrics };
}

test("A5 — a trial with node1 fps below the 20/node preflight is excluded from the campaign rollup with a named reason", () => {
  const { bins, counts, metrics } = baseTrialInputs();

  const failingPreconditions = evaluatePreconditions({
    mode: "replay",
    avgNode1Fps: 12, // below 20
    avgNode2Fps: 24,
    nodeModesSeen: new Set(["fused_two_node"]),
    allowDegraded: false,
    hasSyncMarker: true,
  });
  const failingTrial = buildTrialReport({
    trialId: "low-fps-trial",
    mode: "replay",
    groundTruthPath: "groundtruth/x.csv",
    alignment,
    bins,
    counts,
    metrics,
    thresholdValue: 0.1,
    thresholdSource: "calibration/x.json",
    preconditions: failingPreconditions,
  });
  assert.equal(failingTrial.preconditionsPassed, false);

  const passingPreconditions = evaluatePreconditions({
    mode: "replay",
    avgNode1Fps: 24,
    avgNode2Fps: 24,
    nodeModesSeen: new Set(["fused_two_node"]),
    allowDegraded: false,
    hasSyncMarker: true,
  });
  const passingTrial = buildTrialReport({
    trialId: "good-trial",
    mode: "replay",
    groundTruthPath: "groundtruth/y.csv",
    alignment,
    bins,
    counts,
    metrics,
    thresholdValue: 0.1,
    thresholdSource: "calibration/y.json",
    preconditions: passingPreconditions,
  });
  assert.equal(passingTrial.preconditionsPassed, true);

  const campaign = buildCampaignReport([failingTrial, passingTrial]);
  assert.equal(campaign.trials.length, 1);
  assert.equal(campaign.trials[0].trialId, "good-trial");
  assert.equal(campaign.excludedTrials.length, 1);
  assert.equal(campaign.excludedTrials[0].trialId, "low-fps-trial");
  assert.match(campaign.excludedTrials[0].reason, /node1_fps_preflight/);
});

test("A5 — a degraded-only trial is excluded unless --allow-degraded is set", () => {
  const blocked = evaluatePreconditions({
    mode: "replay",
    avgNode1Fps: 24,
    avgNode2Fps: 24,
    nodeModesSeen: new Set(["single_node"]),
    allowDegraded: false,
    hasSyncMarker: true,
  });
  assert.equal(blocked.find((c) => c.name === "not_degraded_only")?.pass, false);

  const allowed = evaluatePreconditions({
    mode: "replay",
    avgNode1Fps: 24,
    avgNode2Fps: 24,
    nodeModesSeen: new Set(["single_node"]),
    allowDegraded: true,
    hasSyncMarker: true,
  });
  assert.equal(allowed.find((c) => c.name === "not_degraded_only")?.pass, true);
});

test("A7 — every derived metric carries {value,status,evidence}", () => {
  const { metrics } = baseTrialInputs();
  for (const [key, metric] of Object.entries(metrics)) {
    assert.doesNotThrow(() => assertMetricValueShape(metric, key));
  }
});

test("A7 — assertMetricValueShape rejects a bare number or a status-less object", () => {
  assert.throws(() => assertMetricValueShape(0.5, "rawNumber"));
  assert.throws(() => assertMetricValueShape({ value: 0.5 }, "missingStatus"));
  assert.throws(() => assertMetricValueShape({ value: 0.5, status: "made_up" }, "badStatus"));
});

test("A7 — buildTrialReport itself refuses a metrics object with a malformed field", () => {
  const { bins, counts } = baseTrialInputs();
  const badMetrics = { recall: { value: 0.9, status: "measured", evidence: "" } } as unknown as ReturnType<
    typeof computeDerivedMetrics
  >;

  assert.throws(() =>
    buildTrialReport({
      trialId: "bad-metrics-trial",
      mode: "replay",
      groundTruthPath: "groundtruth/z.csv",
      alignment,
      bins,
      counts,
      metrics: badMetrics,
      thresholdValue: null,
      thresholdSource: "unspecified",
      preconditions: [],
    }),
  );
});
