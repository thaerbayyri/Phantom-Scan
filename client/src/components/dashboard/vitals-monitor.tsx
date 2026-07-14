import { Activity, Wind } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { TargetState, VitalSigns } from "@shared/schema";
import { cn } from "@/lib/utils";

interface VitalsMonitorProps {
    vitals: VitalSigns | null;
    targetState?: TargetState | null;
}

/**
 * Heart-rate / respiration readout from the CSI-phase vitals pipeline.
 * Gated on `target_visible`: shows "NO TARGET" unless the presence state
 * machine vouches for a target — vitals reinforce presence even when the
 * person stands perfectly still.
 */
export function VitalsMonitor({ vitals, targetState }: VitalsMonitorProps) {
    // Graceful fallback for missing vitals
    const hr = vitals?.heartRateBpm ?? 0;
    const rr = vitals?.respirationRateRpm ?? 0;
    const reliable = vitals?.vitalsReliable ?? false;
    const targetVisible = Boolean(targetState?.target_visible);

    return (
        <Card className="flex h-full min-w-0 flex-col border-white/10 bg-card/50 backdrop-blur-sm">
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                <Activity className="h-5 w-5 text-rose-500" />
                <CardTitle className="text-base font-medium">Vital Signs</CardTitle>
                {!targetVisible && (
                    <span className="text-xs text-muted-foreground ml-auto bg-muted px-2 py-0.5 rounded">
                        NO TARGET
                    </span>
                )}
                {targetVisible && !reliable && hr === 0 && (
                    <span className="text-xs text-muted-foreground ml-auto bg-muted px-2 py-0.5 rounded">
                        CALIBRATING
                    </span>
                )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4 px-5 pb-5 pt-1">
                {/* Heart Rate Section */}
                <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Activity
                                className={cn(
                                    "h-4 w-4 text-rose-500",
                                    reliable && "animate-pulse"
                                )}
                            />
                            <span className="text-xs font-medium text-muted-foreground">
                                Heart Rate (BPM)
                            </span>
                        </div>
                        <span className={cn("font-mono text-xl", !reliable && "opacity-50")}>
                            {hr > 0 ? hr : "--"}
                        </span>
                    </div>
                    <Progress
                        value={hr > 0 ? (hr / 150) * 100 : 0}
                        className="h-1.5 bg-rose-500/10"
                    // We'd ideally want a standard UI progress bar color override here
                    />
                </div>

                {/* Respiration Section */}
                <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Wind
                                className={cn(
                                    "h-4 w-4 text-cyan-500",
                                    reliable && "animate-pulse"
                                )}
                            />
                            <span className="text-xs font-medium text-muted-foreground">
                                Respiration (RPM)
                            </span>
                        </div>
                        <span className={cn("font-mono text-xl", !reliable && "opacity-50")}>
                            {rr > 0 ? rr : "--"}
                        </span>
                    </div>
                    <Progress
                        value={rr > 0 ? (rr / 40) * 100 : 0}
                        className="h-1.5 bg-cyan-500/10"
                    />
                </div>
            </CardContent>
        </Card>
    );
}
