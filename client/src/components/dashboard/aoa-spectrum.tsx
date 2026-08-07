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
 * MUSIC pseudo-spectrum over the server's TEMPORAL sample window — a signal
 * signature, NOT a spatial angle-of-arrival. Confirmed 2026-08-07
 * (PS-GAP-MUSIC-001 fix session, Task 0): the input buffer is 16
 * time-sequential single-antenna CSI scalars interleaved from two
 * clock-unsynchronized nodes; no spatial direction is physically encoded in
 * it, so the x-axis "degrees" are a steering-vector correlation coordinate,
 * not a measured bearing. The underlying input-independence defect
 * (spectrum frozen regardless of input) was fixed the same session — the
 * curve now genuinely tracks the signal — but the relabeling below is
 * permanent for this hardware: fixing the math cannot add a spatial
 * aperture that the single-antenna nodes don't have.
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
        <CardHeader className="flex flex-col gap-0.5 px-4 pb-2 pt-4">
          <div className="flex flex-row items-center gap-2">
            <Radio className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm">Signal Signature (temporal MUSIC)</CardTitle>
          </div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">
            TEMPORAL SIGNATURE — NOT SPATIAL ANGLE
          </span>
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
      <CardHeader className="flex flex-col gap-0.5 px-4 pb-2 pt-4">
        <div className="flex flex-row items-center gap-2">
          <Radio className="h-4 w-4 text-chart-1" />
          <CardTitle className="text-sm">Signal Signature (temporal MUSIC)</CardTitle>
        </div>
        {/* Same honesty-caveat convention as getLivePositionCaveat's
            "ON-AXIS ESTIMATE - NOT ROOM POSITION" treatment: single-antenna
            nodes have no spatial aperture, so the x-axis is a steering
            coordinate over the temporal window, not a physical bearing. */}
        <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">
          TEMPORAL SIGNATURE — NOT SPATIAL ANGLE
        </span>
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
              hovertemplate: "Steering coord: %{x}<br>Power: %{y:.1f} dB<extra></extra>",
            },
            {
              type: "scatter",
              mode: "markers",
              x: [plotData.peakAngle],
              y: [Math.max(...plotData.powers)],
              marker: {
                // De-emphasized (was red/size 10): the peak is a signature
                // feature, not a measured direction — it must not read as a
                // confident spatial fix.
                color: "hsl(217, 30%, 55%)",
                size: 6,
                symbol: "diamond-open",
              },
              name: "Peak",
              hovertemplate: "Signature peak (steering coord %{x} — not a spatial angle)<extra></extra>",
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 40, r: 12, t: 8, b: 28 },
            xaxis: {
              title: "Steering coordinate (not physical direction)",
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
