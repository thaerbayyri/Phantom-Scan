import { useEffect, useCallback, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useWebSocket } from "@/hooks/use-websocket";
import { TopBar } from "@/components/dashboard/top-bar";
import { HardwareConfig } from "@/components/dashboard/hardware-config";
import { SystemControlPanel } from "@/components/dashboard/system-control-panel";
import { VirtualTerminal } from "@/components/dashboard/virtual-terminal";
import { ControlPanel } from "@/components/dashboard/control-panel";
import { PointCloud3D } from "@/components/dashboard/point-cloud-3d";
import { AoAHeatmap } from "@/components/dashboard/aoa-heatmap";
import { AoASpectrum } from "@/components/dashboard/aoa-spectrum";
import { DopplerSpectrogram } from "../components/dashboard/doppler-spectrogram";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import { TargetIdentityCard } from "@/components/dashboard/target-identity-card";
import { DistanceMeter } from "@/components/dashboard/distance-meter";
import { VitalsMonitor } from "@/components/dashboard/vitals-monitor";
import { ResizableWrapper } from "@/components/ui/resizable-wrapper";
import type { DataSource } from "@shared/schema";

export default function Dashboard() {
  const {
    status,
    channelEstimate,
    isarFrame,
    pointCloud,
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
    vitalSigns,
    poseFrame,
  } = useWebSocket();

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHardwareOpen, setIsHardwareOpen] = useState(false);
  const [isSystemControlOpen, setIsSystemControlOpen] = useState(false);
  const [isDiagnosticOpen, setIsDiagnosticOpen] = useState(false);

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
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenHardware={() => setIsHardwareOpen(true)}
        onOpenSystemControl={() => setIsSystemControlOpen(true)}
        onOpenDiagnostic={() => setIsDiagnosticOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden relative">
        {/* Full-screen 3D Background */}
        <div className="absolute inset-0 z-0">
          <PointCloud3D points={pointCloud} radialTarget={radialTarget} poseFrame={poseFrame} />
        </div>

        {/* Floating Widgets Container */}
        {/* pointer-events-none ensures we can click through to the 3D canvas */}
        <main className="flex-1 p-4 z-10 relative pointer-events-none overflow-hidden">
          <div className="flex justify-between h-full gap-4">

            {/* Left Floating Widgets */}
            <div className="flex flex-col gap-4 w-80 pointer-events-auto">
              <AoASpectrum frame={isarFrame} className="h-48 resizable-card bg-card/80 backdrop-blur border-white/10" />
              <MetricsPanel
                channelEstimate={channelEstimate}
                isarFrame={isarFrame}
              />
            </div>

            {/* Right Floating Widgets */}
            <div className="flex flex-col gap-3 w-96 pointer-events-auto drop-shadow-xl h-full overflow-y-auto pr-2 pb-4 scrollbar-hidden">
              <TargetIdentityCard 
                identity={targetIdentity ?? null} 
                bearingRad={radialTarget?.theta}
              />
              <div className="grid grid-cols-2 gap-3">
                <DistanceMeter
                  distanceCm={radialTarget?.distanceCm ?? 200}
                  wallDistance={radialTarget?.wallDistance ?? 5.0}
                  bearingRad={radialTarget?.theta}
                />
                <VitalsMonitor vitals={vitalSigns} />
              </div>

              <ResizableWrapper defaultHeight={150} minHeight={100} maxHeight={300}>
                <AoAHeatmap data={heatmap} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
              <ResizableWrapper defaultHeight={150} minHeight={100} maxHeight={300}>
                <DopplerSpectrogram frame={dopplerFrame} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
            </div>
          </div>
        </main>

        {/* Settings Sidebar */}
        <Sheet open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
          <SheetContent side="left" className="w-[400px] overflow-y-auto border-r border-white/10 bg-background/95 backdrop-blur-md px-0">
            <SheetHeader className="px-4">
              <SheetTitle className="text-left font-bold text-xl">Signal Processing Settings</SheetTitle>
            </SheetHeader>
            <div className="pb-12 space-y-2">
              <ControlPanel config={config} onConfigChange={updateConfig} />
            </div>
          </SheetContent>
        </Sheet>

        {/* Hardware Config Modal */}
        <Dialog open={isHardwareOpen} onOpenChange={setIsHardwareOpen}>
          <DialogContent className="max-w-2xl bg-card border-white/10 p-0 overflow-hidden">
            <HardwareConfig />
          </DialogContent>
        </Dialog>

        {/* System Control Shell Modal */}
        <Dialog open={isSystemControlOpen} onOpenChange={setIsSystemControlOpen}>
          <DialogContent className="max-w-3xl bg-card border-white/10 p-0 overflow-hidden">
            <SystemControlPanel />
          </DialogContent>
        </Dialog>

        {/* Diagnostic Terminal Modal */}
        <Dialog open={isDiagnosticOpen} onOpenChange={setIsDiagnosticOpen}>
          <DialogContent className="max-w-3xl bg-card border-white/10 p-0 overflow-hidden">
            <VirtualTerminal />
          </DialogContent>
        </Dialog>
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
