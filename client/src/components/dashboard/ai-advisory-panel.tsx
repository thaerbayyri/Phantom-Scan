import type { AdvisoryIdentity, AdvisoryVitalSigns } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Sparkles, Gauge } from "lucide-react";

interface AIAdvisoryPanelProps {
    identity: AdvisoryIdentity | null;
    vitals: AdvisoryVitalSigns | null;
    /** Resets the AI sidecar's activity-state motion baseline (walking/
     * rapid_change heuristic only) — no model weight is touched. Omit to
     * hide the "Calibrate Empty Room" control entirely. */
    onCalibrate?: () => void;
    /** Wall-clock ms of the last calibration ack, or null if none yet. */
    lastCalibratedAt?: number | null;
}

function percent(value: number): string {
    return `${Math.round(value * 100)}%`;
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
export function AIAdvisoryPanel({ identity, vitals, onCalibrate, lastCalibratedAt }: AIAdvisoryPanelProps) {
    if (!identity && !vitals) {
        return null;
    }

    const advisoryLabel = identity?.advisoryLabel ?? "unknown";
    const calibratedSecondsAgo = lastCalibratedAt ? Math.max(0, Math.round((Date.now() - lastCalibratedAt) / 1000)) : null;
    const humanProb = identity?.humanProb ?? 0.5;
    const mechProb = identity?.mechanicalProb ?? 0.5;
    const heuristicActivity = identity?.activityState;
    const modelActivity = identity?.advisoryActivity;
    const hasRoomModel = Boolean(identity?.modelId || identity?.countModelId);
    const presenceProb = identity?.presenceProb;
    const count = identity?.advisoryCount;
    const vitalsShown = vitals?.vitalsReliable === true;

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
                    <div className="space-y-1 text-[10px] font-mono uppercase text-purple-300/80">
                        <div>Advisory label: {advisoryLabel}</div>
                        <div title="Presence head output. Uncalibrated unless a per-room presence model is loaded.">
                            Presence: {presenceProb == null ? "n/a" : percent(presenceProb)}
                            {presenceProb != null && identity.presenceCalibrated === false ? " (uncalibrated)" : ""}
                        </div>
                    </div>
                )}
                {identity && hasRoomModel && (
                    <div
                        className="space-y-1 text-[10px] font-mono uppercase text-purple-300/80"
                        title={`Per-room model ${identity.modelId} trained on labelled recordings of room ${identity.roomId ?? "?"}. Not valid in other rooms.`}
                    >
                        {modelActivity && (
                            <div>
                                Activity (room model): {modelActivity}
                                {identity.advisoryActivityConfidence != null && ` · ${percent(identity.advisoryActivityConfidence)}`}
                            </div>
                        )}
                        {count != null && (
                            <div className={identity.countLowConfidence ? "text-amber-300" : undefined}>
                                People (room model): {count}{identity.countIsLowerBound ? "+" : ""}
                                {identity.advisoryCountConfidence != null && ` · ${percent(identity.advisoryCountConfidence)}`}
                                {identity.countLowConfidence ? " · low confidence" : ""}
                            </div>
                        )}
                    </div>
                )}
                {identity?.embeddingDrift != null && (
                    <div
                        className="text-[10px] font-mono uppercase text-purple-300/80"
                        title={`RuView ${identity.embeddingModelId ?? "csi-embed-v2"} embedding distance from the empty-room reference (0 = same, 2 = opposite). It means the signal environment changed, not that someone is present; a moved door or router also raises it.`}
                    >
                        Environment change vs empty room: {identity.embeddingDrift.toFixed(3)}
                        {identity.embeddingRefAgeS != null && ` · ref ${Math.round(identity.embeddingRefAgeS)}s old`}
                    </div>
                )}
                {identity && !hasRoomModel && (
                    <div className="text-[10px] font-mono uppercase text-purple-300/50">
                        No model trained for this room
                    </div>
                )}
                {heuristicActivity && heuristicActivity !== "unknown" && (
                    <div
                        className={`text-[10px] font-mono uppercase ${
                            heuristicActivity === "rapid_change" ? "text-amber-300" : "text-purple-300/80"
                        }`}
                        title="Motion-energy heuristic only — not derived from pose or body shape."
                    >
                        Motion heuristic: {heuristicActivity === "rapid_change" ? "abrupt signal change" : heuristicActivity}
                    </div>
                )}
                {vitals && (
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-muted-foreground">
                        <div>HR: {vitalsShown && vitals.heartRateBpm != null ? vitals.heartRateBpm.toFixed(0) : "--"} bpm</div>
                        <div className="text-right">
                            RR: {vitalsShown && vitals.respirationRateRpm != null ? vitals.respirationRateRpm.toFixed(0) : "--"} rpm
                        </div>
                        {!vitalsShown && (
                            <div className="col-span-2 text-[9px] text-purple-300/50">Vitals unreliable — not shown</div>
                        )}
                    </div>
                )}
                <div className="border-t border-purple-400/15 pt-2 text-[9px] leading-relaxed text-purple-200/70">
                    Model-derived output from the AI sidecar. Never gates or overrides the
                    deterministic verdict shown in Target Identity above.
                </div>
                {onCalibrate && (
                    <div className="flex items-center justify-between gap-2 border-t border-purple-400/15 pt-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onCalibrate}
                            className="h-7 gap-1.5 border-purple-400/30 text-[10px]"
                            title="Stand in an empty room, then click this to reset the sidecar's activity-state motion baseline to current ambient noise. Does not retrain any model weight."
                            data-testid="btn-calibrate-empty-room"
                        >
                            <Gauge className="h-3 w-3" />
                            Calibrate Empty Room
                        </Button>
                        {calibratedSecondsAgo !== null && (
                            <span className="text-[9px] text-purple-300/60">
                                calibrated {calibratedSecondsAgo}s ago
                            </span>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
