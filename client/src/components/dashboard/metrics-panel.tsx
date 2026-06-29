import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Target, Gauge, Zap } from "lucide-react";
import type { ChannelEstimate, ISARFrame } from "@shared/schema";

interface MetricsPanelProps {
  channelEstimate: ChannelEstimate | null;
  isarFrame: ISARFrame | null;
  className?: string;
}

function MetricCard({
  icon: Icon,
  label,
  value,
  unit,
  color,
  testId,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  unit: string;
  color: string;
  testId: string;
}) {
  return (
    <Card className="min-w-0">
      <CardContent className="p-3.5">
        <div className="flex items-center gap-2">
          <div className={`rounded-md p-2 ${color}`}>
            <Icon className="h-3.5 w-3.5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="truncate text-xs text-muted-foreground">{label}</div>
            <div className="flex min-w-0 items-baseline gap-1">
              <span
                className="truncate text-lg font-mono font-semibold"
                data-testid={testId}
              >
                {value}
              </span>
              <span className="text-xs text-muted-foreground">{unit}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function MetricsPanel({
  channelEstimate,
  isarFrame,
  className = "",
}: MetricsPanelProps) {
  const h1Mag = channelEstimate
    ? Math.sqrt(
        channelEstimate.h1.re ** 2 + channelEstimate.h1.im ** 2
      ).toFixed(3)
    : "0.000";

  const h2Mag = channelEstimate
    ? Math.sqrt(
        channelEstimate.h2.re ** 2 + channelEstimate.h2.im ** 2
      ).toFixed(3)
    : "0.000";

  const pRatio = channelEstimate
    ? Math.sqrt(
        channelEstimate.precodingRatio.re ** 2 +
          channelEstimate.precodingRatio.im ** 2
      ).toFixed(3)
    : "0.000";

  const peakAngle = isarFrame ? isarFrame.peakAngle.toFixed(1) : "0.0";

  return (
    <div className={`grid grid-cols-2 gap-2.5 ${className}`}>
      <MetricCard
        icon={Activity}
        label="h1 Magnitude"
        value={h1Mag}
        unit=""
        color="bg-chart-1/20 text-chart-1"
        testId="metric-h1-magnitude"
      />
      <MetricCard
        icon={Gauge}
        label="h2 Magnitude"
        value={h2Mag}
        unit=""
        color="bg-chart-2/20 text-chart-2"
        testId="metric-h2-magnitude"
      />
      <MetricCard
        icon={Zap}
        label="Precoding |p|"
        value={pRatio}
        unit=""
        color="bg-chart-3/20 text-chart-3"
        testId="metric-precoding-ratio"
      />
      <MetricCard
        icon={Target}
        label="Peak AoA"
        value={peakAngle}
        unit="°"
        color="bg-chart-4/20 text-chart-4"
        testId="metric-peak-aoa"
      />
    </div>
  );
}
