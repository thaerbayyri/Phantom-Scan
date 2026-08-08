import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Ruler } from "lucide-react";
import type { TargetState } from "@shared/schema";
import type { TargetPresentationCaveat } from "@shared/target-presentation";
import { bearingToCardinal } from "@shared/bearing";

interface DistanceMeterProps {
    distanceCm: number;
    wallDistance: number;
    bearingRad?: number;
    targetState?: TargetState | null;
    hasLivePosition?: boolean;
    presentationCaveat?: TargetPresentationCaveat | null;
    className?: string;
}

/**
 * Range readout: SVG half-circle gauge of the target distance (green far →
 * red close over an 8 m range), a wall-reflection tick, and the compass
 * bearing (cardinal) of the target. Blanked whenever hasLivePosition is
 * false so a cleared target can't keep showing a distance.
 */
export function DistanceMeter({
    distanceCm,
    wallDistance,
    bearingRad,
    targetState,
    hasLivePosition = false,
    presentationCaveat,
    className = "",
}: DistanceMeterProps) {
    const distanceM = distanceCm / 100;
    const maxRange = 8; // meters
    const hasTruthfulDistance = hasLivePosition;
    // Fused mode's node anchors both sit at z=0 (shared/schema.ts
    // NODE_ANCHORS), so radialTarget.theta collapses to due-east/due-west
    // only — not a real compass bearing. Label it honestly as which side of
    // the baseline the target is on, matching the caveat text below.
    const isFusedAxisOnly = targetState?.node_mode === "fused_two_node";
    const bearingLabel = isFusedAxisOnly ? "Axis Side" : "Bearing";

    // Color gradient: green (far) → orange (mid) → red (close)
    const ratio = Math.min(1, distanceM / maxRange);
    const hue = ratio * 120; // 0=red, 60=yellow, 120=green
    const gaugeColor = `hsl(${hue}, 85%, 50%)`;

    // Arc angle (180° full)
    const arcAngle = Math.min(180, (distanceM / maxRange) * 180);

    // Wall distance indicator
    const wallRatio = Math.min(1, wallDistance / maxRange);

    return (
        <Card className={`min-w-0 ${className}`}>
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                <Ruler className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Distance Meter</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-2 px-5 pb-5 pt-1">
                {/* SVG Radial Gauge */}
                <svg viewBox="0 0 200 120" className="w-full max-w-[185px]">
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
                        style={{ fontSize: "26px", fontWeight: 700, fontFamily: "monospace" }}
                    >
                        {hasTruthfulDistance ? distanceCm.toFixed(0) : "--"}
                    </text>
                    <text
                        x="100"
                        y="102"
                        textAnchor="middle"
                        className="fill-muted-foreground"
                        style={{ fontSize: "11px", fontFamily: "monospace" }}
                    >
                        cm
                    </text>

                    {/* Range labels */}
                    <text x="18" y="115" className="fill-muted-foreground" style={{ fontSize: "9px" }}>0</text>
                    <text x="168" y="115" className="fill-muted-foreground" style={{ fontSize: "9px" }}>{maxRange}m</text>
                </svg>

                {/* Distance in meters subtitle */}
                <div className="flex items-center justify-center gap-2 text-xs font-mono text-muted-foreground">
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2 py-1 rounded-md border border-white/5">
                        <span className="text-primary/60">{hasTruthfulDistance ? `${distanceM.toFixed(2)}m` : "--"}</span>
                        {!hasTruthfulDistance && (
                            <span className="text-muted-foreground">
                                {targetState?.source_mode === "live" && targetState?.state === "none"
                                    ? "EMPTY ROOM"
                                    : "NO TARGET"}
                            </span>
                        )}
                        {bearingRad !== undefined && (
                            <>
                                <span className="text-white/20">|</span>
                                <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-tighter">{bearingLabel}</span>
                                    <span className="font-black text-primary text-sm animate-pulse-slow">
                                        {bearingToCardinal(bearingRad)}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {hasTruthfulDistance && presentationCaveat && (
                    <div className="w-full max-w-[220px] border-t border-white/10 pt-2 text-center text-[9px] leading-relaxed text-amber-100/80">
                        <div className="font-semibold tracking-[0.14em] text-amber-300">{presentationCaveat.primary}</div>
                        <div className="mt-0.5 text-slate-400">{presentationCaveat.secondary}</div>
                    </div>
                )}

            </CardContent>
        </Card>
    );
}
