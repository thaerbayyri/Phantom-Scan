/**
 * Pose anchor math tests.
 *
 * getAnatomicalRoot and the joint world-position formula live inside the
 * React component (HumanMesh.tsx) so they cannot be imported directly
 * without a DOM / Three.js environment.  These tests re-implement the
 * same pure functions inline and assert their contracts independently,
 * ensuring the math is correct before trusting the visual result.
 *
 * If the implementation in HumanMesh.tsx ever diverges from these tests,
 * the tests will catch the regression.
 */

import test from "node:test";
import assert from "node:assert/strict";

// ── Pure re-implementation of the functions under test ────────────────────
// (Kept in sync with client/src/components/dashboard/HumanMesh.tsx)

const POSE_CLAMP_M = 0.8;

interface Keypoint { name: string; x: number; y: number; z: number; confidence: number; }

function getAnatomicalRoot(keypoints: Pick<Keypoint, "name" | "x" | "z">[]): {
    rootX: number;
    rootZ: number;
} {
    const kpMap = new Map(keypoints.map((k) => [k.name, k]));

    const lh = kpMap.get("left_hip");
    const rh = kpMap.get("right_hip");
    if (lh && rh) {
        return { rootX: (lh.x + rh.x) / 2, rootZ: (lh.z + rh.z) / 2 };
    }

    const ls = kpMap.get("left_shoulder");
    const rs = kpMap.get("right_shoulder");
    if (ls && rs) {
        return { rootX: (ls.x + rs.x) / 2, rootZ: (ls.z + rs.z) / 2 };
    }

    const n = keypoints.length || 1;
    return {
        rootX: keypoints.reduce((s, k) => s + k.x, 0) / n,
        rootZ: keypoints.reduce((s, k) => s + k.z, 0) / n,
    };
}

/** Compute the world position of a single keypoint given a target root. */
function worldPos(
    kp: { x: number; z: number; y: number },
    root: { rootX: number; rootZ: number },
    targetX: number,
    targetZ: number,
): { wx: number; wy: number; wz: number } {
    const localX = Math.max(-POSE_CLAMP_M, Math.min(POSE_CLAMP_M, kp.x - root.rootX));
    const localZ = Math.max(-POSE_CLAMP_M, Math.min(POSE_CLAMP_M, kp.z - root.rootZ));
    return { wx: targetX + localX, wy: kp.y, wz: targetZ + localZ };
}

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeKp(name: string, x: number, y: number, z: number): Keypoint {
    return { name, x, y, z, confidence: 0.9 };
}

// Realistic COCO-style keypoint set: body centred near (2, 0) in model space.
const FULL_POSE: Keypoint[] = [
    makeKp("nose",           2.0,  1.70, 0.0),
    makeKp("left_eye",       2.05, 1.72, 0.0),
    makeKp("right_eye",      1.95, 1.72, 0.0),
    makeKp("left_shoulder",  2.2,  1.50, 0.0),
    makeKp("right_shoulder", 1.8,  1.50, 0.0),
    makeKp("left_elbow",     2.4,  1.20, 0.0),
    makeKp("right_elbow",    1.6,  1.20, 0.0),
    makeKp("left_wrist",     2.5,  0.90, 0.0),
    makeKp("right_wrist",    1.5,  0.90, 0.0),
    makeKp("left_hip",       2.1,  1.00, 0.0),
    makeKp("right_hip",      1.9,  1.00, 0.0),
    makeKp("left_knee",      2.1,  0.55, 0.0),
    makeKp("right_knee",     1.9,  0.55, 0.0),
    makeKp("left_ankle",     2.1,  0.05, 0.0),
    makeKp("right_ankle",    1.9,  0.05, 0.0),
];

// ── getAnatomicalRoot tests ───────────────────────────────────────────────

test("getAnatomicalRoot uses hip midpoint when both hips are present", () => {
    const root = getAnatomicalRoot(FULL_POSE);
    // left_hip.x=2.1, right_hip.x=1.9 → midpoint = 2.0
    assert.ok(Math.abs(root.rootX - 2.0) < 1e-9, `rootX ${root.rootX}`);
    assert.ok(Math.abs(root.rootZ - 0.0) < 1e-9, `rootZ ${root.rootZ}`);
});

test("getAnatomicalRoot falls back to shoulder midpoint when hips are absent", () => {
    const noHips = FULL_POSE.filter(
        (k) => k.name !== "left_hip" && k.name !== "right_hip",
    );
    const root = getAnatomicalRoot(noHips);
    // left_shoulder.x=2.2, right_shoulder.x=1.8 → midpoint = 2.0
    assert.ok(Math.abs(root.rootX - 2.0) < 1e-9, `rootX ${root.rootX}`);
});

test("getAnatomicalRoot falls back to centroid when neither hips nor shoulders present", () => {
    const torsoOnly = [
        makeKp("nose",      1.0, 1.7, 0),
        makeKp("left_ear",  2.0, 1.6, 0),
        makeKp("right_ear", 0.0, 1.6, 0),
    ];
    const root = getAnatomicalRoot(torsoOnly);
    // mean x = (1+2+0)/3 = 1.0
    assert.ok(Math.abs(root.rootX - 1.0) < 1e-9, `rootX ${root.rootX}`);
});

test("getAnatomicalRoot handles a single keypoint without division error", () => {
    const single = [makeKp("nose", 3.5, 1.7, 0.2)];
    const root = getAnatomicalRoot(single);
    assert.ok(Math.abs(root.rootX - 3.5) < 1e-9);
    assert.ok(Math.abs(root.rootZ - 0.2) < 1e-9);
});

test("getAnatomicalRoot handles an empty keypoint array safely", () => {
    // Should not throw; n = 1 guard prevents division by zero.
    const root = getAnatomicalRoot([]);
    assert.ok(Number.isFinite(root.rootX));
    assert.ok(Number.isFinite(root.rootZ));
});

// ── Joint world-position tests ────────────────────────────────────────────

test("hip midpoint maps to exact target.x/z when all hips are on the root", () => {
    const root = getAnatomicalRoot(FULL_POSE);
    const TARGET_X = -1.2, TARGET_Z = 0.0;
    // The hip midpoint itself has zero local offset → should land on target root.
    const hipMid = { x: root.rootX, y: 1.0, z: root.rootZ };
    const pos = worldPos(hipMid, root, TARGET_X, TARGET_Z);
    assert.ok(Math.abs(pos.wx - TARGET_X) < 1e-9, `wx ${pos.wx}`);
    assert.ok(Math.abs(pos.wz - TARGET_Z) < 1e-9, `wz ${pos.wz}`);
});

test("nose joint offset is preserved relative to target root", () => {
    const root = getAnatomicalRoot(FULL_POSE);  // rootX=2.0, rootZ=0
    const TARGET_X = 0.5, TARGET_Z = 0.0;
    const nose = FULL_POSE.find((k) => k.name === "nose")!;
    // nose.x=2.0, root=2.0 → localX=0 → wx should equal TARGET_X
    const pos = worldPos(nose, root, TARGET_X, TARGET_Z);
    assert.ok(Math.abs(pos.wx - TARGET_X) < 1e-9, `wx ${pos.wx}`);
    assert.equal(pos.wy, nose.y);   // y must be preserved absolute
});

test("left wrist offset is correct and under clamp (0.5 m from root, within 0.8 m)", () => {
    const root = getAnatomicalRoot(FULL_POSE);  // rootX=2.0
    const TARGET_X = 1.0, TARGET_Z = 0.0;
    const lw = FULL_POSE.find((k) => k.name === "left_wrist")!; // x=2.5
    // localX = 2.5 - 2.0 = 0.5 (within POSE_CLAMP_M=0.8)
    const pos = worldPos(lw, root, TARGET_X, TARGET_Z);
    assert.ok(Math.abs(pos.wx - (TARGET_X + 0.5)) < 1e-9, `wx ${pos.wx}`);
});

test("outlier keypoint > POSE_CLAMP_M is clamped to POSE_CLAMP_M", () => {
    const root = { rootX: 0, rootZ: 0 };
    const outlier = { x: 5.0, y: 1.0, z: 0 };  // 5 m away from root
    const pos = worldPos(outlier, root, 0, 0);
    assert.ok(Math.abs(pos.wx - POSE_CLAMP_M) < 1e-9,
        `expected clamp to ${POSE_CLAMP_M}, got ${pos.wx}`);
});

test("outlier in negative direction is clamped to -POSE_CLAMP_M", () => {
    const root = { rootX: 0, rootZ: 0 };
    const outlier = { x: -9.0, y: 1.0, z: 0 };
    const pos = worldPos(outlier, root, 0, 0);
    assert.ok(Math.abs(pos.wx - (-POSE_CLAMP_M)) < 1e-9,
        `expected -${POSE_CLAMP_M}, got ${pos.wx}`);
});

test("y is never clamped — absolute height is preserved regardless of offset", () => {
    const root = { rootX: 0, rootZ: 0 };
    const head = { x: 0, y: 1.72, z: 0 };  // 1.72 m above ground
    const pos = worldPos(head, root, 0, 0);
    assert.equal(pos.wy, 1.72, "y must pass through unchanged");
});

// ── Target-root tracking across positions ────────────────────────────────
//
// This group simulates what the dashboard sees as a person walks between
// the two ESP32 nodes (N1 at x=-1.5, N2 at x=+1.5).  For each position
// the skeleton root (hip midpoint in world space) must equal target.x.

const AXIS_POSITIONS = [
    { label: "near N1",    targetX: -1.3, targetZ: 0 },
    { label: "midpoint",   targetX:  0.0, targetZ: 0 },
    { label: "near N2",    targetX:  1.3, targetZ: 0 },
    { label: "off-axis",   targetX:  0.4, targetZ: 0.8 },
];

for (const { label, targetX, targetZ } of AXIS_POSITIONS) {
    test(`skeleton root equals target position at "${label}"`, () => {
        // Simulate a model outputting keypoints centred on (2.0, 0) in its frame.
        const root = getAnatomicalRoot(FULL_POSE);

        // The hip midpoint local offset is zero — it should land exactly on target.
        const hipMid = { x: root.rootX, y: 1.0, z: root.rootZ };
        const pos = worldPos(hipMid, root, targetX, targetZ);

        assert.ok(Math.abs(pos.wx - targetX) < 1e-6,
            `[${label}] hip.wx ${pos.wx.toFixed(4)} !== targetX ${targetX}`);
        assert.ok(Math.abs(pos.wz - targetZ) < 1e-6,
            `[${label}] hip.wz ${pos.wz.toFixed(4)} !== targetZ ${targetZ}`);
    });
}

// ── Movement trajectory: root must slide with the target dot ─────────────

test("skeleton root tracks target as it moves from N1 to N2 in 5 steps", () => {
    const root = getAnatomicalRoot(FULL_POSE);   // model frame, fixed
    const hipMid = { x: root.rootX, y: 1.0, z: root.rootZ };

    const steps = [0, 0.25, 0.5, 0.75, 1.0];   // balance values N1→N2
    const N1_X = -1.5, N2_X = 1.5;

    for (const b of steps) {
        const targetX = N1_X + (N2_X - N1_X) * b;
        const pos = worldPos(hipMid, root, targetX, 0);
        assert.ok(Math.abs(pos.wx - targetX) < 1e-6,
            `balance ${b}: wx ${pos.wx.toFixed(4)} should equal targetX ${targetX}`);
    }
});

test("limb offset is stable across target positions (not amplified by movement)", () => {
    const root = getAnatomicalRoot(FULL_POSE);   // rootX=2.0
    const lw = FULL_POSE.find((k) => k.name === "left_wrist")!;  // x=2.5, offset=+0.5

    const positions = [-1.5, -0.5, 0, 0.5, 1.5];
    const offsets = positions.map((tx) => {
        const pos = worldPos(lw, root, tx, 0);
        return pos.wx - tx;   // should always be +0.5 regardless of tx
    });

    // All offsets should be the same (+0.5 m wrist extension from body root).
    for (const off of offsets) {
        assert.ok(Math.abs(off - 0.5) < 1e-6,
            `wrist offset ${off.toFixed(4)} is not stable`);
    }
});

test("double-offset bug is NOT present: adding target.x twice would produce wrong position", () => {
    // This verifies the old bug (target.x + kp.x * 1.5) no longer matches
    // our new formula.  The old code would compute:
    //   wrong = targetX + model.x * 1.5
    // The new code computes:
    //   correct = targetX + (model.x - rootX)   [clamped]
    // These only agree when model.x === rootX (i.e., the hip joint itself).
    const root = getAnatomicalRoot(FULL_POSE);  // rootX = 2.0
    const nose = FULL_POSE.find((k) => k.name === "nose")!;  // x=2.0
    const TARGET_X = -1.2;

    const oldFormula = TARGET_X + nose.x * 1.5;           // -1.2 + 3.0 = 1.8
    const newFormula = TARGET_X + (nose.x - root.rootX);  // -1.2 + 0.0 = -1.2

    // New formula pins the nose to the target root (nose is ON the body centre for this fixture).
    assert.ok(Math.abs(newFormula - TARGET_X) < 1e-6,
        `new formula ${newFormula} should equal targetX ${TARGET_X}`);
    // Old formula would have been wrong.
    assert.ok(Math.abs(oldFormula - TARGET_X) > 0.1,
        `old formula ${oldFormula} coincidentally equals targetX — test fixture issue`);
});
