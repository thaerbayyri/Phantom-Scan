import { useRef, useMemo, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RadialTarget } from "@shared/schema";
import { dampAngle, DECAY_RATES } from "@/lib/smooth-follow";

// ═══════════════════════════════════════════════════════════════════
//  DirectionalNode — glowing sphere + heading arrow + fading trail
// ═══════════════════════════════════════════════════════════════════

interface DirectionalNodeProps {
    target: RadialTarget;
    /** Shared, already-damped position (RadialScene owns the damping/snap decision). */
    positionRef: MutableRefObject<THREE.Vector3>;
    /** Shared, already-damped speed, used in place of raw target.speed for visual scale. */
    speedRef: MutableRefObject<number>;
}

// Max trail length
const TRAIL_LENGTH = 60;

/** 0 at the axis midpoint → 1 at a node; drives the "swelling near a node" visual emphasis in fused mode. */
function getNearNodeStrength(balance?: number): number {
    if (balance === undefined) return 0;
    return Math.min(1, Math.abs(balance - 0.5) * 2);
}

/**
 * THE target marker: glowing sphere + heading arrow + fading motion trail.
 * Movement is conveyed four ways — the sphere lerps toward each new fused
 * position, the arrow rotates/scales with travel direction and speed, the
 * glow pulses fast while `isMoving` (slow "breathing" when idle), and the
 * trail draws the last 60 positions fading from old to new. Color also
 * flips cyan (#00e5ff) when moving vs darker teal (#0097a7) when still.
 */
export function DirectionalNode({ target, positionRef, speedRef }: DirectionalNodeProps) {
    const groupRef = useRef<THREE.Group>(null);
    const arrowRef = useRef<THREE.Group>(null);
    const glowRef = useRef<THREE.Mesh>(null);
    const trailRef = useRef<THREE.LineSegments>(null);

    const currentAngle = useRef(target.angle);

    // Trail history
    const trailPositions = useRef<THREE.Vector3[]>([]);
    const trailGeometry = useRef<THREE.BufferGeometry>(new THREE.BufferGeometry());
    const lastTrailPoint = useRef<THREE.Vector3>(positionRef.current.clone());

    // Pre-allocate trail buffer
    const trailBuffer = useMemo(() => {
        const positions = new Float32Array(TRAIL_LENGTH * 2 * 3); // line segments
        const colors = new Float32Array(TRAIL_LENGTH * 2 * 4); // RGBA
        return { positions, colors };
    }, []);
    const nearNodeStrength = getNearNodeStrength(target.balance);
    const isFusedTarget = target.balance !== undefined;
    const coreRadius = 0.22 + nearNodeStrength * 0.09;
    const glowRadius = 0.34 + nearNodeStrength * 0.14;
    const ringInner = 0.36 + target.confidence * 0.18 + nearNodeStrength * 0.05;
    const ringOuter = 0.43 + target.confidence * 0.18 + nearNodeStrength * 0.08;

    useFrame((state, delta) => {
        if (!groupRef.current) return;

        const t = state.clock.elapsedTime;

        // ── Position: directly from the shared, already-damped/snapped
        // value RadialScene computes once per frame (Area 2/NEW-3). Detect
        // the jump here (rather than lerping) purely to know when to reset
        // the trail — the position itself is never locally smoothed.
        const incoming = positionRef.current;
        const jumpDistance = groupRef.current.position.distanceTo(incoming);
        groupRef.current.position.copy(incoming);
        if (jumpDistance > 0.3 || trailPositions.current.length === 0) {
            lastTrailPoint.current.copy(incoming);
            trailPositions.current = [incoming.clone()];
        }

        // ── Smooth heading rotation ──
        currentAngle.current = dampAngle(
            currentAngle.current,
            target.angle,
            isFusedTarget ? DECAY_RATES.headingArrowFused : DECAY_RATES.headingArrowSingle,
            delta,
        );

        // Rotate arrow to point in direction of travel
        if (arrowRef.current) {
            arrowRef.current.rotation.y = -currentAngle.current + Math.PI / 2;

            // Scale arrow by (smoothed) speed (min 0.3, max 1.5)
            const arrowScale = target.isMoving
                ? Math.min(1.9, 0.38 + speedRef.current * 2.7 + nearNodeStrength * 0.28)
                : 0.34 + nearNodeStrength * 0.16;
            arrowRef.current.scale.setScalar(arrowScale);
        }

        // ── Glow pulse ──
        if (glowRef.current) {
            const pulse = target.isMoving
                ? 1.0 + Math.sin(t * 4) * 0.2  // Fast pulse when moving
                : 1.0 + Math.sin(t * 1.5) * 0.08; // Gentle breathe idle
            glowRef.current.scale.setScalar(pulse);
        }

        // ── Update trail ──
        // Record a new breadcrumb only after ≥2 cm of actual travel, so an
        // idle target doesn't grow a fake trail from lerp micro-motion.
        const currentPos = groupRef.current.position.clone();
        if (currentPos.distanceTo(lastTrailPoint.current) >= 0.02) {
            trailPositions.current.push(currentPos);
            lastTrailPoint.current.copy(currentPos);
            if (trailPositions.current.length > TRAIL_LENGTH) {
                trailPositions.current.shift();
            }
        }

        // Build trail line segments
        const trail = trailPositions.current;
        if (trail.length >= 2 && trailRef.current) {
            const segCount = trail.length - 1;
            const posArr = trailBuffer.positions;
            const colArr = trailBuffer.colors;

            for (let i = 0; i < segCount; i++) {
                const idx = i * 6;
                const cidx = i * 8;
                const opacity = (i / segCount); // Fade from old→new

                posArr[idx + 0] = trail[i].x;
                posArr[idx + 1] = trail[i].y;
                posArr[idx + 2] = trail[i].z;
                posArr[idx + 3] = trail[i + 1].x;
                posArr[idx + 4] = trail[i + 1].y;
                posArr[idx + 5] = trail[i + 1].z;

                // Cyan fading trail
                colArr[cidx + 0] = 0.0; colArr[cidx + 1] = 0.9; colArr[cidx + 2] = 1.0; colArr[cidx + 3] = opacity * 0.6;
                colArr[cidx + 4] = 0.0; colArr[cidx + 5] = 0.9; colArr[cidx + 6] = 1.0; colArr[cidx + 7] = opacity * 0.8;
            }

            // Update geometry
            const geo = trailGeometry.current;
            geo.setAttribute("position", new THREE.BufferAttribute(posArr.slice(0, segCount * 6), 3));
            geo.setAttribute("color", new THREE.BufferAttribute(colArr.slice(0, segCount * 8), 4));
            geo.attributes.position.needsUpdate = true;
            geo.attributes.color.needsUpdate = true;

            trailRef.current.geometry = geo;
        }
    });

    // Dynamic color based on state: bright cyan + hot emissive while moving,
    // dimmer teal while still — the fastest at-a-glance moving/idle cue.
    const nodeColor = target.isMoving ? "#00e5ff" : "#0097a7";
    const emissiveColor = target.isMoving ? "#00e5ff" : "#006064";
    const emissiveIntensity = target.isMoving ? 2.5 : 1.0;

    return (
        <>
            {/* Trail */}
            <lineSegments ref={trailRef}>
                <bufferGeometry />
                <lineBasicMaterial
                    vertexColors
                    transparent
                    opacity={0.7}
                    blending={THREE.AdditiveBlending}
                />
            </lineSegments>

            <group ref={groupRef}>
                {/* Ground shadow */}
                <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.28, 0]}>
                    <circleGeometry args={[0.45, 32]} />
                    <meshBasicMaterial color="#004d40" transparent opacity={0.3} />
                </mesh>

                {/* Confidence ring */}
                <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.27, 0]}>
                    <ringGeometry args={[ringInner, ringOuter, 32]} />
                    <meshBasicMaterial
                        color={nodeColor}
                        transparent
                        opacity={0.42 + target.confidence * 0.24 + nearNodeStrength * 0.16}
                        side={THREE.DoubleSide}
                    />
                </mesh>

                {/* Core sphere (target node) */}
                <mesh>
                    <sphereGeometry args={[coreRadius, 32, 32]} />
                    <meshStandardMaterial
                        color={nodeColor}
                        emissive={emissiveColor}
                        emissiveIntensity={emissiveIntensity + nearNodeStrength * 0.9}
                        roughness={0.1}
                        metalness={0.9}
                    />
                </mesh>

                {/* Outer glow */}
                <mesh ref={glowRef}>
                    <sphereGeometry args={[glowRadius, 32, 32]} />
                    <meshBasicMaterial
                        color={nodeColor}
                        transparent
                        opacity={0.18 + nearNodeStrength * 0.08}
                    />
                </mesh>

                {/* Heading Arrow (direction cone) */}
                <group ref={arrowRef}>
                    {/* Arrow shaft */}
                    <mesh position={[0, 0, 0.35]} rotation={[Math.PI / 2, 0, 0]}>
                        <cylinderGeometry args={[0.02, 0.02, 0.3, 8]} />
                        <meshStandardMaterial
                            color="#ffffff"
                            emissive={nodeColor}
                            emissiveIntensity={1.5}
                            transparent
                            opacity={0.9}
                        />
                    </mesh>

                    {/* Arrow head (cone) */}
                    <mesh position={[0, 0, 0.55]} rotation={[Math.PI / 2, 0, 0]}>
                        <coneGeometry args={[0.06, 0.15, 8]} />
                        <meshStandardMaterial
                            color="#ffffff"
                            emissive={nodeColor}
                            emissiveIntensity={2}
                        />
                    </mesh>
                </group>

                {/* Point light — brightness proportional to confidence */}
                <pointLight
                    color={nodeColor}
                    intensity={1 + target.confidence * 2.5 + nearNodeStrength * 1.4}
                    distance={5}
                    decay={2}
                />
            </group>
        </>
    );
}
