/**
 * Phantom Balance Fusion — two-node CSI fusion, 1-D localization.
 *
 * With only two nodes we cannot resolve a true (x, z). What we CAN do is use each
 * node's *absolute, unsaturated* per-window amplitude perturbation (`absStd`) as a
 * proximity proxy, then place the target on the straight line between the two board
 * anchors via
 *
 *     balance = r2 / (r1 + r2)     (0 → at node 1, 0.5 → midpoint, 1 → at node 2)
 *
 * This module is intentionally PURE (no sockets, no clock) so the localization math
 * is unit-tested independently of the websocket pipeline.
 */

export interface NodeAnchor {
  x: number;
  z: number;
}

/**
 * Display-only motion saturation scale (the legacy `* 4` factor).
 *
 * COUPLING WARNING: this constant only affects the *display* `motion` value
 * (localization uses the raw unsaturated `absStd`). But `motion` is exactly what
 * `motionThreshold` is compared against, so it sets where motion saturates to 1.0.
 * If you retune this, re-derive `motionThreshold` in the same change — never
 * independently. See `computeNodeMotion` and `DEFAULT_MOTION_THRESHOLD`.
 */
export const MOTION_SATURATION_SCALE = 4;

/**
 * Presence/motion gate for emitting a fused target. THIS IS THE DETECTOR.
 *
 * Calibrated 2026-07-20 against this rig's measured empty-room baseline
 * (`max(motion1, motion2)` over 296 samples: mean 0.49, sigma 0.027, max 0.58 —
 * see LIVE_HARDWARE_TEST_REPORT.md). 0.6 sits just above that noise ceiling.
 * Re-calibrate via scripts/calibrate-threshold.ts (and re-validate against a
 * negative control: a fan/curtain must be REJECTED while a still, breathing-only
 * person is still detected) if the room or hardware setup changes materially.
 * Override at runtime via PHANTOM_MOTION_THRESHOLD, or persistently via the
 * "Fused Target Presence Threshold" slider (server/lib/runtime-settings.ts).
 */
export const DEFAULT_MOTION_THRESHOLD = Number.parseFloat(
  process.env.PHANTOM_MOTION_THRESHOLD ?? "0.6",
);

/**
 * Deadband for the approach/recede trend, in m/s along the N1–N2 axis.
 *
 * PLACEHOLDER (~0.05 m/s) — calibrate against real data, not settled. At the
 * ~3–7 fps historically measured on this firmware path, balance updates are
 * ~150–330 ms apart and balance itself is noisy over its 3 s window, so the
 * instantaneous velocity estimate is jumpy. This deadband is coupled to the
 * same window/fps assumptions as PHANTOM_MOTION_THRESHOLD — retune together.
 * Override at runtime via PHANTOM_TREND_DEADBAND_MPS.
 */
export const TREND_DEADBAND_MPS = Number.parseFloat(
  process.env.PHANTOM_TREND_DEADBAND_MPS ?? "0.05",
);

/**
 * Endpoint bias for the display projection.
 *
 * 1.0 = linear balance; values below 1 pull the projected x harder toward the
 * nearest node while keeping 0, 0.5, and 1 fixed. This affects only the
 * on-axis displayed position, not the underlying balance ratio.
 */
export const BALANCE_BIAS_EXPONENT = Number.parseFloat(
  process.env.PHANTOM_BALANCE_BIAS_EXPONENT ?? "0.72",
);

/**
 * Contrast exponent applied to the raw per-node perturbations BEFORE the
 * balance ratio: balance = r2^p / (r1^p + r2^p).
 *
 * Both nodes see the same walking person, so r1 and r2 are correlated and the
 * linear ratio compresses toward 0.5 (the dot hugs the midpoint). p > 1 widens
 * balance toward 0/1 when one node clearly sees more perturbation, letting the
 * target reach the node it is actually near. p = 1 restores the linear ratio.
 * Unlike BALANCE_BIAS_EXPONENT (display-only), this shapes the balance VALUE
 * and therefore also the trend velocity. Override via PHANTOM_BALANCE_CONTRAST.
 */
export const BALANCE_CONTRAST_EXPONENT = Number.parseFloat(
  process.env.PHANTOM_BALANCE_CONTRAST ?? "2.0",
);

export type NodeTrend = "approaching" | "receding" | "stable";

/**
 * Per-node approach/recede trend from the signed axis velocity.
 *
 * `axisVelMps` > 0 means balance rising = target moving toward node 2.
 * Inside the deadband the PREVIOUS trends are kept (hysteresis) so the label
 * doesn't flicker between frames; pass `{ 1: "stable", 2: "stable" }` when no
 * live target exists.
 */
export function computeNodeTrends(
  axisVelMps: number,
  prev: { 1: NodeTrend; 2: NodeTrend },
  deadbandMps: number = TREND_DEADBAND_MPS,
): { 1: NodeTrend; 2: NodeTrend } {
  if (!Number.isFinite(axisVelMps) || Math.abs(axisVelMps) < deadbandMps) {
    return prev;
  }
  return axisVelMps > 0
    ? { 1: "receding", 2: "approaching" } // balance rising -> toward N2
    : { 1: "approaching", 2: "receding" };
}

const EPS = 1e-6;

export interface NodeMotion {
  /** Mean amplitude over the window. */
  mean: number;
  /** Raw, UNSATURATED per-window std of amplitude — used for `balance`. */
  absStd: number;
  /** Saturated 0..1 motion for display/thresholding only. */
  motion: number;
}

/**
 * Per-node motion energy from a window of per-subcarrier amplitude FRAMES
 * (each frame = amplitude vector for one received packet).
 *
 * Per-node update step:
 *   k         = min frame length (subcarrier count)
 *   sub_std_j = temporal pstdev of subcarrier j across the window
 *   absStd    = mean(sub_std)          — raw, unsaturated → balance
 *   base      = mean frame amplitude   — normalizer
 *   motion    = min(1, absStd/base·4)  — display/threshold only
 *
 * This is what makes balance track a moving person: per-subcarrier temporal
 * variation is human-induced perturbation, whereas a single "best subcarrier"
 * scalar changes selection index frame-to-frame and its std is mostly noise.
 */
export function computeNodeMotionFromMatrix(frames: number[][]): NodeMotion {
  const usable = frames.filter((f) => f.length > 0);
  if (usable.length < 2) {
    return { mean: 0, absStd: 0, motion: 0 };
  }
  const k = Math.min(...usable.map((f) => f.length));
  if (k === 0) {
    return { mean: 0, absStd: 0, motion: 0 };
  }

  // Per-subcarrier temporal std: for each subcarrier j, measure how much its
  // amplitude varied across the window, then average the k stds into absStd —
  // the raw (unsaturated) perturbation that feeds the balance ratio.
  let stdSum = 0;
  for (let j = 0; j < k; j++) {
    let m = 0;
    for (const f of usable) m += f[j];
    m /= usable.length;
    let acc = 0;
    for (const f of usable) {
      const d = f[j] - m;
      acc += d * d;
    }
    stdSum += Math.sqrt(acc / usable.length);
  }
  const absStd = stdSum / k;

  // Baseline amplitude (mean over subcarriers, then over frames) — normalizes
  // absStd so `motion` is a relative perturbation comparable across nodes with
  // different RSSI/gain. `|| 1.0` guards divide-by-zero on silent input.
  let base = 0;
  for (const f of usable) {
    let s = 0;
    for (let j = 0; j < k; j++) s += f[j];
    base += s / k;
  }
  base = base / usable.length || 1.0;

  const motion = Math.min(1.0, (absStd / base) * MOTION_SATURATION_SCALE);
  return { mean: base, absStd, motion };
}

export interface FuseInput {
  /** Raw unsaturated perturbation (absStd) for node 1 and node 2. */
  r1: number;
  r2: number;
  /** Saturated display motion for node 1 and node 2 (for the presence gate). */
  motion1: number;
  motion2: number;
  anchors: { 1: NodeAnchor; 2: NodeAnchor };
  motionThreshold?: number;
  /** Balance contrast exponent p (default BALANCE_CONTRAST_EXPONENT). */
  contrastExponent?: number;
}

export interface FusedTarget {
  x: number;
  z: number;
  /** 0 → at node 1, 0.5 → midpoint, 1 → at node 2. Contrast-shaped (see
   * BALANCE_CONTRAST_EXPONENT) — this is the DISPLAY value; it is what
   * positions the on-screen target, not the canonical linear ratio. */
  balance: number;
  /** Canonical, undecorated balance = r2/(r1+r2) — independent of
   * BALANCE_CONTRAST_EXPONENT and BALANCE_BIAS_EXPONENT. Authoritative
   * cross-check value (PS-AUDIT-003/011, ADR-054); never drives the
   * on-screen target position, which remains `balance` above. */
  balanceLinear: number;
  /** Range to the NEAREST node anchor in meters (physically meaningful). */
  distToNearestNodeM: number;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/**
 * Canonical linear balance = r2/(r1+r2), with no contrast exponent or
 * display bias applied. This is the authoritative/canonical cross-check
 * value (PS-AUDIT-003/011, ADR-054) — it is NEVER used to place the
 * on-screen target, which uses the contrast+bias-shaped `balance` instead.
 */
export function computeLinearBalance(r1: number, r2: number): number {
  const a = Number.isFinite(r1) ? Math.max(0, r1) : 0;
  const b = Number.isFinite(r2) ? Math.max(0, r2) : 0;
  return a + b > EPS ? b / (a + b) : 0.5;
}

/**
 * Bias the projected display position toward the nearest node while preserving
 * 0, 0.5, and 1 exactly. Used only for the displayed on-axis estimate.
 */
export function biasBalanceTowardNearestNode(
  balance: number,
  exponent: number = BALANCE_BIAS_EXPONENT,
): number {
  const clamped = clamp01(balance);
  const signed = clamped * 2 - 1;
  const magnitude = Math.abs(signed);
  if (magnitude <= EPS) {
    return 0.5;
  }
  const biasedMagnitude = Math.pow(magnitude, exponent);
  return clamp01(0.5 + Math.sign(signed) * biasedMagnitude * 0.5);
}

/**
 * Fuse two nodes into a 1-D target on the line between the anchors.
 *
 * Returns `null` (NO target — not a centered ghost) when neither node clears the
 * motion threshold, or when there is effectively no perturbation. This is the
 * empty-room gate: a quiet room must not paint a target at the midpoint.
 */
export function fuseTwoNodeTarget(input: FuseInput): FusedTarget | null {
  const threshold = input.motionThreshold ?? DEFAULT_MOTION_THRESHOLD;
  const r1 = Number.isFinite(input.r1) ? Math.max(0, input.r1) : 0;
  const r2 = Number.isFinite(input.r2) ? Math.max(0, input.r2) : 0;

  // PRESENCE GATE: someone is "present" only if at least one node's saturated
  // motion clears the calibrated threshold AND there is real perturbation
  // energy (r1+r2 > EPS). Failing either → null → the UI shows an empty room.
  const present = Math.max(input.motion1, input.motion2) >= threshold && r1 + r2 > EPS;
  if (!present) {
    return null;
  }

  // Contrast-sharpened ratio (see BALANCE_CONTRAST_EXPONENT): widens balance
  // toward the node that clearly sees more perturbation.
  const p = input.contrastExponent ?? BALANCE_CONTRAST_EXPONENT;
  const r1p = Math.pow(r1, p);
  const r2p = Math.pow(r2, p);
  const balance = r1p + r2p > EPS ? r2p / (r1p + r2p) : 0.5;
  // Place the target on the straight N1–N2 line by linear interpolation of the
  // (display-biased) balance: 0 → exactly at node 1, 1 → exactly at node 2.
  const biasedBalance = biasBalanceTowardNearestNode(balance);
  const n1 = input.anchors[1];
  const n2 = input.anchors[2];
  const x = n1.x + (n2.x - n1.x) * biasedBalance;
  const z = n1.z + (n2.z - n1.z) * biasedBalance;

  // Distance to the nearest anchor is the only physically meaningful range in
  // this 1-D geometry (feeds the "distance" readout on the dashboard).
  const d1 = Math.hypot(x - n1.x, z - n1.z);
  const d2 = Math.hypot(x - n2.x, z - n2.z);

  const balanceLinear = computeLinearBalance(r1, r2);

  return { x, z, balance, balanceLinear, distToNearestNodeM: Math.min(d1, d2) };
}

// ── Fallback (non-Kalman, non-fused) velocity — Area 5/NEW-1 ───────────────

export interface FallbackVelocitySample {
  x: number;
  z: number;
  atMs: number;
}

export interface FallbackVelocityResult {
  vx: number;
  vz: number;
  speed: number;
}

/** Real-time gap beyond which a fallback sample is treated as a fresh start, never diffed. */
export const FALLBACK_VELOCITY_MAX_GAP_S = 0.25;
/** Floor on dt so a near-zero interval can't blow up the velocity. */
export const FALLBACK_VELOCITY_MIN_DT_S = 0.02;

/**
 * Frame-rate-independent instantaneous velocity for the non-Kalman, non-fused
 * fallback path (used when the primary DBSCAN/Kalman tracker misses this tick).
 * Returns zero — never a spike — when there is no previous sample or the real
 * elapsed gap exceeds `FALLBACK_VELOCITY_MAX_GAP_S`.
 *
 * Callers own invalidating `prev` (passing `null`) on every condition that
 * breaks positional continuity: primary-tracker success, a fused_two_node
 * <-> single_node mode transition, and the 5s hard-clear/1.5s stale-hold
 * lifecycle — this function only guards the generic real-time-gap case.
 */
export function computeFallbackVelocity(
  prev: FallbackVelocitySample | null,
  raw: { x: number; z: number },
  nowMs: number,
): FallbackVelocityResult {
  if (!prev) {
    return { vx: 0, vz: 0, speed: 0 };
  }
  const realGapS = (nowMs - prev.atMs) / 1000;
  if (realGapS > FALLBACK_VELOCITY_MAX_GAP_S) {
    return { vx: 0, vz: 0, speed: 0 };
  }
  const dt = Math.max(realGapS, FALLBACK_VELOCITY_MIN_DT_S);
  const vx = (raw.x - prev.x) / dt;
  const vz = (raw.z - prev.z) / dt;
  return { vx, vz, speed: Math.hypot(vx, vz) };
}
