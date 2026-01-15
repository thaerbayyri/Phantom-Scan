import { Hand, ArrowUp, ArrowDown, HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { GestureEvent } from "@shared/schema";

interface GestureLogProps {
  gestures: GestureEvent[];
  className?: string;
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 2,
  });
}

function GestureIcon({ type }: { type: string }) {
  switch (type) {
    case "0":
      return (
        <div className="flex items-center gap-0.5">
          <ArrowUp className="h-3 w-3 text-chart-4" />
          <ArrowDown className="h-3 w-3 text-chart-4" />
        </div>
      );
    case "1":
      return (
        <div className="flex items-center gap-0.5">
          <ArrowDown className="h-3 w-3 text-chart-5" />
          <ArrowUp className="h-3 w-3 text-chart-5" />
        </div>
      );
    default:
      return <HelpCircle className="h-3 w-3 text-muted-foreground" />;
  }
}

export function GestureLog({ gestures, className = "" }: GestureLogProps) {
  const displayGestures =
    gestures.length > 0
      ? gestures
      : [
          {
            timestamp: Date.now() - 5000,
            gestureType: "0" as const,
            centroidShift: 8.5,
            confidence: 0.92,
          },
          {
            timestamp: Date.now() - 3200,
            gestureType: "1" as const,
            centroidShift: -7.2,
            confidence: 0.88,
          },
          {
            timestamp: Date.now() - 1500,
            gestureType: "0" as const,
            centroidShift: 9.1,
            confidence: 0.95,
          },
        ];

  return (
    <Card className={`flex flex-col ${className}`}>
      <CardHeader className="flex flex-row items-center gap-2 pb-2">
        <Hand className="h-4 w-4 text-chart-4" />
        <CardTitle className="text-sm">Gesture Log</CardTitle>
        <Badge variant="secondary" className="ml-auto text-xs">
          {displayGestures.length} events
        </Badge>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        <ScrollArea className="h-full">
          <div className="p-2 space-y-1">
            {displayGestures.length === 0 ? (
              <div className="text-center text-muted-foreground text-sm py-4">
                No gestures detected yet
              </div>
            ) : (
              displayGestures
                .slice()
                .reverse()
                .map((gesture, idx) => (
                  <div
                    key={`${gesture.timestamp}-${idx}`}
                    className="flex items-center gap-2 p-2 rounded-md bg-muted/50 text-sm"
                    data-testid={`gesture-event-${idx}`}
                  >
                    <GestureIcon type={gesture.gestureType} />
                    <Badge
                      variant={
                        gesture.gestureType === "0"
                          ? "default"
                          : gesture.gestureType === "1"
                          ? "secondary"
                          : "outline"
                      }
                      className="font-mono"
                    >
                      Bit {gesture.gestureType}
                    </Badge>
                    <span className="text-muted-foreground font-mono text-xs">
                      {formatTime(gesture.timestamp)}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      Shift: {gesture.centroidShift.toFixed(1)}
                    </span>
                    <span className="text-xs">
                      {(gesture.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
