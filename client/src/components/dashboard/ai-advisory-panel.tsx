import type { TargetIdentity, VitalSigns } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sparkles } from "lucide-react";

interface AIAdvisoryPanelProps {
    identity: TargetIdentity | null;
    vitals: VitalSigns | null;
}

/**
 * AI sidecar advisory readout (PS-REMED-WP3-FOLLOWUP-01). Renders model-
 * derived identity/vitals that the server relays ONLY from isAI-registered
 * clients (server/lib/websocket.ts advisoryIdentity/advisoryVitalSigns).
 * Visually distinct from TargetIdentityCard/VitalsMonitor (dashed border,
 * amber/purple accent, permanent non-authoritative badge) so this can never
 * be mistaken for the deterministic verdict. Renders nothing when no AI
 * sidecar is connected, so a dashboard without one sees zero UI change.
 */
export function AIAdvisoryPanel({ identity, vitals }: AIAdvisoryPanelProps) {
    if (!identity && !vitals) {
        return null;
    }

    const label = identity?.label ?? "unknown";
    const humanProb = identity?.humanProb ?? 0.5;
    const mechProb = identity?.mechanicalProb ?? 0.5;

    return (
        <Card className="min-w-0 border-dashed border-purple-400/40 bg-purple-950/10">
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                <Sparkles className="h-4 w-4 text-purple-400" />
                <CardTitle className="min-w-0 text-base">AI Advisory</CardTitle>
                <span className="ml-auto rounded-full bg-purple-900/50 px-2 py-0.5 text-xs font-bold uppercase tracking-[0.1em] text-purple-300">
                    Non-Authoritative
                </span>
            </CardHeader>
            <CardContent className="space-y-3 px-5 pb-5">
                {identity && (
                    <div className="relative h-6 overflow-hidden rounded-full bg-muted/50 opacity-90">
                        <div
                            className="absolute left-0 top-0 h-full bg-gradient-to-r from-purple-600 to-purple-400 transition-all duration-500 ease-out"
                            style={{ width: `${humanProb * 100}%` }}
                        />
                        <div
                            className="absolute right-0 top-0 h-full bg-gradient-to-l from-amber-600 to-amber-400 transition-all duration-500 ease-out"
                            style={{ width: `${mechProb * 100}%` }}
                        />
                        <div className="absolute inset-0 flex items-center justify-between px-2 text-[10px] font-mono text-white">
                            <span>HUMAN {(humanProb * 100).toFixed(0)}%</span>
                            <span>MECH {(mechProb * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                )}
                {identity && (
                    <div className="text-[10px] font-mono uppercase text-purple-300/80">
                        Model label: {label}
                    </div>
                )}
                {vitals && (
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-muted-foreground">
                        <div>HR: {vitals.heartRateBpm > 0 ? vitals.heartRateBpm : "--"} bpm</div>
                        <div className="text-right">
                            RR: {vitals.respirationRateRpm > 0 ? vitals.respirationRateRpm : "--"} rpm
                        </div>
                    </div>
                )}
                <div className="border-t border-purple-400/15 pt-2 text-[9px] leading-relaxed text-purple-200/70">
                    Model-derived output from the AI sidecar. Never gates or overrides the
                    deterministic verdict shown in Target Identity above.
                </div>
            </CardContent>
        </Card>
    );
}
