/**
 * Offline presence evaluation on labelled recordings (data/datasets/<room>/).
 *
 *   npx tsx scripts/eval-presence-on-datasets.ts room1 empty walking two_people
 *
 * Replays the recordings through the same pipeline the dashboard runs
 * (800 ms windows -> AGC-normalised perturbation -> per-node baseline trackers
 * -> room presence, baselines frozen while a target is visible). The trackers
 * are NOT reset between recordings, so the first label is the "calibration"
 * and the later ones are people entering a room that was calibrated empty.
 * Prints, per recording, the share of ticks at each tier: an empty recording
 * should be mostly `absent`, occupied ones mostly present.
 */
import { readFileSync, readdirSync } from "node:fs";
import { computeAgcNormalizedPerturbation } from "../server/lib/node-fusion";
import { NodeBaselineTracker, RoomPresence, tierAtLeast } from "../server/lib/node-baseline";
import { blockBootstrapAuc } from "./accuracy/auc-bootstrap";

// Flags (PS-FIX-04): --nodes 1,2   restrict to these node ids (default 1,2,3,4; the others see no frames)
//                    --window-ms N perturbation window (default env PHANTOM_MOTION_WINDOW_MS or 800;
//                                  scripts/calibrate-threshold.ts defaults to 1500 -- numbers do not transfer)
const rawArgs = process.argv.slice(2);
const flagValue = (name: string): string | undefined => {
  const i = rawArgs.indexOf(name);
  return i >= 0 ? rawArgs[i + 1] : undefined;
};
const FLAGS_WITH_VALUE = new Set(["--nodes", "--window-ms"]);
const positional = rawArgs.filter((a, i) => !a.startsWith("--") && !FLAGS_WITH_VALUE.has(rawArgs[i - 1]));
const NODES = (flagValue("--nodes") ?? "1,2,3,4").split(",").map(Number);
if (NODES.some((n) => !Number.isInteger(n) || n < 1 || n > 4)) {
  console.error("--nodes must be a comma list of node ids 1-4, e.g. --nodes 1,2");
  process.exit(1);
}
const WINDOW_MS = Number(flagValue("--window-ms") ?? process.env.PHANTOM_MOTION_WINDOW_MS ?? 800);
if (!Number.isFinite(WINDOW_MS) || WINDOW_MS <= 0) {
  console.error("--window-ms must be a positive number");
  process.exit(1);
}
const TICK_MS = 50;
const BLOCK_TICKS = Math.ceil(10_000 / TICK_MS); // >= 10 s blocks for the bootstrap
const [room, ...labels] = positional;
if (!room || labels.length === 0) {
  console.error("usage: eval-presence-on-datasets.ts <room> <label> [<label> ...] [--nodes 1,2] [--window-ms 800]");
  process.exit(1);
}
console.log(`nodes ${NODES.join(",")}  window ${WINDOW_MS} ms  tick ${TICK_MS} ms`);

interface Frame { t: number; amps: number[] }
const dir = `data/datasets/${room}/`;

function loadRecordings(label: string): Frame[][][] {
  const files = readdirSync(dir).filter((f) => f.includes(`__${label}__`) && f.endsWith(".jsonl")).sort();
  const groups = new Map<string, string[]>();
  for (const f of files) groups.set(f.replace(/\.part\d+\.jsonl$/, ".jsonl"), [...(groups.get(f.replace(/\.part\d+\.jsonl$/, ".jsonl")) ?? []), f]);
  return [...groups.values()].map((parts) => {
    const byNode: Frame[][] = [[], [], [], []];
    for (const f of parts) {
      for (const line of readFileSync(dir + f, "utf8").split("\n")) {
        if (!line) continue;
        const o = JSON.parse(line);
        if (o.type === "frame" && NODES.includes(o.n)) byNode[o.n - 1].push({ t: o.t, amps: o.a });
      }
    }
    byNode.forEach((a) => a.sort((x, y) => x.t - y.t));
    return byNode;
  });
}

const trackers = [0, 1, 2, 3].map(() => new NodeBaselineTracker());
const presence = new RoomPresence();
let visible = false;
let clock = 0;
const results: { label: string; idx: number; maxZs: number[] }[] = [];

for (const label of labels) {
  for (const [idx, rec] of loadRecordings(label).entries()) {
    const start = Math.min(...rec.map((n) => n[0]?.t ?? Infinity));
    const end = Math.max(...rec.map((n) => n[n.length - 1]?.t ?? 0));
    const cursor = [0, 0, 0, 0];
    const counts: Record<string, number> = {};
    let ticks = 0;
    const perNodeZ = [0, 0, 0, 0];
    const maxZs: number[] = [];
    for (let t = start + WINDOW_MS; t <= end; t += TICK_MS) {
      const ups = rec.map((frames, n) => {
        while (cursor[n] < frames.length && frames[cursor[n]].t <= t - WINDOW_MS) cursor[n]++;
        let hi = cursor[n];
        while (hi < frames.length && frames[hi].t <= t) hi++;
        const raw = computeAgcNormalizedPerturbation(frames.slice(cursor[n], hi).map((f) => f.amps));
        return trackers[n].update(raw, clock + (t - start), visible);
      });
      const tier = presence.update(ups.map((u) => u.tier), clock + (t - start));
      visible = tierAtLeast(tier, "present_still");
      counts[tier] = (counts[tier] ?? 0) + 1;
      ups.forEach((u, n) => (perNodeZ[n] += u.z));
      if (t - start > 20_000) maxZs.push(Math.max(...ups.map((u) => u.z))); // skip warm-up/settling
      ticks++;
    }
    clock += end - start + 1000;
    results.push({ label, idx, maxZs });
    const pct = (k: string) => (((counts[k] ?? 0) / ticks) * 100).toFixed(0).padStart(3) + "%";
    console.log(
      `${label.padEnd(11)}#${idx} ${((end - start) / 1000).toFixed(0).padStart(4)}s  absent ${pct("absent")}  still ${pct("present_still")}  moving ${pct("present_moving")}  active ${pct("active")}  meanZ ${perNodeZ.map((z) => (z / ticks).toFixed(1)).join("/")}`,
    );
  }
}

// Separation of the strongest-node z between each recording and the LAST empty one.
// Rank-based AUC over ALL ticks (no subsampling) with a 95 % moving-block bootstrap CI (>= 10 s blocks, fixed seed).
// Empty recordings are included on purpose: their AUC against the reference is the empty-vs-empty negative control
// (a score that separates two empties is drifting, not detecting; the CI covers within-recording variability only).
const quantile = (a: number[], q: number) => [...a].sort((x, y) => x - y)[Math.floor(q * (a.length - 1))] ?? 0;
function aucText(positive: number[], negative: number[]): string {
  const r = blockBootstrapAuc(positive, negative, { block: BLOCK_TICKS, nBoot: 300 });
  return r.auc === null ? "n/a (empty class)" : `${r.auc.toFixed(2)} [${(r.lo as number).toFixed(2)}, ${(r.hi as number).toFixed(2)}]`;
}
const emptyRuns = results.filter((r) => r.label === "empty");
const reference = emptyRuns[emptyRuns.length - 1];
if (reference) {
  console.log("\nstrongest-node z (after 20 s):  p50 / p90 / p99    AUC vs last empty [95% block-bootstrap CI]");
  for (const r of results) {
    const a = r === reference ? "  -  " : aucText(r.maxZs, reference.maxZs);
    console.log(`${r.label.padEnd(11)}#${r.idx}  ${[0.5, 0.9, 0.99].map((q) => quantile(r.maxZs, q).toFixed(1).padStart(5)).join(" / ")}        ${a}`);
  }
}
