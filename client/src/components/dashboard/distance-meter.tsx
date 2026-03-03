import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Ruler } from "lucide-react";

interface DistanceMeterProps {
    distanceCm: number;
    wallDistance: number;
    className?: string;
}

export function DistanceMeter({ distanceCm, wallDistance, className = "" }: DistanceMeterProps) {
    const distanceM = distanceCm / 100;
    const maxRange = 8; // meters

    // Color gradient: green (far) → orange (mid) → red (close)
    const ratio = Math.min(1, distanceM / maxRange);
    const hue = ratio * 120; // 0=red, 60=yellow, 120=green
    const gaugeColor = `hsl(${hue}, 85%, 50%)`;

    // Arc angle (180° full)
    const arcAngle = Math.min(180, (distanceM / maxRange) * 180);

    // Wall distance indicator
    const wallRatio = Math.min(1, wallDistance / maxRange);

    return (
        <Card className={`${className}`}>
            <CardHeader className="flex flex-row items-center gap-2 pb-2">
                <Ruler className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm">Distance Meter</CardTitle>
                <span className="ml-auto text-xs font-mono text-muted-foreground">
                    Wall: {wallDistance.toFixed(1)}m
                </span>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-2 py-3">
                {/* SVG Radial Gauge */}
                <svg viewBox="0 0 200 120" className="w-full max-w-[200px]">
                    {/* Background arc */}
                    <path
                        d="M 20 100 A 80 80 0 0 1 180 100"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        className="text-muted/30"
                        strokeLinecap="round"
                    />

                    {/* Distance arc */}
                    <path
                        d="M 20 100 A 80 80 0 0 1 180 100"
                        fill="none"
                        stroke={gaugeColor}
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${arcAngle * 2.79} 1000`}
                        className="transition-all duration-300 ease-out"
                    />

                    {/* Wall marker */}
                    {(() => {
                        const wallAngle = Math.PI - (wallRatio * Math.PI);
                        const wx = 100 + 80 * Math.cos(wallAngle);
                        const wy = 100 - 80 * Math.sin(wallAngle);
                        return (
                            <circle cx={wx} cy={wy} r="4" fill="#64748b" stroke="#94a3b8" strokeWidth="1.5" />
                        );
                    })()}

                    {/* Distance text */}
                    <text
                        x="100"
                        y="85"
                        textAnchor="middle"
                        className="fill-foreground"
                        style={{ fontSize: "28px", fontWeight: 700, fontFamily: "monospace" }}
                    >
                        {distanceCm.toFixed(0)}
                    </text>
                    <text
                        x="100"
                        y="102"
                        textAnchor="middle"
                        className="fill-muted-foreground"
                        style={{ fontSize: "12px", fontFamily: "monospace" }}
                    >
                        cm
                    </text>

                    {/* Range labels */}
                    <text x="18" y="115" className="fill-muted-foreground" style={{ fontSize: "9px" }}>0</text>
                    <text x="168" y="115" className="fill-muted-foreground" style={{ fontSize: "9px" }}>{maxRange}m</text>
                </svg>

                {/* Distance in meters subtitle */}
                <div className="text-xs text-muted-foreground font-mono">
                    {distanceM.toFixed(2)}m from ESP32
                </div>
            </CardContent>
        </Card>
    );
}
