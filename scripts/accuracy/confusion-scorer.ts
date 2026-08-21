/**
 * Bins two time-aligned streams at 1 Hz (matches firmware feature-state
 * cadence, build prompt §4.1) and scores per-bin TP/FP/FN/TN plus the
 * derived campaign metrics from §4.4.
 *
 * Majority-vote resampling, NOT nearest-neighbor: a bin is positive only if
 * the underlying signal covered >=50% of that 1 s window, so short
 * drop-outs/blips aren't silently rounded away.
 */
import type { SystemSample } from "./system-state-adapter";
import type { GroundTruthLog } from "./ground-truth-adapter";
import { isGroundTruthPositiveAt } from "./ground-truth-adapter";
import type { TimeAlignment } from "./time-aligner";
import { systemToGroundTruthMs } from "./time-aligner";
import { type MetricValue, measured, toBeMeasured } from "./types";

const BIN_MS = 1000;
/** Occupancy sampling resolution within each bin — 20 samples/bin at 1 Hz bins. */
const STEP_MS = 50;

export interface Bin {
  binIndex: number;
  /** Ground-truth-aligned bin start (ground-truth clock). */
  tStartMs: number;
  groundTruthPositive: boolean;
  systemPositive: boolean;
  /** Distinct system states observed while covering this bin (diagnostics, e.g. stale-demotion visibility). */
  systemStates: string[];
}

interface AlignedSample {
  gtMs: number;
  state: string;
  isHumanVerdict: boolean;
}

export function buildBins(
  systemSamples: SystemSample[],
  groundTruth: GroundTruthLog,
  alignment: TimeAlignment,
  startMs: number,
  endMs: number,
): Bin[] {
  const aligned: AlignedSample[] = systemSamples
    .map((s) => ({
      gtMs: systemToGroundTruthMs(s.sessionTsMs, alignment),
      state: s.state,
      isHumanVerdict: s.isHumanVerdict,
    }))
    .sort((a, b) => a.gtMs - b.gtMs);

  const binCount = Math.max(0, Math.floor((endMs - startMs) / BIN_MS));
  const bins: Bin[] = [];
  let sampleIdx = 0;

  for (let i = 0; i < binCount; i++) {
    const binStart = startMs + i * BIN_MS;
    const binEnd = binStart + BIN_MS;

    let gtPositiveMs = 0;
    let sysPositiveMs = 0;
    const statesSeen = new Set<string>();

    for (let t = binStart; t < binEnd; t += STEP_MS) {
      if (isGroundTruthPositiveAt(groundTruth, t)) {
        gtPositiveMs += STEP_MS;
      }

      // Held-state step function: the most recent sample at/before t.
      while (sampleIdx + 1 < aligned.length && aligned[sampleIdx + 1].gtMs <= t) {
        sampleIdx++;
      }
      const current = aligned[sampleIdx];
      if (current && current.gtMs <= t) {
        statesSeen.add(current.state);
        if (current.isHumanVerdict) sysPositiveMs += STEP_MS;
      }
    }

    bins.push({
      binIndex: i,
      tStartMs: binStart,
      groundTruthPositive: gtPositiveMs >= BIN_MS / 2,
      systemPositive: sysPositiveMs >= BIN_MS / 2,
      systemStates: Array.from(statesSeen),
    });
  }

  return bins;
}

export interface ConfusionCounts {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}

export function computeConfusion(bins: Bin[]): ConfusionCounts {
  const counts: ConfusionCounts = { tp: 0, fp: 0, fn: 0, tn: 0 };
  for (const bin of bins) {
    if (bin.groundTruthPositive && bin.systemPositive) counts.tp++;
    else if (bin.groundTruthPositive && !bin.systemPositive) counts.fn++;
    else if (!bin.groundTruthPositive && bin.systemPositive) counts.fp++;
    else counts.tn++;
  }
  return counts;
}

export interface DerivedMetrics {
  recall: MetricValue;
  precision: MetricValue;
  f1: MetricValue;
  falsePositiveRateFraction: MetricValue;
  falsePositiveEventsPerHour: MetricValue;
  timeToFirstDetectS: MetricValue;
  longestFalseNegativeRunS: MetricValue;
}

export function computeDerivedMetrics(bins: Bin[], counts: ConfusionCounts): DerivedMetrics {
  const { tp, fp, fn, tn } = counts;

  const recall =
    tp + fn > 0
      ? measured(tp / (tp + fn), `TP=${tp}, FN=${fn} across ${tp + fn} ground-truth-positive bins`)
      : toBeMeasured("no ground-truth-positive bins in this trial");

  const precision =
    tp + fp > 0
      ? measured(tp / (tp + fp), `TP=${tp}, FP=${fp} across ${tp + fp} system-positive bins`)
      : toBeMeasured("system never reported a positive bin");

  const f1 =
    recall.status === "MEASURED" &&
    precision.status === "MEASURED" &&
    (recall.value as number) + (precision.value as number) > 0
      ? measured(
          (2 * (precision.value as number) * (recall.value as number)) /
            ((precision.value as number) + (recall.value as number)),
          "harmonic mean of measured precision and recall",
        )
      : toBeMeasured("precision and/or recall not measured, or precision+recall = 0");

  const falsePositiveRateFraction =
    fp + tn > 0
      ? measured(fp / (fp + tn), `FP=${fp}, TN=${tn} across ${fp + tn} ground-truth-negative bins`)
      : toBeMeasured("no ground-truth-negative bins in this trial");

  const fpEvents = countContiguousFalsePositiveRuns(bins);
  const trialHours = (bins.length * BIN_MS) / 3_600_000;
  const falsePositiveEventsPerHour =
    trialHours > 0
      ? measured(
          fpEvents / trialHours,
          `${fpEvents} discrete FP run(s) over a ${trialHours.toFixed(4)} h trial — one long FP and many short ones are NOT equivalent to falsePositiveRateFraction alone`,
        )
      : toBeMeasured("trial has zero duration (no bins)");

  const firstDetectS = findTimeToFirstDetectS(bins);
  const timeToFirstDetectS =
    firstDetectS !== null
      ? measured(firstDetectS, "seconds from first ground-truth-positive interval's onset to the first TP bin in that interval, event-level")
      : toBeMeasured(
          bins.some((b) => b.groundTruthPositive)
            ? "system produced zero TP bins in this trial — time-to-first-detect is undefined, not merely unmeasured"
            : "trial contains no ground-truth-positive interval",
        );

  const longestRunS = findLongestFalseNegativeRunS(bins);
  const longestFalseNegativeRunS =
    longestRunS !== null
      ? measured(longestRunS, "longest continuous FN run (seconds) inside any confirmed-present interval")
      : toBeMeasured("trial contains no ground-truth-positive interval — drop-out duration is not applicable");

  return {
    recall,
    precision,
    f1,
    falsePositiveRateFraction,
    falsePositiveEventsPerHour,
    timeToFirstDetectS,
    longestFalseNegativeRunS,
  };
}

function countContiguousFalsePositiveRuns(bins: Bin[]): number {
  let runs = 0;
  let inRun = false;
  for (const bin of bins) {
    const isFalsePositive = !bin.groundTruthPositive && bin.systemPositive;
    if (isFalsePositive && !inRun) {
      runs++;
      inRun = true;
    } else if (!isFalsePositive) {
      inRun = false;
    }
  }
  return runs;
}

/** Earliest TP bin in the trial, minus the onset of the ground-truth-positive
 * run that contains it (a contiguous run of groundTruthPositive bins). */
function findTimeToFirstDetectS(bins: Bin[]): number | null {
  const firstTpIdx = bins.findIndex((bin) => bin.groundTruthPositive && bin.systemPositive);
  if (firstTpIdx === -1) return null;

  let onsetIdx = firstTpIdx;
  while (onsetIdx > 0 && bins[onsetIdx - 1].groundTruthPositive) {
    onsetIdx--;
  }
  return (bins[firstTpIdx].tStartMs - bins[onsetIdx].tStartMs) / 1000;
}

function findLongestFalseNegativeRunS(bins: Bin[]): number | null {
  let longest = 0;
  let current = 0;
  let sawPositiveInterval = false;

  for (const bin of bins) {
    if (!bin.groundTruthPositive) {
      current = 0;
      continue;
    }
    sawPositiveInterval = true;
    if (bin.systemPositive) {
      current = 0;
    } else {
      current += 1;
      longest = Math.max(longest, current);
    }
  }

  return sawPositiveInterval ? longest : null; // bins are 1 s each.
}
