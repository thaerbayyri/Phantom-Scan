import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import path from "path";
import { FusedPositionKalman } from "./fused-position-kalman";

// Same session used to derive this filter's Q/R starting values (see the
// class docstring) — a real live 4-node fused_room recording, not synthetic.
const SESSION_FILE = "test_2026-09-08T13-52-34-674Z.csv";

function loadSessionXZ(fileName: string): { ts: number; x: number; z: number }[] {
  const raw = fs.readFileSync(path.resolve("data", "sessions", fileName), "utf-8");
  const lines = raw.split("\n").slice(1); // drop the "# phantom_session_meta" comment line
  const header = lines[0].split(",");
  const tsIdx = header.indexOf("timestamp");
  const xIdx = header.indexOf("x_disp_m");
  const zIdx = header.indexOf("z_disp_m");
  const points: { ts: number; x: number; z: number }[] = [];
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const cols = line.split(",");
    const ts = Number.parseInt(cols[tsIdx], 10);
    const x = Number.parseFloat(cols[xIdx]);
    const z = Number.parseFloat(cols[zIdx]);
    if (Number.isFinite(ts) && Number.isFinite(x) && Number.isFinite(z)) {
      points.push({ ts, x, z });
    }
  }
  return points;
}

function stdev(vals: number[]): number {
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  return Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length);
}

// ── FusedPositionKalman ──────────────────────────────────────────────

test("FusedPositionKalman: repeated measurement at a fixed point converges near that point", () => {
  const kf = new FusedPositionKalman();
  let t = 0;
  for (let i = 0; i < 50; i++) {
    t += 50;
    kf.predict(t);
    kf.update([2, 3]);
  }
  const state = kf.getState();
  assert.ok(Math.abs(state.x - 2) < 0.2, `x ${state.x} should converge near 2`);
  assert.ok(Math.abs(state.z - 3) < 0.2, `z ${state.z} should converge near 3`);
});

test("FusedPositionKalman: starts at the origin with zero velocity before any update", () => {
  const kf = new FusedPositionKalman();
  assert.deepEqual(kf.getState(), { x: 0, z: 0, vx: 0, vz: 0 });
});

test("FusedPositionKalman: a single predict after a large gap is bounded by the dt ceiling, not the full elapsed time", () => {
  const kf = new FusedPositionKalman();
  let t = 0;
  let x = 0;
  for (let i = 0; i < 40; i++) {
    t += 50;
    x += 0.05; // ~1 m/s steady motion along x
    kf.predict(t);
    kf.update([x, 0]);
  }
  const before = kf.getState();
  assert.ok(before.vx > 0.5, `sanity: filter should have picked up nonzero x velocity, got ${before.vx}`);

  // A real 5s gap (observed real max across live 4-node sessions was
  // ~0.83s) must only extrapolate MAX_DT (0.3s) worth of motion, not the
  // full 5s -- otherwise one stale-drop gap would fling the marker far
  // ahead of the real target.
  kf.predict(t + 5000);
  const after = kf.getState();
  const displacedM = after.x - before.x;
  assert.ok(
    displacedM < before.vx * 0.5,
    `a single predict after a 5s gap displaced x by ${displacedM}m -- should stay near MAX_DT*velocity (~0.3*${before.vx}), not extrapolate the full 5s`,
  );
});

test("FusedPositionKalman: a single wild outlier tick is gated out, not applied", () => {
  const kf = new FusedPositionKalman();
  let t = 0;
  for (let i = 0; i < 30; i++) {
    t += 50;
    kf.predict(t);
    kf.update([1, 1]);
  }
  const before = kf.getState();

  t += 50;
  kf.predict(t);
  kf.update([50, 50]); // wild single-tick spike, far outside the innovation gate
  const after = kf.getState();
  assert.ok(
    Math.hypot(after.x - before.x, after.z - before.z) < 1,
    `a single wild outlier must be gated out, not yank the filtered position toward it (moved to x=${after.x} z=${after.z})`,
  );

  // The filter must still be trackable afterward -- feeding the real point
  // again a few more times must re-converge, proving the gate doesn't get
  // permanently stuck.
  for (let i = 0; i < 20; i++) {
    t += 50;
    kf.predict(t);
    kf.update([1, 1]);
  }
  const recovered = kf.getState();
  assert.ok(Math.abs(recovered.x - 1) < 0.2 && Math.abs(recovered.z - 1) < 0.2);
});

test("FusedPositionKalman: getState always returns finite numbers (no NaN/Infinity propagation)", () => {
  const kf = new FusedPositionKalman();
  let t = 0;
  for (let i = 0; i < 10; i++) {
    t += 50;
    kf.predict(t);
    kf.update([i * 0.1, i * 0.05]);
  }
  const state = kf.getState();
  for (const v of Object.values(state)) {
    assert.ok(Number.isFinite(v), `state value ${v} must be finite`);
  }
});

test("FusedPositionKalman: reset returns to the zero-velocity origin state", () => {
  const kf = new FusedPositionKalman();
  let t = 0;
  for (let i = 0; i < 10; i++) {
    t += 50;
    kf.predict(t);
    kf.update([5, 5]);
  }
  kf.reset();
  assert.deepEqual(kf.getState(), { x: 0, z: 0, vx: 0, vz: 0 });
});

// ── Real recorded 4-node fused_room data ────────────────────────────────
// Replays actual x_disp_m/z_disp_m (and real inter-tick timestamps) from a
// real live 4-node session -- not synthetic -- through the filter, per the
// same Q/R this class's docstring derives from this exact session.

test("FusedPositionKalman: filtering the real recorded session reduces mean tick-to-tick jitter on both axes", () => {
  const points = loadSessionXZ(SESSION_FILE);
  assert.ok(points.length > 100, "sanity: session fixture must have loaded real rows");

  const kf = new FusedPositionKalman();
  const filteredXs: number[] = [];
  const filteredZs: number[] = [];
  for (const p of points) {
    kf.predict(p.ts);
    kf.update([p.x, p.z]);
    const s = kf.getState();
    filteredXs.push(s.x);
    filteredZs.push(s.z);
  }

  const meanAbsDelta = (vals: number[]) => {
    let sum = 0;
    for (let i = 1; i < vals.length; i++) sum += Math.abs(vals[i] - vals[i - 1]);
    return sum / (vals.length - 1);
  };
  const rawXJitter = meanAbsDelta(points.map((p) => p.x));
  const rawZJitter = meanAbsDelta(points.map((p) => p.z));
  const filteredXJitter = meanAbsDelta(filteredXs);
  const filteredZJitter = meanAbsDelta(filteredZs);

  assert.ok(
    filteredXJitter < rawXJitter,
    `filtered x mean tick-to-tick jitter ${filteredXJitter} should be lower than raw ${rawXJitter}`,
  );
  assert.ok(
    filteredZJitter < rawZJitter,
    `filtered z mean tick-to-tick jitter ${filteredZJitter} should be lower than raw ${rawZJitter}`,
  );
});

test("FusedPositionKalman: filtering the real recorded session tracks the raw track tightly, except for rare gated outlier ticks", () => {
  // A handful of the raw recording's own ticks are themselves anomalous
  // (one such tick, verified separately, has an out-of-order timestamp and
  // a physically implausible ~0.5m single-tick jump — a sensor/parse
  // glitch, not real human motion) and are correctly gated out rather than
  // followed; this test checks overall tracking fidelity via median/p95
  // deviation, not worst-single-tick deviation, since a small number of
  // legitimately-rejected outliers are the gate's intended behavior, not a
  // lag failure.
  const points = loadSessionXZ(SESSION_FILE);
  const kf = new FusedPositionKalman();
  const deviations: number[] = [];
  for (const p of points) {
    kf.predict(p.ts);
    kf.update([p.x, p.z]);
    const s = kf.getState();
    deviations.push(Math.hypot(s.x - p.x, s.z - p.z));
  }
  deviations.sort((a, b) => a - b);
  const median = deviations[Math.floor(deviations.length / 2)];
  const p95 = deviations[Math.floor(deviations.length * 0.95)];

  assert.ok(median < 0.05, `median deviation from raw ${median}m should stay tight (real data: ~0.0024m)`);
  assert.ok(p95 < 0.1, `p95 deviation from raw ${p95}m should stay bounded (real data: ~0.021m)`);
});
