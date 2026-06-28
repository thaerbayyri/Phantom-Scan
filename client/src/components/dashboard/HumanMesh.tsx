import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget, PoseFrame } from "@shared/schema";

// ═══════════════════════════════════════════════════════════════════
//  HumanMesh — DensePose-inspired wireframe figure
//  Supports dual-mode rendering: 
//  1. Real-time AI reconstructed skeleton when poseFrame is present
//  2. Procedural animation driven by speed/breathing otherwise
// ═══════════════════════════════════════════════════════════════════

interface HumanMeshProps {
    target: RadialTarget;
    poseFrame?: PoseFrame | null;
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

export function HumanMesh({ target, poseFrame }: HumanMeshProps) {
    const groupRef = useRef<THREE.Group>(null);
    const bodyRef = useRef<THREE.Group>(null);
    const leftLegRef = useRef<THREE.Group>(null);
    const rightLegRef = useRef<THREE.Group>(null);
    const leftArmRef = useRef<THREE.Group>(null);
    const rightArmRef = useRef<THREE.Group>(null);
    const headGlowRef = useRef<THREE.Mesh>(null);

    const targetPos = useRef(new THREE.Vector3(target.x, 0, target.z));
    const currentAngle = useRef(target.angle);

    useFrame((state) => {
        // Skip procedural updates if we are in AI Pose mode
        if (poseFrame && poseFrame.keypoints && poseFrame.keypoints.length > 0) return;
        
        if (!groupRef.current) return;
        const t = state.clock.elapsedTime;

        // Smooth position
        targetPos.current.set(target.x, 0, target.z);
        groupRef.current.position.lerp(targetPos.current, 0.12);

        // Smooth heading
        const angleDiff = target.angle - currentAngle.current;
        const wrapped = Math.atan2(Math.sin(angleDiff), Math.cos(angleDiff));
        currentAngle.current += wrapped * 0.12;
        if (bodyRef.current) {
            bodyRef.current.rotation.y = -currentAngle.current + Math.PI / 2;
        }

        if (target.isMoving && target.speed > 0.02) {
            // Walking animation — swing legs and arms
            const walkSpeed = Math.min(8, target.speed * 6);
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

    // Map predicted skeleton points to Three.js coordinates
    const jointsMap = useMemo(() => {
        if (!hasAIPose || !poseFrame) return new Map<string, THREE.Vector3>();
        const map = new Map<string, THREE.Vector3>();
        for (const kp of poseFrame.keypoints) {
            // Apply scale offsets relative to target center coordinate (target.x, target.z)
            // Model outputs x and z offsets (typically around -1.0 to 1.0).
            const x = target.x + kp.x * 1.5;
            const y = kp.y; // height coordinate computed in scripts/ai_inference.py
            const z = target.z + kp.z * 1.5;
            map.set(kp.name, new THREE.Vector3(x, y, z));
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
                <pointLight color={color} intensity={target.confidence * 1.5} distance={4} decay={2} position={[0, 1.2, 0]} />
            </group>

            {/* Ground shadow */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
                <circleGeometry args={[0.3, 32]} />
                <meshBasicMaterial color="#004d40" transparent opacity={0.25} />
            </mesh>
        </group>
    );
}
