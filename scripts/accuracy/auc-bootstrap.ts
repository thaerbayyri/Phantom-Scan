/**
 * Rank-based AUC and moving-block bootstrap confidence intervals (offline evaluation only).
 *
 * AUC = P(pos > neg) + 0.5 P(pos == neg); 0.5 is chance. Windows of one recording are strongly
 * autocorrelated, so the CI resamples contiguous BLOCKS (>= 10 s) separately inside each class with a
 * seeded PRNG: deterministic. A class with no samples gives `null`, never a fabricated 0 or 0.5.
 * Mirrors scripts/presence_eval/stats.py (same definitions; a parity vector is pinned in the test).
 */

/** Deterministic PRNG (mulberry32). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Mann-Whitney AUC with average ranks for ties, O(n log n). null if either class is empty. */
export function rankAuc(pos: readonly number[], neg: readonly number[]): number | null {
  const nP = pos.length;
  const nN = neg.length;
  if (nP === 0 || nN === 0) return null;
  const all = new Float64Array(nP + nN);
  const isPos = new Uint8Array(nP + nN);
  for (let i = 0; i < nP; i++) {
    all[i] = pos[i];
    isPos[i] = 1;
  }
  for (let i = 0; i < nN; i++) all[nP + i] = neg[i];
  const order = Array.from({ length: nP + nN }, (_, i) => i).sort((x, y) => all[x] - all[y]);
  let rankSumPos = 0;
  let i = 0;
  while (i < order.length) {
    let j = i;
    while (j + 1 < order.length && all[order[j + 1]] === all[order[i]]) j++;
    const avgRank = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) if (isPos[order[k]]) rankSumPos += avgRank;
    i = j + 1;
  }
  return (rankSumPos - (nP * (nP + 1)) / 2) / (nP * nN);
}

function blockResample(x: readonly number[], block: number, rand: () => number): number[] {
  const m = x.length;
  const b = Math.max(1, Math.min(block, m));
  const out: number[] = [];
  while (out.length < m) {
    const start = Math.floor(rand() * (m - b + 1));
    for (let k = 0; k < b && out.length < m; k++) out.push(x[start + k]);
  }
  return out;
}

export interface AucCi {
  auc: number | null;
  lo: number | null;
  hi: number | null;
  nPos: number;
  nNeg: number;
}

export function blockBootstrapAuc(
  pos: readonly number[],
  neg: readonly number[],
  opts: { block: number; nBoot?: number; seed?: number },
): AucCi {
  const auc = rankAuc(pos, neg);
  const base = { auc, nPos: pos.length, nNeg: neg.length };
  if (auc === null) return { ...base, lo: null, hi: null };
  const rand = mulberry32(opts.seed ?? 20261102);
  const nBoot = opts.nBoot ?? 500;
  const vals: number[] = [];
  for (let i = 0; i < nBoot; i++) {
    const a = rankAuc(blockResample(pos, opts.block, rand), blockResample(neg, opts.block, rand));
    if (a !== null) vals.push(a);
  }
  vals.sort((p, q) => p - q);
  const at = (q: number) => vals[Math.min(vals.length - 1, Math.max(0, Math.floor(q * (vals.length - 1))))];
  return { ...base, lo: at(0.025), hi: at(0.975) };
}
