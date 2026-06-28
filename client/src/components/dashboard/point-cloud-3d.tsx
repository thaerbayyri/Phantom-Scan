import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Box } from "lucide-react";
import type { PointCloudPoint, RadialTarget, PoseFrame } from "@shared/schema";
import { RadialScene } from "./RadialScene";

interface PointCloud3DProps {
  points: PointCloudPoint[];
  radialTarget?: RadialTarget | null;
  poseFrame?: PoseFrame | null;
  className?: string;
}

export function PointCloud3D({ points, radialTarget, poseFrame, className = "" }: PointCloud3DProps) {
  // Fallback demo points if empty
  const renderPoints = useMemo(() => {
    if (points.length === 0) {
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
    <div className={`relative w-full h-full ${className}`}>
      <Canvas camera={{ position: [0, 8, 6], fov: 50 }}>
        <color attach="background" args={["#000810"]} />
        <RadialScene radialTarget={radialTarget ?? null} points={renderPoints} poseFrame={poseFrame ?? null} />
        <OrbitControls
          makeDefault
          maxPolarAngle={Math.PI / 2.1}
          minDistance={3}
          maxDistance={30}
        />
      </Canvas>

      {/* Overlay stats */}
      <div className="absolute top-4 left-4 text-xs font-mono text-white/50 pointer-events-none">
        [ 3D RADIAL SCENE ]<br />
        Points: {renderPoints.length}<br />
        Target: {radialTarget ? `r=${radialTarget.r.toFixed(1)}m θ=${((radialTarget.theta * 180) / Math.PI).toFixed(0)}°` : "SEARCHING..."}
      </div>
    </div>
  );
}
