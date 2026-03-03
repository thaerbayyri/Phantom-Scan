import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Box } from "lucide-react";
import type { PointCloudPoint, RadialTarget } from "@shared/schema";
import { RadialScene } from "./RadialScene";

interface PointCloud3DProps {
  points: PointCloudPoint[];
  radialTarget?: RadialTarget | null;
  className?: string;
}

export function PointCloud3D({ points, radialTarget, className = "" }: PointCloud3DProps) {
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
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Box className="h-4 w-4 text-primary" />
        <CardTitle className="text-sm">3D Radial Scene</CardTitle>
        {radialTarget && (
          <span className="ml-auto text-xs text-muted-foreground font-mono">
            r={radialTarget.r.toFixed(1)}m · θ={((radialTarget.theta * 180) / Math.PI).toFixed(0)}°
            {radialTarget.isMoving ? " · MOVING" : " · IDLE"}
          </span>
        )}
      </CardHeader>
      <CardContent className="flex-1 p-0 relative min-h-[300px]">
        <Canvas camera={{ position: [0, 8, 6], fov: 50 }}>
          <color attach="background" args={["#000810"]} />
          <RadialScene radialTarget={radialTarget ?? null} points={renderPoints} />
          <OrbitControls
            makeDefault
            maxPolarAngle={Math.PI / 2.1}
            minDistance={3}
            maxDistance={20}
          />
        </Canvas>

        {/* Overlay stats */}
        <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-sm p-2 rounded text-xs text-white pointer-events-none">
          Points: {renderPoints.length}<br />
          Target: {radialTarget ? "TRACKING" : "SEARCHING..."}
        </div>
      </CardContent>
    </Card>
  );
}
