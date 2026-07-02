import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Billboard } from "@react-three/drei";
import * as THREE from "three";
import type { RadialTarget, PointCloudPoint, PoseFrame, TargetState, SensorNode } from "@shared/schema";
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
                <Text fontSize={0.7} color="#00ffff" anchorX="center" anchorY="middle">N</Text>
            </Billboard>
            <Billboard position={[0, -6.5, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" anchorX="center" anchorY="middle">S</Text>
            </Billboard>
            <Billboard position={[6.5, 0, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" anchorX="center" anchorY="middle">E</Text>
            </Billboard>
            <Billboard position={[-6.5, 0, 0.15]} follow={true}>
                <Text fontSize={0.6} color="#00cccc" anchorX="center" anchorY="middle">W</Text>
            </Billboard>
        </group>
    );
}

// ═══════════════════════════════════════════════════════════════════
//  ESP32 Beacon — glowing node at origin
// ═══════════════════════════════════════════════════════════════════

// Distinct colors per node so N1/N2 are visually separable.
const NODE_COLORS: Record<number, string> = { 1: "#00ffcc", 2: "#ff7ac6" };

const TREND_STYLE: Record<string, { glyph: string; color: string }> = {
    approaching: { glyph: "▼", color: "#4ade80" }, // green: target closing in
    receding: { glyph: "▲", color: "#fbbf24" },    // amber: target moving away
    stable: { glyph: "•", color: "#64748b" },      // dim: idle / below deadband
};

function ESPBeacon({
    position = [0, 0.15, 0],
    color = "#00ffcc",
    motion = 0,
    label,
    distanceM,
    trend = "stable",
}: {
    position?: [number, number, number];
    color?: string;
    motion?: number;
    label?: string;
    distanceM?: number;
    trend?: "approaching" | "receding" | "stable";
}) {
    const coreRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (coreRef.current) {
            const t = state.clock.elapsedTime;
            // Pulse harder as the node sees more motion (activity glow).
            const pulse = 1 + Math.sin(t * 2) * (0.15 + motion * 0.4);
            coreRef.current.scale.setScalar(pulse);
        }
    });

    return (
        <group position={position}>
            <mesh ref={coreRef}>
                <sphereGeometry args={[0.12, 32, 32]} />
                <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.5 + motion * 2.5} roughness={0.1} metalness={0.8} />
            </mesh>
            <mesh>
                <sphereGeometry args={[0.2, 32, 32]} />
                <meshBasicMaterial color={color} transparent opacity={0.15} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.15, 0]}>
                <ringGeometry args={[0.15, 0.25, 32]} />
                <meshBasicMaterial color={color} transparent opacity={0.4} side={THREE.DoubleSide} />
            </mesh>
            <SignalRipple color={color} />
            <pointLight color={color} intensity={1.5 + motion * 2} distance={8} decay={2} />
            {label && (
                <Billboard position={[0, 0.62, 0]} follow={true}>
                    <Text fontSize={0.32} color={color} anchorX="center" anchorY="middle">
                        {distanceM !== undefined ? `${label} · ${distanceM.toFixed(1)} m` : label}
                    </Text>
                    {distanceM !== undefined && (
                        <Text
                            position={[0, -0.34, 0]}
                            fontSize={0.22}
                            color={TREND_STYLE[trend].color}
                            anchorX="center"
                            anchorY="middle"
                        >
                            {`${TREND_STYLE[trend].glyph} ${trend}`}
                        </Text>
                    )}
                </Billboard>
            )}
        </group>
    );
}

function SignalRipple({ color = "#00ffcc" }: { color?: string }) {
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
            <mesh ref={ring1Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color={color} transparent opacity={0.3} side={THREE.DoubleSide} /></mesh>
            <mesh ref={ring2Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color={color} transparent opacity={0.2} side={THREE.DoubleSide} /></mesh>
            <mesh ref={ring3Ref}><ringGeometry args={[0.9, 1.0, 64]} /><meshBasicMaterial color={color} transparent opacity={0.1} side={THREE.DoubleSide} /></mesh>
        </group>
    );
}

// Faint connector lines from the target to each node so the two per-node
// distances are visually legible as segments.
function TargetLinks({ target, nodes }: { target: RadialTarget; nodes: SensorNode[] }) {
    const geometries = useMemo(
        () =>
            nodes.map((n) =>
                new THREE.BufferGeometry().setFromPoints([
                    new THREE.Vector3(target.x, 0.25, target.z),
                    new THREE.Vector3(n.x, 0.15, n.z),
                ]),
            ),
        [target.x, target.z, nodes],
    );
    return (
        <>
            {geometries.map((g, i) => (
                <lineSegments key={nodes[i].node_id} geometry={g}>
                    <lineBasicMaterial
                        color={NODE_COLORS[nodes[i].node_id] ?? "#00ffcc"}
                        transparent
                        opacity={0.25}
                    />
                </lineSegments>
            ))}
        </>
    );
}

// Faint line between the two node anchors — the axis the target slides along.
function NodeAxis({ a, b }: { a: SensorNode; b: SensorNode }) {
    const geometry = useMemo(
        () =>
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(a.x, 0.02, a.z),
                new THREE.Vector3(b.x, 0.02, b.z),
            ]),
        [a.x, a.z, b.x, b.z],
    );
    return (
        <lineSegments geometry={geometry}>
            <lineBasicMaterial color="#00ffaa" transparent opacity={0.35} />
        </lineSegments>
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
    targetState: TargetState | null;
    nodes?: SensorNode[];
}

export function RadialScene({ radialTarget, points, poseFrame, targetState, nodes = [] }: RadialSceneProps) {
    const label = radialTarget?.label ?? "unknown";
    const wallDistance = radialTarget?.wallDistance ?? 5.0;
    const canRenderTarget = Boolean(
        radialTarget &&
        targetState?.target_visible &&
        !targetState.stale &&
        targetState.state !== "none" &&
        targetState.state !== "stale"
    );
    const canRenderConfidentHuman = Boolean(canRenderTarget && targetState?.position_confident);

    // Fused mode: point the travel arrow along the axis toward the node the
    // target is approaching (per-node trend), instead of the single-node angle.
    const approachedNode =
        radialTarget?.balance !== undefined
            ? nodes.find((n) => n.trend === "approaching")
            : undefined;
    const fusedArrowTarget =
        radialTarget && approachedNode
            ? { ...radialTarget, angle: approachedNode.x >= radialTarget.x ? 0 : Math.PI }
            : null;

    return (
        <>
            <ambientLight intensity={0.3} />
            <directionalLight position={[5, 10, 5]} intensity={0.6} />
            <fog attach="fog" args={["#000810", 8, 18]} />

            <PolarGrid />
            {/* Node beacons: one per ESP32-S3 anchor (fallback to single origin
                beacon when no node data has arrived yet). */}
            {nodes.length > 0 ? (
                <>
                    {nodes.map((n) => (
                        <ESPBeacon
                            key={n.node_id}
                            position={[n.x, 0.15, n.z]}
                            color={NODE_COLORS[n.node_id] ?? "#00ffcc"}
                            motion={n.active ? n.motion : 0}
                            label={`N${n.node_id}`}
                            distanceM={canRenderTarget ? n.distanceM : undefined}
                            trend={n.trend}
                        />
                    ))}
                    {nodes.length >= 2 && <NodeAxis a={nodes[0]} b={nodes[1]} />}
                    {canRenderTarget && radialTarget && (
                        <TargetLinks target={radialTarget} nodes={nodes} />
                    )}
                </>
            ) : (
                <ESPBeacon />
            )}
            <FloorPlane />
            <AmbientPoints points={points} />

            {/* Wall plane at detected reflection distance */}
            <WallPlane distance={wallDistance} />

            {/* Render only state-authorized target objects. Unknown targets stay abstract. */}
            {canRenderTarget && radialTarget && (
                label === "mechanical" ? (
                    <MachineStatic target={radialTarget} />
                ) : label === "human" && canRenderConfidentHuman ? (
                    <HumanMesh target={radialTarget} poseFrame={poseFrame} />
                ) : (
                    <DirectionalNode target={fusedArrowTarget ?? radialTarget} />
                )
            )}
        </>
    );
}

