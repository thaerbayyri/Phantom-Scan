/**
 * Calibration soak analysis (PS-FIX-11). Pure functions: no sockets, no files, no settings. `scripts/calibrate-threshold.ts` collects
 * runs with `BlockAccumulator`; `evaluateCalibration` decides whether a recommendation may be printed at all.
 *
 * Rules (each refusal is reported by name; a recommendation is printed ONLY when there is none):
 *   soak-too-short      empty soak shorter than minSoakMin (default 60 min)
 *   no-negative-control no fan run, or one shorter than minFanMin (default 5 min)
 *   pooled-epochs       the empty/fan runs span a link-state change (held RSSI step >= 6 dB or frame-rate collapse <= 0.7x, between
 *                       or inside runs) or more than one calendar day: scores from different link states must not be pooled
 *   drift               empty-vs-empty control: first half vs second half of the empty soak separates (symmetric AUC upper bound > 0.65)
 *   too-few-blocks      fewer than MIN_HELD_OUT_BLOCKS held-out empty blocks for a metric
 *
 * Statistic: per metric, the MAXIMUM inside each 10 s block (a false alarm needs only one sample above the threshold, so the block
 * maximum is the unit that matters). Percentiles and false alarms per hour are computed on HELD-OUT empty blocks (the second half in
 * time); the candidate threshold is chosen on the first half only. False alarms/hour and misses are reported separately; misses need
 * an occupied run and are `null` ("[TO BE MEASURED]") without one. The link-state rule here is a COARSER, conservative version of
 * scripts/presence_eval/epochs.py (10 s blocks, 20 s hold) and was chosen post hoc; it refuses, it never splits.
 */
import { blockBootstrapAuc } from "./auc-bootstrap";

export const BLOCK_S = 10;
export const DEFAULT_MIN_SOAK_MIN = 60;
export const DEFAULT_MIN_FAN_MIN = 5;
export const DEFAULT_TARGET_FALSE_ALARMS_PER_HOUR = 1;
export const DRIFT_SYMMETRIC_UPPER_BOUND = 0.65;
export const LINK_STEP_DB = 6;
export const RATE_COLLAPSE = 0.7;
export const MIN_BASELINE_FPS = 20;
export const PRE_BLOCKS = 6;
export const HOLD_BLOCKS = 2;
export const MIN_HELD_OUT_BLOCKS = 100;
export const PERCENTILES = [0.5, 0.9, 0.95, 0.99] as const;
const BOOTSTRAP_BLOCK = 6;   // 60 s of consecutive 10 s block maxima

export type RunLabel = "empty" | "fan" | "occupied";
export type Refusal = "soak-too-short" | "no-negative-control" | "pooled-epochs" | "drift" | "too-few-blocks";

export interface NodeBlocks {
  /** Median RSSI per complete 10 s block; null when no frame arrived. */
  rssiMedian: (number | null)[];
  /** Frames per complete 10 s block. */
  frames: number[];
}

export interface CalibrationRun {
  schema: 1;
  label: RunLabel;
  startedAtMs: number;
  blockS: number;
  /** Per metric ("motion.fused", "motion.n1", "roomZ", ...) the maximum in each complete 10 s block; null when no sample fell in it. */
  metrics: Record<string, (number | null)[]>;
  nodes: Record<string, NodeBlocks>;
  provenance?: Record<string, string>;
}

export function medianOf(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Collects samples and frames into 10 s blocks relative to `startedAtMs`; the incomplete last block is dropped. */
export class BlockAccumulator {
  private readonly maxima = new Map<string, Map<number, number>>();
  private readonly rssi = new Map<number, Map<number, number[]>>();
  private lastBlock = -1;

  constructor(private readonly label: RunLabel, private readonly startedAtMs: number) {}

  private blockOf(tMs: number): number {
    return Math.floor((tMs - this.startedAtMs) / (BLOCK_S * 1000));
  }

  addSample(metric: string, tMs: number, value: number): void {
    const b = this.blockOf(tMs);
    if (b < 0 || !Number.isFinite(value)) return;
    const m = this.maxima.get(metric) ?? new Map<number, number>();
    m.set(b, Math.max(m.get(b) ?? -Infinity, value));
    this.maxima.set(metric, m);
    this.lastBlock = Math.max(this.lastBlock, b);
  }

  addFrame(nodeId: number, tMs: number, rssiDbm: number): void {
    const b = this.blockOf(tMs);
    if (b < 0) return;
    const m = this.rssi.get(nodeId) ?? new Map<number, number[]>();
    const list = m.get(b) ?? [];
    list.push(rssiDbm);
    m.set(b, list);
    this.rssi.set(nodeId, m);
    this.lastBlock = Math.max(this.lastBlock, b);
  }

  finish(provenance?: Record<string, string>): CalibrationRun {
    const complete = Math.max(0, this.lastBlock); // blocks 0..lastBlock-1 are complete
    const range = Array.from({ length: complete }, (_, i) => i);
    const metrics: Record<string, (number | null)[]> = {};
    for (const [name, m] of Array.from(this.maxima.entries())) metrics[name] = range.map((i) => m.get(i) ?? null);
    const nodes: Record<string, NodeBlocks> = {};
    for (const [id, m] of Array.from(this.rssi.entries())) {
      nodes[String(id)] = { rssiMedian: range.map((i) => medianOf(m.get(i) ?? [])), frames: range.map((i) => (m.get(i) ?? []).length) };
    }
    return { schema: 1, label: this.label, startedAtMs: this.startedAtMs, blockS: BLOCK_S, metrics, nodes, provenance };
  }
}

export function runBlocks(run: CalibrationRun): number {
  return Math.max(0, ...Object.values(run.metrics).map((v) => v.length), ...Object.values(run.nodes).map((n) => n.frames.length));
}

export interface LinkStep {
  node: string;
  atBlock: number;
  kind: "rssi" | "frame-rate";
  detail: string;
}

/** Held RSSI steps and frame-rate collapses inside one node's block series (conservative: any one is a refusal). */
export function detectLinkSteps(node: string, nb: NodeBlocks): LinkStep[] {
  const out: LinkStep[] = [];
  const n = nb.frames.length;
  let i = PRE_BLOCKS;
  while (i + HOLD_BLOCKS <= n) {
    const preRssi = medianOf(nb.rssiMedian.slice(i - PRE_BLOCKS, i).filter((v): v is number => v !== null));
    const hold = nb.rssiMedian.slice(i, i + HOLD_BLOCKS);
    const preFps = (medianOf(nb.frames.slice(i - PRE_BLOCKS, i)) ?? 0) / BLOCK_S;
    const holdFps = nb.frames.slice(i, i + HOLD_BLOCKS).map((f) => f / BLOCK_S);
    let hit: LinkStep | null = null;
    if (preRssi !== null && hold.every((v) => v !== null && Math.abs(v - preRssi) >= LINK_STEP_DB && Math.sign(v - preRssi) === Math.sign((hold[0] as number) - preRssi))) {
      hit = { node, atBlock: i, kind: "rssi", detail: `median RSSI ${preRssi.toFixed(1)} -> ${(medianOf(hold as number[]) as number).toFixed(1)} dBm held ${HOLD_BLOCKS * BLOCK_S} s` };
    } else if (preFps >= MIN_BASELINE_FPS && holdFps.every((f) => f <= RATE_COLLAPSE * preFps)) {
      hit = { node, atBlock: i, kind: "frame-rate", detail: `frame rate ${preFps.toFixed(1)} -> ${(medianOf(holdFps) as number).toFixed(1)} fps held ${HOLD_BLOCKS * BLOCK_S} s` };
    }
    if (hit) {
      out.push(hit);
      i += PRE_BLOCKS;   // let the new level become the baseline, otherwise one persistent step is reported again
    } else {
      i += 1;
    }
  }
  return out;
}

function localDay(ms: number): string {
  const d = new Date(ms);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/** Why these runs must not be pooled; [] when they look like one link state. */
export function poolingProblems(runs: readonly CalibrationRun[]): string[] {
  const problems: string[] = [];
  const ordered = [...runs].sort((a, b) => a.startedAtMs - b.startedAtMs);
  for (const r of ordered) {
    for (const [id, nb] of Object.entries(r.nodes)) {
      for (const s of detectLinkSteps(id, nb)) problems.push(`${r.label} run @${new Date(r.startedAtMs).toISOString()} node ${id}: ${s.kind} step at block ${s.atBlock} (${s.detail})`);
    }
  }
  for (let k = 1; k < ordered.length; k++) {
    const a = ordered[k - 1];
    const b = ordered[k];
    if (localDay(a.startedAtMs) !== localDay(b.startedAtMs)) problems.push(`runs on different calendar days (${localDay(a.startedAtMs)} vs ${localDay(b.startedAtMs)}): nodes may have been moved`);
    for (const id of Object.keys(a.nodes)) {
      const nb = b.nodes[id];
      if (!nb) continue;
      const pre = medianOf(a.nodes[id].rssiMedian.slice(-PRE_BLOCKS).filter((v): v is number => v !== null));
      const post = medianOf(nb.rssiMedian.slice(0, PRE_BLOCKS).filter((v): v is number => v !== null));
      if (pre !== null && post !== null && Math.abs(post - pre) >= LINK_STEP_DB) problems.push(`node ${id}: median RSSI ${pre.toFixed(1)} -> ${post.toFixed(1)} dBm between consecutive runs`);
      const fpsA = (medianOf(a.nodes[id].frames.slice(-PRE_BLOCKS)) ?? 0) / BLOCK_S;
      const fpsB = (medianOf(nb.frames.slice(0, PRE_BLOCKS)) ?? 0) / BLOCK_S;
      if (fpsA >= MIN_BASELINE_FPS && fpsB <= RATE_COLLAPSE * fpsA) problems.push(`node ${id}: frame rate ${fpsA.toFixed(1)} -> ${fpsB.toFixed(1)} fps between consecutive runs`);
    }
  }
  return problems;
}

function concat(runs: readonly CalibrationRun[], metric: string): number[] {
  const out: number[] = [];
  for (const r of [...runs].sort((a, b) => a.startedAtMs - b.startedAtMs)) for (const v of r.metrics[metric] ?? []) if (v !== null) out.push(v);
  return out;
}

export function quantile(sorted: readonly number[], q: number): number | null {
  if (sorted.length === 0) return null;
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1))];
}

export interface MetricResult {
  metric: string;
  calibrationBlocks: number;
  heldOutBlocks: number;
  /** Percentiles of the HELD-OUT empty block maxima. */
  heldOutPercentiles: Record<string, number | null>;
  driftAuc: { auc: number | null; lo: number | null; hi: number | null; symmetricUpperBound: number | null; passes: boolean | null };
  /** Smallest value that leaves <= target false alarms/hour on the CALIBRATION half; null when refused. */
  candidate: number | null;
  /** Held-out empty false alarms per hour at `candidate`; fan false alarms per hour at `candidate`. */
  heldOutFalseAlarmsPerHour: number | null;
  fanFalseAlarmsPerHour: number | null;
  /** Share of occupied blocks whose maximum stays below `candidate`; null = no occupied run ("[TO BE MEASURED]"). */
  occupiedMissRate: number | null;
}

export interface CalibrationEvaluation {
  refusals: { code: Refusal; detail: string }[];
  /** Always false: this module never writes a setting. */
  writesSettings: false;
  recommendationAllowed: boolean;
  metrics: MetricResult[];
}

export interface EvaluateInput {
  empty: readonly CalibrationRun[];
  fan: readonly CalibrationRun[];
  occupied?: readonly CalibrationRun[];
}

export interface EvaluateOptions {
  minSoakMin?: number;
  minFanMin?: number;
  targetFalseAlarmsPerHour?: number;
}

function blocksToHours(n: number): number {
  return (n * BLOCK_S) / 3600;
}

function falseAlarmsPerHour(blocks: readonly number[], threshold: number): number | null {
  if (blocks.length === 0) return null;
  return blocks.filter((v) => v > threshold).length / blocksToHours(blocks.length);
}

function evaluateMetric(metric: string, input: EvaluateInput, target: number): MetricResult {
  const emptyAll = concat(input.empty, metric);
  const half = Math.floor(emptyAll.length / 2);
  const calib = emptyAll.slice(0, half);
  const held = emptyAll.slice(half);
  const ci = blockBootstrapAuc(held, calib, { block: BOOTSTRAP_BLOCK });
  const sym = ci.lo === null || ci.hi === null ? null : Math.max(ci.hi, 1 - ci.lo);
  const driftAuc = { auc: ci.auc, lo: ci.lo, hi: ci.hi, symmetricUpperBound: sym, passes: sym === null ? null : sym <= DRIFT_SYMMETRIC_UPPER_BOUND };
  const sorted = [...held].sort((a, b) => a - b);
  const heldOutPercentiles: Record<string, number | null> = {};
  for (const q of PERCENTILES) heldOutPercentiles[`p${Math.round(q * 100)}`] = quantile(sorted, q);
  const base = { metric, calibrationBlocks: calib.length, heldOutBlocks: held.length, heldOutPercentiles, driftAuc };
  if (calib.length === 0) return { ...base, candidate: null, heldOutFalseAlarmsPerHour: null, fanFalseAlarmsPerHour: null, occupiedMissRate: null };
  const calibSorted = [...calib].sort((a, b) => a - b);
  const allowedAbove = Math.floor(target * blocksToHours(calib.length));
  const candidate = calibSorted[Math.max(0, calibSorted.length - 1 - allowedAbove)];
  const fan = concat(input.fan, metric);
  const occ = concat(input.occupied ?? [], metric);
  return {
    ...base,
    candidate,
    heldOutFalseAlarmsPerHour: falseAlarmsPerHour(held, candidate),
    fanFalseAlarmsPerHour: falseAlarmsPerHour(fan, candidate),
    occupiedMissRate: occ.length === 0 ? null : occ.filter((v) => v <= candidate).length / occ.length,
  };
}

export function evaluateCalibration(input: EvaluateInput, opts: EvaluateOptions = {}): CalibrationEvaluation {
  const minSoakMin = opts.minSoakMin ?? DEFAULT_MIN_SOAK_MIN;
  const minFanMin = opts.minFanMin ?? DEFAULT_MIN_FAN_MIN;
  const target = opts.targetFalseAlarmsPerHour ?? DEFAULT_TARGET_FALSE_ALARMS_PER_HOUR;
  const refusals: { code: Refusal; detail: string }[] = [];
  const emptyMin = (input.empty.reduce((s, r) => s + runBlocks(r), 0) * BLOCK_S) / 60;
  const fanMin = (input.fan.reduce((s, r) => s + runBlocks(r), 0) * BLOCK_S) / 60;
  if (emptyMin < minSoakMin) refusals.push({ code: "soak-too-short", detail: `empty soak ${emptyMin.toFixed(1)} min < required ${minSoakMin} min` });
  if (input.fan.length === 0 || fanMin < minFanMin) refusals.push({ code: "no-negative-control", detail: `fan (negative control) ${fanMin.toFixed(1)} min < required ${minFanMin} min` });
  const pooled = poolingProblems([...input.empty, ...input.fan]);
  if (pooled.length > 0) refusals.push({ code: "pooled-epochs", detail: pooled.join("; ") });
  const names = Object.keys(input.empty[0]?.metrics ?? {}).sort();
  const results = names.map((m) => evaluateMetric(m, input, target));
  const tooFew = results.filter((r) => r.heldOutBlocks < MIN_HELD_OUT_BLOCKS).map((r) => `${r.metric} (${r.heldOutBlocks})`);
  if (tooFew.length > 0) refusals.push({ code: "too-few-blocks", detail: `held-out empty blocks < ${MIN_HELD_OUT_BLOCKS}: ${tooFew.join(", ")}` });
  const drifting = results.filter((r) => r.driftAuc.passes === false).map((r) => `${r.metric} (symmetric upper bound ${r.driftAuc.symmetricUpperBound?.toFixed(2)})`);
  if (drifting.length > 0) refusals.push({ code: "drift", detail: `empty-vs-empty control separates the two halves: ${drifting.join(", ")}` });
  const allowed = refusals.length === 0;
  const metrics = allowed ? results : results.map((r) => ({ ...r, candidate: null, heldOutFalseAlarmsPerHour: null, fanFalseAlarmsPerHour: null, occupiedMissRate: null }));
  return { refusals, writesSettings: false, recommendationAllowed: allowed, metrics };
}

const fmt = (v: number | null, d = 3): string => (v === null ? "n/a" : v.toFixed(d));

export function renderEvaluation(ev: CalibrationEvaluation): string {
  const lines: string[] = ["=== Calibration evaluation (offline; nothing is written, no setting is changed) ==="];
  if (ev.refusals.length > 0) {
    lines.push("", "REFUSED — no recommended value is printed:");
    for (const r of ev.refusals) lines.push(`  [${r.code}] ${r.detail}`);
  }
  lines.push("", "metric | calib blocks | held-out blocks | held-out p50 / p90 / p95 / p99 | drift AUC (sym. upper bound) | candidate | held-out FA/h | fan FA/h | occupied miss rate");
  for (const m of ev.metrics) {
    const p = m.heldOutPercentiles;
    lines.push(`${m.metric} | ${m.calibrationBlocks} | ${m.heldOutBlocks} | ${fmt(p.p50 ?? null)} / ${fmt(p.p90 ?? null)} / ${fmt(p.p95 ?? null)} / ${fmt(p.p99 ?? null)} | ${fmt(m.driftAuc.auc, 2)} (${fmt(m.driftAuc.symmetricUpperBound, 2)}) | ${ev.recommendationAllowed ? fmt(m.candidate, 4) : "refused"} | ${fmt(m.heldOutFalseAlarmsPerHour, 1)} | ${fmt(m.fanFalseAlarmsPerHour, 1)} | ${m.occupiedMissRate === null ? "[TO BE MEASURED]" : fmt(m.occupiedMissRate, 2)}`);
  }
  if (ev.recommendationAllowed) lines.push("", "A candidate is a number for Thaer to consider, not a setting: apply it only through the documented env/settings path, after a replay on both failure directions.");
  return lines.join("\n");
}
