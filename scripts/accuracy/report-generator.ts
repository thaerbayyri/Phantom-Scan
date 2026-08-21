/**
 * Assembles a single trial's scoring output into a report that can never
 * omit provenance (build prompt §4.4/§4.5/§6 A5/A7): threshold provenance is
 * mandatory, and a trial failing its own preconditions is excluded from any
 * campaign rollup rather than silently dropped or silently included.
 */
import type { Bin, ConfusionCounts, DerivedMetrics } from "./confusion-scorer";
import type { TimeAlignment } from "./time-aligner";
import { assertMetricValueShape, measured, toBeMeasured, type MetricValue } from "./types";

export interface PreconditionCheck {
  name: string;
  pass: boolean;
  detail: string;
}

export interface ThresholdProvenance {
  /** Exact PHANTOM_MOTION_THRESHOLD (or fused_motion_threshold) used for this trial, or null if unknown. */
  motionThreshold: number | null;
  /** Which calibration run produced it — pass --threshold-source, or "unspecified" if the operator didn't record it. */
  calibrationSource: string;
}

export interface TrialReport {
  trialId: string;
  mode: "replay" | "live";
  recordingPath?: string;
  groundTruthPath: string;
  syncOffsetMs: MetricValue;
  syncDriftPpm: number;
  binCount: number;
  confusion: ConfusionCounts;
  metrics: DerivedMetrics;
  thresholdProvenance: ThresholdProvenance;
  preconditions: PreconditionCheck[];
  preconditionsPassed: boolean;
  generatedAtMs: number;
}

export interface CampaignReport {
  trials: TrialReport[];
  excludedTrials: Array<{ trialId: string; reason: string }>;
  generatedAtMs: number;
}

export function buildTrialReport(input: {
  trialId: string;
  mode: "replay" | "live";
  recordingPath?: string;
  groundTruthPath: string;
  alignment: TimeAlignment;
  bins: Bin[];
  counts: ConfusionCounts;
  metrics: DerivedMetrics;
  thresholdValue: number | null;
  thresholdSource: string;
  preconditions: PreconditionCheck[];
}): TrialReport {
  for (const [key, metric] of Object.entries(input.metrics)) {
    assertMetricValueShape(metric, `metrics.${key}`);
  }

  return {
    trialId: input.trialId,
    mode: input.mode,
    recordingPath: input.recordingPath,
    groundTruthPath: input.groundTruthPath,
    syncOffsetMs: measured(
      input.alignment.offsetMs,
      `resolved from explicit sync marker(s); drift=${input.alignment.driftPpm.toFixed(2)} ppm`,
    ),
    syncDriftPpm: input.alignment.driftPpm,
    binCount: input.bins.length,
    confusion: input.counts,
    metrics: input.metrics,
    thresholdProvenance: {
      motionThreshold: input.thresholdValue,
      calibrationSource: input.thresholdSource,
    },
    preconditions: input.preconditions,
    preconditionsPassed: input.preconditions.every((check) => check.pass),
    generatedAtMs: Date.now(),
  };
}

export function evaluatePreconditions(input: {
  mode: "replay" | "live";
  avgNode1Fps: number | null;
  avgNode2Fps: number | null;
  nodeModesSeen: Set<string>;
  allowDegraded: boolean;
  hasSyncMarker: boolean;
}): PreconditionCheck[] {
  const checks: PreconditionCheck[] = [];

  checks.push({
    name: "sync_marker_present",
    pass: input.hasSyncMarker,
    detail: input.hasSyncMarker
      ? "sync marker resolved in both ground-truth and system streams"
      : "TO_BE_MEASURED — no sync marker",
  });

  if (input.mode === "replay") {
    const node1Ok = input.avgNode1Fps !== null && input.avgNode1Fps >= 20;
    const node2Ok = input.avgNode2Fps !== null && input.avgNode2Fps >= 20;
    checks.push({
      name: "node1_fps_preflight",
      pass: node1Ok,
      detail: `node1 avg fps = ${input.avgNode1Fps ?? "unknown"} (P0 preflight requires >= 20/node)`,
    });
    checks.push({
      name: "node2_fps_preflight",
      pass: node2Ok,
      detail: `node2 avg fps = ${input.avgNode2Fps ?? "unknown"} (P0 preflight requires >= 20/node)`,
    });
  } else {
    checks.push({
      name: "node_fps_preflight",
      pass: true,
      detail:
        "live mode: per-node fps is not carried on the targetState WS message, so this gate cannot auto-verify P0 here — confirm fps >= 20/node manually before trusting this trial",
    });
  }

  const modesSeen = Array.from(input.nodeModesSeen);
  const degradedOnly = modesSeen.length > 0 && modesSeen.every((mode) => mode === "single_node");
  if (degradedOnly && !input.allowDegraded) {
    checks.push({
      name: "not_degraded_only",
      pass: false,
      detail: "trial ran entirely in single_node/degraded mode; pass --allow-degraded to score a degraded-mode trial intentionally",
    });
  } else {
    checks.push({
      name: "not_degraded_only",
      pass: true,
      detail: degradedOnly
        ? "degraded-only trial explicitly allowed via --allow-degraded"
        : "fused_two_node evidence present in this trial",
    });
  }

  return checks;
}

export function buildCampaignReport(trialReports: TrialReport[]): CampaignReport {
  const included = trialReports.filter((report) => report.preconditionsPassed);
  const excludedTrials = trialReports
    .filter((report) => !report.preconditionsPassed)
    .map((report) => ({
      trialId: report.trialId,
      reason: report.preconditions
        .filter((check) => !check.pass)
        .map((check) => `${check.name}: ${check.detail}`)
        .join("; "),
    }));

  return { trials: included, excludedTrials, generatedAtMs: Date.now() };
}

function formatMetric(metric: MetricValue): string {
  if (metric.status === "TO_BE_MEASURED") {
    return `TO_BE_MEASURED (${metric.evidence})`;
  }
  return `${(metric.value as number).toFixed(4)} — ${metric.evidence}`;
}

export function renderMarkdown(report: TrialReport): string {
  const lines: string[] = [];
  lines.push(`# Accuracy Trial Report — ${report.trialId}`);
  lines.push("");
  lines.push(`Mode: \`${report.mode}\` | Generated: ${new Date(report.generatedAtMs).toISOString()}`);
  lines.push("");
  lines.push(`Preconditions: **${report.preconditionsPassed ? "PASS" : "FAILED — excluded from campaign rollups"}**`);
  lines.push("");
  lines.push("| Precondition | Pass | Detail |");
  lines.push("|---|---|---|");
  for (const check of report.preconditions) {
    lines.push(`| ${check.name} | ${check.pass ? "yes" : "no"} | ${check.detail} |`);
  }
  lines.push("");
  lines.push("## Threshold provenance");
  lines.push("");
  lines.push(
    `PHANTOM_MOTION_THRESHOLD = ${report.thresholdProvenance.motionThreshold ?? "unknown"} (source: ${report.thresholdProvenance.calibrationSource})`,
  );
  lines.push("");
  lines.push("## Time alignment");
  lines.push("");
  lines.push(`sync offset: ${formatMetric(report.syncOffsetMs)}`);
  lines.push("");
  lines.push("## Confusion matrix (per 1 s bin)");
  lines.push("");
  lines.push("| TP | FP | FN | TN | bins |");
  lines.push("|---|---|---|---|---|");
  lines.push(
    `| ${report.confusion.tp} | ${report.confusion.fp} | ${report.confusion.fn} | ${report.confusion.tn} | ${report.binCount} |`,
  );
  lines.push("");
  lines.push("## Derived metrics");
  lines.push("");
  lines.push("| Metric | Value |");
  lines.push("|---|---|");
  lines.push(`| Recall (detection rate) | ${formatMetric(report.metrics.recall)} |`);
  lines.push(`| Precision | ${formatMetric(report.metrics.precision)} |`);
  lines.push(`| F1 | ${formatMetric(report.metrics.f1)} |`);
  lines.push(`| False-positive rate (fraction of negative bins) | ${formatMetric(report.metrics.falsePositiveRateFraction)} |`);
  lines.push(`| False-positive events/hour | ${formatMetric(report.metrics.falsePositiveEventsPerHour)} |`);
  lines.push(`| Time to first detect (s) | ${formatMetric(report.metrics.timeToFirstDetectS)} |`);
  lines.push(`| Longest false-negative run (s) | ${formatMetric(report.metrics.longestFalseNegativeRunS)} |`);
  lines.push("");

  return lines.join("\n");
}

export function renderCampaignMarkdown(campaign: CampaignReport): string {
  const lines: string[] = [];
  lines.push("# Accuracy Campaign Rollup");
  lines.push("");
  lines.push(`Generated: ${new Date(campaign.generatedAtMs).toISOString()}`);
  lines.push("");
  lines.push(`Included trials: ${campaign.trials.length} | Excluded trials: ${campaign.excludedTrials.length}`);
  lines.push("");

  if (campaign.trials.length === 0) {
    lines.push("No trials passed preconditions — all headline metrics are `TO_BE_MEASURED`.");
    lines.push("");
  } else {
    lines.push("| Trial | Recall | Precision | F1 | FPR | FP/hour |");
    lines.push("|---|---|---|---|---|---|");
    for (const trial of campaign.trials) {
      lines.push(
        `| ${trial.trialId} | ${formatMetric(trial.metrics.recall)} | ${formatMetric(trial.metrics.precision)} | ${formatMetric(trial.metrics.f1)} | ${formatMetric(trial.metrics.falsePositiveRateFraction)} | ${formatMetric(trial.metrics.falsePositiveEventsPerHour)} |`,
      );
    }
    lines.push("");
  }

  if (campaign.excludedTrials.length > 0) {
    lines.push("## Excluded trials (precondition failure)");
    lines.push("");
    lines.push("| Trial | Reason |");
    lines.push("|---|---|");
    for (const excluded of campaign.excludedTrials) {
      lines.push(`| ${excluded.trialId} | ${excluded.reason} |`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export { toBeMeasured };
