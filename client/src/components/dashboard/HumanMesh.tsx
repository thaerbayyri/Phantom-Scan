import { useRef, useMemo, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget, PoseFrame } from "@shared/schema";
import { dampAngle, DECAY_RATES } from "@/lib/smooth-follow";

// ═══════════════════════════════════════════════════════════════════
//  HumanMesh — DensePose-inspired wireframe figure
//  Supports dual-mode rendering:
//  1. Real-time AI reconstructed skeleton when poseFrame is present
//  2. Procedural animation driven by speed/breathing otherwise
// ═══════════════════════════════════════════════════════════════════

interface HumanMeshProps {
    target: RadialTarget;
    poseFrame?: PoseFrame | null;
    /** Shared, already-damped position (RadialScene owns the damping/snap decision). */
    positionRef: MutableRefObject<THREE.Vector3>;
    /** Shared, already-damped speed, used in place of raw target.speed for the walk cycle. */
    speedRef: MutableRefObject<number>;
}

function getNearNodeStrength(balance?: number): number {
    if (balance === undefined) return 0;
    return Math.min(1, Math.abs(balance - 0.5) * 2);
}

// ── Pose-anchor constants ───────────────────────────────────────────
// Maximum distance a single keypoint can appear from the body root on
// the x/z plane.  Prevents noisy or outlier joints from flying off
// into the scene far away from the detected target position.
const POSE_CLAMP_M = 0.8;

// Return the x/z anatomical root of a keypoint set so that local
// offsets are computed relative to the body, not the scene origin.
// Priority: hip midpoint → shoulder midpoint → mean of all joints.
function getAnatomicalRoot(keypoints: { name: string; x: number; z: number }[]): {
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

    // Final fallback: mean of all available joints (x/z only).
    const n = keypoints.length || 1;
    return {
        rootX: keypoints.reduce((s, k) => s + k.x, 0) / n,
        rootZ: keypoints.reduce((s, k) => s + k.z, 0) / n,
    };
}

const BONE_CONNECTIONS = [
    ["nose", "left_eye"], ["nose", "right_eye"],
    ["left_eye", "left_ear"], ["right_eye", "right_ear"],
    ["left_shoulder", "right_shoulder"],
    ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
    ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"],
    ["left_shoulder", "left_hip"], ["right_shoulder", "right_hip"],
    ["left_hip", "right_hip"],
    ["left_hip", "left_knee"], ["left_knee", "left_ankle"],
    ["right_hip", "right_knee"], ["right_knee", "right_ankle"]
];

export function HumanMesh({ target, poseFrame, positionRef, speedRef }: HumanMeshProps) {
    const groupRef = useRef<THREE.Group>(null);
    const bodyRef = useRef<THREE.Group>(null);
    const leftLegRef = useRef<THREE.Group>(null);
    const rightLegRef = useRef<THREE.Group>(null);
    const leftArmRef = useRef<THREE.Group>(null);
    const rightArmRef = useRef<THREE.Group>(null);
    const headGlowRef = useRef<THREE.Mesh>(null);

    const currentAngle = useRef(target.angle);
    const nearNodeStrength = getNearNodeStrength(target.balance);
    const isFusedTarget = target.balance !== undefined;

    useFrame((state, delta) => {
        // Skip procedural updates if we are in AI Pose mode
        if (poseFrame && poseFrame.keypoints && poseFrame.keypoints.length > 0) return;

        if (!groupRef.current) return;
        const t = state.clock.elapsedTime;

        // Position comes directly from the shared, already-damped/snapped
        // value RadialScene computes once per frame (Area 2/NEW-3) — no
        // local lerp or snap check here.
        groupRef.current.position.copy(positionRef.current);

        // Smooth heading
        currentAngle.current = dampAngle(
            currentAngle.current,
            target.angle,
            isFusedTarget ? DECAY_RATES.headingBodyFused : DECAY_RATES.headingBodySingle,
            delta,
        );
        if (bodyRef.current) {
            bodyRef.current.rotation.y = -currentAngle.current + Math.PI / 2;
        }

        if (target.isMoving && target.speed > 0.02) {
            // Walking animation — swing legs and arms
            const walkSpeed = Math.min(8, speedRef.current * 6);
            const swing = Math.sin(t * walkSpeed) * 0.5;

            if (leftLegRef.current) leftLegRef.current.rotation.x = swing;
            if (rightLegRef.current) rightLegRef.current.rotation.x = -swing;
            if (leftArmRef.current) leftArmRef.current.rotation.x = -swing * 0.7;
            if (rightArmRef.current) rightArmRef.current.rotation.x = swing * 0.7;
        } else {
            // Idle breathing
            const breathe = Math.sin(t * 1.5) * 0.02;
            if (leftLegRef.current) leftLegRef.current.rotation.x *= 0.9;
            if (rightLegRef.current) rightLegRef.current.rotation.x *= 0.9;
            if (leftArmRef.current) leftArmRef.current.rotation.x *= 0.9;
            if (rightArmRef.current) rightArmRef.current.rotation.x *= 0.9;
            if (bodyRef.current) bodyRef.current.position.y = breathe;
        }

        // Head glow pulse
        if (headGlowRef.current) {
            const pulse = 1.0 + Math.sin(t * 2) * 0.1;
            headGlowRef.current.scale.setScalar(pulse);
        }
    });

    const hasAIPose = useMemo(() => {
        return !!(poseFrame && poseFrame.keypoints && poseFrame.keypoints.length > 0);
    }, [poseFrame]);

    // Map predicted skeleton points to Three.js world coordinates.
    //
    // Anchoring strategy:
    //   1. Extract the anatomical root (hip/shoulder midpoint) from the
    //      keypoints themselves — this is the body centre in the model's
    //      own coordinate frame.
    //   2. Subtract the root to get a true local-body offset per joint.
    //   3. Clamp each offset to POSE_CLAMP_M to prevent noisy joints from
    //      flying away from the body.
    //   4. Add the authoritative radialTarget.x/z to anchor the whole
    //      skeleton to the live detected position.
    //   5. y is kept absolute — scripts/ai_inference.py already outputs
    //      height in scene units (head ~1.65 m, feet ~0 m).
    const jointsMap = useMemo(() => {
        if (!hasAIPose || !poseFrame) return new Map<string, THREE.Vector3>();
        const { rootX, rootZ } = getAnatomicalRoot(poseFrame.keypoints);
        const map = new Map<string, THREE.Vector3>();
        for (const kp of poseFrame.keypoints) {
            // Local body offset, clamped to prevent drift from the target dot.
            const localX = Math.max(-POSE_CLAMP_M, Math.min(POSE_CLAMP_M, kp.x - rootX));
            const localZ = Math.max(-POSE_CLAMP_M, Math.min(POSE_CLAMP_M, kp.z - rootZ));
            // World position = authoritative target root + local body offset.
            map.set(kp.name, new THREE.Vector3(
                target.x + localX,
                kp.y,           // absolute height from inference script
                target.z + localZ,
            ));
        }
        return map;
    }, [poseFrame, target.x, target.z, hasAIPose]);

    const color = "#00e5ff";
    const emissive = "#006064";

    if (hasAIPose) {
        return (
            <group>
                {/* 1. Joint Spheres */}
                {Array.from(jointsMap.entries()).map(([name, pos]) => (
                    <mesh key={name} position={pos}>
                        <sphereGeometry args={[0.065, 16, 16]} />
                        <meshStandardMaterial 
                            color={color} 
                            emissive={color} 
                            emissiveIntensity={2.5} 
                            roughness={0.1} 
                            metalness={0.9} 
                        />
                    </mesh>
                ))}

                {/* 2. Bone Connector Cylinders */}
                {BONE_CONNECTIONS.map(([j1Name, j2Name], idx) => {
                    const p1 = jointsMap.get(j1Name);
                    const p2 = jointsMap.get(j2Name);
                    if (!p1 || !p2) return null;

                    const direction = new THREE.Vector3().subVectors(p2, p1);
                    const length = direction.length();
                    const midpoint = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);

                    const quaternion = new THREE.Quaternion();
                    const up = new THREE.Vector3(0, 1, 0);
                    direction.normalize();
                    quaternion.setFromUnitVectors(up, direction);

                    return (
                        <mesh key={idx} position={midpoint} quaternion={quaternion}>
                            <cylinderGeometry args={[0.018, 0.018, length, 8]} />
                            <meshStandardMaterial 
                                color={color} 
                                emissive={color} 
                                emissiveIntensity={0.6} 
                                roughness={0.3} 
                                metalness={0.7}
                            />
                        </mesh>
                    );
                })}

                {/* Chest Light Source */}
                {jointsMap.has("left_shoulder") && jointsMap.has("right_shoulder") && (
                    <pointLight
                        color={color}
                        intensity={1.8}
                        distance={4}
                        decay={2}
                        position={
                            new THREE.Vector3().addVectors(
                                jointsMap.get("left_shoulder")!,
                                jointsMap.get("right_shoulder")!
                            ).multiplyScalar(0.5)
                        }
                    />
                )}
            </group>
        );
    }

    return (
        <group ref={groupRef}>
            <group ref={bodyRef}>
                {/* Head */}
                <mesh position={[0, 1.65, 0]}>
                    <sphereGeometry args={[0.12, 16, 16]} />
                    <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={1.5} roughness={0.2} metalness={0.8} />
                </mesh>
                <mesh ref={headGlowRef} position={[0, 1.65, 0]}>
                    <sphereGeometry args={[0.16, 16, 16]} />
                    <meshBasicMaterial color={color} transparent opacity={0.1} />
                </mesh>

                {/* Torso (capsule-like) */}
                <mesh position={[0, 1.2, 0]}>
                    <capsuleGeometry args={[0.1, 0.45, 8, 16]} />
                    <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.8} wireframe roughness={0.3} metalness={0.7} />
                </mesh>

                {/* Pelvis */}
                <mesh position={[0, 0.85, 0]}>
                    <sphereGeometry args={[0.1, 8, 8]} />
                    <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.6} roughness={0.3} />
                </mesh>

                {/* Left Arm */}
                <group ref={leftArmRef} position={[0.2, 1.4, 0]}>
                    <mesh position={[0, -0.18, 0]}>
                        <capsuleGeometry args={[0.035, 0.3, 4, 8]} />
                        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.6} wireframe />
                    </mesh>
                </group>

                {/* Right Arm */}
                <group ref={rightArmRef} position={[-0.2, 1.4, 0]}>
                    <mesh position={[0, -0.18, 0]}>
                        <capsuleGeometry args={[0.035, 0.3, 4, 8]} />
                        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.6} wireframe />
                    </mesh>
                </group>

                {/* Left Leg */}
                <group ref={leftLegRef} position={[0.08, 0.8, 0]}>
                    <mesh position={[0, -0.25, 0]}>
                        <capsuleGeometry args={[0.04, 0.4, 4, 8]} />
                        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.5} wireframe />
                    </mesh>
                </group>

                {/* Right Leg */}
                <group ref={rightLegRef} position={[-0.08, 0.8, 0]}>
                    <mesh position={[0, -0.25, 0]}>
                        <capsuleGeometry args={[0.04, 0.4, 4, 8]} />
                        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.5} wireframe />
                    </mesh>
                </group>

                {/* Point light */}
                <pointLight color={color} intensity={target.confidence * 1.5 + nearNodeStrength} distance={4} decay={2} position={[0, 1.2, 0]} />
            </group>

            {/* Ground shadow */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
                <circleGeometry args={[0.3, 32]} />
                <meshBasicMaterial color="#004d40" transparent opacity={0.25} />
            </mesh>
        </group>
    );
}
