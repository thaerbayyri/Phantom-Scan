import type { DemoStatus } from "@shared/schema";
import { describeDemoBanner } from "@/lib/demo-banner";
import { cn } from "@/lib/utils";

interface DemoBannerProps {
    demoStatus: DemoStatus | null;
}

const TONE_CLASSES = {
    simulated: "border-amber-400/40 bg-amber-500/15 text-amber-200",
    replay: "border-sky-400/40 bg-sky-500/15 text-sky-200",
    error: "border-red-400/40 bg-red-500/15 text-red-200",
} as const;

/**
 * Permanent banner while a demo runs (or after one failed to start). A demo
 * is never a live measurement, so this says exactly what is being shown.
 */
export function DemoBanner({ demoStatus }: DemoBannerProps) {
    const banner = describeDemoBanner(demoStatus);
    if (!banner) {
        return null;
    }

    return (
        <div
            role="status"
            data-testid="demo-banner"
            className={cn(
                "flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-1.5 text-xs",
                TONE_CLASSES[banner.tone],
            )}
        >
            <span className="font-bold tracking-wide">{banner.headline}</span>
            <span className="opacity-90">{banner.detail}</span>
        </div>
    );
}
