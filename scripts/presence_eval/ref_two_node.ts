/**
 * Reference baseline for the presence evaluation: the repo's OWN two-node logic, restricted to nodes 1 and 2.
 *
 *   npx tsx scripts/presence_eval/ref_two_node.ts > reports/presence-eval-2026-11/results/ref_two_node.json
 *
 * Read-only. Imports pure functions only (NodeBaselineTracker/RoomPresence tiers as in
 * scripts/eval-presence-on-datasets.ts, and fuseTwoNodeTarget's energy gate); writes nothing, touches no setting.
 * Each row = a fresh pair of trackers calibrated on `calib` (the whole recording), then run on `test`.
 * eval-presence-on-datasets.ts itself hard-codes four trackers, so it cannot be restricted to nodes 1+2 without editing it.
 */
import { readFileSync, readdirSync } from "node:fs";
import { computeAgcNormalizedPerturbation, computeNodeMotionFromMatrix, fuseTwoNodeTarget, DEFAULT_MOTION_THRESHOLD } from "../../server/lib/node-fusion";
import { NodeBaselineTracker, RoomPresence, tierAtLeast } from "../../server/lib/node-baseline";

const WINDOW_MS = 800;
const TICK_MS = 50;
const DIR = "data/datasets/room1/";
const room = JSON.parse(readFileSync("config/room.json", "utf8"));
const anchors = { 1: room.anchors["1"], 2: room.anchors["2"] };

interface Frame { t: number; amps: number[] }
type Rec = Frame[][]; // index 0 = node 1, 1 = node 2
const cache = new Map<string, Rec>();

function load(key: string): Rec {
  const hit = cache.get(key);
  if (hit) return hit;
  const files = readdirSync(DIR).filter((f) => f.includes(`__${key}`) && f.endsWith(".jsonl")).sort((a, b) => a.length - b.length || a.localeCompare(b));
  const groups = new Set(files.map((f) => f.replace(/\.part\d+\.jsonl$/, ".jsonl")));
  if (groups.size !== 1) throw new Error(`key ${key} matched ${groups.size} recordings`);
  const rec: Rec = [[], []];
  for (const f of files) {
    for (const line of readFileSync(DIR + f, "utf8").split("\n")) {
      if (!line) continue;
      const o = JSON.parse(line);
      if (o.type === "frame" && (o.n === 1 || o.n === 2)) rec[o.n - 1].push({ t: o.t, amps: o.a });
    }
  }
  rec.forEach((a) => a.sort((x, y) => x.t - y.t));
  cache.set(key, rec);
  return rec;
}

const quantile = (a: number[], q: number) => [...a].sort((x, y) => x - y)[Math.floor(q * (a.length - 1))] ?? 0;

function run(calib: string, test: string, label: string, protocol: string) {
  const trackers = [new NodeBaselineTracker(), new NodeBaselineTracker()];
  const presence = new RoomPresence();
  let visible = false;
  let clock = 0;
  let result: Record<string, unknown> | null = null;
  for (const [phase, key] of [["calib", calib], ["test", test]] as const) {
    const rec = load(key);
    const start = Math.min(...rec.map((n) => n[0]?.t ?? Infinity));
    const end = Math.max(...rec.map((n) => n[n.length - 1]?.t ?? 0));
    const cursor = [0, 0];
    const tiers: Record<string, number> = {};
    const motions: number[] = [];
    let ticks = 0, legacyPresent = 0, ttfd: number | null = null;
    for (let t = start + WINDOW_MS; t <= end; t += TICK_MS) {
      const windows = rec.map((frames, n) => {
        while (cursor[n] < frames.length && frames[cursor[n]].t <= t - WINDOW_MS) cursor[n]++;
        let hi = cursor[n];
        while (hi < frames.length && frames[hi].t <= t) hi++;
        return frames.slice(cursor[n], hi).map((f) => f.amps);
      });
      const ups = windows.map((w, n) => trackers[n].update(computeAgcNormalizedPerturbation(w), clock + (t - start), visible));
      const tier = presence.update(ups.map((u) => u.tier), clock + (t - start));
      visible = tierAtLeast(tier, "present_still");
      if (phase === "test") {
        tiers[tier] = (tiers[tier] ?? 0) + 1;
        if (ttfd === null && visible) ttfd = (t - start) / 1000;
        const m = windows.map((w) => computeNodeMotionFromMatrix(w));
        motions.push(Math.max(m[0].motion, m[1].motion));
        const target = fuseTwoNodeTarget({ r1: m[0].absStd, r2: m[1].absStd, motion1: m[0].motion, motion2: m[1].motion, anchors });
        if (target !== null) legacyPresent++;
        ticks++;
      }
    }
    clock += end - start + 1000;
    if (phase === "test") {
      const share = (k: string) => +((tiers[k] ?? 0) / ticks).toFixed(4);
      result = {
        protocol, calib, test, label, seconds: +((end - start) / 1000).toFixed(1), ticks,
        tierShare: { absent: share("absent"), present_still: share("present_still"), present_moving: share("present_moving"), active: share("active") },
        occupiedShare: +(1 - share("absent")).toFixed(4), ttfdSecondsFromTestStart: ttfd,
        legacyGateThreshold: DEFAULT_MOTION_THRESHOLD, legacyTargetShare: +(legacyPresent / ticks).toFixed(4),
        maxMotionP50: +quantile(motions, 0.5).toFixed(4), maxMotionP99: +quantile(motions, 0.99).toFixed(4),
      };
    }
  }
  return result;
}

const S6 = "s6__empty", S7 = "s7__walking", S1S = "s1__still__20261027", S5 = "s5__empty_fan", S8 = "s8__empty", S9 = "s9__empty", S10 = "s10__still", S2 = "s2__still";
const E18 = "s1__empty__20261018T180250Z";
const rows = [
  ...[[S7, "walking"], [S1S, "still"], [S5, "empty_fan"], [S8, "empty"], [S9, "empty"]].map(([k, l]) => run(S6, k, l, "adjacent_same_evening")),
  run(S9, S10, "still", "adjacent_same_evening"),
  ...[[S7, "walking"], [S2, "still"], [S1S, "still"], [S10, "still"], [S5, "empty_fan"], [S6, "empty"], [S8, "empty"], [S9, "empty"]].map(([k, l]) => run(E18, k, l, "cross_session_from_18Oct_empty")),
];
console.log(JSON.stringify({ nodes: [1, 2], note: "tier decision = NodeBaselineTracker x2 -> RoomPresence; legacy = fuseTwoNodeTarget energy gate; both read-only", rows }, null, 1));
