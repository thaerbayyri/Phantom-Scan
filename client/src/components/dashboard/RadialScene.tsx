import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Billboard, Line } from "@react-three/drei";
import * as THREE from "three";
import type { RadialTarget, PointCloudPoint, PoseFrame, TargetState, SensorNode, SignalField } from "@shared/schema";
import { summarizeTargetSpatial } from "@shared/target-spatial";
import { canPresentAxisMotionVector } from "@shared/target-presentation";
import { headingVectorFromAngle } from "@shared/bearing";
import { dampVector3, dampScalar, DECAY_RATES } from "@/lib/smooth-follow";
import { DirectionalNode } from "./DirectionalNode";
import { HumanMesh } from "./HumanMesh";
import { MachineStatic } from "./MachineStatic";

/** 0 at the axis midpoint → 1 at a node; drives the position-decay-tier pick below. */
function getNearNodeStrength(balance?: number): number {
    if (balance === undefined) return 0;
    return Math.min(1, Math.abs(balance - 0.5) * 2);
}

/** Frame-rate-independent decay rate for the shared target position, per Area 1/2. */
function positionDecayRate(
    distanceToRaw: number,
    speed: number,
    isFusedTarget: boolean,
    nearNodeStrength: number,
): number {
    if (distanceToRaw > 0.25) return DECAY_RATES.positionFar;
    if (speed > 0.18) return DECAY_RATES.positionFast;
    if (isFusedTarget) {
        return DECAY_RATES.positionFusedBase + nearNodeStrength * DECAY_RATES.positionFusedNearScale;
    }
    if (distanceToRaw > 0.08) return DECAY_RATES.positionNear;
    return DECAY_RATES.positionSettle;
}

// ═══════════════════════════════════════════════════════════════════
//  Polar Grid — concentric rings + radial spokes
// ═══════════════════════════════════════════════════════════════════

/** Static radar backdrop: 8 concentric range rings, 12 spokes, meter rings and N/E/S/W compass labels. */
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

            {/* Cardinal Markers (Labels on floor grid). The group is rotated
                -π/2 about x, so local +y lands at world -z: north (+z world,
                schema convention) is the local -y slot. */}
            <Billboard position={[0, -6.5, 0.15]} follow={true}>
                <Text fontSize={0.7} color="#00ffff" anchorX="center" anchorY="middle">N</Text>
            </Billboard>
            <Billboard position={[0, 6.5, 0.15]} follow={true}>
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

// Distinct colors per node so all 4 anchors are visually separable.
const NODE_COLORS: Record<number, string> = {
    1: "#00ffcc",
    2: "#ff7ac6",
    3: "#ffd166",
    4: "#7dd3fc",
};

/**
 * One glowing sphere per ESP32 node anchor. Its pulse amplitude, emissive
 * intensity and point-light all scale with the node's live `motion` (0..1),
 * so an operator can see WHICH node currently senses the perturbation.
 */
function ESPBeacon({
    position = [0, 0.15, 0],
    color = "#00ffcc",
    motion = 0,
    label,
}: {
    position?: [number, number, number];
    color?: string;
    motion?: number;
    label?: string;
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
                        {label}
                    </Text>
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
/**
 * Translucent disc + ring of radius positionUncertaintyM around the smoothed
 * target marker. The fused_room position is a coarse perturbation centroid, so
 * the honest drawing is "somewhere inside this circle", not a precise dot.
 * The radius is a heuristic display size (see computePositionUncertaintyM), not
 * a measured error.
 */
function PositionUncertaintyRing({
    radiusM,
    positionRef,
}: {
    radiusM: number;
    positionRef: React.MutableRefObject<THREE.Vector3>;
}) {
    const group = useRef<THREE.Group>(null);
    useFrame(() => {
        if (group.current) group.current.position.set(positionRef.current.x, 0.03, positionRef.current.z);
    });
    const outer = Math.max(0.15, radiusM);
    return (
        <group ref={group}>
            <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[outer, 64]} />
                <meshBasicMaterial color="#38bdf8" transparent opacity={0.09} side={THREE.DoubleSide} depthWrite={false} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[Math.max(0.05, outer - 0.04), outer, 64]} />
                <meshBasicMaterial color="#38bdf8" transparent opacity={0.6} side={THREE.DoubleSide} depthWrite={false} />
            </mesh>
        </group>
    );
}

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

/**
 * Closed perimeter line through all active node anchors (fused_room mode,
 * 3-4 active nodes) — replaces the single N1-N2 axis with an actual room
 * outline. Relies on `nodes` already being in perimeter order (1->2->3->4->1,
 * see shared/schema.ts's NODE_ANCHORS comment) rather than sorting by
 * position, so a 3-active-node subset still traces a sensible partial loop.
 */
function RoomBoundary({ nodes }: { nodes: SensorNode[] }) {
    const points = useMemo(() => {
        const pts = nodes.map((n) => new THREE.Vector3(n.x, 0.02, n.z));
        if (pts.length > 0) pts.push(pts[0].clone());
        return pts;
    }, [nodes]);
    if (points.length < 2) return null;
    // drei's <Line> (not raw JSX <line>, which TS resolves to the SVG
    // intrinsic element) draws a continuous connected polyline through points.
    return <Line points={points} color="#00ffaa" transparent opacity={0.3} />;
}

function signalFieldIntensityColor(t: number): THREE.Color {
    // blue (low) -> green (mid) -> red (high), same convention as RuView's
    // floor-grid reference (F:\RuView-0.8.2-esp32\ui\components\gaussian-splats.js).
    const clamped = Math.min(1, Math.max(0, t));
    return clamped < 0.5
        ? new THREE.Color(0, clamped * 2, 1 - clamped * 2)
        : new THREE.Color((clamped - 0.5) * 2, 1 - (clamped - 0.5) * 2, 0);
}

/**
 * Floor-plane intensity grid for fused_room mode, adapted from RuView's
 * gaussian-splats.js floor-grid pattern (Three.js Points colored by a
 * spatial signal_field array) — ported to react-three-fiber. Rendering aid
 * only (see shared/schema.ts's signalFieldSchema HONESTY NOTE), not a
 * physical measurement.
 */
function SignalFieldGrid({ signalField }: { signalField: SignalField | null }) {
    const geometry = useMemo(() => {
        if (!signalField || signalField.values.length === 0) return null;
        // Room size and per-axis cell sizes come from the server's configured
        // geometry (server/lib/room-geometry.ts), not client constants.
        const { gridWidth, gridDepth, cellSizeM, cellDepthM, roomWidthM, roomDepthM, values } = signalField;
        const max = values.reduce((m, v) => Math.max(m, v), 0) || 1;
        const positions: number[] = [];
        const colors: number[] = [];
        for (let gz = 0; gz < gridDepth; gz++) {
            const cz = -roomDepthM / 2 + (gz + 0.5) * cellDepthM;
            for (let gx = 0; gx < gridWidth; gx++) {
                const cx = -roomWidthM / 2 + (gx + 0.5) * cellSizeM;
                positions.push(cx, 0.005, cz);
                const c = signalFieldIntensityColor(values[gz * gridWidth + gx] / max);
                colors.push(c.r, c.g, c.b);
            }
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
        geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        return geo;
    }, [signalField]);

    if (!geometry) return null;

    return (
        <points geometry={geometry}>
            <pointsMaterial size={0.12} vertexColors transparent opacity={0.55} sizeAttenuation />
        </points>
    );
}

function NodeInfluenceRings({ node }: { node: SensorNode }) {
    const color = NODE_COLORS[node.node_id] ?? "#00ffcc";
    return (
        <group rotation={[-Math.PI / 2, 0, 0]} position={[node.x, 0.01, node.z]}>
            {[0.9, 1.8].map((radius, index) => (
                <mesh key={`${node.node_id}-${radius}`}>
                    <ringGeometry args={[radius - 0.015, radius + 0.015, 48]} />
                    <meshBasicMaterial
                        color={color}
                        transparent
                        opacity={index === 0 ? 0.12 : 0.06}
                        side={THREE.DoubleSide}
                    />
                </mesh>
            ))}
        </group>
    );
}

/**
 * Soft glowing band along the N1–N2 baseline (fused mode only) — visualizes
 * the 1-D corridor the fused target can occupy; the midpoint ring brightens
 * (`emphasis`) when the target is crossing the middle zone.
 */
function NodeAxisField({
    a,
    b,
    emphasis = 0,
}: {
    a: SensorNode;
    b: SensorNode;
    emphasis?: number;
}) {
    const midpointX = (a.x + b.x) / 2;
    const midpointZ = (a.z + b.z) / 2;
    const axisLength = Math.max(0.6, Math.hypot(b.x - a.x, b.z - a.z));
    const axisAngle = Math.atan2(b.z - a.z, b.x - a.x);

    return (
        <group position={[midpointX, 0.012, midpointZ]} rotation={[-Math.PI / 2, 0, axisAngle]}>
            <mesh>
                <planeGeometry args={[axisLength, 0.7]} />
                <meshBasicMaterial color="#22d3ee" transparent opacity={0.08 + emphasis * 0.1} side={THREE.DoubleSide} />
            </mesh>
            <mesh position={[0, 0, 0.001]}>
                <ringGeometry args={[0.22, 0.34 + emphasis * 0.14, 48]} />
                <meshBasicMaterial color="#e2f3ff" transparent opacity={0.18 + emphasis * 0.2} side={THREE.DoubleSide} />
            </mesh>
        </group>
    );
}

/**
 * The MOVEMENT arrow: a line from the target in its direction of travel,
 * length ∝ speed (0.6–1.8 m), rendered only while `isMoving` is true (and
 * gated upstream by canPresentAxisMotionVector's 0.05 m/s speed floor).
 */
function TargetMotionVector({ target }: { target: RadialTarget }) {
    const geometry = useMemo(() => {
        const length = Math.max(0.6, Math.min(1.8, 0.6 + target.speed * 2.5));
        // Canonical travel-angle decode (cos → x, sin → z) — matches
        // DirectionalNode's heading cone; see shared/bearing.ts.
        const { dx, dz } = headingVectorFromAngle(target.angle);
        const endX = target.x + dx * length;
        const endZ = target.z + dz * length;
        return new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(target.x, 0.32, target.z),
            new THREE.Vector3(endX, 0.32, endZ),
        ]);
    }, [target.angle, target.speed, target.x, target.z]);

    if (!target.isMoving) {
        return null;
    }

    return (
        <lineSegments geometry={geometry}>
            <lineBasicMaterial color="#7dd3fc" transparent opacity={0.75} />
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
            // Same axis convention as the target marker: x, y(up), z(north).
            pos[i * 3] = p.x;
            pos[i * 3 + 1] = p.y;
            pos[i * 3 + 2] = p.z;

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
    signalField?: SignalField | null;
    showLivePosition?: boolean;
    /** Draw the illustrative (procedural, not measured) human figure on the target. */
    showIllustrativeBody?: boolean;
}

/**
 * The radar scene: grid + node beacons + axis + the target dot and motion
 * arrow. `canRenderTarget` is the final render gate — the page-level
 * presentation gate (showLivePosition) AND a non-none/stale state must both
 * hold before any target geometry is mounted.
 */
export function RadialScene({
    radialTarget,
    points,
    poseFrame,
    targetState,
    nodes = [],
    signalField = null,
    showLivePosition = false,
    showIllustrativeBody = false,
}: RadialSceneProps) {
    const label = radialTarget?.label ?? "unknown";
    const wallDistance = radialTarget?.wallDistance ?? 5.0;
    const canRenderTarget = Boolean(
        showLivePosition &&
        radialTarget &&
        targetState &&
        targetState.state !== "none" &&
        targetState.state !== "stale"
    );

    // Shared position/speed state for DirectionalNode + HumanMesh (Area 2/3):
    // one damped position and one damped speed, computed once per frame here
    // and copied down so the dot and body never diverge against the same
    // radialTarget.x/z. The snap decision (large jump, reacquisition, mode
    // flip) also lives here so it fires exactly once instead of being
    // duplicated (and desynced) across both children.
    const smoothedPosition = useRef(new THREE.Vector3(radialTarget?.x ?? 0, 0.3, radialTarget?.z ?? 0));
    const smoothedSpeed = useRef(radialTarget?.speed ?? 0);
    const rawTargetVecScratch = useRef(new THREE.Vector3());
    const prevCanRenderTarget = useRef(canRenderTarget);
    const prevNodeMode = useRef(targetState?.node_mode);

    useFrame((_state, delta) => {
        if (!radialTarget) return;

        const reacquired = canRenderTarget && !prevCanRenderTarget.current;
        const modeFlipped = targetState?.node_mode !== prevNodeMode.current;
        prevCanRenderTarget.current = canRenderTarget;
        prevNodeMode.current = targetState?.node_mode;

        const rawTargetVec = rawTargetVecScratch.current.set(radialTarget.x, 0.3, radialTarget.z);
        const distanceToRaw = smoothedPosition.current.distanceTo(rawTargetVec);

        if (reacquired || modeFlipped || distanceToRaw > 0.3) {
            smoothedPosition.current.copy(rawTargetVec);
            smoothedSpeed.current = 0;
            return;
        }

        const isFusedTarget = radialTarget.balance !== undefined;
        const nearNodeStrength = getNearNodeStrength(radialTarget.balance);
        const decayRate = positionDecayRate(distanceToRaw, radialTarget.speed, isFusedTarget, nearNodeStrength);
        dampVector3(smoothedPosition.current, rawTargetVec, decayRate, delta);
        smoothedSpeed.current = dampScalar(smoothedSpeed.current, radialTarget.speed, DECAY_RATES.speed, delta);
    });
    // The human figure is an ILLUSTRATION, not a measurement: CSI on this
    // 1-antenna-per-node hardware cannot support a body-shape claim, so the AI
    // poseFrame skeleton stays gated off (canPresentVolumetricTarget) and only
    // HumanMesh's procedural walk/breathe figure is drawn, driven by the dot's
    // speed and always captioned. dashboard.tsx derives showIllustrativeBody
    // from canPresentIllustrativeBody (the same gate as the dot, so the body
    // can never outlive it) AND the operator's Skeleton toggle.
    const canRenderIllustrativeBody = showIllustrativeBody;
    // Mechanical (fan/machine) volumetric overlay remains disabled.
    const canRenderVolumetricOverlay = false;
    const spatialSummary = useMemo(
        () => summarizeTargetSpatial(radialTarget, nodes, targetState),
        [radialTarget, nodes, targetState],
    );
    const fusedNodes = targetState?.node_mode === "fused_two_node" && nodes.length >= 2;
    const fusedRoom = targetState?.node_mode === "fused_room" && nodes.length >= 3;
    const midpointEmphasis = spatialSummary?.presentationMode === "fused_axis" && spatialSummary.balanceZone === "midpoint"
        ? 1
        : 0.25;

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
    const showAxisMotionVector = canPresentAxisMotionVector({
        dataSource: "esp32",
        radialTarget,
        targetState,
    });

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
                        <group key={n.node_id}>
                            <NodeInfluenceRings node={n} />
                            <ESPBeacon
                                position={[n.x, 0.15, n.z]}
                                color={NODE_COLORS[n.node_id] ?? "#00ffcc"}
                                motion={n.active ? n.motion : 0}
                                label={`N${n.node_id}`}
                            />
                        </group>
                    ))}
                    {fusedNodes && <NodeAxisField a={nodes[0]} b={nodes[1]} emphasis={midpointEmphasis} />}
                    {fusedNodes && <NodeAxis a={nodes[0]} b={nodes[1]} />}
                    {fusedRoom && <RoomBoundary nodes={nodes} />}
                    {canRenderTarget && radialTarget && (
                        <TargetLinks target={radialTarget} nodes={nodes} />
                    )}
                </>
            ) : (
                <ESPBeacon />
            )}
            <FloorPlane />
            {fusedRoom && <SignalFieldGrid signalField={signalField} />}
            <AmbientPoints points={points} />

            {/* Wall plane at detected reflection distance. 1-D range indicator:
                its due-east placement is fictional orientation, so only show it
                alongside a rendered target. */}
            {canRenderTarget && <WallPlane distance={wallDistance} />}

            {/* Render only state-authorized target objects. Unknown targets stay abstract. */}
            {canRenderTarget && radialTarget && (
                <>
                    {/* Always keep the live target anchor visible in the radar,
                        even when a richer human/mechanical overlay is rendered. */}
                    <DirectionalNode
                        target={fusedArrowTarget ?? radialTarget}
                        positionRef={smoothedPosition}
                        speedRef={smoothedSpeed}
                    />
                    {label === "mechanical" && canRenderVolumetricOverlay ? (
                        <MachineStatic target={radialTarget} />
                    ) : canRenderIllustrativeBody ? (
                        <>
                            <HumanMesh
                                target={radialTarget}
                                poseFrame={null}
                                positionRef={smoothedPosition}
                                speedRef={smoothedSpeed}
                            />
                            <Billboard position={[radialTarget.x, 2.1, radialTarget.z]} follow={true}>
                                <Text
                                    fontSize={0.09}
                                    color="#fbbf24"
                                    fillOpacity={0.75}
                                    anchorX="center"
                                    anchorY="middle"
                                >
                                    ILLUSTRATIVE BODY - NOT MEASURED POSE
                                </Text>
                            </Billboard>
                        </>
                    ) : null}
                    {fusedRoom && radialTarget.positionUncertaintyM !== undefined && (
                        <PositionUncertaintyRing radiusM={radialTarget.positionUncertaintyM} positionRef={smoothedPosition} />
                    )}
                    {showAxisMotionVector && (
                        <TargetMotionVector target={fusedArrowTarget ?? radialTarget} />
                    )}
                    {/* Honesty label: the dot is a perturbation-proxy estimate, not
                        RF-ranged/multilateration position — on-axis for 2 nodes,
                        a weighted room centroid for 3-4 (see fuseNodeTargets). */}
                    {(targetState?.node_mode === "fused_two_node" || targetState?.node_mode === "fused_room") && (
                        <Billboard position={[radialTarget.x, 0.95, radialTarget.z]} follow={true}>
                            <Text
                                fontSize={0.11}
                                color="#cbd5e1"
                                fillOpacity={0.34}
                                anchorX="center"
                                anchorY="middle"
                            >
                                {targetState.node_mode === "fused_room"
                                    ? "room-centroid estimate" +
                                      (radialTarget.positionUncertaintyM !== undefined
                                          ? ` ~ within ${radialTarget.positionUncertaintyM.toFixed(1)} m`
                                          : "")
                                    : "axis projection"}
                            </Text>
                        </Billboard>
                    )}
                </>
            )}
        </>
    );
}

