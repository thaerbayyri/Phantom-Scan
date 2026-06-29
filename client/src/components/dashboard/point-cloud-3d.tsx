import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { PointCloudPoint, RadialTarget, PoseFrame, TargetState } from "@shared/schema";
import { RadialScene } from "./RadialScene";

interface PointCloud3DProps {
  points: PointCloudPoint[];
  radialTarget?: RadialTarget | null;
  poseFrame?: PoseFrame | null;
  targetState?: TargetState | null;
  className?: string;
}

export function PointCloud3D({ points, radialTarget, poseFrame, targetState, className = "" }: PointCloud3DProps) {
  return (
    <div className={`relative w-full h-full ${className}`}>
      <Canvas camera={{ position: [0, 8, 6], fov: 50 }}>
        <color attach="background" args={["#000810"]} />
        <RadialScene
          radialTarget={radialTarget ?? null}
          points={points}
          poseFrame={poseFrame ?? null}
          targetState={targetState ?? null}
        />
        <OrbitControls
          makeDefault
          maxPolarAngle={Math.PI / 2.1}
          minDistance={3}
          maxDistance={30}
        />
      </Canvas>

      {/* Operator view keeps the scene clean; debug lives in diagnostics instead. */}
    </div>
  );
}
