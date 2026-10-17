import {
  Complex,
  complex,
  add,
  sub,
  mul,
  div,
  magnitude,
  fromPolar,
  negate,
  scale,
  conj,
} from "./complex";
import type {
  CSISample,
  ChannelEstimate,
  ISARFrame,
  AoASpectrumPoint,
  PointCloudPoint,
  HeatmapData,
  ProcessingConfig,
} from "@shared/schema";



// Simple eigenvalue decomposition using power iteration
// Returns eigenvalues and eigenvectors sorted by magnitude
function powerIterationEigen(
  R: Complex[][],
  numIterations: number = 50
): { eigenvalues: number[]; eigenvectors: Complex[][] } {
  const n = R.length;
  const eigenvalues: number[] = [];
  const eigenvectors: Complex[][] = [];

  // Make a copy of R to deflate
  const A: Complex[][] = R.map(row => row.map(c => ({ ...c })));

  for (let k = 0; k < n; k++) {
    // Deterministic dense start vector (seeded LCG per deflation step):
    // identical input covariance must yield an identical spectrum, so the
    // AoA display cannot flicker from re-randomized eigenvectors.
    let seed = (0x9e3779b9 ^ (k * 0x85ebca6b)) >>> 0;
    const rand = () =>
      ((seed = (seed * 1664525 + 1013904223) >>> 0) / 0x100000000) - 0.5;
    let v: Complex[] = Array(n).fill(null).map(() => ({
      re: rand(),
      im: rand()
    }));

    // Normalize
    let norm = Math.sqrt(v.reduce((sum, c) => sum + c.re * c.re + c.im * c.im, 0));
    v = v.map(c => scale(c, 1 / norm));

    // Power iteration
    for (let iter = 0; iter < numIterations; iter++) {
      // w = A * v
      const w: Complex[] = Array(n).fill(null).map(() => ({ re: 0, im: 0 }));
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          w[i] = add(w[i], mul(A[i][j], v[j]));
        }
      }

      // Normalize
      norm = Math.sqrt(w.reduce((sum, c) => sum + c.re * c.re + c.im * c.im, 0));
      if (norm < 1e-10) break;
      v = w.map(c => scale(c, 1 / norm));
    }

    // ── PS-GAP-MUSIC-001 fix (deflation guard) ────────────────────────────
    // When the deflated residual collapses (rank-deficient R — e.g. a rank-1
    // single-snapshot covariance), the `norm < 1e-10` break above used to
    // leave `v` as the RAW SEEDED START VECTOR: input-independent AND not
    // orthogonal to the already-extracted signal eigenvector, so the "noise
    // subspace" was a fixed fake basis and the MUSIC spectrum was bit-for-bit
    // identical for any input. The mathematically correct behavior for a
    // rank-deficient covariance is that the remaining eigenvectors span the
    // ORTHOGONAL COMPLEMENT of the already-extracted ones — any orthonormal
    // basis of that complement is valid. So: Gram-Schmidt-orthogonalize v
    // against every previously extracted eigenvector (deterministic
    // canonical-basis fallback if v was entirely inside their span). The
    // noise projector then genuinely depends on the input's signal subspace,
    // restoring input dependence.
    for (const u of eigenvectors) {
      let proj: Complex = { re: 0, im: 0 };
      for (let i = 0; i < n; i++) {
        proj = add(proj, mul(conj(u[i]), v[i]));
      }
      for (let i = 0; i < n; i++) {
        v[i] = sub(v[i], mul(u[i], proj));
      }
    }
    norm = Math.sqrt(v.reduce((sum, c) => sum + c.re * c.re + c.im * c.im, 0));
    if (norm > 1e-8) {
      v = v.map(c => scale(c, 1 / norm));
    } else {
      // v was (numerically) entirely inside the span of the extracted
      // eigenvectors. Deterministically pick the first canonical basis
      // vector with a non-trivial component in the orthogonal complement.
      for (let basis = 0; basis < n; basis++) {
        const cand: Complex[] = Array(n)
          .fill(null)
          .map((_, i) => (i === basis ? { re: 1, im: 0 } : { re: 0, im: 0 }));
        for (const u of eigenvectors) {
          let proj: Complex = { re: 0, im: 0 };
          for (let i = 0; i < n; i++) {
            proj = add(proj, mul(conj(u[i]), cand[i]));
          }
          for (let i = 0; i < n; i++) {
            cand[i] = sub(cand[i], mul(u[i], proj));
          }
        }
        const candNorm = Math.sqrt(cand.reduce((sum, c) => sum + c.re * c.re + c.im * c.im, 0));
        if (candNorm > 1e-6) {
          v = cand.map(c => scale(c, 1 / candNorm));
          break;
        }
      }
    }

    // Compute eigenvalue: v^H * A * v
    const Av: Complex[] = Array(n).fill(null).map(() => ({ re: 0, im: 0 }));
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        Av[i] = add(Av[i], mul(A[i][j], v[j]));
      }
    }
    let lambda: Complex = { re: 0, im: 0 };
    for (let i = 0; i < n; i++) {
      lambda = add(lambda, mul(conj(v[i]), Av[i]));
    }

    eigenvalues.push(magnitude(lambda));
    eigenvectors.push(v);

    // Deflate: A = A - lambda * v * v^H
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const outer = mul(v[i], conj(v[j]));
        A[i][j] = sub(A[i][j], scale(outer, magnitude(lambda)));
      }
    }
  }

  return { eigenvalues, eigenvectors };
}

// MUSIC pseudo-spectrum over a TEMPORAL sample window.
//
// HONESTY NOTE (PS-GAP-MUSIC-001 / Task 0 finding, 2026-08-07): in production
// (`websocket.ts` `sampleBuffer`) the input is a rolling window of
// time-sequential single-antenna CSI scalars — interleaved from two
// clock-unsynchronized nodes — NOT spatially distinct antenna channels. No
// eigen-math can recover a physical angle-of-arrival from this input; the
// "angle" axis is a steering-vector correlation coordinate over the temporal
// window (a signal SIGNATURE), not a measured spatial direction. The UI
// labels it accordingly. See PhantomScan_MUSIC_Fix_Session_Report.md.
export function computeMUSICSpectrum(
  samples: Complex[],
  angleMin: number,
  angleMax: number,
  numAngles: number = 121,
  numSignals: number = 1
): AoASpectrumPoint[] {
  const N = samples.length;
  if (N < 3) {
    return [];
  }

  // Degenerate input (flat/empty signal): return the honest empty spectrum
  // (the client's AoASpectrum component renders "no live stream" for an
  // empty spectrum) instead of a plausible-looking fake curve.
  let inputPower = 0;
  for (const s of samples) inputPower += s.re * s.re + s.im * s.im;
  if (inputPower < 1e-12) {
    return [];
  }

  // ── PS-GAP-MUSIC-001 fix (covariance rank) ──────────────────────────────
  // The old code claimed "averaging over sliding windows" but actually built
  // R from ONE outer product, R = x·x^H — exactly rank 1, which triggered
  // the deflation collapse fixed in powerIterationEigen. Now genuinely
  // average over K forward sub-window snapshots of length M:
  //     R = (1/K) Σ_k x_k · x_k^H,  x_k = samples[k .. k+M-1]
  // For a real varied signal this gives rank up to K, a genuine noise
  // subspace, and a spectrum that actually depends on the input.
  const M = Math.max(3, Math.floor(N / 2));
  const K = N - M + 1;
  const R: Complex[][] = Array(M)
    .fill(null)
    .map(() =>
      Array(M)
        .fill(null)
        .map(() => ({ re: 0, im: 0 }))
    );

  for (let k = 0; k < K; k++) {
    for (let i = 0; i < M; i++) {
      for (let j = 0; j < M; j++) {
        R[i][j] = add(R[i][j], mul(samples[k + i], conj(samples[k + j])));
      }
    }
  }
  for (let i = 0; i < M; i++) {
    for (let j = 0; j < M; j++) {
      R[i][j] = scale(R[i][j], 1 / K);
    }
  }

  // Eigen-decomposition of covariance matrix
  const { eigenvalues, eigenvectors } = powerIterationEigen(R);

  // Separate signal and noise subspaces
  // Sort eigenvalues and find noise subspace (smaller eigenvalues)
  const sortedIndices = eigenvalues
    .map((val, idx) => ({ val, idx }))
    .sort((a, b) => b.val - a.val)
    .map(item => item.idx);

  // Noise subspace: eigenvectors corresponding to smallest eigenvalues
  const noiseSubspaceIndices = sortedIndices.slice(numSignals);
  const En: Complex[][] = noiseSubspaceIndices.map(idx => eigenvectors[idx]);

  // Element spacing in wavelengths
  const d = 0.5;
  const spectrum: AoASpectrumPoint[] = [];

  for (let i = 0; i < numAngles; i++) {
    const angle = angleMin + (i * (angleMax - angleMin)) / (numAngles - 1);
    const theta = (angle * Math.PI) / 180;

    // Steering vector a(theta) — over the M-element sub-window, matching R.
    const a: Complex[] = [];
    for (let n = 0; n < M; n++) {
      const phase = -2 * Math.PI * d * n * Math.sin(theta);
      a.push(fromPolar(1, phase));
    }

    // MUSIC pseudo-spectrum: 1 / (a^H * En * En^H * a)
    // Compute En^H * a first
    let denominator: Complex = { re: 0, im: 0 };

    for (const noiseVec of En) {
      // Project steering vector onto noise eigenvector
      let projection: Complex = { re: 0, im: 0 };
      for (let k = 0; k < M; k++) {
        projection = add(projection, mul(conj(noiseVec[k]), a[k]));
      }
      // Add |projection|^2 to denominator
      const projMag2 = projection.re * projection.re + projection.im * projection.im;
      denominator = add(denominator, { re: projMag2, im: 0 });
    }

    // MUSIC spectrum = 1 / denominator (take real part)
    const denomReal = Math.max(denominator.re, 1e-10);
    const powerLinear = 1 / denomReal;
    const powerDb = 10 * Math.log10(powerLinear);

    spectrum.push({ angle, power: powerDb });
  }

  return spectrum;
}

// Find peak in MUSIC spectrum
export function findSpectrumPeak(spectrum: AoASpectrumPoint[]): {
  angle: number;
  power: number;
} {
  if (spectrum.length === 0) {
    return { angle: 0, power: -100 };
  }

  let maxPower = -Infinity;
  let maxAngle = 0;

  for (const point of spectrum) {
    if (point.power > maxPower) {
      maxPower = point.power;
      maxAngle = point.angle;
    }
  }

  return { angle: maxAngle, power: maxPower };
}

// Convert AoA and amplitude to 3D coordinates
export function aoaToPoint(
  aoa: number,
  amplitude: number,
  timestamp: number,
  distance: number = 3
): PointCloudPoint {
  const thetaRad = (aoa * Math.PI) / 180;
  const x = distance * Math.sin(thetaRad);
  const y = distance * Math.cos(thetaRad);
  const z = 0; // Assume 2D plane for simplicity

  return { x, y, z, amplitude, timestamp };
}



// Heatmap accumulator for Time vs Angle visualization
export class HeatmapAccumulator {
  private readonly angles: number[];
  private readonly maxTimeSlots: number;
  private times: number[] = [];
  private intensities: number[][] = [];
  private startTime: number = 0;

  constructor(
    angleMin: number = -60,
    angleMax: number = 60,
    numAngles: number = 121,
    maxTimeSlots: number = 100
  ) {
    this.angles = Array.from(
      { length: numAngles },
      (_, i) => angleMin + (i * (angleMax - angleMin)) / (numAngles - 1)
    );
    this.maxTimeSlots = maxTimeSlots;
  }

  addSpectrum(timestamp: number, spectrum: AoASpectrumPoint[]) {
    // Phase-1 bug audit: the reduce() below has no seed, so it throws on an
    // empty spectrum. The current sole call site pre-filters to a non-empty
    // array, but this guard makes the method safe on its own contract too.
    if (spectrum.length === 0) {
      return;
    }

    if (this.startTime === 0) {
      this.startTime = timestamp;
    }

    const relativeTime = (timestamp - this.startTime) / 1000;
    this.times.push(relativeTime);

    // Map spectrum to fixed angle grid
    const intensityRow = this.angles.map((targetAngle) => {
      const closest = spectrum.reduce((prev, curr) =>
        Math.abs(curr.angle - targetAngle) < Math.abs(prev.angle - targetAngle)
          ? curr
          : prev
      );
      return closest.power;
    });

    this.intensities.push(intensityRow);

    // Trim to max size
    if (this.times.length > this.maxTimeSlots) {
      this.times.shift();
      this.intensities.shift();
    }
  }

  getData(): HeatmapData {
    return {
      times: [...this.times],
      angles: [...this.angles],
      intensities: this.intensities.map((row) => [...row]),
    };
  }

  reset() {
    this.times = [];
    this.intensities = [];
    this.startTime = 0;
  }
}


// ═══════════════════════════════════════════════════════════════════
// Hampel Filter — sliding-window median + MAD outlier removal
// Removes hardware noise spikes (integer bursts from ESP32)
// ═══════════════════════════════════════════════════════════════════
export class HampelFilter {
  private buffer: number[] = [];
  private readonly windowSize: number;
  private readonly nSigma: number;
  private readonly k = 1.4826; // Consistency constant for Gaussian

  constructor(windowSize = 7, nSigma = 3.0) {
    this.windowSize = windowSize;
    this.nSigma = nSigma;
  }

  /** Push a value and return filtered output (outlier → median). */
  push(value: number): number {
    this.buffer.push(value);
    if (this.buffer.length > this.windowSize * 3) {
      this.buffer = this.buffer.slice(-this.windowSize * 2);
    }

    if (this.buffer.length < this.windowSize) return value;

    const window = this.buffer.slice(-this.windowSize);
    const sorted = [...window].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const deviations = window.map(v => Math.abs(v - median));
    const sortedDev = [...deviations].sort((a, b) => a - b);
    const mad = sortedDev[Math.floor(sortedDev.length / 2)];
    const threshold = this.nSigma * this.k * mad;

    if (mad > 1e-10 && Math.abs(value - median) > threshold) {
      return median; // Replace outlier
    }
    return value;
  }

  reset() {
    this.buffer = [];
  }
}


// ═══════════════════════════════════════════════════════════════════
// Micro-Doppler Classifier — sliding FFT human/machine discrimination
// ═══════════════════════════════════════════════════════════════════
/**
 * Labels the detected target "human" vs "mechanical" from its motion
 * signature. Rationale: fans/machines produce fast, strictly periodic
 * amplitude modulation (high >5 Hz spectral ratio + strong autocorrelation
 * peak), whereas human movement is slower and aperiodic. Output feeds the
 * `targetIdentity` broadcast and the radial target's label/humanProb.
 */
export class MicroDopplerClassifier {
  private amplitudeBuffer: number[] = [];
  private readonly bufferSize: number;
  private readonly sampleRate: number;
  private lastLabel: "human" | "mechanical" | "unknown" = "unknown";
  private lastHumanProb = 0.5;
  private lastPeriodicity = 0;
  private lastHighFreqRatio = 0;

  constructor(bufferSize = 40, sampleRate = 20) {
    this.bufferSize = bufferSize;
    this.sampleRate = sampleRate;
  }

  /** Push dynamic amplitude; returns classification incl. the raw features
   *  (periodicity, highFreqRatio) shown on the Target Identity card. */
  push(amplitude: number): {
    label: "human" | "mechanical" | "unknown";
    humanProb: number;
    mechanicalProb: number;
    periodicity: number;
    highFreqRatio: number;
  } {
    this.amplitudeBuffer.push(amplitude);
    if (this.amplitudeBuffer.length > this.bufferSize * 2) {
      this.amplitudeBuffer = this.amplitudeBuffer.slice(-this.bufferSize);
    }

    if (this.amplitudeBuffer.length < this.bufferSize) {
      return {
        label: this.lastLabel,
        humanProb: this.lastHumanProb,
        mechanicalProb: 1 - this.lastHumanProb,
        periodicity: this.lastPeriodicity,
        highFreqRatio: this.lastHighFreqRatio,
      };
    }

    const window = this.amplitudeBuffer.slice(-this.bufferSize);
    const mean = window.reduce((s, v) => s + v, 0) / window.length;
    const centered = window.map(v => v - mean);

    // Simple FFT via DFT (buffer is small, O(N²) is fine for N=40)
    const N = centered.length;
    const halfN = Math.floor(N / 2) + 1;
    const powerSpectrum = new Float64Array(halfN);

    for (let k = 0; k < halfN; k++) {
      let re = 0, im = 0;
      for (let n = 0; n < N; n++) {
        const angle = (-2 * Math.PI * k * n) / N;
        re += centered[n] * Math.cos(angle);
        im += centered[n] * Math.sin(angle);
      }
      powerSpectrum[k] = re * re + im * im;
    }

    let totalPower = 0;
    for (let k = 1; k < halfN; k++) totalPower += powerSpectrum[k];
    totalPower += 1e-10;

    // Feature 1: High-frequency ratio (>5Hz)
    const freqPerBin = this.sampleRate / N;
    const highFreqStartBin = Math.ceil(5.0 / freqPerBin);
    let highFreqPower = 0;
    for (let k = highFreqStartBin; k < halfN; k++) highFreqPower += powerSpectrum[k];
    const highFreqRatio = highFreqPower / totalPower;

    // Feature 2: Periodicity via autocorrelation peak
    let autocorrMax = 0;
    const autocorr0 = centered.reduce((s, v) => s + v * v, 0);
    if (autocorr0 > 1e-10) {
      for (let lag = 3; lag < Math.floor(N / 2); lag++) {
        let sum = 0;
        for (let i = 0; i < N - lag; i++) sum += centered[i] * centered[i + lag];
        const normalized = sum / autocorr0;
        if (normalized > autocorrMax) autocorrMax = normalized;
      }
    }

    // Classification
    let mechanicalScore = 0;
    mechanicalScore += Math.min(1, highFreqRatio * 3) * 0.5;
    mechanicalScore += Math.min(1, autocorrMax * 1.5) * 0.5;

    const humanProb = Math.max(0, Math.min(1, 1 - mechanicalScore));
    const label: "human" | "mechanical" | "unknown" =
      humanProb > 0.65 ? "human" : humanProb < 0.35 ? "mechanical" : "unknown";

    this.lastLabel = label;
    this.lastHumanProb = humanProb;
    this.lastPeriodicity = autocorrMax;
    this.lastHighFreqRatio = highFreqRatio;

    return {
      label,
      humanProb,
      mechanicalProb: 1 - humanProb,
      periodicity: autocorrMax,
      highFreqRatio,
    };
  }

  reset() {
    this.amplitudeBuffer = [];
    this.lastLabel = "unknown";
    this.lastHumanProb = 0.5;
    this.lastPeriodicity = 0;
    this.lastHighFreqRatio = 0;
  }
}


// ═══════════════════════════════════════════════════════════════════
// PDP Ranger — IFFT Power Delay Profile distance estimation
// ═══════════════════════════════════════════════════════════════════
/**
 * Estimates target range (cm) and wall distance (m) for the distance gauge.
 * Method: IFFT of the averaged CSI vector gives a power-delay profile; the
 * strongest peak's delay bin → time-of-flight distance, the farthest peak →
 * wall reflection. The PDP estimate is blended with an RSSI path-loss
 * estimate (weight ∝ peak strength) and EMA-smoothed (α=0.25) so the
 * readout doesn't jump frame to frame.
 */
export class PDPRanger {
  private static readonly C = 3e8;         // Speed of light
  private static readonly BW = 20e6;       // 20MHz Wi-Fi bandwidth
  private readonly nFFT: number;
  private readonly peakThreshold: number;
  private csiBuffer: { re: number; im: number }[][] = [];
  private readonly bufferSize = 10;
  private lastDistanceCm = 200;
  private lastWallDistance = 5.0;
  // EMA smoothing state
  private emaDistanceCm = 200;
  private emaWallDistance = 5.0;
  private readonly emaAlpha = 0.25; // Smoothing factor (lower = smoother)

  constructor(nFFT = 64, peakThreshold = 0.3) {
    this.nFFT = nFFT;
    this.peakThreshold = peakThreshold;
  }

  /** Parabolic interpolation: given pdp[left], pdp[center], pdp[right], return fractional bin offset. */
  private parabolicPeak(left: number, center: number, right: number): number {
    const denom = 2 * (2 * center - left - right);
    if (Math.abs(denom) < 1e-12) return 0;
    return (left - right) / denom; // Returns offset ∈ [-0.5, 0.5]
  }

  /** RSSI-based log-distance estimate (calibrated for ESP32 at 2.4 GHz). */
  private rssiToMeters(rssi: number): number {
    // Free-space path loss: d = 10^((P_ref - RSSI) / (10n))
    // P_ref = -30 dBm at 1m, n = 2.5 (typical indoor)
    const d = Math.pow(10, (-30 - rssi) / 25);
    return Math.max(0.3, Math.min(8, d));
  }

  /** Push dual-path CSI, return distance in cm + wall distance in m. */
  push(
    h1: Complex,
    h2: Complex,
    rssi: number = -50,
  ): { distanceCm: number; wallDistance: number } {
    // Build mini CSI vector
    const crossRe = h1.re * h2.re + h1.im * h2.im;
    const crossIm = h1.im * h2.re - h1.re * h2.im;
    const sumRe = h1.re + h2.re;
    const sumIm = h1.im + h2.im;

    const csiVec = [
      { re: h1.re, im: h1.im },
      { re: h2.re, im: h2.im },
      { re: crossRe, im: crossIm },
      { re: sumRe, im: sumIm },
    ];

    this.csiBuffer.push(csiVec);
    if (this.csiBuffer.length > this.bufferSize) {
      this.csiBuffer = this.csiBuffer.slice(-this.bufferSize);
    }

    const rssiDist = this.rssiToMeters(rssi);

    if (this.csiBuffer.length < 3) {
      // RSSI fallback
      return { distanceCm: Math.round(rssiDist * 100), wallDistance: this.lastWallDistance };
    }

    // Average CSI across recent frames
    const vecLen = csiVec.length;
    const avgRe = new Float64Array(vecLen);
    const avgIm = new Float64Array(vecLen);
    for (const vec of this.csiBuffer) {
      for (let i = 0; i < vecLen; i++) {
        avgRe[i] += vec[i].re;
        avgIm[i] += vec[i].im;
      }
    }
    const count = this.csiBuffer.length;
    for (let i = 0; i < vecLen; i++) {
      avgRe[i] /= count;
      avgIm[i] /= count;
    }

    // Zero-pad + IFFT
    const N = this.nFFT;
    const pdp = new Float64Array(N);

    for (let n = 0; n < N; n++) {
      let re = 0, im = 0;
      for (let k = 0; k < vecLen; k++) {
        const angle = (2 * Math.PI * k * n) / N;
        re += avgRe[k] * Math.cos(angle) - avgIm[k] * Math.sin(angle);
        im += avgRe[k] * Math.sin(angle) + avgIm[k] * Math.cos(angle);
      }
      pdp[n] = re * re + im * im;
    }

    // Normalize
    let pdpMax = 0;
    for (let i = 0; i < N; i++) if (pdp[i] > pdpMax) pdpMax = pdp[i];
    if (pdpMax < 1e-10) {
      return { distanceCm: this.lastDistanceCm, wallDistance: this.lastWallDistance };
    }
    for (let i = 0; i < N; i++) pdp[i] /= pdpMax;

    // Compute noise floor (median of lower half of PDP values)
    const sortedPdp = Array.from(pdp).sort((a, b) => a - b);
    const noiseFloor = sortedPdp[Math.floor(sortedPdp.length * 0.6)] * 2 + 0.05;
    const dynamicThreshold = Math.max(this.peakThreshold, noiseFloor);

    // Distance per bin (using Wi-Fi channel bandwidth)
    const distPerBin = PDPRanger.C / (2 * PDPRanger.BW * N / vecLen);

    // Find peaks with parabolic interpolation for sub-bin accuracy
    const peaks: { exactBin: number; power: number }[] = [];
    const halfN = Math.floor(N / 2);
    for (let i = 1; i < halfN - 1; i++) {
      if (pdp[i] > dynamicThreshold && pdp[i] > pdp[i - 1] && pdp[i] >= pdp[i + 1]) {
        // Parabolic interpolation for sub-bin precision
        const offset = this.parabolicPeak(pdp[i - 1], pdp[i], pdp[i + 1]);
        const exactBin = i + offset;
        peaks.push({ exactBin, power: pdp[i] });
      }
    }

    let rawDistanceCm: number;

    if (peaks.length > 0) {
      // Use strongest (highest power) peak for primary target
      peaks.sort((a, b) => b.power - a.power);
      const primaryPeak = peaks[0];

      const pdpDist = Math.max(0.3, Math.min(8, primaryPeak.exactBin * distPerBin));

      // Blend PDP with RSSI: when PDP has strong peak (power > 0.7), trust PDP more.
      // When weak, blend more with RSSI for stability.
      const pdpWeight = Math.min(0.85, primaryPeak.power * 0.9);
      const blendedDist = pdpDist * pdpWeight + rssiDist * (1 - pdpWeight);

      rawDistanceCm = Math.round(blendedDist * 100 * 10) / 10;

      // Wall distance: use the last peak (farthest)
      if (peaks.length > 1) {
        const farthest = peaks.reduce((acc, p) => p.exactBin > acc.exactBin ? p : acc);
        const wallD = farthest.exactBin * distPerBin;
        const newWallDist = Math.max(blendedDist + 0.5, Math.min(10, wallD));
        // EMA smooth wall distance
        this.emaWallDistance += this.emaAlpha * (newWallDist - this.emaWallDistance);
        this.lastWallDistance = Math.round(this.emaWallDistance * 100) / 100;
      }
    } else {
      // RSSI fallback
      rawDistanceCm = Math.round(rssiDist * 100 * 10) / 10;
    }

    // EMA smoothing on distance — prevents noisy jumps
    this.emaDistanceCm += this.emaAlpha * (rawDistanceCm - this.emaDistanceCm);
    this.lastDistanceCm = Math.round(this.emaDistanceCm * 10) / 10;

    return {
      distanceCm: this.lastDistanceCm,
      wallDistance: this.lastWallDistance,
    };
  }

  reset() {
    this.csiBuffer = [];
    this.lastDistanceCm = 200;
    this.lastWallDistance = 5.0;
    this.emaDistanceCm = 200;
    this.emaWallDistance = 5.0;
  }
}


// ═══════════════════════════════════════════════════════════════════
// Background Subtractor — running-average clutter removal
// H_dynamic(t) = H_current(t) - mean(H_window)
// ═══════════════════════════════════════════════════════════════════
/**
 * First stage of every frame: removes the static room reflection (walls,
 * furniture) by subtracting the running-average channel, leaving only the
 * dynamic component caused by a moving/breathing person. All downstream
 * motion and presence math operates on this residual.
 */
export class BackgroundSubtractor {
  private h1Window: Complex[] = [];
  private h2Window: Complex[] = [];
  private windowSize: number;

  constructor(windowSize = 50) {
    this.windowSize = windowSize;
  }

  setWindowSize(n: number) {
    this.windowSize = n;
    // Trim if current buffer exceeds new size
    while (this.h1Window.length > n) {
      this.h1Window.shift();
      this.h2Window.shift();
    }
  }

  /** Push a raw sample and return the dynamic (clutter-removed) components */
  process(h1: Complex, h2: Complex): { h1Dynamic: Complex; h2Dynamic: Complex } {
    this.h1Window.push({ ...h1 });
    this.h2Window.push({ ...h2 });

    if (this.h1Window.length > this.windowSize) {
      this.h1Window.shift();
      this.h2Window.shift();
    }

    // Compute running average (static component)
    const len = this.h1Window.length;
    const h1Avg: Complex = {
      re: this.h1Window.reduce((s, c) => s + c.re, 0) / len,
      im: this.h1Window.reduce((s, c) => s + c.im, 0) / len,
    };
    const h2Avg: Complex = {
      re: this.h2Window.reduce((s, c) => s + c.re, 0) / len,
      im: this.h2Window.reduce((s, c) => s + c.im, 0) / len,
    };

    // Dynamic = current - static_avg
    return {
      h1Dynamic: sub(h1, h1Avg),
      h2Dynamic: sub(h2, h2Avg),
    };
  }

  reset() {
    this.h1Window = [];
    this.h2Window = [];
  }
}


// ═══════════════════════════════════════════════════════════════════
// Motion Gate — variance-based motion detection
// Compares variance of amplitude over last k samples against η
// ═══════════════════════════════════════════════════════════════════
/**
 * Produces the per-frame `motionDetected` flag (the "Motion / No Motion"
 * badge and half of the moving/idle decision in buildTargetState).
 * Physics: a person disturbing the WiFi channel makes the clutter-removed
 * amplitude fluctuate; an empty room's variance sits at the noise floor.
 * The first 100 samples auto-calibrate that floor (threshold = 3σ), so the
 * gate adapts to each room without manual tuning.
 */
export class MotionGate {
  private amplitudeBuffer: number[] = [];
  private readonly bufferSize = 30;

  // Auto-calibrate from still frames
  private calibrationSamples: number[] = [];
  private readonly calibrationCount = 100;
  private calibratedThreshold = 0.05; // default η
  private isCalibrated = false;

  /**
   * Push a magnitude value and return motion status.
   * During first 100 samples, auto-calibrates the noise floor.
   */
  update(
    amplitudeMag: number,
    manualThreshold?: number
  ): { motionDetected: boolean; variance: number; threshold: number } {
    this.amplitudeBuffer.push(amplitudeMag);
    if (this.amplitudeBuffer.length > this.bufferSize) {
      this.amplitudeBuffer.shift();
    }

    // Auto-calibration phase
    if (!this.isCalibrated) {
      this.calibrationSamples.push(amplitudeMag);
      if (this.calibrationSamples.length >= this.calibrationCount) {
        const mean =
          this.calibrationSamples.reduce((a, b) => a + b, 0) /
          this.calibrationSamples.length;
        const variance =
          this.calibrationSamples.reduce(
            (s, x) => s + (x - mean) ** 2,
            0
          ) / this.calibrationSamples.length;
        // Threshold = 3× the noise-floor std-dev
        this.calibratedThreshold = Math.sqrt(variance) * 3;
        this.isCalibrated = true;
      }
    }

    // Compute variance over buffer
    const n = this.amplitudeBuffer.length;
    if (n < 2) {
      return { motionDetected: false, variance: 0, threshold: this.calibratedThreshold };
    }
    const mean = this.amplitudeBuffer.reduce((a, b) => a + b, 0) / n;
    const variance =
      this.amplitudeBuffer.reduce((s, x) => s + (x - mean) ** 2, 0) / n;

    const threshold = manualThreshold ?? this.calibratedThreshold;

    return {
      motionDetected: variance > threshold,
      variance,
      threshold,
    };
  }

  reset() {
    this.amplitudeBuffer = [];
    this.calibrationSamples = [];
    this.isCalibrated = false;
    this.calibratedThreshold = 0.05;
  }
}


// ═══════════════════════════════════════════════════════════════════
// Doppler Computer — sliding-window DFT to build time × frequency map
// ═══════════════════════════════════════════════════════════════════
export class DopplerComputer {
  private amplitudeHistory: number[] = [];
  private readonly fftSize = 64;
  private readonly maxTimeSlots = 100;
  private times: number[] = [];
  private spectrogramRows: number[][] = [];
  private startTime = 0;

  /** Push a dynamic amplitude sample (after background subtraction) */
  addSample(timestamp: number, dynamicAmplitude: number) {
    if (this.startTime === 0) this.startTime = timestamp;

    this.amplitudeHistory.push(dynamicAmplitude);

    // Only compute a row when we have enough samples for one DFT window
    if (this.amplitudeHistory.length >= this.fftSize) {
      const window = this.amplitudeHistory.slice(-this.fftSize);
      const row = this.computeDFTMagnitudes(window);

      this.times.push((timestamp - this.startTime) / 1000);
      this.spectrogramRows.push(row);

      if (this.times.length > this.maxTimeSlots) {
        this.times.shift();
        this.spectrogramRows.shift();
      }
    }

    // Keep history bounded
    if (this.amplitudeHistory.length > this.fftSize * 2) {
      this.amplitudeHistory = this.amplitudeHistory.slice(-this.fftSize);
    }
  }

  /** Real-valued DFT → magnitude spectrum (only positive frequencies) */
  private computeDFTMagnitudes(x: number[]): number[] {
    const N = x.length;
    const halfN = Math.floor(N / 2);
    const mags: number[] = [];

    // Apply Hanning window
    const windowed = x.map(
      (v, n) => v * (0.5 - 0.5 * Math.cos((2 * Math.PI * n) / (N - 1)))
    );

    for (let k = 0; k < halfN; k++) {
      let re = 0;
      let im = 0;
      for (let n = 0; n < N; n++) {
        const angle = (2 * Math.PI * k * n) / N;
        re += windowed[n] * Math.cos(angle);
        im -= windowed[n] * Math.sin(angle);
      }
      const mag = Math.sqrt(re * re + im * im) / N;
      // Convert to dB, clamp floor
      mags.push(Math.max(-60, 20 * Math.log10(mag + 1e-10)));
    }

    return mags;
  }

  getData(): { times: number[]; frequencies: number[]; intensities: number[][] } {
    const halfN = Math.floor(this.fftSize / 2);
    // Doppler frequency bins (normalized, 0 to 0.5 × sample rate)
    const frequencies = Array.from(
      { length: halfN },
      (_, k) => (k / this.fftSize) * 20 // assume ~20Hz sample rate
    );

    return {
      times: [...this.times],
      frequencies,
      intensities: this.spectrogramRows.map((row) => [...row]),
    };
  }

  reset() {
    this.amplitudeHistory = [];
    this.times = [];
    this.spectrogramRows = [];
    this.startTime = 0;
  }
}

// Data parser for CSI traces from hardware
// NOTE: CSV/ASCII parsers removed — binary serial at high baud rates only.
// Use the Python CSIFilterPipeline for offline CSV analysis.
export class CSIDataParser {
  // Parse JSON format from ESP32/USRP
  static parseJSON(data: unknown): CSISample | null {
    try {
      const obj = data as Record<string, unknown>;

      // Handle different JSON formats
      if (obj.timestamp !== undefined && obj.h1 !== undefined && obj.h2 !== undefined) {
        const h1 = obj.h1 as Record<string, number>;
        const h2 = obj.h2 as Record<string, number>;

        // Phase-1 bug audit: was `||`, which coerces a legitimate 0 the same
        // as a missing field, silently corrupting phase data for a
        // genuinely-zero channel sample. `??` only falls through on
        // null/undefined.
        return {
          timestamp: obj.timestamp as number,
          h1: { re: h1.re ?? h1.real ?? 0, im: h1.im ?? h1.imag ?? 0 },
          h2: { re: h2.re ?? h2.real ?? 0, im: h2.im ?? h2.imag ?? 0 },
          rssi: obj.rssi as number | undefined,
        };
      }

      // Handle array format [re1, im1, re2, im2]
      if (Array.isArray(obj.csi) && obj.csi.length >= 4) {
        const csi = obj.csi as number[];
        return {
          timestamp: (obj.timestamp as number) || Date.now(),
          h1: { re: csi[0], im: csi[1] },
          h2: { re: csi[2], im: csi[3] },
          rssi: obj.rssi as number | undefined,
        };
      }

      return null;
    } catch {
      return null;
    }
  }
}

// Demo data generator for testing
export class DemoDataGenerator {
  private time = 0;
  private readonly sampleRate = 20; // Hz

  // Room-walk simulation: person walks a figure-8 loop
  // producing wide angle swings (-50° to +50°) that MUSIC can resolve
  private walkPhase = 0;

  generateSample(): CSISample {
    this.time += 1000 / this.sampleRate;
    this.walkPhase += (2 * Math.PI) / (this.sampleRate * 12); // 12s full loop

    // Figure-8 path: angle oscillates widely between -50° and +50°
    const personAngle = 50 * Math.sin(this.walkPhase);
    // Depth oscillates so PDP range also changes 1.5m → 4.5m
    const personDepth = 3.0 + 1.5 * Math.sin(this.walkPhase * 2);

    const theta = (personAngle * Math.PI) / 180;

    // Static channel (walls/clutter)
    const staticMag = 0.8;
    const staticPhase = Math.PI / 4;
    const h1Static = fromPolar(staticMag, staticPhase);
    const h2Static = fromPolar(staticMag * 0.9, staticPhase + 0.1);

    // Moving human: magnitude scales with depth (farther = weaker)
    const movingMag = Math.max(0.1, 0.5 - personDepth * 0.05);
    const t = this.time / 1000;

    // Vital signs: breathing 0.3Hz + heart rate 1.2Hz
    const respPhase = 0.8 * Math.sin(2 * Math.PI * 0.3 * t);
    const hrPhase = 0.15 * Math.sin(2 * Math.PI * 1.2 * t);

    // Directional phase: AoA drives inter-antenna phase difference
    const aoapPhase = 2 * Math.PI * Math.sin(theta) * personDepth * 0.3 + t * 0.5;
    const h1Phase = aoapPhase + respPhase + hrPhase;
    // Antenna 2 sees slight different path length based on AoA
    const h2Phase = aoapPhase + 0.4 * Math.sin(theta) + 0.5 * (respPhase + hrPhase);

    const h1Moving = fromPolar(movingMag, h1Phase);
    const h2Moving = fromPolar(movingMag * 0.95, h2Phase);

    // Light noise
    const noiseLevel = 0.015;
    const noise1: Complex = {
      re: (Math.random() - 0.5) * noiseLevel,
      im: (Math.random() - 0.5) * noiseLevel,
    };
    const noise2: Complex = {
      re: (Math.random() - 0.5) * noiseLevel,
      im: (Math.random() - 0.5) * noiseLevel,
    };

    return {
      timestamp: Date.now(),
      h1: add(add(h1Static, h1Moving), noise1),
      h2: add(add(h2Static, h2Moving), noise2),
      rssi: -55 + personDepth * -2 + Math.random() * 5,
    };
  }

  getPersonAngle(): number {
    return 50 * Math.sin(this.walkPhase);
  }

  reset() {
    this.time = 0;
    this.walkPhase = 0;
  }
}

