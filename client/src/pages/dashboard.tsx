import { useEffect, useCallback, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useWebSocket } from "@/hooks/use-websocket";
import { TopBar } from "@/components/dashboard/top-bar";
import { HardwareConfig } from "@/components/dashboard/hardware-config";
import { SystemControlPanel } from "@/components/dashboard/system-control-panel";
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
import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";

export default function Dashboard() {
  const { session, logout } = useAuth();
  const [, setLocation] = useLocation();
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
    radialTarget,
    targetIdentity,
    targetState,
    vitalSigns,
    poseFrame,
  } = useWebSocket();

  const truthfulTargetVisible = Boolean(targetState?.target_visible && radialTarget);
  const targetBearing = truthfulTargetVisible ? radialTarget?.theta : undefined;
  const targetDistanceCm = truthfulTargetVisible && radialTarget ? radialTarget.distanceCm : 0;
  const wallDistance = truthfulTargetVisible && radialTarget ? radialTarget.wallDistance : 0;
  const visibleVitals = truthfulTargetVisible ? vitalSigns : null;
  const visibleIdentity = truthfulTargetVisible ? targetIdentity : null;

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHardwareOpen, setIsHardwareOpen] = useState(false);
  const [isSystemControlOpen, setIsSystemControlOpen] = useState(false);

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

  const handleLogout = useCallback(async () => {
    await logout();
    setLocation("/login");
  }, [logout, setLocation]);

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <TopBar
        status={status}
        operatorName={session.username}
        isConnected={isConnected}
        motionStatus={motionStatus}
        recordingStatus={recordingStatus}
        targetState={targetState}
        onStart={startProcessing}
        onStop={stopProcessing}
        onDataSourceChange={handleDataSourceChange}
        onStartRecording={startRecording}
        onStopRecording={stopRecording}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenHardware={() => setIsHardwareOpen(true)}
        onOpenSystemControl={() => setIsSystemControlOpen(true)}
        onLogout={handleLogout}
      />

      <div className="relative flex flex-1 min-h-0">
        {/* Full-screen 3D Background */}
        <div className="absolute inset-0 z-0">
          <PointCloud3D
            points={pointCloud}
            radialTarget={truthfulTargetVisible ? radialTarget : null}
            poseFrame={truthfulTargetVisible ? poseFrame : null}
            targetState={targetState}
          />
        </div>

        {/* Floating Widgets Container */}
        {/* pointer-events-none ensures we can click through to the 3D canvas */}
        <main className="pointer-events-none relative z-10 flex-1 min-h-0 overflow-auto px-4 py-3">
          <div className="grid min-h-full w-full grid-cols-1 items-start gap-4 xl:grid-cols-[calc(17rem+10px)_minmax(0,1fr)_21rem] 2xl:grid-cols-[calc(18rem+10px)_minmax(0,1fr)_22rem]">

            {/* Left Floating Widgets */}
            <section className="pointer-events-auto flex min-w-0 flex-col gap-3 pt-2 xl:pl-0 xl:max-h-full">
              <AoASpectrum frame={isarFrame} className="h-[14rem] min-h-[14rem] overflow-hidden border-white/10 bg-card/80 backdrop-blur xl:h-[15rem]" />
              <MetricsPanel
                channelEstimate={channelEstimate}
                isarFrame={isarFrame}
              />
            </section>

            <div className="hidden xl:block" aria-hidden="true" />

            {/* Right Floating Widgets */}
            <section className="pointer-events-auto flex min-w-0 flex-col gap-3 pt-2 drop-shadow-xl xl:justify-self-end xl:min-h-0 xl:overflow-y-auto xl:pb-3">
              <TargetIdentityCard 
                identity={visibleIdentity} 
                bearingRad={targetBearing}
                targetState={targetState ?? null}
              />
              <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                <DistanceMeter
                  distanceCm={targetDistanceCm}
                  wallDistance={wallDistance}
                  bearingRad={targetBearing}
                  targetState={targetState ?? null}
                />
                <VitalsMonitor vitals={visibleVitals} targetState={targetState ?? null} />
              </div>

              <ResizableWrapper defaultHeight={128} minHeight={112} maxHeight={220}>
                <AoAHeatmap data={heatmap} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
              <ResizableWrapper defaultHeight={128} minHeight={112} maxHeight={220}>
                <DopplerSpectrogram frame={dopplerFrame} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
            </section>
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
      </div>

      <footer className="border-t bg-card px-4 py-2">
        <div className="text-center text-xs text-muted-foreground">
          Press <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">Space</kbd> to start/stop
          {" | "}
          <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">R</kbd> to reset
        </div>
      </footer>
    </div>
  );
}
