import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { dampVector3, dampAngle, dampScalar, DECAY_RATES } from "./smooth-follow";

function kFromAlpha(alpha: number): number {
    return -Math.log(1 - alpha) * 60;
}

// [label, per-frame alpha the constant was derived from, expected k]
// HumanMesh's own position tiers (speed>0.16, fused base, else) are
// documented here even though Area 2 retires HumanMesh's independent
// position lerp in favor of RadialScene's single shared tier system
// (DECAY_RATES.position*) — kept as plain numbers since no live constant
// corresponds to them anymore.
const K_TABLE: Array<[string, number, number]> = [
    ["DirectionalNode position: distance>0.25", 0.88, DECAY_RATES.positionFar],
    ["DirectionalNode position: speed>0.18", 0.8, DECAY_RATES.positionFast],
    ["DirectionalNode position: fused-near-node base", 0.7, DECAY_RATES.positionFusedBase],
    ["DirectionalNode position: distance>0.08", 0.6, DECAY_RATES.positionNear],
    ["DirectionalNode position: else", 0.34, DECAY_RATES.positionSettle],
    ["DirectionalNode heading: fused", 0.22, DECAY_RATES.headingArrowFused],
    ["DirectionalNode heading: non-fused", 0.12, DECAY_RATES.headingArrowSingle],
    ["HumanMesh position: speed>0.16 (retired, documented only)", 0.42, 33],
    ["HumanMesh position: fused base (retired, documented only)", 0.28, 20],
    ["HumanMesh position: else (retired, documented only)", 0.16, 10.5],
    ["HumanMesh heading: fused", 0.2, DECAY_RATES.headingBodyFused],
    ["HumanMesh heading: non-fused", 0.12, DECAY_RATES.headingBodySingle],
];

test("k = -ln(1-alpha)*60 table matches the tuned per-frame alphas", () => {
    for (const [label, alpha, expectedK] of K_TABLE) {
        const k = kFromAlpha(alpha);
        assert.ok(
            Math.abs(k - expectedK) < 1,
            `${label}: alpha=${alpha} -> k=${k.toFixed(2)}, expected ~${expectedK}`,
        );
    }
});

test("DECAY_RATES.positionFusedNearScale approximates positionFar - positionFusedBase", () => {
    // At nearNodeStrength=1 the fused tier's alpha (0.88) coincides with the
    // distance>0.25 tier's alpha, so the k-space step size approximates
    // positionFar - positionFusedBase (the mapping is nonlinear so this is a
    // documented approximation, not an exact identity).
    const step = DECAY_RATES.positionFar - DECAY_RATES.positionFusedBase;
    assert.ok(Math.abs(step - DECAY_RATES.positionFusedNearScale) < 2, `step=${step}`);
});

function simulateDamped(steps: number, totalTime: number, decayRate: number): THREE.Vector3 {
    const current = new THREE.Vector3(0, 0, 0);
    const target = new THREE.Vector3(10, 0, 0);
    const dt = totalTime / steps;
    for (let i = 0; i < steps; i++) {
        dampVector3(current, target, decayRate, dt);
    }
    return current;
}

function simulateFixedAlpha(steps: number, alpha: number): THREE.Vector3 {
    const current = new THREE.Vector3(0, 0, 0);
    const target = new THREE.Vector3(10, 0, 0);
    for (let i = 0; i < steps; i++) {
        current.lerp(target, alpha);
    }
    return current;
}

test("dampVector3 converges to the same result regardless of step count for a fixed elapsed time", () => {
    const totalTime = 1.0;
    const decayRate = 8;

    const resultN = simulateDamped(30, totalTime, decayRate);
    const result2N = simulateDamped(60, totalTime, decayRate);
    const result4N = simulateDamped(120, totalTime, decayRate);

    assert.ok(
        resultN.distanceTo(result2N) < 0.01,
        `30-step vs 60-step diverged: ${resultN.x.toFixed(4)} vs ${result2N.x.toFixed(4)}`,
    );
    assert.ok(
        result2N.distanceTo(result4N) < 0.01,
        `60-step vs 120-step diverged: ${result2N.x.toFixed(4)} vs ${result4N.x.toFixed(4)}`,
    );
});

test("dampScalar and dampAngle share the same frame-rate-independence property", () => {
    const totalTime = 1.0;
    const decayRate = 8;

    let scalarN = 0;
    let scalar2N = 0;
    for (let i = 0; i < 30; i++) scalarN = dampScalar(scalarN, 10, decayRate, totalTime / 30);
    for (let i = 0; i < 60; i++) scalar2N = dampScalar(scalar2N, 10, decayRate, totalTime / 60);
    assert.ok(Math.abs(scalarN - scalar2N) < 0.01, `scalar: ${scalarN} vs ${scalar2N}`);

    let angleN = 0;
    let angle2N = 0;
    const targetAngle = Math.PI * 0.9;
    for (let i = 0; i < 30; i++) angleN = dampAngle(angleN, targetAngle, decayRate, totalTime / 30);
    for (let i = 0; i < 60; i++) angle2N = dampAngle(angle2N, targetAngle, decayRate, totalTime / 60);
    assert.ok(Math.abs(angleN - angle2N) < 0.01, `angle: ${angleN} vs ${angle2N}`);
});

test("a naive fixed-alpha-per-frame lerp is NOT frame-rate independent (the bug this file fixes)", () => {
    // Same wall-clock window, two frame rates: a 60fps display produces
    // ~3 frames in 50ms, a 120fps display produces ~6. A per-frame-fixed
    // alpha (the old bug) treats both as "3 steps of convergence" vs
    // "6 steps of convergence" instead of the same elapsed time.
    const alpha = 0.6;

    const resultN = simulateFixedAlpha(3, alpha);
    const result2N = simulateFixedAlpha(6, alpha);

    assert.ok(
        resultN.distanceTo(result2N) > 0.5,
        `expected fixed-alpha lerp to diverge across step counts, got ${resultN.x.toFixed(4)} vs ${result2N.x.toFixed(4)}`,
    );
});

test("dampVector3 clamps large deltas so a multi-second stall does not snap instantly", () => {
    const current = new THREE.Vector3(0, 0, 0);
    const target = new THREE.Vector3(10, 0, 0);
    dampVector3(current, target, 8, 5);
    const expectedX = 10 * (1 - Math.exp(-8 * 0.1));
    assert.ok(Math.abs(current.x - expectedX) < 1e-9, `x=${current.x}, expected ${expectedX}`);
});

test("dampAngle wraps across the +-PI boundary the short way", () => {
    const result = dampAngle(Math.PI - 0.1, -Math.PI + 0.1, 8, 1);
    const rewrapped = Math.atan2(Math.sin(result), Math.cos(result));
    assert.ok(
        result > Math.PI - 0.15 || result < -Math.PI + 0.15,
        `expected the short way around the wrap, got ${result} (rewrapped ${rewrapped})`,
    );
});
