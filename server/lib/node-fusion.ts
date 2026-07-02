/**
 * Two-node CSI fusion (RuView-style 1-D localization).
 *
 * With only two nodes we cannot resolve a true (x, z). What we CAN do — following
 * RuView's `ruview-dashboard-bridge.py` — is use each node's *absolute, unsaturated*
 * per-window amplitude perturbation (`absStd`) as a proximity proxy, then place the
 * target on the straight line between the two board anchors via
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
 * Display-only motion saturation scale (the inherited RuView `* 4`).
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
 * This default is a PLACEHOLDER. It MUST be calibrated from a recorded empty-room
 * baseline (`mean + k·σ` of `max(motion1, motion2)`), and validated against a
 * negative control: a fan/curtain must be REJECTED while a still (breathing-only)
 * person is still detected. Override at runtime via PHANTOM_MOTION_THRESHOLD.
 */
export const DEFAULT_MOTION_THRESHOLD = Number.parseFloat(
  process.env.PHANTOM_MOTION_THRESHOLD ?? "0.12",
);

const EPS = 1e-6;

export interface NodeMotion {
  /** Mean amplitude over the window. */
  mean: number;
  /** Raw, UNSATURATED per-window std of amplitude — used for `balance`. */
  absStd: number;
  /** Saturated 0..1 motion for display/thresholding only. */
  motion: number;
}

/** Population std (matches RuView `_pvar` = sum((x-mean)^2)/n). */
function pstdev(xs: number[], mean: number): number {
  if (xs.length === 0) return 0;
  let acc = 0;
  for (const x of xs) {
    const d = x - mean;
    acc += d * d;
  }
  return Math.sqrt(acc / xs.length);
}

/**
 * Per-node motion energy from a window of amplitude samples.
 * `absStd` (raw) feeds localization; `motion` (saturated) feeds display + gating.
 */
export function computeNodeMotion(amps: number[]): NodeMotion {
  if (amps.length === 0) {
    return { mean: 0, absStd: 0, motion: 0 };
  }
  const mean = amps.reduce((s, v) => s + v, 0) / amps.length;
  const absStd = pstdev(amps, mean);
  const base = mean || 1.0;
  const motion = Math.min(1.0, (absStd / base) * MOTION_SATURATION_SCALE);
  return { mean, absStd, motion };
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
}

export interface FusedTarget {
  x: number;
  z: number;
  /** 0 → at node 1, 0.5 → midpoint, 1 → at node 2. */
  balance: number;
  /** Range to the NEAREST node anchor in meters (physically meaningful). */
  distToNearestNodeM: number;
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

  const present = Math.max(input.motion1, input.motion2) >= threshold && r1 + r2 > EPS;
  if (!present) {
    return null;
  }

  const balance = r2 / (r1 + r2);
  const n1 = input.anchors[1];
  const n2 = input.anchors[2];
  const x = n1.x + (n2.x - n1.x) * balance;
  const z = n1.z + (n2.z - n1.z) * balance;

  const d1 = Math.hypot(x - n1.x, z - n1.z);
  const d2 = Math.hypot(x - n2.x, z - n2.z);

  return { x, z, balance, distToNearestNodeM: Math.min(d1, d2) };
}
