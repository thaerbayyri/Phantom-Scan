import type { PointCloudPoint, TrackedTarget } from "@shared/schema";

// ── Item 4 (PhantomScan_Research_Gap_Analysis.md): spatial noise-floor
// calibration ─────────────────────────────────────────────────────────
//
// ADR-057 flagged `maxEnergy > 10` (below, TrackingProcessor.process) as a
// hardcoded threshold with no documented derivation and no calibrated
// absolute noise floor — unlike the temporal MotionGate
// (server/lib/signal-processing.ts), which auto-calibrates against its
// first 100 samples. This mainly exposes STATIONARY-person detection via
// spatial clustering; the temporal motion gate already covers moving
// targets, so this is not the primary presence signal.
//
// IMPORTANT CAVEAT this calibration does NOT fix: per DETECTION_REPORT.md
// ("Single-antenna caveat") and the AoA UI copy across the client, the
// MUSIC/AoA *angle* feeding this point cloud is synthetic-only on the
// current single-antenna hardware — it carries no physically valid spatial
// aperture. Calibrating `energyThreshold` only calibrates the MAGNITUDE
// judgment ("is there real reflected energy here at all", used solely as
// presence evidence via hasSingleNodePresenceEvidence's hasTrackedTarget
// input) — it does NOT make the resulting point/cluster POSITION any more
// physically meaningful. Do not present a calibrated energy threshold as
// having fixed AoA accuracy; it has not.

/**
 * Empty-room / negative-control calibration for a magnitude-only energy
 * threshold — mean+k*sigma over the samples given: a provisional, descriptive
 * helper, not drift- or pooling-checked (scripts/calibrate-threshold.ts no longer
 * derives PHANTOM_MOTION_THRESHOLD this way; PS-FIX-11), applied here to cluster energy (or raw MUSIC spectrum power) samples
 * instead of temporal motion variance. Pure and unit-testable with
 * synthetic OR real recorded empty-room samples — this function itself
 * makes no live/network calls.
 */
export interface EnergyThresholdCalibration {
  sampleCount: number;
  mean: number;
  sigma: number;
  max: number;
  /** mean + kSigma * sigma — the suggested absolute threshold. */
  suggestedThreshold: number;
}

export function calibrateEnergyThreshold(
  emptyRoomEnergySamples: number[],
  kSigma: number = 3,
): EnergyThresholdCalibration {
  const samples = emptyRoomEnergySamples.filter((v) => Number.isFinite(v));
  if (samples.length === 0) {
    return { sampleCount: 0, mean: 0, sigma: 0, max: 0, suggestedThreshold: 0 };
  }
  const mean = samples.reduce((s, v) => s + v, 0) / samples.length;
  const variance = samples.reduce((s, v) => s + (v - mean) * (v - mean), 0) / samples.length;
  const sigma = Math.sqrt(variance);
  const max = Math.max(...samples);
  return { sampleCount: samples.length, mean, sigma, max, suggestedThreshold: mean + kSigma * sigma };
}

/** Env-overridable default so a calibration result can be applied without a
 * code change, matching the DEFAULT_MOTION_THRESHOLD convention in
 * node-fusion.ts. Unchanged (10) until a real empty-room capture exists —
 * see docs/SPATIAL_CALIBRATION.md for status ([TO BE MEASURED]). */
export const DEFAULT_SPATIAL_ENERGY_THRESHOLD = Number.parseFloat(
  process.env.PHANTOM_SPATIAL_ENERGY_THRESHOLD ?? "10",
);

// ── DBSCAN Clustering ───────────────────────────────────────────────

export class DBSCAN {
    private eps: number;
    private minPts: number;

    constructor(eps: number = 0.5, minPts: number = 3) {
        this.eps = eps;
        this.minPts = minPts;
    }

    public cluster(points: PointCloudPoint[]): PointCloudPoint[][] {
        const visited = new Set<number>();
        const clusters: PointCloudPoint[][] = [];

        for (let i = 0; i < points.length; i++) {
            if (visited.has(i)) continue;

            visited.add(i);
            const neighbors = this.regionQuery(points, i);

            if (neighbors.length < this.minPts) {
                // Noise (initially), but might be part of another cluster later
                // We don't mark as noise explicitly here, just skip starting a cluster
                continue;
            }

            const cluster: PointCloudPoint[] = [points[i]];
            this.expandCluster(points, visited, neighbors, cluster);
            clusters.push(cluster);
        }

        return clusters;
    }

    private expandCluster(
        points: PointCloudPoint[],
        visited: Set<number>,
        neighbors: number[],
        cluster: PointCloudPoint[]
    ) {
        for (let i = 0; i < neighbors.length; i++) {
            const neighborIdx = neighbors[i];

            if (!visited.has(neighborIdx)) {
                visited.add(neighborIdx);
                const newNeighbors = this.regionQuery(points, neighborIdx);
                if (newNeighbors.length >= this.minPts) {
                    neighbors.push(...newNeighbors);
                }
            }

            // Check if point is not yet member of any cluster
            // Simplified: Just add to current cluster if not already there
            // Unique add handling is implicit if we process carefully,
            // but for simplicity we just add. A Set/Map check would be rigorous.
            // Here we assume disjoint due to visited check, but points can be border points.
            // For this specific visualization, approximate is fine.
            if (!cluster.includes(points[neighborIdx])) {
                cluster.push(points[neighborIdx]);
            }
        }
    }

    private regionQuery(points: PointCloudPoint[], pointIdx: number): number[] {
        const neighbors: number[] = [];
        const p = points[pointIdx];

        for (let i = 0; i < points.length; i++) {
            if (i === pointIdx) continue;
            if (this.distance(p, points[i]) <= this.eps) {
                neighbors.push(i);
            }
        }
        return neighbors;
    }

    private distance(p1: PointCloudPoint, p2: PointCloudPoint): number {
        return Math.sqrt(
            Math.pow(p1.x - p2.x, 2) +
            Math.pow(p1.y - p2.y, 2) +
            Math.pow(p1.z - p2.z, 2)
        );
    }
}

// ── Kalman Filter ───────────────────────────────────────────────────

/**
 * 6-state constant-velocity Kalman filter [x,y,z,vx,vy,vz] that smooths the
 * noisy cluster centroid into a stable target track. Its velocity estimate is
 * where the target's `speed`/`isMoving` and heading come from, so movement
 * shown on the radar is filtered physics, not raw frame-to-frame jitter.
 */
export class KalmanFilter {
    // State: [x, y, z, vx, vy, vz]
    private x: number[];
    private P: number[][]; // Covariance
    private Q: number[][]; // Process noise
    private R: number[][]; // Measurement noise
    private lastUpdate: number;

    constructor() {
        this.x = [0, 0, 0, 0, 0, 0];
        this.lastUpdate = Date.now();

        // Initial covariance
        this.P = this.identity(6, 1.0);

        // Process noise (trust the physics model this much)
        // Low = smooth but laggy, High = reactive but jittery
        this.Q = this.identity(6, 0.01);

        // Measurement noise (trust the sensor this much)
        // High = trust model more, Low = trust measurement more
        this.R = this.identity(3, 0.1);
    }

    public predict() {
        const now = Date.now();
        // Clamp dt to a reasonable minimum (e.g. 20Hz = 0.05s) to avoid 
        // infinite velocity explosions during sudden packet bursts.
        const dt = Math.max(0.05, (now - this.lastUpdate) / 1000);
        this.lastUpdate = now;

        // State Transition Matrix F
        // x' = x + vx*dt
        const F = [
            [1, 0, 0, dt, 0, 0],
            [0, 1, 0, 0, dt, 0],
            [0, 0, 1, 0, 0, dt],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1],
        ];

        // Predict state: x = F * x
        const newX = new Array(6).fill(0);
        for (let i = 0; i < 6; i++) {
            for (let j = 0; j < 6; j++) {
                newX[i] += F[i][j] * this.x[j];
            }
        }
        this.x = newX;

        // Predict covariance: P = F*P*F' + Q
        // Simplified for diagonal Q/P for performance if needed, but doing full matrix mult here
        const FP = this.multiply(F, this.P);
        const FPFt = this.multiply(FP, this.transpose(F));
        this.P = this.add(FPFt, this.Q);
    }

    public update(measurement: [number, number, number]) {
        // Measurement Matrix H (we measure x, y, z)
        const H = [
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
        ];

        // Innovation: y = z - Hx
        const y = [
            measurement[0] - this.x[0],
            measurement[1] - this.x[1],
            measurement[2] - this.x[2],
        ];

        // Innovation Covariance: S = H*P*H' + R
        const HP = this.multiply(H, this.P);
        const S = this.add(this.multiply(HP, this.transpose(H)), this.R);

        // Kalman Gain: K = P*H'*inv(S)
        const Sinv = this.invert3x3(S);
        if (Sinv === null) {
            // Phase-1 bug audit: S was singular/near-singular — skip this
            // update rather than injecting NaN/Infinity into tracked
            // position/velocity, which would otherwise corrupt the track
            // until the next trackingProcessor.reset().
            console.warn("[Kalman] skipping update: singular innovation covariance");
            return;
        }
        const K = this.multiply(this.multiply(this.P, this.transpose(H)), Sinv);

        // Update State: x = x + K*y
        for (let i = 0; i < 6; i++) {
            for (let j = 0; j < 3; j++) {
                this.x[i] += K[i][j] * y[j];
            }
        }

        // Physics-based constrain: human sprint limit (~10 m/s)
        const MAX_HUMAN_SPEED = 10.0;
        this.x[3] = Math.max(-MAX_HUMAN_SPEED, Math.min(MAX_HUMAN_SPEED, this.x[3])); // vx
        this.x[4] = Math.max(-MAX_HUMAN_SPEED, Math.min(MAX_HUMAN_SPEED, this.x[4])); // vy
        this.x[5] = Math.max(-MAX_HUMAN_SPEED, Math.min(MAX_HUMAN_SPEED, this.x[5])); // vz

        // Update Covariance: P = (I - K*H)*P
        const I = this.identity(6);
        const KH = this.multiply(K, H);
        this.P = this.multiply(this.subtract(I, KH), this.P);
    }

    public getState() {
        return {
            x: this.x[0],
            y: this.x[1],
            z: this.x[2],
            vx: this.x[3],
            vy: this.x[4],
            vz: this.x[5],
        };
    }

    // ── Helper Math ──

    private identity(n: number, val: number = 1.0): number[][] {
        return Array(n).fill(0).map((_, i) => Array(n).fill(0).map((_, j) => (i === j ? val : 0)));
    }

    private multiply(A: number[][], B: number[][]): number[][] {
        const rowsA = A.length, colsA = A[0].length, colsB = B[0].length;
        const C = Array(rowsA).fill(0).map(() => Array(colsB).fill(0));
        for (let i = 0; i < rowsA; i++) {
            for (let j = 0; j < colsB; j++) {
                for (let k = 0; k < colsA; k++) {
                    C[i][j] += A[i][k] * B[k][j];
                }
            }
        }
        return C;
    }

    private add(A: number[][], B: number[][]): number[][] {
        return A.map((row, i) => row.map((val, j) => val + B[i][j]));
    }

    private subtract(A: number[][], B: number[][]): number[][] {
        return A.map((row, i) => row.map((val, j) => val - B[i][j]));
    }

    private transpose(A: number[][]): number[][] {
        return A[0].map((_, i) => A.map(row => row[i]));
    }

    private invert3x3(m: number[][]): number[][] | null {
        // Standard 3x3 inversion
        const det =
            m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
            m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

        // Phase-1 bug audit: a singular/near-singular S previously produced
        // invDet = Infinity/NaN with no guard, silently corrupting the
        // tracked state. Reject rather than propagate.
        if (!Number.isFinite(det) || Math.abs(det) < 1e-9) {
            return null;
        }

        const invDet = 1 / det;

        return [
            [
                (m[1][1] * m[2][2] - m[2][1] * m[1][2]) * invDet,
                (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet,
                (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet,
            ],
            [
                (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet,
                (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet,
                (m[1][0] * m[0][2] - m[0][0] * m[1][2]) * invDet,
            ],
            [
                (m[1][0] * m[2][1] - m[2][0] * m[1][1]) * invDet,
                (m[2][0] * m[0][1] - m[0][0] * m[2][1]) * invDet,
                (m[0][0] * m[1][1] - m[1][0] * m[0][1]) * invDet,
            ],
        ];
    }
}

// ── Tracking Processor ──────────────────────────────────────────────

export class TrackingProcessor {
    private dbscan: DBSCAN;
    private kalman: KalmanFilter;
    private lastTarget: TrackedTarget | null = null;
    private consecutiveMisses = 0;
    /** Item 4: was a hardcoded literal `10` inline below; now configurable
     * (default unchanged) so a real calibration result — see
     * calibrateEnergyThreshold / DEFAULT_SPATIAL_ENERGY_THRESHOLD above —
     * can be applied without editing this class. */
    private energyThreshold: number;

    private pointBuffer: PointCloudPoint[] = [];

    constructor(energyThreshold: number = DEFAULT_SPATIAL_ENERGY_THRESHOLD) {
        this.dbscan = new DBSCAN(0.8, 4); // eps=0.8m, minPts=4
        this.kalman = new KalmanFilter();
        this.energyThreshold = energyThreshold;
    }

    public reset() {
        this.kalman = new KalmanFilter();
        this.lastTarget = null;
        this.consecutiveMisses = 0;
        this.pointBuffer = [];
    }

    /**
     * One tracking step per frame: buffer the newest AoA point-cloud points,
     * DBSCAN-cluster them, pick the highest-energy cluster as the target,
     * feed its amplitude-weighted centroid to the Kalman filter, and derive
     * speed (m/s), isMoving (speed > 0.1) and heading. Coasts through up to
     * 10 consecutive misses (~0.5 s) before declaring the target lost (null).
     */
    public process(newPoints: PointCloudPoint[]): TrackedTarget | null {
        // Add new points to buffer
        this.pointBuffer.push(...newPoints);

        // Keep last 50 points or so to have density for clustering
        if (this.pointBuffer.length > 50) {
            this.pointBuffer = this.pointBuffer.slice(-50);
        }

        if (this.pointBuffer.length === 0) return null;

        // 1. Cluster points
        const clusters = this.dbscan.cluster(this.pointBuffer);

        // 2. Identify target (largest cluster)
        let bestCluster: PointCloudPoint[] | null = null;
        let maxEnergy = -Infinity;

        for (const cluster of clusters) {
            // Calculate total energy of cluster
            const energy = cluster.reduce((sum, p) => sum + p.amplitude, 0);
            if (energy > maxEnergy) {
                maxEnergy = energy;
                bestCluster = cluster;
            }
        }

        // 3. Update Kalman Filter
        this.kalman.predict(); // Always predict

        let acquiredThisTick = false;
        if (bestCluster && maxEnergy > this.energyThreshold) { // Item 4: calibratable (see class field)
            acquiredThisTick = true;
            // Calculate centroid
            let cx = 0, cy = 0, cz = 0;
            let totalWeight = 0;

            for (const p of bestCluster) {
                cx += p.x * p.amplitude;
                cy += p.y * p.amplitude;
                cz += p.z * p.amplitude;
                totalWeight += p.amplitude;
            }

            cx /= totalWeight;
            cy /= totalWeight;
            cz /= totalWeight;

            // Update Filter
            this.kalman.update([cx, cy, cz]);
            this.consecutiveMisses = 0;
        } else {
            this.consecutiveMisses++;
        }

        // 4. Return result if valid.
        //
        // PS-GAP-TRK-001 (found by tracking.test.ts, this session): coasting
        // through misses is only legitimate if a target was ACTUALLY ACQUIRED
        // at some point — without the acquired/lastTarget check below, a cold
        // start with only sub-threshold noise clusters returned a fabricated
        // target at the Kalman origin (confidence 0.9) for the first 10
        // ticks, and that non-null return is precisely the `hasTrackedTarget`
        // evidence ADR-057's single-node presence gate trusts.
        if ((acquiredThisTick || this.lastTarget) && this.consecutiveMisses < 10) { // Keep track for ~0.5s if lost
            const state = this.kalman.getState();
            const speed = Math.sqrt(state.vx ** 2 + state.vz ** 2);
            const isMoving = speed > 0.1;

            // Calculate angle (facing direction)
            let angle = this.lastTarget?.angle || 0;
            if (isMoving) {
                angle = Math.atan2(state.vz, state.vx);
            }

            this.lastTarget = {
                id: 1, // Single target for now
                x: state.x,
                y: state.y,
                z: state.z,
                vx: state.vx,
                vy: state.vy,
                vz: state.vz,
                intensity: maxEnergy > 0 ? maxEnergy : (this.lastTarget?.intensity || 0) * 0.9,
                confidence: Math.max(0, 1.0 - this.consecutiveMisses * 0.1),
                isMoving,
                angle,
            };
            return this.lastTarget;
        }

        this.lastTarget = null;
        return null;
    }
}
