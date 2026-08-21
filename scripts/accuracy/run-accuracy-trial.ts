/**
 * CLI entry point for the accuracy harness. Scores one trial — either a
 * replayed recording CSV or a live read-only WS tap — against a ground-truth
 * presence log, and writes report.json + report.md.
 *
 * Usage (replay mode, scores an existing recording):
 *   tsx scripts/accuracy/run-accuracy-trial.ts \
 *     --mode=replay \
 *     --recording=recordings/2026-08-12_S2_negative-control.csv \
 *     --groundtruth=groundtruth/2026-08-12_S2.csv \
 *     --threshold-source=calibration/2026-08-12_room-baseline.json \
 *     --out=reports/2026-08-12_S2/
 *
 * Usage (live mode, taps the running dashboard's /ws targetState stream for
 * --duration seconds, read-only — F2: never a control path):
 *   tsx scripts/accuracy/run-accuracy-trial.ts \
 *     --mode=live --ws-url=ws://localhost:5000/ws --duration=60 \
 *     --groundtruth=groundtruth/2026-08-12_live.csv --out=reports/live-run/
 *
 * Refuses to score (exit 1, "TO_BE_MEASURED — no sync marker") if either
 * stream lacks an explicit sync marker — never guesses an alignment.
 */
import * as fs from "fs";
import * as path from "path";
import { parseGroundTruthCsv, groundTruthTimeBounds } from "./ground-truth-adapter";
import { loadSystemStateReplayCsv, captureLiveSystemState, type SystemSample } from "./system-state-adapter";
import { resolveAlignment, systemToGroundTruthMs, NoSyncMarkerError, type SyncEvent } from "./time-aligner";
import { buildBins, computeConfusion, computeDerivedMetrics } from "./confusion-scorer";
import { buildTrialReport, evaluatePreconditions, renderMarkdown } from "./report-generator";

function parseArgs(argv: string[]): Map<string, string> {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    const eq = key.indexOf("=");
    if (eq >= 0) {
      args.set(key.slice(0, eq), key.slice(eq + 1));
      continue;
    }
    const next = argv[i + 1];
    if (next && !next.startsWith("--")) {
      args.set(key, next);
      i += 1;
    } else {
      args.set(key, "true");
    }
  }
  return args;
}

function average(values: number[]): number | null {
  const finite = values.filter((v) => Number.isFinite(v));
  if (finite.length === 0) return null;
  return finite.reduce((sum, v) => sum + v, 0) / finite.length;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const mode = (args.get("--mode") ?? "replay") as "replay" | "live";
  const outDir = args.get("--out");
  const groundTruthPath = args.get("--groundtruth");
  const allowDegraded = args.has("--allow-degraded");
  const thresholdSource = args.get("--threshold-source") ?? "unspecified — pass --threshold-source to record calibration provenance";

  if (!outDir || !groundTruthPath) {
    console.error(
      "Usage: tsx scripts/accuracy/run-accuracy-trial.ts --mode=replay|live --groundtruth=<path> --out=<dir> [--recording=<path>] [--ws-url=<url>] [--duration=<s>] [--threshold-source=<path>] [--allow-degraded]",
    );
    process.exit(1);
    return;
  }

  const groundTruth = parseGroundTruthCsv(fs.readFileSync(path.resolve(groundTruthPath), "utf-8"));

  let systemSamples: SystemSample[];
  let systemSyncMs: number | null;
  let avgNode1Fps: number | null = null;
  let avgNode2Fps: number | null = null;
  const nodeModesSeen = new Set<string>();
  let thresholdValue: number | null = null;
  let trialId: string;
  let recordingPath: string | undefined;

  if (mode === "replay") {
    recordingPath = args.get("--recording");
    if (!recordingPath) {
      console.error("--recording is required for --mode=replay");
      process.exit(1);
      return;
    }
    const log = loadSystemStateReplayCsv(path.resolve(recordingPath));
    systemSamples = log.samples;
    systemSyncMs = log.syncMarkerSessionTsMs;
    thresholdValue = log.sessionMeta?.fusedMotionThreshold ?? log.sessionMeta?.motionThreshold ?? null;
    for (const sample of systemSamples) nodeModesSeen.add(sample.nodeMode);
    avgNode1Fps = average(systemSamples.map((s) => s.node1Fps));
    avgNode2Fps = average(systemSamples.map((s) => s.node2Fps));
    trialId = path.basename(recordingPath).replace(/\.csv$/i, "");
  } else if (mode === "live") {
    const wsUrl = args.get("--ws-url") ?? "ws://localhost:5000/ws";
    const durationS = Number.parseFloat(args.get("--duration") ?? "60");
    console.log(`[run-accuracy-trial] live capture: connecting to ${wsUrl} for ${durationS}s (read-only tap) ...`);
    const capture = await captureLiveSystemState({ wsUrl, durationMs: durationS * 1000 });
    systemSamples = capture.samples;
    systemSyncMs = capture.samples.length > 0 ? capture.captureStartWallClockMs : null;
    for (const sample of systemSamples) nodeModesSeen.add(sample.nodeMode);
    trialId = `live-${new Date(capture.captureStartWallClockMs).toISOString().replace(/[:.]/g, "-")}`;
  } else {
    console.error(`Unknown --mode "${mode}" (expected replay|live)`);
    process.exit(1);
    return;
  }

  let alignment;
  try {
    const syncEvents: SyncEvent[] =
      groundTruth.syncMarkerMs !== null && systemSyncMs !== null
        ? [{ groundTruthMs: groundTruth.syncMarkerMs, systemMs: systemSyncMs }]
        : [];
    alignment = resolveAlignment(syncEvents);
  } catch (err) {
    if (err instanceof NoSyncMarkerError) {
      console.error(err.message);
      process.exit(1);
      return;
    }
    throw err;
  }

  const alignedSystemTimes = systemSamples.map((s) => systemToGroundTruthMs(s.sessionTsMs, alignment));
  const gtBounds = groundTruthTimeBounds(groundTruth);
  const allTimes = [...alignedSystemTimes, ...(gtBounds ? [gtBounds.startMs, gtBounds.endMs] : [])];
  if (allTimes.length === 0) {
    console.error("No system samples or ground-truth intervals to score.");
    process.exit(1);
    return;
  }
  const startMs = Math.min(...allTimes);
  const endMs = Math.max(...allTimes);

  const bins = buildBins(systemSamples, groundTruth, alignment, startMs, endMs);
  const counts = computeConfusion(bins);
  const metrics = computeDerivedMetrics(bins, counts);

  const preconditions = evaluatePreconditions({
    mode,
    avgNode1Fps,
    avgNode2Fps,
    nodeModesSeen,
    allowDegraded,
    hasSyncMarker: true,
  });

  const report = buildTrialReport({
    trialId,
    mode,
    recordingPath,
    groundTruthPath,
    alignment,
    bins,
    counts,
    metrics,
    thresholdValue,
    thresholdSource,
    preconditions,
  });

  const resolvedOutDir = path.resolve(outDir);
  fs.mkdirSync(resolvedOutDir, { recursive: true });
  fs.writeFileSync(path.join(resolvedOutDir, "report.json"), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(resolvedOutDir, "report.md"), renderMarkdown(report));

  console.log(
    `[run-accuracy-trial] wrote report to ${resolvedOutDir} (preconditions ${report.preconditionsPassed ? "PASS" : "FAILED — excluded from campaign rollups"})`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
