import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Billboard } from "@react-three/drei";
import * as THREE from "three";
import type { RadialTarget, PointCloudPoint, PoseFrame } from "@shared/schema";
import { DirectionalNode } from "./DirectionalNode";
import { HumanMesh } from "./HumanMesh";
import { MachineStatic } from "./MachineStatic";

// ═══════════════════════════════════════════════════════════════════
//  Polar Grid — concentric rings + radial spokes
// ═══════════════════════════════════════════════════════════════════

function PolarGrid() {
    const ringCount = 8;
    const spokeCount = 12;
    const maxRadius = 6;

    return (
        <group rotation={[-Math.PI / 2, 0, 0]}>
            {Array.from({ length: ringCount }, (_, i) => {
                const r = ((i + 1) / ringCount) * maxRadius;
                const opacity = 0.15 + (i / ringCount) * 0.1;
                return (
                    <mesh key={`ring-${i}`}>
                        <ringGeometry args={[r - 0.01, r + 0.01, 64]} />
                        <meshBasicMaterial color="#00ffff" transparent opacity={opacity} side={THREE.DoubleSide} />
                    </mesh>
                );
            })}

            {Array.from({ length: spokeCount }, (_, i) => {
                const angle = (i / spokeCount) * Math.PI * 2;
                const points = [
                    new THREE.Vector3(0, 0, 0),
                    new THREE.Vector3(Math.cos(angle) * maxRadius, Math.sin(angle) * maxRadius, 0),
                ];
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                return (
                    <lineSegments key={`spoke-${i}`} geometry={geometry}>
                        <lineBasicMaterial color="#00ffff" transparent opacity={0.08} />
                    </lineSegments>
                );
            })}

            {Array.from({ length: 6 }, (_, i) => {
                const r = i + 1;
                return (
                    <mesh key={`label-ring-${i}`}>
                        <ringGeometry args={[r - 0.02, r + 0.02, 64]} />
                        <meshBasicMaterial color="#00cccc" transparent opacity={0.25} side={THREE.DoubleSide} />
                    </mesh>
                );
            })}

            {/* Cardinal Markers (Labels on floor grid) */}
            <Billboard position={[0, 6.5, 0.15]} follow={true}>
                <Text fontSize={0.7} color="#00ffff" font="monospace" anchorX="center" anchorY="middle">N</Text>
            </Billboard>
            <Billboard position={[0, -6.5, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" font="monospace" anchorX="center" anchorY="middle">S</Text>
            </Billboard>
            <Billboard position={[6.5, 0, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" font="monospace" anchorX="center" anchorY="middle">E</Text>
            </Billboard>
            <Billboard position={[-6.5, 0, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" font="monospace" anchorX="center" anchorY="middle">W</Text>
            </Billboard>
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
        }
    });

    return (
        <group position={[0, 0.15, 0]}>
            <mesh>
                <sphereGeometry args={[0.12, 32, 32]} />
                <meshStandardMaterial color="#00ffcc" emissive="#00ffcc" emissiveIntensity={2} roughness={0.1} metalness={0.8} />
            </mesh>
            <mesh>
                <sphereGeometry args={[0.2, 32, 32]} />
                <meshBasicMaterial color="#00ffcc" transparent opacity={0.15} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.15, 0]}>
                <ringGeometry args={[0.15, 0.25, 32]} />
                <meshBasicMaterial color="#00ffcc" transparent opacity={0.4} side={THREE.DoubleSide} />
            </mesh>
            <SignalRipple />
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
        [ring1Ref, ring2Ref, ring3Ref].forEach((ref, i) => {
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
            <mesh ref={ring1Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color="#00ffcc" transparent opacity={0.3} side={THREE.DoubleSide} /></mesh>
            <mesh ref={ring2Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color="#00ffcc" transparent opacity={0.2} side={THREE.DoubleSide} /></mesh>
            <mesh ref={ring3Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color="#00ffcc" transparent opacity={0.1} side={THREE.DoubleSide} /></mesh>
        </group>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  Wall Plane — static reflection boundary
// ═══════════════════════════════════════════════════════════════════

function WallPlane({ distance }: { distance: number }) {
    return (
        <group position={[distance, 1.5, 0]}>
            <mesh>
                <planeGeometry args={[0.05, 3]} />
                <meshStandardMaterial
                    color="#334155"
                    emissive="#1e293b"
                    emissiveIntensity={0.5}
                    transparent
                    opacity={0.6}
                    side={THREE.DoubleSide}
                />
            </mesh>
            {/* Wall indicator strips */}
            {Array.from({ length: 5 }, (_, i) => (
                <mesh key={i} position={[0, -1.2 + i * 0.6, 0]}>
                    <planeGeometry args={[0.08, 0.02]} />
                    <meshBasicMaterial color="#64748b" transparent opacity={0.5} side={THREE.DoubleSide} />
                </mesh>
            ))}
        </group>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  Floor Plane — ground reference
// ═══════════════════════════════════════════════════════════════════

function FloorPlane() {
    return (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
            <planeGeometry args={[14, 14]} />
            <meshStandardMaterial
                color="#0a1628"
                transparent
                opacity={0.4}
                roughness={0.9}
                metalness={0.1}
            />
        </mesh>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  Ambient points
// ═══════════════════════════════════════════════════════════════════

function AmbientPoints({ points }: { points: PointCloudPoint[] }) {
    const { positions, colors } = useMemo(() => {
        const pos = new Float32Array(points.length * 3);
        const col = new Float32Array(points.length * 3);
        const colorObj = new THREE.Color();

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            pos[i * 3] = p.x;
            pos[i * 3 + 1] = p.z;
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
                <bufferAttribute attach="attributes-position" args={[positions, 3]} count={positions.length / 3} array={positions} itemSize={3} />
                <bufferAttribute attach="attributes-color" args={[colors, 3]} count={colors.length / 3} array={colors} itemSize={3} />
            </bufferGeometry>
            <pointsMaterial vertexColors size={0.03} sizeAttenuation transparent opacity={0.4} />
        </points>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  RadialScene — Main scene with conditional entity rendering
// ═══════════════════════════════════════════════════════════════════

interface RadialSceneProps {
    radialTarget: RadialTarget | null;
    points: PointCloudPoint[];
    poseFrame: PoseFrame | null;
}

export function RadialScene({ radialTarget, points, poseFrame }: RadialSceneProps) {
    const label = radialTarget?.label ?? "unknown";
    const wallDistance = radialTarget?.wallDistance ?? 5.0;

    return (
        <>
            <ambientLight intensity={0.3} />
            <directionalLight position={[5, 10, 5]} intensity={0.6} />
            <fog attach="fog" args={["#000810", 8, 18]} />

            <PolarGrid />
            <ESPBeacon />
            <FloorPlane />
            <AmbientPoints points={points} />

            {/* Wall plane at detected reflection distance */}
            <WallPlane distance={wallDistance} />

            {/* Conditional entity based on classification */}
            {radialTarget && (
                label === "human" ? (
                    <HumanMesh target={radialTarget} poseFrame={poseFrame} />
                ) : label === "mechanical" ? (
                    <MachineStatic target={radialTarget} />
                ) : (
                    <DirectionalNode target={radialTarget} />
                )
            )}
        </>
    );
}
