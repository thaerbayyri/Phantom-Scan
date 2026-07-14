import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Cpu } from "lucide-react";
import type { NodeFeatureState } from "@shared/schema";

interface NodeFeaturesCardProps {
    nodeFeatures: NodeFeatureState[];
    className?: string;
}

/**
 * Firmware DSP metrics (RuView 0xC5110006 feature-state, 1 Hz per node).
 * Board-computed presence/motion/vitals shown verbatim for cross-checking
 * against the host-DSP estimates — the two pipelines are independent.
 * With current firmware the resp/heart confidences are real autocorrelation
 * peak ratios computed on the board (0 = no periodic signal, 1 = strong);
 * legacy 0xC5110002 firmware reports a fixed 100% for any estimate.
 */
export function NodeFeaturesCard({ nodeFeatures, className = "" }: NodeFeaturesCardProps) {
    return (
        <Card className={`min-w-0 ${className}`}>
            <CardHeader className="flex flex-row flex-wrap items-center gap-2 px-5 pb-3 pt-5">
                <Cpu className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Board DSP</CardTitle>
                <span className="ml-auto text-[10px] font-mono uppercase tracking-tight text-muted-foreground">
                    firmware feature-state
                </span>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 px-5 pb-5 pt-1">
                {nodeFeatures.length === 0 ? (
                    <div className="text-xs font-mono text-muted-foreground">
                        no board DSP packets (boards silent, or firmware sending neither 0xC5110002 vitals nor 0xC5110006 feature-state)
                    </div>
                ) : (
                    nodeFeatures.map((nf) => (
                        <div
                            key={nf.node_id}
                            className="rounded-md border border-white/5 bg-muted/30 px-3 py-2 font-mono text-xs"
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-bold text-primary">N{nf.node_id}</span>
                                <span className="text-[10px] text-muted-foreground">
                                    {(nf.age_ms / 1000).toFixed(1)}s ago
                                </span>
                            </div>
                            <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                                <span>
                                    presence <span className="text-foreground">{nf.presence.toFixed(2)}</span>
                                </span>
                                <span>
                                    motion <span className="text-foreground">{nf.motion.toFixed(2)}</span>
                                </span>
                                <span>
                                    resp{" "}
                                    <span className="text-foreground">
                                        {nf.resp_bpm.toFixed(0)} bpm
                                    </span>{" "}
                                    <span className="text-[10px]">({(nf.resp_conf * 100).toFixed(0)}%)</span>
                                </span>
                                <span>
                                    heart{" "}
                                    <span className="text-foreground">
                                        {nf.hr_bpm.toFixed(0)} bpm
                                    </span>{" "}
                                    <span className="text-[10px]">({(nf.hr_conf * 100).toFixed(0)}%)</span>
                                </span>
                                {nf.rssi !== undefined && (
                                    <span>
                                        rssi <span className="text-foreground">{nf.rssi} dBm</span>
                                    </span>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </CardContent>
        </Card>
    );
}
