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
  GestureEvent,
  HeatmapData,
  ProcessingConfig,
} from "@shared/schema";

// Calculate precoding ratio: p = -h1/h2
export function calculatePrecodingRatio(h1: Complex, h2: Complex): Complex {
  return negate(div(h1, h2));
}

// Apply signal nulling to remove static reflections
export function applyNulling(
  sample: CSISample,
  config: ProcessingConfig
): ChannelEstimate {
  const precodingRatio = calculatePrecodingRatio(sample.h1, sample.h2);

  // Nulled signal: h1 + p * h2 should be near zero for static objects
  // For moving objects, the residual reveals their contribution
  const pTimesH2 = mul(precodingRatio, sample.h2);
  const nulledSignal = add(sample.h1, pTimesH2);

  // Apply threshold - if magnitude too low, treat as noise
  const nulledMag = magnitude(nulledSignal);
  const thresholdLinear = Math.pow(10, -config.nullingThreshold / 20);

  const finalNulled: Complex =
    nulledMag < thresholdLinear ? { re: 0, im: 0 } : nulledSignal;

  return {
    timestamp: sample.timestamp,
    h1: sample.h1,
    h2: sample.h2,
    precodingRatio,
    nulledSignal: finalNulled,
  };
}

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

// Matched filter templates for gesture detection
// Bit 0: Forward then backward (positive then negative centroid shift)
// Bit 1: Backward then forward (negative then positive centroid shift)
const GESTURE_TEMPLATE_0 = [1, 1, 1, 0.5, 0, -0.5, -1, -1, -1]; // Forward-backward
const GESTURE_TEMPLATE_1 = [-1, -1, -1, -0.5, 0, 0.5, 1, 1, 1]; // Backward-forward

function normalizeTemplate(template: number[]): number[] {
  const norm = Math.sqrt(template.reduce((sum, v) => sum + v * v, 0));
  return template.map(v => v / norm);
}

const NORM_TEMPLATE_0 = normalizeTemplate(GESTURE_TEMPLATE_0);
const NORM_TEMPLATE_1 = normalizeTemplate(GESTURE_TEMPLATE_1);

// Compute cross-correlation between signal and template
function matchedFilterCorrelation(signal: number[], template: number[]): number {
  if (signal.length < template.length) return 0;

  // Use the last template.length samples
  const segment = signal.slice(-template.length);

  // Normalize the segment
  const mean = segment.reduce((sum, v) => sum + v, 0) / segment.length;
  const centered = segment.map(v => v - mean);
  const segmentNorm = Math.sqrt(centered.reduce((sum, v) => sum + v * v, 0));

  if (segmentNorm < 1e-6) return 0;

  const normalized = centered.map(v => v / segmentNorm);

  // Compute correlation
  let correlation = 0;
  for (let i = 0; i < template.length; i++) {
    correlation += normalized[i] * template[i];
  }

  return correlation;
}

// Gesture detection using matched filter on centroid shifts
export class GestureDetector {
  private centroidHistory: { time: number; centroid: number }[] = [];
  private readonly windowSize = 20;
  private readonly templateLength = 9;
  private correlationThreshold: number;
  private lastDetectionTime = 0;
  private readonly minDetectionInterval = 500; // ms between detections

  constructor(threshold: number = 5) {
    this.correlationThreshold = 0.6 + (threshold / 50) * 0.3; // Map 0-50 to 0.6-0.9
  }

  updateThreshold(threshold: number) {
    this.correlationThreshold = 0.6 + (threshold / 50) * 0.3;
  }

  addSample(timestamp: number, centroid: number): GestureEvent | null {
    this.centroidHistory.push({ time: timestamp, centroid });

    // Keep only recent samples
    if (this.centroidHistory.length > this.windowSize) {
      this.centroidHistory.shift();
    }

    // Need enough samples for matched filter
    if (this.centroidHistory.length < this.templateLength) {
      return null;
    }

    // Check minimum interval since last detection
    if (timestamp - this.lastDetectionTime < this.minDetectionInterval) {
      return null;
    }

    // Compute centroid velocity/shift signal
    const shifts: number[] = [];
    for (let i = 1; i < this.centroidHistory.length; i++) {
      shifts.push(this.centroidHistory[i].centroid - this.centroidHistory[i - 1].centroid);
    }

    if (shifts.length < this.templateLength) {
      return null;
    }

    // Apply matched filter for each gesture template
    const corr0 = matchedFilterCorrelation(shifts, NORM_TEMPLATE_0);
    const corr1 = matchedFilterCorrelation(shifts, NORM_TEMPLATE_1);

    // Detect gesture based on correlation strength
    if (corr0 > this.correlationThreshold && corr0 > corr1) {
      this.lastDetectionTime = timestamp;
      this.centroidHistory = []; // Reset after detection

      return {
        timestamp,
        gestureType: "0",
        centroidShift: corr0 * 10, // Scale for display
        confidence: Math.min(1, corr0),
      };
    }

    if (corr1 > this.correlationThreshold && corr1 > corr0) {
      this.lastDetectionTime = timestamp;
      this.centroidHistory = []; // Reset after detection

      return {
        timestamp,
        gestureType: "1",
        centroidShift: corr1 * -10, // Negative for backward-forward
        confidence: Math.min(1, corr1),
      };
    }

    return null;
  }

  reset() {
    this.centroidHistory = [];
    this.lastDetectionTime = 0;
  }
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
export class CSIDataParser {
  // Parse CSV format: timestamp,h1_re,h1_im,h2_re,h2_im[,rssi]
  static parseCSVLine(line: string): CSISample | null {
    const parts = line.trim().split(',');
    if (parts.length < 5) return null;

    try {
      const timestamp = parseFloat(parts[0]);
      const h1: Complex = {
        re: parseFloat(parts[1]),
        im: parseFloat(parts[2]),
      };
      const h2: Complex = {
        re: parseFloat(parts[3]),
        im: parseFloat(parts[4]),
      };
      const rssi = parts.length > 5 ? parseFloat(parts[5]) : undefined;

      if (isNaN(timestamp) || isNaN(h1.re) || isNaN(h1.im) || isNaN(h2.re) || isNaN(h2.im)) {
        return null;
      }

      return { timestamp, h1, h2, rssi };
    } catch {
      return null;
    }
  }

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

  // Parse bulk CSV data
  static parseCSVBulk(csv: string): CSISample[] {
    const lines = csv.trim().split('\n');
    const samples: CSISample[] = [];

    for (const line of lines) {
      // Skip header
      if (line.startsWith('timestamp') || line.startsWith('#')) continue;

      const sample = this.parseCSVLine(line);
      if (sample) samples.push(sample);
    }

    return samples;
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
    const movingPhase = 2 * Math.PI * Math.sin(theta) + (this.time / 1000) * 0.5;
    const h1Moving = fromPolar(movingMag, movingPhase);
    const h2Moving = fromPolar(movingMag * 0.95, movingPhase + 0.05);

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
