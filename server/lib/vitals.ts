import { Complex, conj, mul, phase, magnitude } from "./complex";
import { HampelFilter } from "./signal-processing";

/**
 * Unwraps an array of phase angles (in radians) to remove 2pi discontinuities.
 */
export function unwrapPhase(phases: number[]): number[] {
    const unwrapped = new Array(phases.length);
    if (phases.length === 0) return unwrapped;

    unwrapped[0] = phases[0];
    for (let i = 1; i < phases.length; i++) {
        let delta = phases[i] - phases[i - 1];
        if (delta > Math.PI) {
            delta -= 2 * Math.PI;
        } else if (delta < -Math.PI) {
            delta += 2 * Math.PI;
        }
        unwrapped[i] = unwrapped[i - 1] + delta;
    }
    return unwrapped;
}

/**
 * A basic Discrete Fourier Transform (DFT) for frequency analysis.
 * (Since buffer sizes for vitals are small, e.g., 200 samples (10 sec @ 20Hz),
 * a standard O(N^2) DFT is lightweight enough without needing a full Radix-2 FFT).
 */
export function computeDFT(data: number[], sampleRate: number): { frequencies: number[], magnitudes: number[] } {
    const N = data.length;
    const frequencies = new Array(N);
    const magnitudes = new Array(N);

    // Precompute mean to remove DC offset (0Hz spike)
    const mean = data.reduce((sum, val) => sum + val, 0) / N;
    const normalizedData = data.map(val => val - mean);

    for (let k = 0; k < N / 2; k++) {
        let re = 0;
        let im = 0;
        const freq = (k * sampleRate) / N;

        for (let n = 0; n < N; n++) {
            const angle = (2 * Math.PI * k * n) / N;
            re += normalizedData[n] * Math.cos(angle);
            im -= normalizedData[n] * Math.sin(angle);
        }

        frequencies[k] = freq;
        magnitudes[k] = Math.sqrt(re * re + im * im) / N; // normalize
    }

    // Slice to only return the positive frequencies (up to Nyquist, N/2)
    return {
        frequencies: frequencies.slice(0, Math.floor(N / 2)),
        magnitudes: magnitudes.slice(0, Math.floor(N / 2))
    };
}

/**
 * Extracts respiration/heart rate from the CSI phase of H1·conj(H2) over a
 * 10 s window. Supports the presence story: a person standing perfectly
 * still produces no motion-gate energy, but their chest displacement still
 * modulates phase in the 0.1–0.5 Hz (breathing) and 0.8–2.0 Hz (heart)
 * bands. Results are broadcast as `vitalSigns` and shown only while a
 * target is visible.
 */
export class VitalsComputer {
    private phaseBuffer: number[] = [];
    private readonly bufferSize: number;
    private readonly sampleRate: number;
    private hampel: HampelFilter;

    // Last calculated vitals
    private currentHeartRate: number = 0;
    private currentRespRate: number = 0;
    private reliable: boolean = false;

    constructor(sampleRate: number = 20, windowSeconds: number = 10) {
        this.sampleRate = sampleRate;
        this.bufferSize = sampleRate * windowSeconds;
        // Window size 7, 3 sigmas for physiological noise rejection
        this.hampel = new HampelFilter(7, 3.0);
    }

    /**
     * Pushes a new raw phase value into the computer.
     * Phase should ideally be from the conjugate-multiplied complex signal (e.g. H1 * conj(H2))
     */
    push(rawPhase: number) {
        // 1. Hampel outlier rejection on raw phase
        const cleanedPhase = this.hampel.push(rawPhase);

        this.phaseBuffer.push(cleanedPhase);
        if (this.phaseBuffer.length > this.bufferSize) {
            this.phaseBuffer.shift();
        }
    }

    /**
     * Computes the vital signs running spectral analysis on the current phase buffer.
     * Returns BPM (Heart) and RPM (Respiration).
     */
    computeVitals(): { heartRateBpm: number, respirationRateRpm: number, vitalsReliable: boolean } {
        if (this.phaseBuffer.length < this.bufferSize / 2) {
            // Need at least 50% buffer to give a reasonable estimate
            return { heartRateBpm: 0, respirationRateRpm: 0, vitalsReliable: false };
        }

        // 2. Unwrap phase
        const unwrapped = unwrapPhase(this.phaseBuffer);

        // 3. Spectral Analysis via DFT
        const { frequencies, magnitudes } = computeDFT(unwrapped, this.sampleRate);

        // 4. Extract Breathing Rate (0.1 Hz - 0.5 Hz) -> ~6 to 30 RPM
        let maxRespMag = 0;
        let respFreq = 0;

        // 5. Extract Heart Rate (0.8 Hz - 2.0 Hz) -> ~48 to 120 BPM
        let maxHbMag = 0;
        let hbFreq = 0;

        for (let i = 0; i < frequencies.length; i++) {
            const f = frequencies[i];
            const m = magnitudes[i];

            // Breathing band
            if (f >= 0.1 && f <= 0.5) {
                if (m > maxRespMag) {
                    maxRespMag = m;
                    respFreq = f;
                }
            }

            // Heart band
            if (f >= 0.8 && f <= 2.0) {
                if (m > maxHbMag) {
                    maxHbMag = m;
                    hbFreq = f;
                }
            }
        }

        // Convert Hz to Beats/Respirations per minute
        this.currentRespRate = respFreq * 60;
        this.currentHeartRate = hbFreq * 60;

        // Simple heuristic: if magnitude is extremely low, it's just noise and not reliable
        this.reliable = (maxRespMag > 0.05 && maxHbMag > 0.01);

        return {
            heartRateBpm: Math.round(this.currentHeartRate),
            respirationRateRpm: Math.round(this.currentRespRate),
            vitalsReliable: this.reliable
        };
    }

    reset() {
        this.phaseBuffer = [];
        this.hampel.reset();
        this.currentHeartRate = 0;
        this.currentRespRate = 0;
        this.reliable = false;
    }
}
