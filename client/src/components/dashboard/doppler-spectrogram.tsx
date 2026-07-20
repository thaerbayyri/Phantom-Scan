import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";
import type { DopplerFrame } from "@shared/schema";

interface DopplerSpectrogramProps {
    frame: DopplerFrame | null;
    className?: string;
}

// Purple ramp (matches --chart-3) instead of stock Viridis, so the panel
// reads as part of the same dark theme as the other charts.
const DOPPLER_COLORSCALE: Array<[number, string]> = [
    [0, "hsl(230, 20%, 14%)"],
    [0.25, "hsl(258, 40%, 26%)"],
    [0.5, "hsl(272, 50%, 45%)"],
    [0.75, "hsl(285, 60%, 62%)"],
    [1, "hsl(300, 85%, 85%)"],
];

// computeDFTMagnitudes clamps the floor at -60 dB, but the ceiling was
// previously hardcoded to 0 dB — far below the DFT magnitude's real range
// (amplitude is |int8 + i*int8|, up to sqrt(127^2+127^2) ~= 45 dB), so almost
// all real motion energy clipped to the top of the scale and the whole plot
// washed out to a flat bright color. 45 dB matches that physical ceiling.
const DOPPLER_ZMIN = -60;
const DOPPLER_ZMAX = 45;

/**
 * Time × frequency heatmap of the dynamic CSI amplitude — the target's raw
 * motion signature: vertical energy bands appear while the person moves and
 * vanish in an empty/still room.
 */
export function DopplerSpectrogram({
    frame,
    className = "",
}: DopplerSpectrogramProps) {
    // Honest empty state: never synthesize a fake spectrogram — a visible
    // plot must always be real data.
    const plotData = useMemo(() => {
        if (!frame || frame.intensities.length === 0) {
            return null;
        }
        return frame;
    }, [frame]);

    if (!plotData) {
        return (
            <Card className={`flex flex-col overflow-hidden ${className}`}>
                <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
                    <Activity className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-sm">Doppler Spectrogram</CardTitle>
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
                <Activity className="h-4 w-4 text-chart-3" />
                <CardTitle className="text-sm">Doppler Spectrogram</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 px-2 pb-2 pt-0">
                <Plot
                    data={[
                        {
                            type: "heatmap",
                            x: plotData.times,
                            y: plotData.frequencies,
                            z: plotData.intensities.length > 0
                                ? plotData.intensities[0].map((_, colIdx) =>
                                    plotData.intensities.map((row) => row[colIdx])
                                )
                                : [],
                            colorscale: DOPPLER_COLORSCALE,
                            zmin: DOPPLER_ZMIN,
                            zmax: DOPPLER_ZMAX,
                            hovertemplate:
                                "Time: %{x:.2f}s<br>Doppler: %{y:.1f} Hz<br>Power: %{z:.1f} dB<extra></extra>",
                            showscale: false,
                        },
                    ]}
                    layout={{
                        autosize: true,
                        paper_bgcolor: "rgba(0,0,0,0)",
                        plot_bgcolor: "rgba(0,0,0,0)",
                        margin: { l: 32, r: 10, t: 6, b: 24 },
                        xaxis: {
                            title: "Time",
                            gridcolor: "rgba(128,128,128,0.2)",
                            zerolinecolor: "rgba(128,128,128,0.4)",
                        },
                        yaxis: {
                            title: "Doppler",
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
                    data-testid="plot-doppler-spectrogram"
                />
            </CardContent>
        </Card>
    );
}
