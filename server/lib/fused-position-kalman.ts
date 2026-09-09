// ── Fused Position Kalman Filter ────────────────────────────────────

/**
 * Two independent 1-D constant-velocity Kalman filters (x and z), smoothing
 * the fused two-node/N-node target position into a stable track. Unlike
 * `KalmanFilter` (tracking.ts, 6-state 3D, used only by the single-node
 * DBSCAN spatial path), this filter is natively 2-D — there is no y axis, no
 * fake y=0 measurement, and no shared state with that class.
 *
 * Each axis carries state [pos, vel] with a 2x2 P/Q/R, using closed-form
 * scalar Kalman math (the measurement matrix H=[1,0] makes the innovation
 * covariance S a scalar, so no matrix-inversion library is needed).
 *
 * Q/R/dt-ceiling starting values are derived from real captured 4-node
 * `fused_room` sessions (`data/sessions/4_node_test_2026-08-24T10-57-26-139Z.csv`,
 * `room_test_2026-08-27T14-19-35-237Z.csv`, `test_2026-09-08T13-52-34-674Z.csv`,
 * `test_2026-09-08T14-28-06-969Z.csv`, `test_2026-09-08T16-27-23-356Z.csv`):
 *   - Measurement noise (R): the best available near-still segment (18
 *     consecutive low-delta ticks, ~1s, in the 2026-09-08T13-52 session)
 *     gave x_std=0.066m, z_std=0.033m -> R_X=0.0044 m^2, R_Z=0.0011 m^2.
 *     None of these sessions are a dedicated "stand still" capture (all are
 *     walking tests, target_state="moving" for ~4985/5000 rows each), so
 *     this is an upper-bound proxy, not a final calibrated value.
 *   - dt ceiling: real observed max inter-tick gap across the 5 sessions
 *     ranged 0.399s-0.829s, confirming gaps this large genuinely happen.
 *     MAX_DT=0.3s bounds a single predict step below that observed range,
 *     well under the existing 1500ms full-staleness reset elsewhere.
 *   - Process noise (Q): whole-session tick-to-tick spread (dx_std
 *     0.053-0.077m, dz_std 0.084-0.132m at ~55ms median dt) sets Q_POS at
 *     roughly 2.5x the derived R per axis; Q_VEL uses a pedestrian
 *     acceleration process-noise PSD (~0.5 (m/s^2)^2, the low end of
 *     published ranges) to favor smoothing while still tracking real
 *     direction changes.
 * These are initial, data-grounded starting values, not a final
 * calibration — a dedicated stationary-target + empty-room soak (mirroring
 * docs/SPATIAL_CALIBRATION.md's methodology) remains future work.
 */

const MIN_DT_S = 0.001;
const MAX_DT_S = 0.3;
/** Outlier rejection gate, in innovation sigmas (matches this project's
 *  repeated 3-sigma convention — MotionGate auto-cal, calibrate-threshold.ts,
 *  firmware calibration_update). A tick whose raw measurement lands further
 *  than this from the filter's own prediction is treated as a spike and
 *  skipped rather than applied. */
const GATE_SIGMA_MULT = 3.0;

const R_X = 0.0044; // m^2
const R_Z = 0.0011; // m^2
const Q_POS_X = 0.011; // m^2, ~2.5x R_X
const Q_POS_Z = 0.00275; // m^2, ~2.5x R_Z
const Q_VEL = 0.5; // (m/s^2)^2, pedestrian acceleration process noise

interface Axis1DState {
  pos: number;
  vel: number;
  pPp: number; // P[0][0] — position variance
  pPv: number; // P[0][1] == P[1][0] — position/velocity covariance
  pVv: number; // P[1][1] — velocity variance
}

function freshAxisState(): Axis1DState {
  return { pos: 0, vel: 0, pPp: 1.0, pPv: 0, pVv: 1.0 };
}

/** Predict one axis forward by dt (constant-velocity model), in place. */
function predictAxis(s: Axis1DState, dt: number, qPos: number): void {
  s.pos = s.pos + s.vel * dt;
  // vel unchanged (constant-velocity model)
  const pPp = s.pPp + 2 * dt * s.pPv + dt * dt * s.pVv + qPos;
  const pPv = s.pPv + dt * s.pVv;
  const pVv = s.pVv + Q_VEL;
  s.pPp = pPp;
  s.pPv = pPv;
  s.pVv = pVv;
}

/**
 * Update one axis with a position measurement, in place. Returns false (and
 * leaves state at its predicted value) when the measurement is gated out as
 * an outlier — the caller keeps predicting rather than applying it.
 */
function updateAxis(s: Axis1DState, measurement: number, r: number): boolean {
  const y = measurement - s.pos; // innovation
  const S = s.pPp + r; // innovation covariance (scalar: H=[1,0])
  if (Math.abs(y) > GATE_SIGMA_MULT * Math.sqrt(S)) {
    return false;
  }
  const kPos = s.pPp / S;
  const kVel = s.pPv / S;
  s.pos = s.pos + kPos * y;
  s.vel = s.vel + kVel * y;
  s.pPp = (1 - kPos) * s.pPp;
  s.pPv = (1 - kPos) * s.pPv;
  s.pVv = s.pVv - kVel * s.pPv;
  return true;
}

export class FusedPositionKalman {
  private xAxis: Axis1DState = freshAxisState();
  private zAxis: Axis1DState = freshAxisState();
  private lastMs: number | null = null;

  /** Advance both axes by the elapsed time since the last predict/update. */
  public predict(nowMs: number): void {
    const dt =
      this.lastMs === null
        ? MIN_DT_S
        : Math.max(MIN_DT_S, Math.min(MAX_DT_S, (nowMs - this.lastMs) / 1000));
    this.lastMs = nowMs;
    predictAxis(this.xAxis, dt, Q_POS_X);
    predictAxis(this.zAxis, dt, Q_POS_Z);
  }

  /** Correct both axes with a raw fused [x, z] measurement. */
  public update(measurement: [number, number]): void {
    updateAxis(this.xAxis, measurement[0], R_X);
    updateAxis(this.zAxis, measurement[1], R_Z);
  }

  public getState(): { x: number; z: number; vx: number; vz: number } {
    return { x: this.xAxis.pos, z: this.zAxis.pos, vx: this.xAxis.vel, vz: this.zAxis.vel };
  }

  /** Replace both axes' state, mirroring TrackingProcessor.reset()'s
   *  replace-the-instance pattern — call on a node-mode flip so stale
   *  velocity/covariance doesn't leak into the new mode's first tick. */
  public reset(): void {
    this.xAxis = freshAxisState();
    this.zAxis = freshAxisState();
    this.lastMs = null;
  }
}
