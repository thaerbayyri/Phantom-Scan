import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Box } from "lucide-react";
import type { PointCloudPoint } from "@shared/schema";

interface PointCloud3DProps {
  points: PointCloudPoint[];
  className?: string;
}

export function PointCloud3D({ points, className = "" }: PointCloud3DProps) {
  const plotData = useMemo(() => {
    if (points.length === 0) {
      // Generate demo grid when no data
      const demoPoints: PointCloudPoint[] = [];
      for (let x = -2; x <= 2; x += 0.5) {
        for (let y = 0; y <= 4; y += 0.5) {
          demoPoints.push({
            x,
            y,
            z: 0,
            amplitude: 0.2,
            timestamp: Date.now(),
          });
        }
      }
      return demoPoints;
    }
    return points;
  }, [points]);

  const x = plotData.map((p) => p.x);
  const y = plotData.map((p) => p.y);
  const z = plotData.map((p) => p.z);
  const amplitudes = plotData.map((p) => p.amplitude);

  const maxAmp = Math.max(...amplitudes, 0.1);
  const sizes = amplitudes.map((a) => Math.max(4, (a / maxAmp) * 20));

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Box className="h-4 w-4 text-chart-1" />
        <CardTitle className="text-sm">3D Point Cloud</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-2">
        <Plot
          data={[
            {
              type: "scatter3d",
              mode: "markers",
              x,
              y,
              z,
              marker: {
                size: sizes,
                color: amplitudes,
                colorscale: "Viridis",
                opacity: 0.8,
                colorbar: {
                  title: "Amplitude",
                  titleside: "right",
                  thickness: 15,
                  len: 0.5,
                },
              },
              hovertemplate:
                "X: %{x:.2f}m<br>Y: %{y:.2f}m<br>Z: %{z:.2f}m<br>Amp: %{marker.color:.2f}<extra></extra>",
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 0, r: 0, t: 0, b: 0 },
            scene: {
              xaxis: {
                title: "X (m)",
                range: [-5, 5],
                gridcolor: "rgba(128,128,128,0.2)",
                zerolinecolor: "rgba(128,128,128,0.4)",
              },
              yaxis: {
                title: "Y (m)",
                range: [0, 10],
                gridcolor: "rgba(128,128,128,0.2)",
                zerolinecolor: "rgba(128,128,128,0.4)",
              },
              zaxis: {
                title: "Z (m)",
                range: [-2, 2],
                gridcolor: "rgba(128,128,128,0.2)",
                zerolinecolor: "rgba(128,128,128,0.4)",
              },
              bgcolor: "rgba(0,0,0,0)",
              camera: {
                eye: { x: 1.5, y: 1.5, z: 1.0 },
              },
            },
            font: {
              color: "hsl(var(--foreground))",
              size: 10,
            },
          }}
          config={{
            displaylogo: false,
            modeBarButtonsToRemove: ["toImage", "sendDataToCloud"],
            responsive: true,
          }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
          data-testid="plot-3d-pointcloud"
        />
      </CardContent>
    </Card>
  );
}
