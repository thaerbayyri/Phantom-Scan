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
    // Initialize random vector
    let v: Complex[] = Array(n).fill(null).map(() => ({
      re: Math.random() - 0.5,
      im: Math.random() - 0.5
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

// MUSIC algorithm for Angle of Arrival estimation
// Uses proper noise subspace estimation and MUSIC pseudo-spectrum
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

  // Build covariance matrix R = E[x * x^H]
  // Using sample covariance with averaging over sliding windows
  const R: Complex[][] = Array(N)
    .fill(null)
    .map(() =>
      Array(N)
        .fill(null)
        .map(() => ({ re: 0, im: 0 }))
    );

  // Compute spatial covariance matrix
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      // R[i][j] = samples[i] * conj(samples[j])
      R[i][j] = mul(samples[i], conj(samples[j]));
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

    // Steering vector a(theta)
    const a: Complex[] = [];
    for (let n = 0; n < N; n++) {
      const phase = -2 * Math.PI * d * n * Math.sin(theta);
      a.push(fromPolar(1, phase));
    }

    // MUSIC pseudo-spectrum: 1 / (a^H * En * En^H * a)
    // Compute En^H * a first
    let denominator: Complex = { re: 0, im: 0 };

    for (const noiseVec of En) {
      // Project steering vector onto noise eigenvector
      let projection: Complex = { re: 0, im: 0 };
      for (let k = 0; k < N; k++) {
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
export class MicroDopplerClassifier {
  private amplitudeBuffer: number[] = [];
  private readonly bufferSize: number;
  private readonly sampleRate: number;
  private lastLabel: "human" | "mechanical" | "unknown" = "unknown";
  private lastHumanProb = 0.5;

  constructor(bufferSize = 40, sampleRate = 20) {
    this.bufferSize = bufferSize;
    this.sampleRate = sampleRate;
  }

  /** Push dynamic amplitude; returns classification. */
  push(amplitude: number): {
    label: "human" | "mechanical" | "unknown";
    humanProb: number;
    mechanicalProb: number;
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

    return { label, humanProb, mechanicalProb: 1 - humanProb };
  }

  reset() {
    this.amplitudeBuffer = [];
    this.lastLabel = "unknown";
    this.lastHumanProb = 0.5;
  }
}


// ═══════════════════════════════════════════════════════════════════
// PDP Ranger — IFFT Power Delay Profile distance estimation
// ═══════════════════════════════════════════════════════════════════
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

        return {
          timestamp: obj.timestamp as number,
          h1: { re: h1.re || h1.real || 0, im: h1.im || h1.imag || 0 },
          h2: { re: h2.re || h2.real || 0, im: h2.im || h2.imag || 0 },
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
  private personAngle = 0;
  private personDirection = 1;
  private gesturePhase = 0; // 0 = normal, 1 = forward, 2 = backward

  generateSample(): CSISample {
    this.time += 1000 / this.sampleRate;

    // Simulate gestures periodically
    if (this.gesturePhase === 0 && Math.random() < 0.02) {
      this.gesturePhase = Math.random() < 0.5 ? 1 : 2;
    }

    // Gesture movement patterns
    if (this.gesturePhase === 1) {
      // Forward-backward (Bit 0)
      this.personAngle += 3;
      if (this.personAngle > 25) {
        this.gesturePhase = -1; // Transition to backward
      }
    } else if (this.gesturePhase === -1) {
      this.personAngle -= 3;
      if (this.personAngle < 5) {
        this.gesturePhase = 0;
      }
    } else if (this.gesturePhase === 2) {
      // Backward-forward (Bit 1)
      this.personAngle -= 3;
      if (this.personAngle < -25) {
        this.gesturePhase = -2; // Transition to forward
      }
    } else if (this.gesturePhase === -2) {
      this.personAngle += 3;
      if (this.personAngle > -5) {
        this.gesturePhase = 0;
      }
    } else {
      // Normal wandering movement
      this.personAngle += this.personDirection * 0.5;
      if (Math.abs(this.personAngle) > 30) {
        this.personDirection *= -1;
      }
    }

    const theta = (this.personAngle * Math.PI) / 180;

    // Generate channel estimates with static + moving components
    const staticMag = 0.8;
    const movingMag = 0.3;

    // Static component (walls, furniture)
    const staticPhase = Math.PI / 4;
    const h1Static = fromPolar(staticMag, staticPhase);
    const h2Static = fromPolar(staticMag * 0.9, staticPhase + 0.1);

    // Moving component (person)
    const t = this.time / 1000;
    const movingPhase = 2 * Math.PI * Math.sin(theta) + t * 0.5;

    // Simulate Vital Signs on both antennas, but diff projection to survive conjugate math
    // Breathing: ~0.3 Hz (18 RPM), Heart Rate: ~1.2 Hz (72 BPM)
    const respPhase = 0.8 * Math.sin(2 * Math.PI * 0.3 * t);
    const hrPhase = 0.15 * Math.sin(2 * Math.PI * 1.2 * t);

    // Antenna 1 sees 100% of the displacement, Antenna 2 sees 50%
    const h1Phase = movingPhase + respPhase + hrPhase;
    const h2Phase = movingPhase + 0.05 + 0.5 * (respPhase + hrPhase);

    const h1Moving = fromPolar(movingMag, h1Phase);
    const h2Moving = fromPolar(movingMag * 0.95, h2Phase);

    // Add noise
    const noiseLevel = 0.02;
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
      rssi: -50 + Math.random() * 10,
    };
  }

  getPersonAngle(): number {
    return this.personAngle;
  }

  reset() {
    this.time = 0;
    this.personAngle = 0;
    this.personDirection = 1;
    this.gesturePhase = 0;
  }
}
