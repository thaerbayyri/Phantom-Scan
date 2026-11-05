import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { spawnSync } from "node:child_process";
import { mulberry32 } from "../auc-bootstrap";
import {
  BLOCK_S,
  BlockAccumulator,
  detectLinkSteps,
  evaluateCalibration,
  renderEvaluation,
  type CalibrationRun,
  type RunLabel,
} from "../calibration-soak";

const DAY0 = new Date(2026, 10, 3, 9, 0, 0).getTime();
const MIN = 60_000;

interface MakeOpts {
  label?: RunLabel;
  start?: number;
  minutes: number;
  seed?: number;
  base?: number;                 // typical block maximum
  drift?: (block: number) => number;   // added to every metric from this block on
  rssi?: (block: number) => number;
  fps?: (block: number) => number;
}

function makeRun(o: MakeOpts): CalibrationRun {
  const rand = mulberry32(o.seed ?? 1);
  const blocks = Math.round((o.minutes * 60) / BLOCK_S);
  const metric = (b: number) => (o.base ?? 0.3) + 0.05 * Math.abs(rand() + rand() - 1) * 4 + (o.drift ? o.drift(b) : 0);
  const nodes: CalibrationRun["nodes"] = {};
  for (const id of ["1", "2"]) {
    nodes[id] = {
      rssiMedian: Array.from({ length: blocks }, (_, b) => (o.rssi ? o.rssi(b) : -40) + (rand() - 0.5)),
      frames: Array.from({ length: blocks }, (_, b) => Math.round(((o.fps ? o.fps(b) : 65) * BLOCK_S) * (0.97 + 0.06 * rand()))),
    };
  }
  return {
    schema: 1,
    label: o.label ?? "empty",
    startedAtMs: o.start ?? DAY0,
    blockS: BLOCK_S,
    metrics: { "motion.fused": Array.from({ length: blocks }, (_, b) => metric(b)), "motion.n1": Array.from({ length: blocks }, (_, b) => metric(b)) },
    nodes,
  };
}

const fanAfter = (o: Partial<MakeOpts> = {}) => makeRun({ label: "fan", start: DAY0 + 100 * MIN, minutes: 10, seed: 9, base: 0.3, ...o });

test("BlockAccumulator keeps the maximum per 10 s block, marks empty blocks null and drops the incomplete last block", () => {
  const acc = new BlockAccumulator("empty", 0);
  acc.addSample("m", 1_000, 0.2);
  acc.addSample("m", 9_000, 0.7);
  acc.addSample("m", 25_000, 0.4);          // block 2; block 1 has no sample
  acc.addSample("m", 31_000, 9.9);          // block 3 is the last one seen -> incomplete, dropped
  acc.addSample("m", 1_000, Number.NaN);    // ignored
  acc.addFrame(1, 2_000, -40);
  acc.addFrame(1, 4_000, -42);
  acc.addFrame(1, 12_000, -50);
  const run = acc.finish();
  assert.deepEqual(run.metrics.m, [0.7, null, 0.4]);
  assert.deepEqual(run.nodes["1"].frames, [2, 1, 0]);
  assert.deepEqual(run.nodes["1"].rssiMedian, [-41, -50, null]);
});

test("a clean 90 min empty soak plus a 10 min fan control is allowed to give a candidate, and it never writes settings", () => {
  const ev = evaluateCalibration({ empty: [makeRun({ minutes: 90 })], fan: [fanAfter()] });
  assert.deepEqual(ev.refusals, []);
  assert.equal(ev.recommendationAllowed, true);
  assert.equal(ev.writesSettings, false);
  const m = ev.metrics.find((x) => x.metric === "motion.fused")!;
  assert.ok(m.candidate !== null && m.candidate > 0.3);
  assert.equal(m.heldOutBlocks, 270);
  assert.ok(m.heldOutFalseAlarmsPerHour !== null && m.heldOutFalseAlarmsPerHour <= 8, "held-out false alarms/hour is reported, not assumed");
  assert.equal(m.occupiedMissRate, null, "no occupied run: misses are [TO BE MEASURED], not zero");
  assert.ok(renderEvaluation(ev).includes("[TO BE MEASURED]"));
});

test("a soak shorter than the required 60 min is refused and no candidate is printed", () => {
  const ev = evaluateCalibration({ empty: [makeRun({ minutes: 30 })], fan: [fanAfter({ start: DAY0 + 40 * MIN })] });
  assert.ok(ev.refusals.some((r) => r.code === "soak-too-short"));
  assert.equal(ev.recommendationAllowed, false);
  assert.ok(ev.metrics.every((m) => m.candidate === null));
  assert.ok(renderEvaluation(ev).includes("REFUSED"));
  assert.equal(evaluateCalibration({ empty: [makeRun({ minutes: 30 })], fan: [fanAfter({ start: DAY0 + 40 * MIN })] }, { minSoakMin: 20 }).refusals.some((r) => r.code === "soak-too-short"), false, "the minimum is configurable");
});

test("without a fan (negative-control) run, or with a very short one, nothing is recommended", () => {
  assert.ok(evaluateCalibration({ empty: [makeRun({ minutes: 90 })], fan: [] }).refusals.some((r) => r.code === "no-negative-control"));
  assert.ok(evaluateCalibration({ empty: [makeRun({ minutes: 90 })], fan: [fanAfter({ minutes: 2 })] }).refusals.some((r) => r.code === "no-negative-control"));
});

test("empty-vs-empty drift inside the soak refuses a recommendation", () => {
  const drifting = makeRun({ minutes: 90, drift: (b) => (b >= 270 ? 0.5 : 0) });   // the second half sits higher
  const ev = evaluateCalibration({ empty: [drifting], fan: [fanAfter()] });
  assert.ok(ev.refusals.some((r) => r.code === "drift"));
  assert.ok(ev.metrics.every((m) => m.candidate === null));
});

test("a held RSSI step inside the soak is a pooled-epochs refusal; a single-block flicker is not", () => {
  const stepped = makeRun({ minutes: 90, rssi: (b) => (b >= 200 ? -52 : -40) });
  assert.ok(evaluateCalibration({ empty: [stepped], fan: [fanAfter()] }).refusals.some((r) => r.code === "pooled-epochs"));
  const flicker = makeRun({ minutes: 90, rssi: (b) => (b === 200 ? -55 : -40) });
  assert.deepEqual(detectLinkSteps("1", flicker.nodes["1"]), []);
});

test("a frame-rate collapse inside the soak is a pooled-epochs refusal", () => {
  const collapsed = makeRun({ minutes: 90, fps: (b) => (b >= 300 ? 40 : 65) });
  const steps = detectLinkSteps("1", collapsed.nodes["1"]);
  assert.equal(steps.length, 1);
  assert.equal(steps[0].kind, "frame-rate");
  assert.ok(evaluateCalibration({ empty: [collapsed], fan: [fanAfter()] }).refusals.some((r) => r.code === "pooled-epochs"));
});

test("runs on different calendar days, or with a level change between them, are never pooled", () => {
  const nextDay = makeRun({ minutes: 50, start: DAY0 + 24 * 60 * MIN, seed: 3 });
  const ev = evaluateCalibration({ empty: [makeRun({ minutes: 50 }), nextDay], fan: [fanAfter({ start: DAY0 + 24 * 60 * MIN + 60 * MIN })] });
  assert.ok(ev.refusals.some((r) => r.code === "pooled-epochs" && r.detail.includes("calendar days")));
  const shifted = makeRun({ minutes: 50, start: DAY0 + 55 * MIN, seed: 3, rssi: () => -52 });
  const ev2 = evaluateCalibration({ empty: [makeRun({ minutes: 50 }), shifted], fan: [fanAfter({ start: DAY0 + 110 * MIN, rssi: () => -52 })] });
  assert.ok(ev2.refusals.some((r) => r.code === "pooled-epochs" && r.detail.includes("between consecutive runs")));
});

test("fan false alarms and occupied misses are reported separately from empty false alarms", () => {
  const loudFan = fanAfter({ base: 0.9 });
  const walking = makeRun({ label: "occupied", start: DAY0 + 115 * MIN, minutes: 10, seed: 5, base: 0.9 });
  const ev = evaluateCalibration({ empty: [makeRun({ minutes: 90 })], fan: [loudFan], occupied: [walking] });
  const m = ev.metrics.find((x) => x.metric === "motion.fused")!;
  assert.ok((m.fanFalseAlarmsPerHour ?? 0) > 100, "a fan far above the candidate shows up as false alarms/hour");
  assert.equal(m.occupiedMissRate, 0);
  assert.ok(m.heldOutFalseAlarmsPerHour !== null && m.heldOutFalseAlarmsPerHour < 20);
});

test("the CLI --evaluate mode reads run files, exits 0 with a candidate for good runs and 3 with a refusal for a short soak, and writes nothing", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cal-soak-"));
  const write = (name: string, run: CalibrationRun) => {
    const p = path.join(dir, name);
    fs.writeFileSync(p, JSON.stringify(run));
    return p;
  };
  const run = (args: string[]) =>
    spawnSync(process.execPath, ["--import", "tsx", "scripts/calibrate-threshold.ts", "--evaluate", ...args], { encoding: "utf-8" });
  try {
    const good = run(["--empty", write("e.json", makeRun({ minutes: 90 })), "--fan", write("f.json", fanAfter())]);
    assert.equal(good.status, 0, good.stdout + good.stderr);
    assert.ok(good.stdout.includes("motion.fused") && !good.stdout.includes("REFUSED"));
    const short = run(["--empty", write("s.json", makeRun({ minutes: 20 })), "--fan", path.join(dir, "f.json")]);
    assert.equal(short.status, 3);
    assert.ok(short.stdout.includes("[soak-too-short]"));
    assert.deepEqual(fs.readdirSync(dir).sort(), ["e.json", "f.json", "s.json"], "evaluation must not write any file");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a live run shorter than the minimum refuses to start (exit 2) before binding any socket", () => {
  const r = spawnSync(process.execPath, ["--import", "tsx", "scripts/calibrate-threshold.ts", "--label", "empty", "--seconds", "120"], { encoding: "utf-8" });
  assert.equal(r.status, 2);
  assert.ok(r.stderr.includes("Refusing to start"));
});

test("the calibration code never imports or calls anything that writes a setting", () => {
  for (const file of ["scripts/accuracy/calibration-soak.ts", "scripts/calibrate-threshold.ts"]) {
    const src = fs.readFileSync(file, "utf-8");
    assert.ok(!/runtime-settings|writeFileSync\([^)]*settings|updateSettings|setRuntimeSetting/.test(src), `${file} must not touch runtime settings`);
  }
});
