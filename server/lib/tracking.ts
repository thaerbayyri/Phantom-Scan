import type { PointCloudPoint, TrackedTarget } from "@shared/schema";

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
        const dt = (now - this.lastUpdate) / 1000;
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
        const K = this.multiply(this.multiply(this.P, this.transpose(H)), this.invert3x3(S));

        // Update State: x = x + K*y
        for (let i = 0; i < 6; i++) {
            for (let j = 0; j < 3; j++) {
                this.x[i] += K[i][j] * y[j];
            }
        }

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

    private invert3x3(m: number[][]): number[][] {
        // Standard 3x3 inversion
        const det =
            m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
            m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

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

    private pointBuffer: PointCloudPoint[] = [];

    constructor() {
        this.dbscan = new DBSCAN(0.8, 4); // eps=0.8m, minPts=4
        this.kalman = new KalmanFilter();
    }

    public reset() {
        this.kalman = new KalmanFilter();
        this.lastTarget = null;
        this.consecutiveMisses = 0;
        this.pointBuffer = [];
    }

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

        if (bestCluster && maxEnergy > 10) { // Threshold for valid target
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

        // 4. Return result if valid
        if (this.consecutiveMisses < 10) { // Keep track for ~0.5s if lost
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
