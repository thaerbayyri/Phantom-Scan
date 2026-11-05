/**
 * Offline: turn recorded datasets (data/datasets/<room>/*.jsonl, read-only) into CalibrationRun files by replaying them through the
 * SAME motion function the live calibrate script uses (computeNodeMotionFromMatrix, 1500 ms per-node window, sampled every 200 ms of
 * RECORDING time), so `calibrate-threshold.ts --evaluate` can be exercised on real data without a live capture.
 *
 *   npx tsx scripts/accuracy/replay-calibration-runs.ts --label empty --out reports/fix-2026-11/results/cal/s8.json <file.jsonl> [more parts...]
 *
 * Parts must be given in order. The run's start time is the first frame's recorder timestamp. Writes only --out (exclusive create).
 * Not a validation of any threshold: it only lets the refusal rules be checked against real link states.
 */
import fs from "fs";
import path from "path";
import { computeNodeMotionFromMatrix } from "../../server/lib/node-fusion";
import { BlockAccumulator, type RunLabel } from "./calibration-soak";

const WINDOW_MS = 1500;
const TICK_MS = 200;
const MIN_WINDOW_FRAMES = 5;

interface Frame {
  t: number;
  n: number;
  rssi: number;
  a: number[];
}

function* readFrames(file: string): Generator<Frame> {
  for (const line of fs.readFileSync(file, "utf-8").split("\n")) {
    if (!line.startsWith('{"type":"frame"')) continue;
    try {
      const o = JSON.parse(line) as { t: number; n: number; rssi: number; a: number[] };
      if (Number.isFinite(o.t) && o.n >= 1 && o.n <= 4 && Array.isArray(o.a)) yield { t: o.t, n: o.n, rssi: o.rssi, a: o.a };
    } catch {
      /* a malformed line is skipped, as the Python loader does (and counts); this tool only needs the usable frames */
    }
  }
}

export function replay(files: string[], label: RunLabel) {
  const windows = new Map<number, Frame[]>();
  let acc: BlockAccumulator | null = null;
  let nextTick = 0;
  for (const file of files) {
    for (const f of readFrames(file)) {
      if (!acc) {
        acc = new BlockAccumulator(label, f.t);
        nextTick = f.t + TICK_MS;
      }
      acc.addFrame(f.n, f.t, f.rssi);
      const win = windows.get(f.n) ?? [];
      win.push(f);
      while (win.length && win[0].t < f.t - WINDOW_MS) win.shift();
      windows.set(f.n, win);
      while (f.t >= nextTick) {
        const motion = new Map<number, number>();
        for (const [id, w] of Array.from(windows.entries())) {
          if (w.length > MIN_WINDOW_FRAMES && w[w.length - 1].t >= nextTick - WINDOW_MS) motion.set(id, computeNodeMotionFromMatrix(w.map((x) => x.a)).motion);
        }
        for (const [id, m] of Array.from(motion.entries())) acc.addSample(`motion.n${id}`, nextTick, m);
        if (motion.has(1) && motion.has(2)) acc.addSample("motion.fused", nextTick, Math.max(motion.get(1)!, motion.get(2)!));
        nextTick += TICK_MS;
      }
    }
  }
  if (!acc) throw new Error("no usable frames in the given files");
  return acc.finish({ command: `replay-calibration-runs ${files.map((f) => path.basename(f)).join(" ")}`, label, note: "replayed from a recording; recorder clock; room state as labelled in the file name" });
}

function main(): void {
  const args = process.argv.slice(2);
  const val = (name: string) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
  };
  const label = (val("--label") ?? "empty") as RunLabel;
  const out = val("--out");
  const files = args.filter((a, i) => a.endsWith(".jsonl") && args[i - 1] !== "--out");
  if (!out || files.length === 0) {
    console.error("usage: replay-calibration-runs.ts --label empty|fan|occupied --out <run.json> <recording.jsonl> [more parts in order]");
    process.exit(2);
  }
  const run = replay(files, label);
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(run), { flag: "wx" });
  console.log(`${out}: ${Object.values(run.metrics)[0]?.length ?? 0} blocks, metrics ${Object.keys(run.metrics).join(", ")}`);
}

if (path.basename(process.argv[1] ?? "") === "replay-calibration-runs.ts") main();
