import type { RadialTarget, SensorNode, TargetIdentity, TargetState } from "@shared/schema";
import type { TargetPresentationCaveat } from "@shared/target-presentation";
import { summarizeTargetSpatial } from "@shared/target-spatial";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { User, Cog } from "lucide-react";

interface TargetIdentityCardProps {
    identity: TargetIdentity | null;
    targetState?: TargetState | null;
    radialTarget?: RadialTarget | null;
    nodes?: SensorNode[];
    presentationCaveat?: TargetPresentationCaveat | null;
    className?: string;
}

export function TargetIdentityCard({
    identity,
    targetState,
    radialTarget,
    nodes = [],
    presentationCaveat,
    className = "",
}: TargetIdentityCardProps) {
    const label = identity?.label ?? "unknown";
    const humanProb = identity?.humanProb ?? 0.5;
    const mechProb = identity?.mechanicalProb ?? 0.5;
    const renderState = targetState?.state ?? "none";
    const spatialSummary = summarizeTargetSpatial(radialTarget, nodes, targetState);

    const isHuman = label === "human";
    const isMech = label === "mechanical";

    return (
        <Card className={`min-w-0 ${className}`}>
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                {isHuman ? (
                    <User className="h-4 w-4 text-cyan-400" />
                ) : isMech ? (
                    <Cog className="h-4 w-4 text-amber-400" />
                ) : (
                    <User className="h-4 w-4 text-muted-foreground" />
                )}
                <CardTitle className="min-w-0 text-base">Target Identity</CardTitle>
                <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2">
                    <span className="text-xs font-mono text-muted-foreground uppercase">
                        {renderState}
                    </span>
                    {spatialSummary?.nearestNodeId !== null && spatialSummary?.nearestNodeId !== undefined && (
                        <span className="text-xs font-mono rounded border border-cyan-400/20 bg-cyan-500/10 px-2 py-0.5 text-cyan-200">
                            N{spatialSummary.nearestNodeId} NEAREST
                        </span>
                    )}
                    <span className={`max-w-full truncate text-xs font-bold px-2 py-0.5 rounded-full ${isHuman ? "bg-cyan-900/50 text-cyan-300" :
                            isMech ? "bg-amber-900/50 text-amber-300" :
                                "bg-muted text-muted-foreground"
                        }`}>
                        {label.toUpperCase()}
                    </span>
                </div>
            </CardHeader>
            <CardContent className="space-y-3 px-5 pb-5">
                {/* Probability bar */}
                <div className="relative h-6 rounded-full overflow-hidden bg-muted/50">
                    {/* Human portion (left, cyan) */}
                    <div
                        className="absolute left-0 top-0 h-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all duration-500 ease-out"
                        style={{ width: `${humanProb * 100}%` }}
                    />
                    {/* Mechanical portion (right, amber) */}
                    <div
                        className="absolute right-0 top-0 h-full bg-gradient-to-l from-amber-600 to-amber-400 transition-all duration-500 ease-out"
                        style={{ width: `${mechProb * 100}%` }}
                    />
                    {/* Labels */}
                    <div className="absolute inset-0 flex items-center justify-between px-2 text-[10px] font-mono text-white">
                        <span>HUMAN {(humanProb * 100).toFixed(0)}%</span>
                        <span>MECH {(mechProb * 100).toFixed(0)}%</span>
                    </div>
                </div>

                {/* Feature indicators */}
                {identity && (
                    <div className="grid grid-cols-2 gap-2 text-[10px] text-muted-foreground font-mono">
                        <div>
                            Periodicity: {identity.periodicity !== undefined ? identity.periodicity.toFixed(3) : "—"}
                        </div>
                        <div className="text-right">
                            HF Ratio: {identity.highFreqRatio !== undefined ? identity.highFreqRatio.toFixed(3) : "—"}
                        </div>
                    </div>
                )}
                {spatialSummary && (
                    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-3 py-2 text-[10px] font-mono text-cyan-100">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="uppercase tracking-[0.16em] text-cyan-300/80">{spatialSummary.zoneLabel}</div>
                            <div className="text-[9px] text-slate-400 uppercase">{spatialSummary.presentationMode === "fused_axis" ? "fused axis" : "single node"}</div>
                        </div>
                        <div className="mt-1 text-cyan-100">{spatialSummary.motionLabel}</div>
                        <div className="mt-1 text-slate-300">{spatialSummary.detailLabel}</div>
                        {spatialSummary.projectionLabel && (
                            <div className="mt-1 text-[9px] text-slate-400">{spatialSummary.projectionLabel}</div>
                        )}
                        {presentationCaveat && (
                            <div className="mt-2 border-t border-cyan-400/15 pt-2 text-[9px] leading-relaxed text-amber-100/90">
                                <div className="font-semibold tracking-[0.16em] text-amber-300">{presentationCaveat.primary}</div>
                                <div className="mt-1 text-slate-300">{presentationCaveat.secondary}</div>
                            </div>
                        )}
                    </div>
                )}
                {!identity && (
                    <div className="text-[10px] text-muted-foreground font-mono uppercase">
                        {targetState?.source_mode === "live" && targetState?.state === "none"
                            ? "Empty room / no live target"
                            : "No truthful classification available"}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
