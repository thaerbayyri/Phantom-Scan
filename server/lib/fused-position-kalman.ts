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
/**
 * Per-tick process noise validated against the real sessions above
 * (Q_POS ≈ 2.5·R per axis, Q_VEL = 0.5 (m/s)²) at the recordings' ~55 ms
 * median tick. Previously that same Q was added on every predict regardless
 * of dt, so a 0.3 s gap got no more uncertainty than a 55 ms tick and the
 * filter came out of every gap overconfident (then gated out the real,
 * moved target). Q now scales by max(1, dt / REFERENCE_DT_S): unchanged for
 * normal and burst ticks (the live loop is a fixed 50 ms interval, and a
 * smaller-than-validated Q makes the gate reject real motion), proportionally
 * larger across gaps up to MAX_DT_S.
 */
const REFERENCE_DT_S = 0.055;
const Q_POS_X = 0.011; // m^2 per reference tick, ~2.5x R_X
const Q_POS_Z = 0.00275; // m^2 per reference tick, ~2.5x R_Z
const Q_VEL = 0.5; // (m/s)^2 per reference tick, pedestrian acceleration
/** Velocity variance at (re-)initialization — ~1 m/s 1σ, a walking pace. */
const INIT_VEL_VARIANCE = 1.0;
/** Consecutive gated-out measurements after which the filter re-initializes
 *  at the new measurement — a persistent jump is a real relocation (node set
 *  change, dead zone), not a spike, and must not lock the track out. */
const MAX_CONSECUTIVE_REJECTIONS = 5;

interface Axis1DState {
  pos: number;
  vel: number;
  pPp: number; // P[0][0] — position variance
  pPv: number; // P[0][1] == P[1][0] — position/velocity covariance
  pVv: number; // P[1][1] — velocity variance
}

function freshAxisState(): Axis1DState {
  return { pos: 0, vel: 0, pPp: 1.0, pPv: 0, pVv: INIT_VEL_VARIANCE };
}

/** State initialized directly at a measurement (no pull from the origin). */
function axisStateAt(measurement: number, r: number): Axis1DState {
  return { pos: measurement, vel: 0, pPp: r, pPv: 0, pVv: INIT_VEL_VARIANCE };
}

/** Predict one axis forward by dt (constant-velocity model). */
function predictAxis(s: Axis1DState, dt: number, qPos: number): Axis1DState {
  const qScale = Math.max(1, dt / REFERENCE_DT_S);
  return {
    pos: s.pos + s.vel * dt,
    vel: s.vel, // constant-velocity model
    pPp: s.pPp + 2 * dt * s.pPv + dt * dt * s.pVv + qPos * qScale,
    pPv: s.pPv + dt * s.pVv,
    pVv: s.pVv + Q_VEL * qScale,
  };
}

/**
 * Update one axis with a position measurement. Returns null when the
 * measurement is gated out as an outlier — the caller keeps the predicted
 * state rather than applying it.
 */
function updateAxis(s: Axis1DState, measurement: number, r: number): Axis1DState | null {
  const y = measurement - s.pos; // innovation
  const S = s.pPp + r; // innovation covariance (scalar: H=[1,0])
  if (Math.abs(y) > GATE_SIGMA_MULT * Math.sqrt(S)) {
    return null;
  }
  const kPos = s.pPp / S;
  const kVel = s.pPv / S;
  return {
    pos: s.pos + kPos * y,
    vel: s.vel + kVel * y,
    pPp: (1 - kPos) * s.pPp,
    pPv: (1 - kPos) * s.pPv,
    // P11' = P11 − K1·P01 with the PRE-update P01 (previously used the
    // already-shrunk P01, under-reducing velocity variance every tick).
    pVv: s.pVv - kVel * s.pPv,
  };
}

interface AxisTrack {
  state: Axis1DState;
  consecutiveRejections: number;
}

/**
 * Apply one measurement to one axis. Axes gate independently (as validated
 * against the real sessions): a rejected tick keeps the predicted state, and
 * MAX_CONSECUTIVE_REJECTIONS in a row re-initializes that axis at the
 * measurement instead of locking the track out.
 */
function stepAxis(track: AxisTrack, measurement: number, r: number): { track: AxisTrack; rejected: boolean } {
  const next = updateAxis(track.state, measurement, r);
  if (next) return { track: { state: next, consecutiveRejections: 0 }, rejected: false };
  const streak = track.consecutiveRejections + 1;
  if (streak >= MAX_CONSECUTIVE_REJECTIONS) {
    return { track: { state: axisStateAt(measurement, r), consecutiveRejections: 0 }, rejected: true };
  }
  return { track: { state: track.state, consecutiveRejections: streak }, rejected: true };
}

export class FusedPositionKalman {
  private xAxis: Axis1DState = freshAxisState();
  private zAxis: Axis1DState = freshAxisState();
  private xRejectStreak = 0;
  private zRejectStreak = 0;
  private lastMs: number | null = null;
  private initialized = false;
  private rejectedCount = 0;

  /** Advance both axes by the elapsed time since the last predict/update. */
  public predict(nowMs: number): void {
    const dt =
      this.lastMs === null
        ? MIN_DT_S
        : Math.max(MIN_DT_S, Math.min(MAX_DT_S, (nowMs - this.lastMs) / 1000));
    this.lastMs = nowMs;
    if (!this.initialized) return; // nothing to propagate before the first fix
    this.xAxis = predictAxis(this.xAxis, dt, Q_POS_X);
    this.zAxis = predictAxis(this.zAxis, dt, Q_POS_Z);
  }

  /** Correct both axes with a raw fused [x, z] measurement. */
  public update(measurement: [number, number]): void {
    const [mx, mz] = measurement;
    if (!this.initialized) {
      this.reinitializeAt(mx, mz);
      return;
    }
    const x = stepAxis({ state: this.xAxis, consecutiveRejections: this.xRejectStreak }, mx, R_X);
    const z = stepAxis({ state: this.zAxis, consecutiveRejections: this.zRejectStreak }, mz, R_Z);
    this.xAxis = x.track.state;
    this.xRejectStreak = x.track.consecutiveRejections;
    this.zAxis = z.track.state;
    this.zRejectStreak = z.track.consecutiveRejections;
    if (x.rejected || z.rejected) this.rejectedCount++;
  }

  public getState(): { x: number; z: number; vx: number; vz: number } {
    return { x: this.xAxis.pos, z: this.zAxis.pos, vx: this.xAxis.vel, vz: this.zAxis.vel };
  }

  /** Diagonal covariance (position/velocity variance per axis). */
  public getVariance(): { pxx: number; pzz: number; vxx: number; vzz: number } {
    return { pxx: this.xAxis.pPp, pzz: this.zAxis.pPp, vxx: this.xAxis.pVv, vzz: this.zAxis.pVv };
  }

  /** Full 2x2 covariance of the x axis (diagnostics/tests). */
  public getCovarianceX(): { pp: number; pv: number; vv: number } {
    return { pp: this.xAxis.pPp, pv: this.xAxis.pPv, vv: this.xAxis.pVv };
  }

  public measurementVarianceX(): number {
    return R_X;
  }

  /** Total measurements gated out as outliers since construction/reset. */
  public getRejectedCount(): number {
    return this.rejectedCount;
  }

  /** Replace both axes' state, mirroring TrackingProcessor.reset()'s
   *  replace-the-instance pattern — call on a node-mode or active-node-set
   *  change so stale velocity/covariance doesn't leak into the next fix. */
  public reset(): void {
    this.xAxis = freshAxisState();
    this.zAxis = freshAxisState();
    this.lastMs = null;
    this.initialized = false;
    this.xRejectStreak = 0;
    this.zRejectStreak = 0;
    this.rejectedCount = 0;
  }

  private reinitializeAt(x: number, z: number): void {
    this.xAxis = axisStateAt(x, R_X);
    this.zAxis = axisStateAt(z, R_Z);
    this.initialized = true;
    this.xRejectStreak = 0;
    this.zRejectStreak = 0;
  }
}
