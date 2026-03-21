import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Ruler } from "lucide-react";

interface DistanceMeterProps {
    distanceCm: number;
    wallDistance: number;
    bearingRad?: number;
    className?: string;
}

export function DistanceMeter({ distanceCm, wallDistance, bearingRad, className = "" }: DistanceMeterProps) {
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
                <div className="text-xs text-muted-foreground font-mono flex items-center justify-center gap-2">
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2 py-1 rounded-md border border-white/5">
                        <span className="text-primary/60">{distanceM.toFixed(2)}m</span>
                        {bearingRad !== undefined && (
                            <>
                                <span className="text-white/20">|</span>
                                <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-tighter">Bearing</span>
                                    <span className="font-black text-primary text-sm animate-pulse-slow">
                                        {(() => {
                                            const deg = (bearingRad * 180) / Math.PI;
                                            if (deg >= -22.5 && deg <= 22.5) return "N";
                                            if (deg > 22.5 && deg <= 67.5) return "NE";
                                            if (deg > 67.5 && deg <= 112.5) return "E";
                                            if (deg < -22.5 && deg >= -67.5) return "NW";
                                            if (deg < -67.5 && deg >= -112.5) return "W";
                                            if (deg > 112.5 && deg <= 157.5) return "SE";
                                            if (deg < -112.5 && deg >= -157.5) return "SW";
                                            return "S";
                                        })()}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
