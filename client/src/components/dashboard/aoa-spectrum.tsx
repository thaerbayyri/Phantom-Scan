import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Radio } from "lucide-react";
import type { ISARFrame } from "@shared/schema";

interface AoASpectrumProps {
  frame: ISARFrame | null;
  className?: string;
}

export function AoASpectrum({ frame, className = "" }: AoASpectrumProps) {
  const plotData = useMemo(() => {
    if (!frame || frame.spectrum.length === 0) {
      // Generate demo spectrum
      const angles = Array.from({ length: 121 }, (_, i) => -60 + i);
      const powers = angles.map((a) => {
        const peak1 = Math.exp(-((a - 15) ** 2) / 50) * 0.8;
        const peak2 = Math.exp(-((a + 25) ** 2) / 80) * 0.4;
        const noise = Math.random() * 0.05;
        return 20 * Math.log10(peak1 + peak2 + noise + 0.01);
      });
      return { angles, powers, peakAngle: 15 };
    }
    return {
      angles: frame.spectrum.map((p) => p.angle),
      powers: frame.spectrum.map((p) => p.power),
      peakAngle: frame.peakAngle,
    };
  }, [frame]);

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Radio className="h-4 w-4 text-chart-1" />
        <CardTitle className="text-sm">AoA Spectrum (MUSIC)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-2">
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
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: {
              title: "Angle (°)",
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
