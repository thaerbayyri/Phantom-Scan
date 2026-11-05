import { useEffect, useCallback, useState } from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useWebSocket } from "@/hooks/use-websocket";
import { TopBar } from "@/components/dashboard/top-bar";
import { ControlPanel } from "@/components/dashboard/control-panel";
import { PointCloud3D } from "@/components/dashboard/point-cloud-3d";
import { AoAHeatmap } from "@/components/dashboard/aoa-heatmap";
import { AoASpectrum } from "@/components/dashboard/aoa-spectrum";
import { DopplerSpectrogram } from "../components/dashboard/doppler-spectrogram";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import { TargetIdentityCard } from "@/components/dashboard/target-identity-card";
import { DistanceMeter } from "@/components/dashboard/distance-meter";
import { NodeFeaturesCard } from "@/components/dashboard/node-features-card";
import { SignalStatsCard } from "@/components/dashboard/signal-stats-card";
import { VitalsMonitor } from "@/components/dashboard/vitals-monitor";
import { AIAdvisoryPanel } from "@/components/dashboard/ai-advisory-panel";
import { DatasetRecorderPanel } from "@/components/dashboard/dataset-recorder-panel";
import { DemoBanner } from "@/components/dashboard/demo-banner";
import { usePersistedFlag } from "@/hooks/use-persisted-flag";
import { ResizableWrapper } from "@/components/ui/resizable-wrapper";
import {
  canPresentLiveTargetPosition,
  canPresentVolumetricTarget,
  canPresentIllustrativeBody,
  canPresentTruthfulTarget,
  getLivePositionCaveat,
} from "@shared/target-presentation";
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
    startRecording,
  datasetStatus,
  startDatasetRecording,
  stopDatasetRecording,
    stopRecording,
    markSyncEvent,
    radialTarget,
    targetIdentity,
    targetState,
    vitalSigns,
    advisoryIdentity,
    advisoryVitalSigns,
    lastCalibratedAt,
    calibrateBaseline,
    demoStatus,
    startDemo,
    stopDemo,
    poseFrame,
    nodes,
    nodeFeatures,
    nodeSignal,
    signalField,
  } = useWebSocket();

  // Presentation gates: every target-related widget below renders ONLY what
  // these shared predicates allow, so the page cannot show a position, vitals
  // or identity that the state machine has not vouched for.
  const livePositionVisible = canPresentLiveTargetPosition({
    dataSource: status.dataSource,
    radialTarget,
    targetState,
  });
  const truthfulTargetVisible = canPresentTruthfulTarget({
    radialTarget,
    targetState,
  });
  const volumetricTargetVisible = canPresentVolumetricTarget({
    dataSource: status.dataSource,
    radialTarget,
    targetState,
  });
  const livePositionCaveat = getLivePositionCaveat({
    dataSource: status.dataSource,
    radialTarget,
    targetState,
  });
  // Derived readouts, all zeroed/hidden whenever the position gate is closed:
  // bearing + distance feed the DistanceMeter gauge; vitals and identity only
  // show while a truthful target is visible.
  const targetBearing = livePositionVisible ? radialTarget?.theta : undefined;
  const targetDistanceCm = livePositionVisible && radialTarget ? radialTarget.distanceCm : 0;
  const wallDistance = livePositionVisible && radialTarget ? radialTarget.wallDistance : 0;
  const visibleVitals = truthfulTargetVisible ? vitalSigns : null;
  const visibleIdentity = livePositionVisible ? targetIdentity : null;

  // Illustrative human figure on the target: ON by default, remembered per
  // viewer. It follows the dot's own gate (never outlives it) and is only ever
  // an illustration - the scene captions it "not measured pose".
  const [skeletonEnabled, setSkeletonEnabled] = usePersistedFlag("phantom.showSkeleton", true);
  const illustrativeBodyVisible =
    skeletonEnabled &&
    canPresentIllustrativeBody({
      dataSource: status.dataSource,
      radialTarget,
      targetState,
    });

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

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
        case "m":
          markSyncEvent();
          break;
      }
    },
    [markSyncEvent, status.isProcessing, startProcessing, stopProcessing]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleLogout = useCallback(async () => {
    await logout();
    setLocation("/login");
  }, [logout, setLocation]);

  return (
    <div className="flex h-svh flex-col overflow-hidden bg-background">
      <TopBar
        status={status}
        operatorName={session.username}
        isConnected={isConnected}
        motionStatus={motionStatus}
        recordingStatus={recordingStatus}
        targetState={targetState}
        radialTarget={livePositionVisible ? radialTarget : null}
        nodes={nodes}
        onStart={startProcessing}
        onStop={stopProcessing}
        onStartRecording={startRecording}
        onStopRecording={stopRecording}
        onMarkSyncEvent={markSyncEvent}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onLogout={handleLogout}
        demoStatus={demoStatus}
        onStartDemo={startDemo}
        onStopDemo={stopDemo}
        showSkeleton={skeletonEnabled}
        onToggleSkeleton={() => setSkeletonEnabled(!skeletonEnabled)}
      />

      <DemoBanner demoStatus={demoStatus} />

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Full-screen 3D Background */}
        <div className="absolute inset-0 z-0">
          <PointCloud3D
            points={pointCloud}
            radialTarget={livePositionVisible ? radialTarget : null}
            poseFrame={volumetricTargetVisible ? poseFrame : null}
            targetState={targetState}
            nodes={nodes}
            signalField={signalField}
            showLivePosition={livePositionVisible}
            showIllustrativeBody={illustrativeBodyVisible}
          />
        </div>

        {/* Floating Widgets Container */}
        {/* pointer-events-none ensures we can click through to the 3D canvas */}
        {/* Single scroll context at every breakpoint: main is the only scroller,
            columns flow naturally over the click-through 3D center. */}
        <main className="pointer-events-none relative z-10 flex-1 min-h-0 overflow-x-hidden overflow-y-auto px-3 py-3 xl:px-4">
          <div className="mx-auto grid min-h-full w-full max-w-[1920px] grid-cols-1 items-start gap-4 xl:grid-cols-[20rem_minmax(0,1fr)_21rem] 2xl:grid-cols-[21rem_minmax(0,1fr)_22rem]">

            {/* Left Floating Widgets: signal plots live here so they get a
                full-width column instead of the crowded target column. */}
            <section className="pointer-events-auto flex min-w-0 flex-col gap-3 pt-2 xl:pr-1">
              <AoASpectrum frame={isarFrame} className="h-[13rem] min-h-[13rem] overflow-hidden border-white/10 bg-card/80 backdrop-blur xl:h-[14rem]" />
              <ResizableWrapper defaultHeight={176} minHeight={160} maxHeight={280}>
                <AoAHeatmap data={heatmap} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
              <ResizableWrapper defaultHeight={176} minHeight={160} maxHeight={280}>
                <DopplerSpectrogram frame={dopplerFrame} className="h-full bg-card/80 backdrop-blur-sm border-white/10" />
              </ResizableWrapper>
              <MetricsPanel
                channelEstimate={channelEstimate}
                isarFrame={isarFrame}
              />
              <SignalStatsCard nodeSignal={nodeSignal} />
            </section>

            <div className="hidden xl:block" aria-hidden="true" />

            {/* Right Floating Widgets */}
            <section className="pointer-events-auto flex min-w-0 flex-col gap-3 pt-2 drop-shadow-xl xl:justify-self-end xl:pb-3 xl:pl-1">
              <TargetIdentityCard
                identity={visibleIdentity}
                targetState={targetState ?? null}
                radialTarget={livePositionVisible ? radialTarget : null}
                nodes={nodes}
                presentationCaveat={livePositionCaveat}
              />
              <DistanceMeter
                distanceCm={targetDistanceCm}
                wallDistance={wallDistance}
                bearingRad={targetBearing}
                targetState={targetState ?? null}
                hasLivePosition={livePositionVisible}
                presentationCaveat={livePositionCaveat}
              />
              <VitalsMonitor vitals={visibleVitals} targetState={targetState ?? null} />
              {/* Only shown while boards actually send firmware feature-state;
                  an always-on "no packets" placeholder is just noise. */}
              {nodeFeatures.length > 0 && <NodeFeaturesCard nodeFeatures={nodeFeatures} />}
              <DatasetRecorderPanel
                status={datasetStatus}
                onStart={startDatasetRecording}
                onStop={stopDatasetRecording}
              />
              <AIAdvisoryPanel
                identity={advisoryIdentity}
                vitals={advisoryVitalSigns}
                onCalibrate={calibrateBaseline}
                lastCalibratedAt={lastCalibratedAt}
              />
            </section>
          </div>
        </main>

        {/* Settings Sidebar */}
        <Sheet open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
          <SheetContent side="left" className="w-[400px] overflow-y-auto border-r border-white/10 bg-background/95 backdrop-blur-md px-0">
            <SheetHeader className="px-4">
              <SheetTitle className="text-left font-bold text-xl">Signal Processing Settings</SheetTitle>
              <SheetDescription className="text-left">
                Adjust the live operator processing controls and visualization settings for ESP32-S3 scans.
              </SheetDescription>
            </SheetHeader>
            <div className="pb-6 space-y-2">
              <ControlPanel config={config} onConfigChange={updateConfig} />
            </div>
            <div className="border-t border-white/10 px-4 py-3 text-xs text-muted-foreground">
              Shortcuts: <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">Space</kbd> start/stop
              {" · "}
              <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">M</kbd> mark sync
              {" · "}
              <kbd className="px-1 py-0.5 bg-muted rounded text-foreground font-mono">R</kbd> reload
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
