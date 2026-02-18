import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Box } from "lucide-react";
import * as THREE from "three";
import { SignalAvatar } from "./signal-avatar";
import type { PointCloudPoint, TrackedTarget } from "@shared/schema";

interface PointCloud3DProps {
  points: PointCloudPoint[];
  trackedTarget?: TrackedTarget | null; // Optional target
  className?: string;
}

function Points({ points }: { points: PointCloudPoint[] }) {
  const geometryRef = useRef<THREE.BufferGeometry>(null);

  // Create static buffer geometry for efficiency
  // Update attributes every frame if points change structure (length), 
  // but if points array is swapped, we just re-create geometry or update buffer.
  // Here we re-create geometry on points change for simplicity (length varies).
  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(points.length * 3);
    const col = new Float32Array(points.length * 3);
    const colorObj = new THREE.Color();

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      pos[i * 3] = p.x;
      pos[i * 3 + 1] = p.z; // Swap Y/Z for Three.js (Y is up)
      pos[i * 3 + 2] = p.y;

      // Color based on amplitude (heat map style: blue to red)
      // Normalize amplitude (0-100dB roughly?) 
      // Assume amplitude is linear/log power? ISAR gives power.
      // Let's assume amplitude 0-1 for color mapping or log scale.
      const normalized = Math.min(1, Math.max(0, p.amplitude / 50));
      colorObj.setHSL((1.0 - normalized) * 0.6, 1.0, 0.5); // Blue (0.6) to Red (0.0)

      col[i * 3] = colorObj.r;
      col[i * 3 + 1] = colorObj.g;
      col[i * 3 + 2] = colorObj.b;
    }
    return { positions: pos, colors: col };
  }, [points]);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={positions.length / 3}
          array={positions} // Optional but good for updates
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
        size={0.05}
        sizeAttenuation
        transparent
        opacity={0.8}
      />
    </points>
  );
}

function Scene({ points, trackedTarget }: { points: PointCloudPoint[], trackedTarget?: TrackedTarget | null }) {
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      <gridHelper args={[10, 10, 0x444444, 0x222222]} />
      <axesHelper args={[1]} />

      {/* Raw Point Cloud */}
      <Points points={points} />

      {/* Tracked Target Avatar */}
      {trackedTarget && <SignalAvatar target={trackedTarget} />}

      <OrbitControls makeDefault />
    </>
  );
}

export function PointCloud3D({ points, trackedTarget, className = "" }: PointCloud3DProps) {
  // Fallback demo points if empty
  const renderPoints = useMemo(() => {
    if (points.length === 0) {
      // Demo grid
      const demo: PointCloudPoint[] = [];
      for (let x = -2; x <= 2; x += 0.5) {
        for (let y = 0; y <= 4; y += 0.5) {
          demo.push({ x, y, z: 0, amplitude: 10 + Math.random() * 20, timestamp: Date.now() });
        }
      }
      return demo;
    }
    return points;
  }, [points]);

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Box className="h-4 w-4 text-primary" />
        <CardTitle className="text-sm">3D Scene</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 relative min-h-[300px]">
        <Canvas camera={{ position: [0, 5, 5], fov: 50 }}>
          <color attach="background" args={["#000"]} />
          <Scene points={renderPoints} trackedTarget={trackedTarget} />
        </Canvas>

        {/* Overlay stats */}
        <div className="absolute top-2 left-2 bg-black/50 p-2 rounded text-xs text-white pointer-events-none">
          Points: {renderPoints.length}<br />
          Target: {trackedTarget ? `ACTIVE (ID:${trackedTarget.id})` : "SEARCHING..."}
        </div>
      </CardContent>
    </Card>
  );
}
