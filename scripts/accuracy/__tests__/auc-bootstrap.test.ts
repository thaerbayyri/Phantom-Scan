import test from "node:test";
import assert from "node:assert/strict";
import { blockBootstrapAuc, mulberry32, rankAuc } from "../auc-bootstrap";

test("rankAuc matches hand-computed values, ties and the extremes", () => {
  assert.equal(rankAuc([1, 2, 3], [0, 2]), 0.75); // 4 wins + 1 tie (0.5) of 6 pairs, 1 loss
  assert.equal(rankAuc([2, 2, 2], [2, 2]), 0.5);
  assert.equal(rankAuc([5, 6], [1, 2, 3]), 1);
  assert.equal(rankAuc([1, 2, 3], [5, 6]), 0);
});

test("rankAuc equals the Python implementation on a vector with many ties (parity pinned)", () => {
  // scripts/presence_eval/stats.py auc([3,1,4,1,5,9,2,6],[2,7,1,8,2,8,1,8]) == 0.453125
  assert.equal(rankAuc([3, 1, 4, 1, 5, 9, 2, 6], [2, 7, 1, 8, 2, 8, 1, 8]), 0.453125);
});

test("rankAuc matches brute force on random data with forced ties", () => {
  const rand = mulberry32(7);
  const pos = Array.from({ length: 60 }, () => Math.round((rand() * 3 + 0.3) * 10) / 10);
  const neg = Array.from({ length: 80 }, () => Math.round(rand() * 3 * 10) / 10);
  let wins = 0;
  for (const p of pos) for (const n of neg) wins += p > n ? 1 : p === n ? 0.5 : 0;
  assert.ok(Math.abs((rankAuc(pos, neg) as number) - wins / (pos.length * neg.length)) < 1e-12);
});

test("an empty class gives null, never a fabricated number", () => {
  assert.equal(rankAuc([], [1]), null);
  assert.equal(rankAuc([1], []), null);
  assert.deepEqual(blockBootstrapAuc([], [1, 2], { block: 7 }), { auc: null, lo: null, hi: null, nPos: 0, nNeg: 2 });
});

test("bootstrap is deterministic for a fixed seed, differs across seeds, and brackets the point estimate", () => {
  const rand = mulberry32(5);
  const pos = Array.from({ length: 200 }, () => rand() + 0.4);
  const neg = Array.from({ length: 200 }, () => rand());
  const a = blockBootstrapAuc(pos, neg, { block: 7, nBoot: 200, seed: 42 });
  assert.deepEqual(a, blockBootstrapAuc(pos, neg, { block: 7, nBoot: 200, seed: 42 }));
  const c = blockBootstrapAuc(pos, neg, { block: 7, nBoot: 200, seed: 43 });
  assert.notDeepEqual([a.lo, a.hi], [c.lo, c.hi]);
  assert.ok((a.lo as number) <= (a.auc as number) && (a.auc as number) <= (a.hi as number));
});

test("block bootstrap is wider than an iid bootstrap on an autocorrelated series", () => {
  const rand = mulberry32(9);
  // stationary AR(1), phi = 0.95: strongly autocorrelated but the two classes overlap
  const walk = (n: number, shift: number) => {
    let s = 0;
    return Array.from({ length: n }, () => (s = 0.95 * s + (rand() - 0.5)) + shift);
  };
  const pos = walk(400, 0.3);
  const neg = walk(400, 0);
  const wide = blockBootstrapAuc(pos, neg, { block: 28, nBoot: 300, seed: 1 });
  const iid = blockBootstrapAuc(pos, neg, { block: 1, nBoot: 300, seed: 1 });
  assert.ok((wide.hi as number) - (wide.lo as number) > (iid.hi as number) - (iid.lo as number));
});
