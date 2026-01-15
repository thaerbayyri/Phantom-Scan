import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";
import type { SignalTrace } from "@shared/schema";

interface SignalTracesProps {
  trace: SignalTrace;
  className?: string;
}

export function SignalTraces({ trace, className = "" }: SignalTracesProps) {
  const plotData = useMemo(() => {
    if (trace.timestamps.length === 0) {
      // Generate demo data
      const timestamps = Array.from({ length: 100 }, (_, i) => i * 0.05);
      const h1Magnitude = timestamps.map(
        (t) => 0.8 + Math.sin(t * 3) * 0.15 + Math.random() * 0.05
      );
      const h2Magnitude = timestamps.map(
        (t) => 0.7 + Math.cos(t * 2.5) * 0.12 + Math.random() * 0.05
      );
      const nulledMagnitude = timestamps.map(
        (t) => 0.1 + Math.sin(t * 5) * 0.05 + Math.random() * 0.02
      );
      return { timestamps, h1Magnitude, h2Magnitude, nulledMagnitude };
    }
    return trace;
  }, [trace]);

  const relativeTime = plotData.timestamps.map((t, i) => i * 0.05);

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Activity className="h-4 w-4 text-chart-3" />
        <CardTitle className="text-sm">Signal Traces</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-2">
        <Plot
          data={[
            {
              type: "scatter",
              mode: "lines",
              name: "h1",
              x: relativeTime,
              y: plotData.h1Magnitude,
              line: { color: "hsl(217, 91%, 60%)", width: 2 },
              hovertemplate: "h1: %{y:.3f}<extra></extra>",
            },
            {
              type: "scatter",
              mode: "lines",
              name: "h2",
              x: relativeTime,
              y: plotData.h2Magnitude,
              line: { color: "hsl(180, 78%, 50%)", width: 2 },
              hovertemplate: "h2: %{y:.3f}<extra></extra>",
            },
            {
              type: "scatter",
              mode: "lines",
              name: "Nulled",
              x: relativeTime,
              y: plotData.nulledMagnitude,
              line: { color: "hsl(280, 65%, 60%)", width: 2 },
              hovertemplate: "Nulled: %{y:.3f}<extra></extra>",
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: {
              title: "Time (s)",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            yaxis: {
              title: "Magnitude",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
              range: [0, 1.2],
            },
            legend: {
              orientation: "h",
              x: 0.5,
              xanchor: "center",
              y: 1.1,
              font: { size: 10 },
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
          data-testid="plot-signal-traces"
        />
      </CardContent>
    </Card>
  );
}
