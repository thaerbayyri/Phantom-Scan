import { useEffect, useCallback } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { TopBar } from "@/components/dashboard/top-bar";
import { ControlPanel } from "@/components/dashboard/control-panel";
import { PointCloud3D } from "@/components/dashboard/point-cloud-3d";
import { AoAHeatmap } from "@/components/dashboard/aoa-heatmap";
import { AoASpectrum } from "@/components/dashboard/aoa-spectrum";
import { SignalTraces } from "@/components/dashboard/signal-traces";
import { GestureLog } from "@/components/dashboard/gesture-log";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import type { DataSource } from "@shared/schema";

export default function Dashboard() {
  const {
    status,
    channelEstimate,
    isarFrame,
    pointCloud,
    gestures,
    heatmap,
    config,
    signalTrace,
    isConnected,
    updateConfig,
    startProcessing,
    stopProcessing,
    setDataSource,
  } = useWebSocket();

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case " ":
          e.preventDefault();
          if (status.isProcessing) {
            stopProcessing();
          } else {
            startProcessing();
          }
          break;
        case "r":
          if (!e.ctrlKey && !e.metaKey) {
            window.location.reload();
          }
          break;
      }
    },
    [status.isProcessing, startProcessing, stopProcessing]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleDataSourceChange = useCallback(
    (source: DataSource) => {
      setDataSource(source);
    },
    [setDataSource]
  );

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar
        status={status}
        isConnected={isConnected}
        onStart={startProcessing}
        onStop={stopProcessing}
        onDataSourceChange={handleDataSourceChange}
      />

      <div className="flex flex-1 overflow-hidden">
        <ControlPanel config={config} onConfigChange={updateConfig} />

        <main className="flex-1 p-4 overflow-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
            <div className="flex flex-col gap-4 min-h-[600px]">
              <PointCloud3D points={pointCloud} className="flex-1 min-h-[300px]" />
              <AoASpectrum frame={isarFrame} className="h-48" />
            </div>

            <div className="flex flex-col gap-4 min-h-[600px]">
              <MetricsPanel
                channelEstimate={channelEstimate}
                isarFrame={isarFrame}
              />
              <AoAHeatmap data={heatmap} className="flex-1 min-h-[200px]" />
              <SignalTraces trace={signalTrace} className="h-48" />
              <GestureLog gestures={gestures} className="h-48" />
            </div>
          </div>
        </main>
      </div>

      <footer className="h-8 border-t bg-card flex items-center justify-center px-4">
        <div className="text-xs text-muted-foreground">
          Press <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">Space</kbd> to start/stop
          {" | "}
          <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">R</kbd> to reset
        </div>
      </footer>
    </div>
  );
}
