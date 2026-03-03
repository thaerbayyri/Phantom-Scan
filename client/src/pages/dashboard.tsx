import { useEffect, useCallback } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { TopBar } from "@/components/dashboard/top-bar";
import { ControlPanel } from "@/components/dashboard/control-panel";
import { PointCloud3D } from "@/components/dashboard/point-cloud-3d";
import { AoAHeatmap } from "@/components/dashboard/aoa-heatmap";
import { AoASpectrum } from "@/components/dashboard/aoa-spectrum";
import { DopplerSpectrogram } from "../components/dashboard/doppler-spectrogram";
import { GestureLog } from "@/components/dashboard/gesture-log";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import { TargetIdentityCard } from "@/components/dashboard/target-identity-card";
import { DistanceMeter } from "@/components/dashboard/distance-meter";
import { ResizableWrapper } from "@/components/ui/resizable-wrapper";
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
    dopplerFrame,
    motionStatus,
    recordingStatus,
    isConnected,
    updateConfig,
    startProcessing,
    stopProcessing,
    setDataSource,
    startRecording,
    stopRecording,
    trackedTarget,
    radialTarget,
    targetIdentity,
  } = useWebSocket();

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
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
        motionStatus={motionStatus}
        recordingStatus={recordingStatus}
        onStart={startProcessing}
        onStop={stopProcessing}
        onDataSourceChange={handleDataSourceChange}
        onStartRecording={startRecording}
        onStopRecording={stopRecording}
      />

      <div className="flex flex-1 overflow-hidden">
        <ControlPanel config={config} onConfigChange={updateConfig} />

        <main className="flex-1 p-4 overflow-auto">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-4">
            {/* Left column — 3D Scene + Spectrum */}
            <div className="flex flex-col gap-4">
              <PointCloud3D points={pointCloud} radialTarget={radialTarget} className="flex-1 min-h-[320px] resizable-card" />
              <AoASpectrum frame={isarFrame} className="h-36 resizable-v" />
            </div>

            {/* Right column — Identity, Distance, Heatmap, Doppler, Gesture */}
            <div className="flex flex-col gap-3">
              {/* Target Identity + Distance Meter — top priority */}
              <div className="grid grid-cols-2 gap-3">
                <TargetIdentityCard identity={targetIdentity ?? null} />
                <DistanceMeter
                  distanceCm={radialTarget?.distanceCm ?? 200}
                  wallDistance={radialTarget?.wallDistance ?? 5.0}
                />
              </div>
              <MetricsPanel
                channelEstimate={channelEstimate}
                isarFrame={isarFrame}
              />
              <ResizableWrapper defaultHeight={200} minHeight={100} maxHeight={500}>
                <AoAHeatmap data={heatmap} className="h-full" />
              </ResizableWrapper>
              <ResizableWrapper defaultHeight={180} minHeight={100} maxHeight={500}>
                <DopplerSpectrogram frame={dopplerFrame} className="h-full" />
              </ResizableWrapper>
              <GestureLog gestures={gestures} className="h-28 resizable-v" />
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
