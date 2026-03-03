import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget } from "@shared/schema";

// ═══════════════════════════════════════════════════════════════════
//  HumanMesh — DensePose-inspired wireframe figure
//  Walking animation driven by speed, idle breathing when stationary
// ═══════════════════════════════════════════════════════════════════

interface HumanMeshProps {
    target: RadialTarget;
}

export function HumanMesh({ target }: HumanMeshProps) {
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

    const color = "#00e5ff";
    const emissive = "#006064";

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
