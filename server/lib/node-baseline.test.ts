import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_TIER_THRESHOLDS,
  NodeBaselineTracker,
  RoomPresence,
  tierAtLeast,
} from "./node-baseline";

/** Feed `raw` for `seconds` at `hz`, returning the last update result. */
function feed(tracker: NodeBaselineTracker, raw: number, seconds: number, hz: number, startMs: number, freeze = false) {
  const stepMs = 1000 / hz;
  let t = startMs;
  let last = tracker.update(raw, t, freeze);
  const end = startMs + seconds * 1000;
  while (t + stepMs <= end + 1e-6) {
    t += stepMs;
    last = tracker.update(raw, t, freeze);
  }
  return { last, endMs: t };
}

test("smoothing is time-constant based: same response after 0.6 s at 20 Hz and 50 Hz", () => {
  const settle = (hz: number) => {
    const tr = new NodeBaselineTracker();
    const warm = feed(tr, 0.1, 6, hz, 0); // past warm-up, baseline ≈ 0.1
    return feed(tr, 0.3, 0.6, hz, warm.endMs).last.smoothed;
  };
  const a = settle(20);
  const b = settle(50);
  assert.ok(Math.abs(a - b) < 0.01, `20 Hz ${a} vs 50 Hz ${b}`);
});

test("warm-up learns the empty-room level quickly, then rise ≈ 0 and tier absent", () => {
  const tr = new NodeBaselineTracker();
  const { last } = feed(tr, 0.12, 6, 20, 0);
  assert.ok(Math.abs(last.baseline - 0.12) < 0.005, `baseline ${last.baseline}`);
  assert.ok(last.rise < 0.05, `rise ${last.rise}`);
  assert.equal(last.tier, "absent");
});

test("motion well above the node's own baseline reaches present_moving only after the 0.4 s debounce", () => {
  const tr = new NodeBaselineTracker();
  const warm = feed(tr, 0.1, 6, 20, 0);
  const early = feed(tr, 0.3, 0.3, 20, warm.endMs);
  assert.equal(early.last.tier, "absent", "must not switch before the debounce elapses");
  const later = feed(tr, 0.3, 1.5, 20, early.endMs);
  assert.ok(tierAtLeast(later.last.tier, "present_moving"), `tier ${later.last.tier}`);
});

test("rise is gain-invariant: a node with 3x amplitude gain produces the same rise", () => {
  const run = (scale: number) => {
    const tr = new NodeBaselineTracker();
    const warm = feed(tr, 0.1 * scale, 6, 20, 0);
    return feed(tr, 0.2 * scale, 3, 20, warm.endMs).last.rise;
  };
  assert.ok(Math.abs(run(1) - run(3)) < 1e-9);
});

test("baseline does not absorb a person while frozen (target held), so rise persists", () => {
  const tr = new NodeBaselineTracker();
  const warm = feed(tr, 0.1, 6, 20, 0);
  const frozen = feed(tr, 0.16, 60, 20, warm.endMs, true);
  assert.ok(frozen.last.baseline < 0.105, `baseline crept to ${frozen.last.baseline}`);
  assert.ok(frozen.last.rise > 0.4, `rise ${frozen.last.rise}`);
});

test("without freeze the slow baseline eventually adapts to a new static level", () => {
  const tr = new NodeBaselineTracker();
  const warm = feed(tr, 0.1, 6, 20, 0);
  // A step that stays within the "not a spike" margin of smoothed once settled.
  const adapted = feed(tr, 0.104, 200, 20, warm.endMs);
  assert.ok(Math.abs(adapted.last.baseline - 0.104) < 0.002, `baseline ${adapted.last.baseline}`);
});

test("freeze is bounded: after the max freeze time the baseline adapts again", () => {
  const tr = new NodeBaselineTracker({ maxFreezeMs: 10_000 });
  const warm = feed(tr, 0.1, 6, 20, 0);
  const longFrozen = feed(tr, 0.102, 200, 20, warm.endMs, true);
  assert.ok(Math.abs(longFrozen.last.baseline - 0.102) < 0.002, `baseline ${longFrozen.last.baseline}`);
});

test("spikes above the smoothed level are excluded from the baseline update", () => {
  const tr = new NodeBaselineTracker();
  const warm = feed(tr, 0.1, 6, 20, 0);
  let t = warm.endMs;
  for (let i = 0; i < 400; i++) {
    t += 50;
    tr.update(i % 2 === 0 ? 0.1 : 0.5, t, false); // alternating spikes
  }
  const r = tr.update(0.1, t + 50, false);
  assert.ok(r.baseline < 0.115, `spikes leaked into baseline: ${r.baseline}`);
});

test("default tier thresholds are ordered still < moving < active", () => {
  const { still, moving, active } = DEFAULT_TIER_THRESHOLDS;
  assert.ok(still > 0 && still < moving && moving < active);
});

test("room presence upgrades immediately but holds a downgrade for 1.5 s", () => {
  const room = new RoomPresence();
  assert.equal(room.update(["absent", "present_moving"], 0), "present_moving");
  assert.equal(room.update(["absent", "absent"], 1000), "present_moving", "downgrade must be held");
  assert.equal(room.update(["absent", "absent"], 1600), "absent");
  assert.equal(room.update(["active"], 1650), "active");
});

test("excess is the absolute rise above baseline, comparable across nodes with different baselines", () => {
  const quiet = new NodeBaselineTracker(); // empty-room level 0.05
  const noisy = new NodeBaselineTracker(); // empty-room level 0.20
  const q = feed(quiet, 0.05, 6, 20, 0);
  const n = feed(noisy, 0.2, 6, 20, 0);
  // The same absolute disturbance (+0.10) hits both nodes.
  const qd = feed(quiet, 0.15, 3, 20, q.endMs).last;
  const nd = feed(noisy, 0.3, 3, 20, n.endMs).last;
  assert.ok(Math.abs(qd.excess - nd.excess) < 0.01, `excess ${qd.excess} vs ${nd.excess}`);
  // The RELATIVE rise differs 4x — which is why it must not weight position.
  assert.ok(qd.rise > 3 * nd.rise, `rise ${qd.rise} vs ${nd.rise}`);
});

test("excess is never negative and is ~0 in a settled empty room", () => {
  const tr = new NodeBaselineTracker();
  const { last } = feed(tr, 0.1, 8, 20, 0);
  assert.ok(last.excess >= 0 && last.excess < 0.01, `excess ${last.excess}`);
});

// ── noise-aware tiers (test_4 scan: a noisy empty room read as occupied) ────

/** Deterministic pseudo-noise: baseline * (1 ± amplitude), mean-preserving. */
function noisy(tracker: NodeBaselineTracker, level: number, amplitude: number, seconds: number, hz: number, startMs: number, seed = 1) {
  let s = seed;
  const rnd = () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296) * 2 - 1;
  const stepMs = 1000 / hz;
  let t = startMs;
  let last = tracker.update(level, t, false);
  const tiers: string[] = [];
  const end = startMs + seconds * 1000;
  while (t + stepMs <= end + 1e-6) {
    t += stepMs;
    last = tracker.update(level * (1 + amplitude * rnd()), t, false);
    tiers.push(last.tier);
  }
  return { last, endMs: t, tiers };
}

test("a noisy but empty room stays absent: the baseline must not sit at the lower noise edge", () => {
  const tr = new NodeBaselineTracker();
  const warm = noisy(tr, 0.18, 0.35, 40, 20, 0);
  const steady = noisy(tr, 0.18, 0.35, 120, 20, warm.endMs, 7);
  const present = steady.tiers.filter((t) => t !== "absent").length / steady.tiers.length;
  assert.ok(present < 0.05, `empty noisy room reads present ${(present * 100).toFixed(1)}% of the time`);
  assert.ok(Math.abs(steady.last.baseline - 0.18) < 0.03, `baseline ${steady.last.baseline} should track the noise MEAN`);
});

test("a genuine sustained rise well above the noise is still detected", () => {
  const tr = new NodeBaselineTracker();
  const warm = noisy(tr, 0.18, 0.2, 40, 20, 0);
  const up = noisy(tr, 0.3, 0.2, 6, 20, warm.endMs, 3);
  assert.ok(tierAtLeast(up.last.tier, "present_moving"), `tier ${up.last.tier}, z=${up.last.z}`);
  assert.ok(up.last.z > 3, `z ${up.last.z}`);
});

test("z is the excess in units of the node's own empty-room fluctuation", () => {
  const quiet = new NodeBaselineTracker();
  const loud = new NodeBaselineTracker();
  const q = noisy(quiet, 0.18, 0.05, 40, 20, 0);
  const l = noisy(loud, 0.18, 0.5, 40, 20, 0);
  const qd = noisy(quiet, 0.21, 0.05, 4, 20, q.endMs, 5).last;
  const ld = noisy(loud, 0.21, 0.5, 4, 20, l.endMs, 5).last;
  assert.ok(qd.z > 3 * ld.z, `the same +0.03 is far more significant on the quiet node: ${qd.z} vs ${ld.z}`);
});
