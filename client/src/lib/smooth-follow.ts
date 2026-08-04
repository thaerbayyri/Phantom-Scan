import * as THREE from "three";

// Multi-second deltas (tab restore, GC pause) would otherwise blow the
// exponential-decay alpha past 1 and overshoot the target.
const MAX_DELTA = 0.1;

/** In-place exponential-decay lerp toward `target`, independent of frame rate. */
export function dampVector3(
    current: THREE.Vector3,
    target: THREE.Vector3,
    decayRate: number,
    delta: number,
): void {
    const d = Math.min(delta, MAX_DELTA);
    const alpha = 1 - Math.exp(-decayRate * d);
    current.lerp(target, alpha);
}

/** Exponential-decay blend of a wrapped angle (radians) toward `target`. */
export function dampAngle(
    current: number,
    target: number,
    decayRate: number,
    delta: number,
): number {
    const d = Math.min(delta, MAX_DELTA);
    const alpha = 1 - Math.exp(-decayRate * d);
    const diff = target - current;
    const wrapped = Math.atan2(Math.sin(diff), Math.cos(diff));
    return current + wrapped * alpha;
}

/** Exponential-decay blend of a plain scalar toward `target`. */
export function dampScalar(
    current: number,
    target: number,
    decayRate: number,
    delta: number,
): number {
    const d = Math.min(delta, MAX_DELTA);
    const alpha = 1 - Math.exp(-decayRate * d);
    return current + (target - current) * alpha;
}

// Decay rates (k = -ln(1-alpha) * 60), derived from the per-frame lerp
// alphas the radar target marker/mesh were originally tuned with at ~60fps.
// Centralized here (rather than duplicated as literals in RadialScene,
// DirectionalNode, HumanMesh) so smooth-follow.test.ts can guard the
// alpha->k derivation against silent drift.
export const DECAY_RATES = {
    positionFar: 128, // distance-to-target > 0.25m
    positionFast: 97, // target speed > 0.18 m/s
    positionFusedBase: 72, // fused two-node mode, base rate
    positionFusedNearScale: 55, // fused: + nearNodeStrength * this
    positionNear: 55, // distance-to-target > 0.08m
    positionSettle: 25, // else (nearly on top of the target)
    speed: 8, // smoothed target.speed feeding visual scale (tau ~125ms)
    headingArrowFused: 15, // DirectionalNode heading, fused two-node mode
    headingArrowSingle: 8, // DirectionalNode heading, single-node mode
    headingBodyFused: 13.5, // HumanMesh heading, fused two-node mode
    headingBodySingle: 8, // HumanMesh heading, single-node mode
} as const;
