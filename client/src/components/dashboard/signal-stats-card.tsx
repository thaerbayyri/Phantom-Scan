import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Waves } from "lucide-react";
import type { NodeSignalState } from "@shared/schema";

interface SignalStatsCardProps {
    nodeSignal: NodeSignalState[];
    className?: string;
}

/**
 * Live per-node CSI signal readout: amplitude and phase of the max-power
 * subcarrier from the most recent frame per node. A diagnostic value, not a
 * spatial measurement — phase here carries no angle-of-arrival meaning on
 * this single-antenna hardware (same honesty caveat as the Signal Signature
 * panel).
 */
export function SignalStatsCard({ nodeSignal, className = "" }: SignalStatsCardProps) {
    return (
        <Card className={`min-w-0 ${className}`}>
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                <Waves className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Signal Stats</CardTitle>
                <span className="ml-auto text-[10px] font-mono uppercase tracking-tight text-muted-foreground">
                    amplitude / phase per node
                </span>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 px-5 pb-5 pt-1">
                {nodeSignal.length === 0 ? (
                    <div className="text-xs font-mono text-muted-foreground">
                        no live CSI signal (nodes silent)
                    </div>
                ) : (
                    nodeSignal.map((ns) => (
                        <div
                            key={ns.node_id}
                            className="rounded-md border border-white/5 bg-muted/30 px-3 py-2 font-mono text-xs"
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-bold text-primary">N{ns.node_id}</span>
                                <span className="text-[10px] text-muted-foreground">
                                    {typeof ns.age_ms === "number" ? `${(ns.age_ms / 1000).toFixed(1)}s ago` : "—"}
                                </span>
                            </div>
                            <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                                <span>
                                    amplitude{" "}
                                    <span className="text-foreground">
                                        {typeof ns.amplitude === "number" ? ns.amplitude.toFixed(2) : "—"}
                                    </span>
                                </span>
                                <span>
                                    phase{" "}
                                    <span className="text-foreground">
                                        {typeof ns.phase_deg === "number" ? `${ns.phase_deg.toFixed(1)}°` : "—"}
                                    </span>
                                </span>
                            </div>
                        </div>
                    ))
                )}
            </CardContent>
        </Card>
    );
}
