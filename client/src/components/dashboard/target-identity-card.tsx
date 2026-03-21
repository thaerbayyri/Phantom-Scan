import type { TargetIdentity } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { User, Cog } from "lucide-react";

interface TargetIdentityCardProps {
    identity: TargetIdentity | null;
    bearingRad?: number;
    className?: string;
}

export function TargetIdentityCard({ identity, bearingRad, className = "" }: TargetIdentityCardProps) {
    const label = identity?.label ?? "unknown";
    const humanProb = identity?.humanProb ?? 0.5;
    const mechProb = identity?.mechanicalProb ?? 0.5;

    const isHuman = label === "human";
    const isMech = label === "mechanical";

    const getCardinal = (rad: number) => {
        const deg = (rad * 180) / Math.PI;
        if (deg >= -22.5 && deg <= 22.5) return "N";
        if (deg > 22.5 && deg <= 67.5) return "NE";
        if (deg > 67.5 && deg <= 112.5) return "E";
        if (deg < -22.5 && deg >= -67.5) return "NW";
        if (deg < -67.5 && deg >= -112.5) return "W";
        if (deg > 112.5 && deg <= 157.5) return "SE";
        if (deg < -112.5 && deg >= -157.5) return "SW";
        return "S";
    };

    return (
        <Card className={`${className}`}>
            <CardHeader className="flex flex-row items-center gap-2 pb-2">
                {isHuman ? (
                    <User className="h-4 w-4 text-cyan-400" />
                ) : isMech ? (
                    <Cog className="h-4 w-4 text-amber-400" />
                ) : (
                    <User className="h-4 w-4 text-muted-foreground" />
                )}
                <CardTitle className="text-sm">Target Identity</CardTitle>
                <div className="ml-auto flex items-center gap-2">
                    {bearingRad !== undefined && (
                        <span className="text-xs font-mono bg-primary/20 text-primary px-2 py-0.5 rounded border border-primary/30 animate-pulse">
                            BEARING: {getCardinal(bearingRad)}
                        </span>
                    )}
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isHuman ? "bg-cyan-900/50 text-cyan-300" :
                            isMech ? "bg-amber-900/50 text-amber-300" :
                                "bg-muted text-muted-foreground"
                        }`}>
                        {label.toUpperCase()}
                    </span>
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
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
            </CardContent>
        </Card>
    );
}
