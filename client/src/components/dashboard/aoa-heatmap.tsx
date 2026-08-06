import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Grid3x3 } from "lucide-react";
import type { HeatmapData } from "@shared/schema";

interface AoAHeatmapProps {
  data: HeatmapData | null;
  className?: string;
}

// Teal ramp (matches --chart-2). Known-null subcarrier columns are masked
// out below rather than colored, so the dark end of this ramp is reached
// only by genuinely weak (but real) readings.
const SUBCARRIER_COLORSCALE: Array<[number, string]> = [
  [0, "hsl(220, 20%, 14%)"],
  [0.25, "hsl(195, 55%, 22%)"],
  [0.5, "hsl(188, 65%, 38%)"],
  [0.75, "hsl(180, 78%, 55%)"],
  [1, "hsl(170, 85%, 82%)"],
];

// The theoretical dB bounds (amplitude = |int8 + i*int8|, so 0 <= amplitude
// <= sqrt(127^2 + 127^2) => -60..45 dB) are almost never reached by real
// hardware: this rig's actual per-subcarrier amplitudes cluster around
// 13-15 dB with only ~2 dB of frame-to-frame spread. A fixed -60..45 scale
// crushes that entire real signal into ~2% of the color range, so every
// non-null subcarrier renders as the same flat color. Auto-ranging to the
// live buffer's 5th/95th percentile keeps the actual signal visible
// regardless of hardware gain, at the cost of "same absolute dB = same
// color" consistency across sessions.
const AUTO_RANGE_MIN_SPREAD_DB = 6;

// ESP-IDF's raw HT20 CSI buffer includes 12 null/guard subcarriers (DC +
// band edges) that report near-zero I/Q — the firmware forwards that buffer
// byte-for-byte (csi_collector.c) with no filtering, and the accumulator
// clamps near-zero amplitude toward a -60 dB floor. These columns aren't a
// low-but-real reading, they're the same dead subcarrier index every frame.
// Rendering them as "signal" paints a permanent dark stripe that looks like
// a rendering glitch.
//
// Detection is relative, not an exact -60 dB pin: a genuine null bin can
// still pick up a little leakage/noise some frames (never exactly 0), so
// requiring every row to hit the floor exactly is fragile — one noisy frame
// un-flags the column and the stripe comes back. Instead, compare each
// column's median level against the median of all columns: real subcarriers
// here vary within ~2 dB of each other, so anything sitting far below that
// baseline is a dead bin, not weak signal.
const NULL_SUBCARRIER_DB_BELOW_MEDIAN = 15;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function maskNullSubcarrierColumns(intensities: number[][]): (number | null)[][] {
  if (intensities.length === 0 || intensities[0].length === 0) {
    return intensities;
  }
  const numCols = intensities[0].length;
  const columnMedians = Array.from({ length: numCols }, (_, c) =>
    median(intensities.map((row) => row[c])),
  );
  const baseline = median(columnMedians);
  const isNullColumn = columnMedians.map(
    (m) => m < baseline - NULL_SUBCARRIER_DB_BELOW_MEDIAN,
  );
  return intensities.map((row) =>
    row.map((v, c) => (isNullColumn[c] ? null : v)),
  );
}

function autoRangeZ(intensities: (number | null)[][]): { zmin: number; zmax: number } {
  const flat: number[] = [];
  for (const row of intensities) {
    for (const v of row) {
      if (typeof v === "number" && Number.isFinite(v)) flat.push(v);
    }
  }
  if (flat.length === 0) {
    return { zmin: -60, zmax: 45 };
  }
  flat.sort((a, b) => a - b);
  const p = (q: number) => flat[Math.min(flat.length - 1, Math.floor(q * flat.length))];
  let zmin = p(0.05);
  let zmax = p(0.95);
  if (zmax - zmin < AUTO_RANGE_MIN_SPREAD_DB) {
    const mid = (zmin + zmax) / 2;
    zmin = mid - AUTO_RANGE_MIN_SPREAD_DB / 2;
    zmax = mid + AUTO_RANGE_MIN_SPREAD_DB / 2;
  }
  return { zmin, zmax };
}

/**
 * Time × subcarrier amplitude waterfall (dB) from the raw CSI stream — human
 * motion appears as coherent ripples sweeping across subcarriers over time.
 * (Formerly an "AoA" heatmap; single-antenna boards carry no spatial angle
 * information, so the axis is the real subcarrier index instead.)
 */
export function AoAHeatmap({ data, className = "" }: AoAHeatmapProps) {
  // Honest empty state: never synthesize fake intensities — a visible heatmap
  // must always be real data.
  const plotData = useMemo(() => {
    if (!data || data.intensities.length === 0) {
      return null;
    }
    return data;
  }, [data]);

  const maskedIntensities = useMemo(
    () => maskNullSubcarrierColumns(plotData?.intensities ?? []),
    [plotData],
  );

  const zRange = useMemo(
    () => autoRangeZ(maskedIntensities),
    [maskedIntensities],
  );

  if (!plotData) {
    return (
      <Card className={`flex flex-col overflow-hidden ${className}`}>
        <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
          <Grid3x3 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">Subcarrier Heatmap (Time × Subcarrier)</CardTitle>
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
        <CardTitle className="text-sm">Subcarrier Heatmap (Time × Subcarrier)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 px-2 pb-2 pt-0">
        <Plot
          data={[
            {
              type: "heatmap",
              x: plotData.angles,
              y: plotData.times,
              z: maskedIntensities,
              colorscale: SUBCARRIER_COLORSCALE,
              zmin: zRange.zmin,
              zmax: zRange.zmax,
              hovertemplate:
                "Subcarrier: %{x}<br>Time: %{y:.2f}s<br>Amplitude: %{z:.2f} dB<extra></extra>",
              showscale: false,
            },
          ]}
          layout={{
            autosize: true,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            margin: { l: 32, r: 10, t: 6, b: 24 },
            xaxis: {
              title: "Subcarrier",
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
