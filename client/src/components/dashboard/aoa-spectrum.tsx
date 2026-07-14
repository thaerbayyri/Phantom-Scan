import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Radio } from "lucide-react";
import type { ISARFrame } from "@shared/schema";

interface AoASpectrumProps {
  frame: ISARFrame | null;
  className?: string;
}

/**
 * MUSIC pseudo-spectrum for the current frame. Derived visualization: with
 * single-antenna boards there is no spatial aperture, so this is computed
 * over a time-sample buffer (synthetic aperture) — useful as a stable signal
 * signature, not a physically calibrated bearing. In fused two-node mode the
 * server treats the peak angle as display-only.
 */
export function AoASpectrum({ frame, className = "" }: AoASpectrumProps) {
  // Honest empty state: never synthesize a fake spectrum — an operator must be
  // able to trust that a visible curve is real data.
  const plotData = useMemo(() => {
    if (!frame || frame.spectrum.length === 0) {
      return null;
    }
    return {
      angles: frame.spectrum.map((p) => p.angle),
      powers: frame.spectrum.map((p) => p.power),
      peakAngle: frame.peakAngle,
    };
  }, [frame]);

  if (!plotData) {
    return (
      <Card className={`flex min-w-0 flex-col overflow-hidden ${className}`}>
        <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
          <Radio className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">AoA Spectrum (MUSIC — derived)</CardTitle>
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
    <Card className={`flex min-w-0 flex-col overflow-hidden ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
        <Radio className="h-4 w-4 text-chart-1" />
        <CardTitle className="text-sm">AoA Spectrum (MUSIC — derived)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 px-2 pb-2 pt-0">
        <Plot
          data={[
            {
              type: "scatter",
              mode: "lines",
              fill: "tozeroy",
              x: plotData.angles,
              y: plotData.powers,
              line: { color: "hsl(217, 91%, 60%)", width: 2 },
              fillcolor: "hsla(217, 91%, 60%, 0.2)",
              hovertemplate: "Angle: %{x}°<br>Power: %{y:.1f} dB<extra></extra>",
            },
            {
              type: "scatter",
              mode: "markers",
              x: [plotData.peakAngle],
              y: [Math.max(...plotData.powers)],
              marker: {
                color: "hsl(0, 84%, 60%)",
                size: 10,
                symbol: "diamond",
              },
              name: "Peak",
              hovertemplate: "Peak: %{x}°<extra></extra>",
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 40, r: 12, t: 8, b: 28 },
            xaxis: {
              title: "Angle (deg)",
              range: [-60, 60],
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            yaxis: {
              title: "Power (dB)",
              gridcolor: "rgba(128,128,128,0.2)",
              zerolinecolor: "rgba(128,128,128,0.4)",
            },
            showlegend: false,
            font: {
              color: "hsl(var(--foreground))",
              size: 10,
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
          data-testid="plot-aoa-spectrum"
        />
      </CardContent>
    </Card>
  );
}
