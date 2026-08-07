/**
 * Item 5 (PhantomScan_Research_Gap_Analysis.md): first dedicated test file for
 * signal-processing.ts — previously zero coverage on this 980-line module.
 *
 * These are ALGORITHMIC/UNIT tests on synthetic, hand-constructed inputs
 * (same convention as tests/test_phantom_cross_node_correlation.py's
 * deterministic synthetic signals) — they validate the math, NOT hardware
 * behavior. Real-hardware validation remains tracked in REAL_TEST_REPORT.md.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  computeMUSICSpectrum,
  findSpectrumPeak,
  HampelFilter,
  MicroDopplerClassifier,
  PDPRanger,
  BackgroundSubtractor,
  MotionGate,
} from "./signal-processing";
import { fromPolar, type Complex } from "./complex";

// ── MUSIC AoA spectrum ──────────────────────────────────────────────────────

/** Ideal ULA steering samples for a plane wave from `angleDeg` (d = 0.5λ,
 * matching computeMUSICSpectrum's own element spacing). */
function steeringSamples(angleDeg: number, n: number): Complex[] {
  const theta = (angleDeg * Math.PI) / 180;
  const samples: Complex[] = [];
  for (let k = 0; k < n; k++) {
    samples.push(fromPolar(1, -2 * Math.PI * 0.5 * k * Math.sin(theta)));
  }
  return samples;
}

test("MUSIC: spectrum has the requested length and finite power at every bin", () => {
  const spectrum = computeMUSICSpectrum(steeringSamples(0, 6), -60, 60, 121, 1);
  assert.equal(spectrum.length, 121);
  for (const p of spectrum) {
    assert.ok(Number.isFinite(p.power), `power ${p.power} at angle ${p.angle} must be finite`);
  }
});

test("MUSIC: fewer than 3 samples returns an empty spectrum (guard clause)", () => {
  assert.deepEqual(computeMUSICSpectrum(steeringSamples(0, 2), -60, 60), []);
});

test("MUSIC: identical covariance input yields an identical spectrum (deterministic eigen start)", () => {
  const samples = steeringSamples(15, 5);
  const a = computeMUSICSpectrum(samples, -60, 60, 61, 1);
  const b = computeMUSICSpectrum(samples, -60, 60, 61, 1);
  assert.deepEqual(a, b, "the seeded LCG start vector must make output reproducible");
});

// ── PS-GAP-MUSIC-001 regression tests (defect FIXED 2026-08-07) ─────────────
// The original defect: a single-vector input made R = x*x^H rank 1; the
// eigen-deflation `norm < 1e-10` guard then silently left the "noise"
// eigenvectors as raw input-independent seed vectors, so the whole spectrum
// was bit-for-bit identical for ANY input. Fixed by (1) Gram-Schmidt
// orthogonalization in powerIterationEigen's deflation (noise subspace is now
// a true orthogonal complement of the signal subspace) and (2) forward
// multi-snapshot covariance averaging in computeMUSICSpectrum. These tests
// pin the FIXED behavior. They validate the MATH on synthetic vectors only —
// production feeds this function TEMPORAL single-antenna samples, so no
// spatial-AoA accuracy claim follows from these (see the function's honesty
// note and PhantomScan_MUSIC_Fix_Session_Report.md).

test("MUSIC (PS-GAP-MUSIC-001 fixed): clean steering input resolves its true synthetic angle", () => {
  for (const ang of [0, 30, -30]) {
    const spectrum = computeMUSICSpectrum(steeringSamples(ang, 16), -60, 60, 121, 1);
    const peak = findSpectrumPeak(spectrum);
    assert.ok(
      Math.abs(peak.angle - ang) <= 3,
      `synthetic steering vector at ${ang}deg must peak within 3deg, got ${peak.angle}`,
    );
  }
});

test("MUSIC (PS-GAP-MUSIC-001 fixed): unrelated random inputs produce meaningfully different spectra", () => {
  // The exact input pair that originally proved the bug (max spectrum
  // difference was 3.55e-15 — bit-for-bit frozen). Post-fix it must differ
  // by a physically meaningful margin.
  function noisyBuffer(seed: number, n: number) {
    let s = seed >>> 0;
    const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 0x100000000) - 0.5;
    const out: Complex[] = [];
    for (let k = 0; k < n; k++) out.push({ re: 3 * rand() + Math.sin(k), im: 3 * rand() });
    return out;
  }
  const specA = computeMUSICSpectrum(noisyBuffer(1, 16), -60, 60, 121, 1);
  const specB = computeMUSICSpectrum(noisyBuffer(999999, 16), -60, 60, 121, 1);
  assert.equal(specA.length, specB.length);
  let maxDiff = 0;
  for (let i = 0; i < specA.length; i++) {
    maxDiff = Math.max(maxDiff, Math.abs(specA[i].power - specB[i].power));
  }
  assert.ok(
    maxDiff > 1,
    `spectra for unrelated inputs must differ by >1 dB somewhere (got max diff ${maxDiff} dB) — ` +
      "a near-zero diff means the PS-GAP-MUSIC-001 input-independence defect regressed",
  );
});

test("MUSIC (PS-GAP-MUSIC-001 fixed): all-zero (degenerate) input returns an empty spectrum, not a fake curve", () => {
  const zeros: Complex[] = Array(16).fill(null).map(() => ({ re: 0, im: 0 }));
  assert.deepEqual(computeMUSICSpectrum(zeros, -60, 60, 121, 1), []);
});

test("findSpectrumPeak: empty spectrum returns the documented sentinel", () => {
  assert.deepEqual(findSpectrumPeak([]), { angle: 0, power: -100 });
});

// ── HampelFilter ────────────────────────────────────────────────────────────

test("HampelFilter: passes normal values through unchanged", () => {
  const f = new HampelFilter(7, 3.0);
  const vals = [10, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95];
  let last = 0;
  for (const v of vals) last = f.push(v);
  assert.equal(last, 9.95, "an in-family value must pass through");
});

test("HampelFilter: replaces a hard outlier spike with the window median", () => {
  const f = new HampelFilter(7, 3.0);
  for (const v of [10, 10.1, 9.9, 10.2, 9.8, 10.05]) f.push(v);
  const out = f.push(1000); // ESP32-style integer burst
  assert.ok(out < 11, `outlier must be replaced by ~median, got ${out}`);
});

test("HampelFilter: values before the window fills pass through untouched", () => {
  const f = new HampelFilter(7, 3.0);
  assert.equal(f.push(42), 42);
  assert.equal(f.push(-7), -7);
});

// ── MicroDopplerClassifier ──────────────────────────────────────────────────
// The deterministic DSP classifier that Item 1 wired into the presence gate.

test("MicroDopplerClassifier: a strong periodic (mechanical) signal classifies as mechanical", () => {
  const c = new MicroDopplerClassifier(40, 20);
  let result = c.push(0);
  // 8 Hz sine at 20 Hz sample rate: high-frequency (>5Hz) AND highly periodic.
  for (let i = 0; i < 80; i++) {
    result = c.push(Math.sin((2 * Math.PI * 8 * i) / 20));
  }
  assert.equal(result.label, "mechanical", `humanProb ${result.humanProb}`);
  assert.ok(result.humanProb < 0.35);
});

test("MicroDopplerClassifier: an aperiodic low-frequency signal does NOT classify as mechanical", () => {
  const c = new MicroDopplerClassifier(40, 20);
  // Slow drift + deterministic pseudo-noise: low HF power, weak periodicity.
  let seed = 12345;
  const rand = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 0x100000000) - 0.5;
  let result = c.push(0);
  for (let i = 0; i < 80; i++) {
    result = c.push(0.5 * Math.sin((2 * Math.PI * 0.4 * i) / 20) + 0.4 * rand());
  }
  assert.notEqual(result.label, "mechanical", `label ${result.label} humanProb ${result.humanProb}`);
});

test("MicroDopplerClassifier: returns last state (label unknown) until the buffer fills", () => {
  const c = new MicroDopplerClassifier(40, 20);
  const r = c.push(1);
  assert.equal(r.label, "unknown");
  assert.equal(r.humanProb, 0.5);
});

// ── PDPRanger ───────────────────────────────────────────────────────────────

test("PDPRanger: returns the RSSI path-loss fallback before the CSI buffer fills", () => {
  const p = new PDPRanger();
  // First push: buffer < 3, so distance comes purely from RSSI path loss.
  // RSSI -30 => d = 10^0 = 1m => 100cm.
  const r = p.push({ re: 1, im: 0 }, { re: 1, im: 0 }, -30);
  assert.equal(r.distanceCm, 100);
});

test("PDPRanger: RSSI fallback clamps to the documented [0.3m, 8m] bounds", () => {
  const near = new PDPRanger().push({ re: 1, im: 0 }, { re: 1, im: 0 }, 0); // absurdly strong
  assert.equal(near.distanceCm, 30, "clamped to 0.3m floor");
  const far = new PDPRanger().push({ re: 1, im: 0 }, { re: 1, im: 0 }, -120); // absurdly weak
  assert.equal(far.distanceCm, 800, "clamped to 8m ceiling");
});

test("PDPRanger: steady CSI input produces a finite, bounded distance estimate", () => {
  const p = new PDPRanger();
  let r = { distanceCm: 0, wallDistance: 0 };
  for (let i = 0; i < 10; i++) {
    r = p.push({ re: 3, im: 1 }, { re: 2, im: -1 }, -50);
  }
  assert.ok(Number.isFinite(r.distanceCm));
  assert.ok(r.distanceCm > 0);
  assert.ok(Number.isFinite(r.wallDistance));
});

// ── BackgroundSubtractor ────────────────────────────────────────────────────

test("BackgroundSubtractor: a constant (static) channel is fully suppressed", () => {
  const b = new BackgroundSubtractor(10);
  let out = b.process({ re: 5, im: 3 }, { re: -2, im: 4 });
  for (let i = 0; i < 20; i++) {
    out = b.process({ re: 5, im: 3 }, { re: -2, im: 4 });
  }
  assert.ok(Math.abs(out.h1Dynamic.re) < 1e-9, "static input => zero dynamic residual");
  assert.ok(Math.abs(out.h1Dynamic.im) < 1e-9);
  assert.ok(Math.abs(out.h2Dynamic.re) < 1e-9);
  assert.ok(Math.abs(out.h2Dynamic.im) < 1e-9);
});

test("BackgroundSubtractor: a step change appears in the dynamic residual", () => {
  const b = new BackgroundSubtractor(10);
  for (let i = 0; i < 10; i++) b.process({ re: 5, im: 0 }, { re: 5, im: 0 });
  // Person enters: channel jumps. The residual must be clearly nonzero.
  const out = b.process({ re: 9, im: 0 }, { re: 9, im: 0 });
  assert.ok(out.h1Dynamic.re > 1, `residual ${out.h1Dynamic.re} must reflect the step`);
});

test("BackgroundSubtractor: setWindowSize trims an over-full window without crashing", () => {
  const b = new BackgroundSubtractor(50);
  for (let i = 0; i < 40; i++) b.process({ re: i, im: 0 }, { re: i, im: 0 });
  b.setWindowSize(5);
  const out = b.process({ re: 40, im: 0 }, { re: 40, im: 0 });
  assert.ok(Number.isFinite(out.h1Dynamic.re));
});

// ── MotionGate ──────────────────────────────────────────────────────────────

test("MotionGate: constant amplitude (empty room) never reports motion", () => {
  const g = new MotionGate();
  let r = g.update(1.0);
  for (let i = 0; i < 150; i++) r = g.update(1.0);
  assert.equal(r.motionDetected, false);
  assert.equal(r.variance, 0);
});

test("MotionGate: auto-calibrates threshold = 3*sigma from the first 100 samples", () => {
  const g = new MotionGate();
  // Deterministic small-noise calibration phase: alternating +/-0.01 around
  // 1.0 => sigma = 0.01, threshold = 0.03.
  let r = g.update(1.01);
  for (let i = 1; i < 100; i++) r = g.update(i % 2 === 0 ? 1.01 : 0.99);
  assert.ok(Math.abs(r.threshold - 0.03) < 1e-9, `threshold ${r.threshold}, expected 0.03`);
});

test("MotionGate: large amplitude swings after calibration trigger motionDetected", () => {
  const g = new MotionGate();
  for (let i = 0; i < 100; i++) g.update(i % 2 === 0 ? 1.01 : 0.99); // quiet calibration
  let r = { motionDetected: false, variance: 0, threshold: 0 };
  for (let i = 0; i < 30; i++) r = g.update(i % 2 === 0 ? 3 : -1); // violent swing
  assert.equal(r.motionDetected, true, `variance ${r.variance} vs threshold ${r.threshold}`);
});

test("MotionGate: a manual threshold overrides the calibrated one", () => {
  const g = new MotionGate();
  for (let i = 0; i < 100; i++) g.update(i % 2 === 0 ? 1.01 : 0.99);
  let r = { motionDetected: false, variance: 0, threshold: 0 };
  for (let i = 0; i < 30; i++) r = g.update(i % 2 === 0 ? 1.2 : 0.8); // moderate swing
  const moderateVariance = r.variance;
  // Manual threshold above that variance suppresses the detection.
  const suppressed = g.update(1.2, moderateVariance * 10);
  assert.equal(suppressed.motionDetected, false);
  assert.equal(suppressed.threshold, moderateVariance * 10);
});

test("MotionGate: reset returns to the uncalibrated default threshold", () => {
  const g = new MotionGate();
  for (let i = 0; i < 100; i++) g.update(i % 2 === 0 ? 2 : 0); // noisy calibration
  g.reset();
  const r = g.update(1.0);
  assert.equal(r.threshold, 0.05, "default eta must be restored on reset");
});
