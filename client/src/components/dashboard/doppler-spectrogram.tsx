import { useMemo } from "react";
import Plot from "react-plotly.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";
import type { DopplerFrame } from "@shared/schema";

interface DopplerSpectrogramProps {
    frame: DopplerFrame | null;
    className?: string;
}

export function DopplerSpectrogram({
    frame,
    className = "",
}: DopplerSpectrogramProps) {
    const plotData = useMemo(() => {
        if (!frame || frame.intensities.length === 0) {
            // Demo spectrogram
            const times = Array.from({ length: 50 }, (_, i) => i * 0.1);
            const frequencies = Array.from({ length: 32 }, (_, k) => k * 0.3125);
            const intensities = times.map((t) =>
                frequencies.map((f) => {
                    const motion = Math.exp(-((f - 3) ** 2) / 4) * Math.sin(t * 2) ** 2;
                    const noise = Math.random() * 0.05;
                    return 20 * Math.log10(motion + noise + 0.001);
                })
            );
            return { times, frequencies, intensities };
        }
        return frame;
    }, [frame]);

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
                            colorscale: "Viridis",
                            zmin: -60,
                            zmax: 0,
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
