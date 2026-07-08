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
  // Honest empty state: never synthesize fake intensities — a visible heatmap
  // must always be real data.
  const plotData = useMemo(() => {
    if (!data || data.intensities.length === 0) {
      return null;
    }
    return data;
  }, [data]);

  if (!plotData) {
    return (
      <Card className={`flex flex-col overflow-hidden ${className}`}>
        <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
          <Grid3x3 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">AoA Heatmap (Time vs Angle)</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 items-center justify-center px-2 pb-2 pt-0">
          <span className="text-xs font-mono uppercase tracking-widest text-muted-foreground/60">
            no live stream
          </span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`flex flex-col overflow-hidden ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
        <Grid3x3 className="h-4 w-4 text-chart-2" />
        <CardTitle className="text-sm">AoA Heatmap (Time vs Angle)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 px-2 pb-2 pt-0">
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
              showscale: false,
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 32, r: 10, t: 6, b: 24 },
            xaxis: {
              title: "Angle",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            yaxis: {
              title: "Time",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            font: {
              color: "hsl(var(--foreground))",
              size: 9,
            },
          }}
          config={{
            displaylogo: false,
            displayModeBar: false,
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
