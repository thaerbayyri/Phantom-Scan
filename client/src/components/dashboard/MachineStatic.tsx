import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget } from "@shared/schema";

// ═══════════════════════════════════════════════════════════════════
//  MachineStatic — Rotating gear/cog mesh for mechanical targets
//  Amber/orange industrial palette, gentle rotation animation
// ═══════════════════════════════════════════════════════════════════

interface MachineStaticProps {
    target: RadialTarget;
}

export function MachineStatic({ target }: MachineStaticProps) {
    const groupRef = useRef<THREE.Group>(null);
    const gearRef = useRef<THREE.Group>(null);
    const glowRef = useRef<THREE.Mesh>(null);

    const targetPos = useRef(new THREE.Vector3(target.x, 0.4, target.z));

    useFrame((state) => {
        if (!groupRef.current) return;
        const t = state.clock.elapsedTime;

        // Smooth position
        targetPos.current.set(target.x, 0.4, target.z);
        groupRef.current.position.lerp(targetPos.current, 0.1);

        // Rotate gear
        if (gearRef.current) {
            gearRef.current.rotation.y = t * 0.8;
            gearRef.current.rotation.z = Math.sin(t * 0.5) * 0.1;
        }

        // Pulsing glow
        if (glowRef.current) {
            const pulse = 1.0 + Math.sin(t * 3) * 0.15;
            glowRef.current.scale.setScalar(pulse);
        }
    });

    const color = "#ff8f00";
    const emissive = "#e65100";

    return (
        <group ref={groupRef}>
            <group ref={gearRef}>
                {/* Main gear body (octagonal) */}
                <mesh>
                    <cylinderGeometry args={[0.25, 0.25, 0.08, 8]} />
                    <meshStandardMaterial
                        color={color}
                        emissive={emissive}
                        emissiveIntensity={1.5}
                        roughness={0.3}
                        metalness={0.9}
                    />
                </mesh>

                {/* Gear teeth (8 teeth around the cylinder) */}
                {Array.from({ length: 8 }, (_, i) => {
                    const angle = (i / 8) * Math.PI * 2;
                    return (
                        <mesh
                            key={`tooth-${i}`}
                            position={[
                                Math.cos(angle) * 0.3,
                                0,
                                Math.sin(angle) * 0.3,
                            ]}
                            rotation={[0, angle, 0]}
                        >
                            <boxGeometry args={[0.08, 0.06, 0.1]} />
                            <meshStandardMaterial
                                color={color}
                                emissive={emissive}
                                emissiveIntensity={1.2}
                                roughness={0.4}
                                metalness={0.8}
                            />
                        </mesh>
                    );
                })}

                {/* Center hub */}
                <mesh>
                    <cylinderGeometry args={[0.06, 0.06, 0.12, 16]} />
                    <meshStandardMaterial
                        color="#ffcc80"
                        emissive={color}
                        emissiveIntensity={2}
                        roughness={0.1}
                        metalness={1.0}
                    />
                </mesh>

                {/* Inner ring */}
                <mesh>
                    <torusGeometry args={[0.14, 0.015, 8, 16]} />
                    <meshStandardMaterial
                        color={color}
                        emissive={emissive}
                        emissiveIntensity={0.8}
                        wireframe
                    />
                </mesh>
            </group>

            {/* Outer glow */}
            <mesh ref={glowRef}>
                <sphereGeometry args={[0.35, 16, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.08} />
            </mesh>

            {/* Warning indicator ring */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.38, 0]}>
                <ringGeometry args={[0.3, 0.4, 8]} />
                <meshBasicMaterial
                    color={color}
                    transparent
                    opacity={0.35}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Point light — amber */}
            <pointLight color={color} intensity={target.confidence * 2} distance={5} decay={2} />

            {/* Ground shadow */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.38, 0]}>
                <circleGeometry args={[0.35, 32]} />
                <meshBasicMaterial color="#4e2c00" transparent opacity={0.2} />
            </mesh>
        </group>
    );
}
