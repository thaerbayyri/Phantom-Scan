import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Grid3x3 } from "lucide-react";
import type { HeatmapData } from "@shared/schema";

interface AoAHeatmapProps {
  data: HeatmapData | null;
  className?: string;
}

export function AoAHeatmap({ data, className = "" }: AoAHeatmapProps) {
  const plotData = useMemo(() => {
    if (!data || data.intensities.length === 0) {
      // Generate demo heatmap
      const angles = Array.from({ length: 121 }, (_, i) => -60 + i);
      const times = Array.from({ length: 50 }, (_, i) => i * 0.1);
      const intensities = times.map((t) =>
        angles.map((a) => {
          // Create moving peak pattern
          const peakAngle = Math.sin(t * 2) * 20;
          const dist = Math.abs(a - peakAngle);
          return Math.exp(-dist * dist / 100) * 0.5 + Math.random() * 0.1;
        })
      );
      return { angles, times, intensities };
    }
    return data;
  }, [data]);

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Grid3x3 className="h-4 w-4 text-chart-2" />
        <CardTitle className="text-sm">AoA Heatmap (Time vs Angle)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-2">
        <Plot
          data={[
            {
              type: "heatmap",
              x: plotData.angles,
              y: plotData.times,
              z: plotData.intensities,
              colorscale: "Hot",
              hovertemplate:
                "Angle: %{x}°<br>Time: %{y:.2f}s<br>Power: %{z:.2f} dB<extra></extra>",
              colorbar: {
                title: "Power (dB)",
                titleside: "right",
                thickness: 15,
                len: 0.9,
              },
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 50, r: 60, t: 10, b: 40 },
            xaxis: {
              title: "Angle (°)",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            yaxis: {
              title: "Time (s)",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
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
          data-testid="plot-aoa-heatmap"
        />
      </CardContent>
    </Card>
  );
}
