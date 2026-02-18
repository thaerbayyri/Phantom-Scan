import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Trail, Sphere } from "@react-three/drei";
import * as THREE from "three";
import type { TrackedTarget } from "@shared/schema";

interface SignalAvatarProps {
    target: TrackedTarget;
}

export function SignalAvatar({ target }: SignalAvatarProps) {
    const meshRef = useRef<THREE.Mesh>(null);

    // Calculate speed for dynamic visual effects
    const speed = useMemo(() => {
        return Math.sqrt(target.vx ** 2 + target.vy ** 2 + target.vz ** 2);
    }, [target.vx, target.vy, target.vz]);

    // Dynamic opacity: fade slightly when stationary, bright when moving
    // Base opacity 0.6 + speed factor
    const targetOpacity = Math.min(1.0, 0.4 + speed * 2.0);

    // Color based on confidence? Or just a nice "Signal" color (cyan/blue)
    const color = new THREE.Color("cyan").multiplyScalar(1 + speed); // Brighten with speed

    useFrame((state, delta) => {
        if (meshRef.current) {
            // Smoothly interpolate position to reduce jitter beyond Kalman
            // (Kalman already smooths, but 60fps interpolation looks better)
            meshRef.current.position.lerp(
                new THREE.Vector3(target.x, target.z, target.y), // Swap Y/Z for Three.js (Y is up)
                0.2
            );

            // Pulse effect
            const pulse = 1 + Math.sin(state.clock.elapsedTime * 4) * 0.1;
            meshRef.current.scale.setScalar(pulse);
        }
    });

    return (
        <group>
            <Trail
                width={0.2} // Width of the trail
                length={20} // Length of the trail
                color={new THREE.Color("cyan")}
                attenuation={(t) => t * t}
            >
                <Sphere ref={meshRef} args={[0.3, 32, 32]}>
                    <meshStandardMaterial
                        color="cyan"
                        emissive="cyan"
                        emissiveIntensity={0.5 + speed}
                        transparent
                        opacity={targetOpacity}
                        roughness={0.1}
                        metalness={0.8}
                    />
                </Sphere>
            </Trail>

            {/* Ground shadow/reference */}
            <mesh position={[target.x, -2, target.y]} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.1, 0.2, 32]} />
                <meshBasicMaterial color="cyan" transparent opacity={0.3} />
            </mesh>
        </group>
    );
}
