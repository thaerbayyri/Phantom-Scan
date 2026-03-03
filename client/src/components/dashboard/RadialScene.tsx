import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget, PointCloudPoint } from "@shared/schema";
import { DirectionalNode } from "./DirectionalNode";

// ═══════════════════════════════════════════════════════════════════
//  Polar Grid — concentric rings + radial spokes
// ═══════════════════════════════════════════════════════════════════

function PolarGrid() {
    const ringCount = 8;
    const spokeCount = 12;
    const maxRadius = 6;

    return (
        <group rotation={[-Math.PI / 2, 0, 0]}>
            {/* Concentric rings */}
            {Array.from({ length: ringCount }, (_, i) => {
                const r = ((i + 1) / ringCount) * maxRadius;
                const opacity = 0.15 + (i / ringCount) * 0.1;
                return (
                    <mesh key={`ring-${i}`}>
                        <ringGeometry args={[r - 0.01, r + 0.01, 64]} />
                        <meshBasicMaterial
                            color="#00ffff"
                            transparent
                            opacity={opacity}
                            side={THREE.DoubleSide}
                        />
                    </mesh>
                );
            })}

            {/* Radial spokes */}
            {Array.from({ length: spokeCount }, (_, i) => {
                const angle = (i / spokeCount) * Math.PI * 2;
                const points = [
                    new THREE.Vector3(0, 0, 0),
                    new THREE.Vector3(
                        Math.cos(angle) * maxRadius,
                        Math.sin(angle) * maxRadius,
                        0
                    ),
                ];
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                return (
                    <lineSegments key={`spoke-${i}`} geometry={geometry}>
                        <lineBasicMaterial color="#00ffff" transparent opacity={0.08} />
                    </lineSegments>
                );
            })}

            {/* Distance labels as small rings at 1m intervals */}
            {Array.from({ length: 6 }, (_, i) => {
                const r = i + 1;
                return (
                    <mesh key={`label-ring-${i}`}>
                        <ringGeometry args={[r - 0.02, r + 0.02, 64]} />
                        <meshBasicMaterial
                            color="#00cccc"
                            transparent
                            opacity={0.25}
                            side={THREE.DoubleSide}
                        />
                    </mesh>
                );
            })}
        </group>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  ESP32 Beacon — glowing node at origin
// ═══════════════════════════════════════════════════════════════════

function ESPBeacon() {
    const pulseRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (pulseRef.current) {
            const t = state.clock.elapsedTime;
            const pulse = 1 + Math.sin(t * 2) * 0.15;
            pulseRef.current.scale.setScalar(pulse);
            pulseRef.current.rotation.z = t * 0.5;
        }
    });

    return (
        <group position={[0, 0.15, 0]}>
            {/* Core sphere */}
            <mesh>
                <sphereGeometry args={[0.12, 32, 32]} />
                <meshStandardMaterial
                    color="#00ffcc"
                    emissive="#00ffcc"
                    emissiveIntensity={2}
                    roughness={0.1}
                    metalness={0.8}
                />
            </mesh>

            {/* Outer glow sphere */}
            <mesh>
                <sphereGeometry args={[0.2, 32, 32]} />
                <meshBasicMaterial
                    color="#00ffcc"
                    transparent
                    opacity={0.15}
                />
            </mesh>

            {/* Base ring */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.15, 0]}>
                <ringGeometry args={[0.15, 0.25, 32]} />
                <meshBasicMaterial
                    color="#00ffcc"
                    transparent
                    opacity={0.4}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Animated signal ripple */}
            <SignalRipple />

            {/* Point light */}
            <pointLight color="#00ffcc" intensity={1.5} distance={8} decay={2} />
        </group>
    );
}

function SignalRipple() {
    const ring1Ref = useRef<THREE.Mesh>(null);
    const ring2Ref = useRef<THREE.Mesh>(null);
    const ring3Ref = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        const t = state.clock.elapsedTime;
        const rings = [ring1Ref, ring2Ref, ring3Ref];
        rings.forEach((ref, i) => {
            if (ref.current) {
                const phase = (t * 0.8 + i * 1.2) % 3.6;
                const scale = 0.3 + phase * 1.2;
                const opacity = Math.max(0, 0.3 - phase * 0.083);
                ref.current.scale.set(scale, scale, 1);
                (ref.current.material as THREE.MeshBasicMaterial).opacity = opacity;
            }
        });
    });

    return (
        <group rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.14, 0]}>
            <mesh ref={ring1Ref}>
                <ringGeometry args={[0.9, 1.0, 64]} />
                <meshBasicMaterial color="#00ffcc" transparent opacity={0.3} side={THREE.DoubleSide} />
            </mesh>
            <mesh ref={ring2Ref}>
                <ringGeometry args={[0.9, 1.0, 64]} />
                <meshBasicMaterial color="#00ffcc" transparent opacity={0.2} side={THREE.DoubleSide} />
            </mesh>
            <mesh ref={ring3Ref}>
                <ringGeometry args={[0.9, 1.0, 64]} />
                <meshBasicMaterial color="#00ffcc" transparent opacity={0.1} side={THREE.DoubleSide} />
            </mesh>
        </group>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  Ambient Point Cloud particles (faint background context)
// ═══════════════════════════════════════════════════════════════════

function AmbientPoints({ points }: { points: PointCloudPoint[] }) {
    const { positions, colors } = useMemo(() => {
        const pos = new Float32Array(points.length * 3);
        const col = new Float32Array(points.length * 3);
        const colorObj = new THREE.Color();

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            pos[i * 3] = p.x;
            pos[i * 3 + 1] = p.z; // Y-up
            pos[i * 3 + 2] = p.y;

            const normalized = Math.min(1, Math.max(0, p.amplitude / 50));
            colorObj.setHSL(0.55 + normalized * 0.1, 0.8, 0.4 + normalized * 0.3);

            col[i * 3] = colorObj.r;
            col[i * 3 + 1] = colorObj.g;
            col[i * 3 + 2] = colorObj.b;
        }
        return { positions: pos, colors: col };
    }, [points]);

    if (points.length === 0) return null;

    return (
        <points>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[positions, 3]}
                    count={positions.length / 3}
                    array={positions}
                    itemSize={3}
                />
                <bufferAttribute
                    attach="attributes-color"
                    args={[colors, 3]}
                    count={colors.length / 3}
                    array={colors}
                    itemSize={3}
                />
            </bufferGeometry>
            <pointsMaterial
                vertexColors
                size={0.03}
                sizeAttenuation
                transparent
                opacity={0.4}
            />
        </points>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  RadialScene — Exported main scene
// ═══════════════════════════════════════════════════════════════════

interface RadialSceneProps {
    radialTarget: RadialTarget | null;
    points: PointCloudPoint[];
}

export function RadialScene({ radialTarget, points }: RadialSceneProps) {
    return (
        <>
            {/* Environment */}
            <ambientLight intensity={0.3} />
            <directionalLight position={[5, 10, 5]} intensity={0.6} />
            <fog attach="fog" args={["#000810", 8, 18]} />

            {/* Polar Grid */}
            <PolarGrid />

            {/* ESP32 Center Beacon */}
            <ESPBeacon />

            {/* Ambient Point Cloud */}
            <AmbientPoints points={points} />

            {/* Directional Target Node */}
            {radialTarget && <DirectionalNode target={radialTarget} />}
        </>
    );
}
