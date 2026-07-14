import { Circle, Wifi, WifiOff, Download, FileText, Database, Settings, LogOut, Shield, ScrollText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { SystemStatus, MotionStatus, RecordingStatus, TargetState, RadialTarget, SensorNode } from "@shared/schema";
import { summarizeTargetSpatial } from "@shared/target-spatial";
import { ScanController } from "./scan-controller";

interface TopBarProps {
  status: SystemStatus;
  operatorName?: string;
  isConnected: boolean;
  motionStatus: MotionStatus;
  recordingStatus: RecordingStatus;
  targetState?: TargetState | null;
  radialTarget?: RadialTarget | null;
  nodes?: SensorNode[];
  onStart: (name?: string) => void;
  onStop: () => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onMarkSyncEvent: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}

export function TopBar({
  status,
  operatorName,
  isConnected,
  motionStatus,
  recordingStatus,
  targetState,
  radialTarget,
  nodes = [],
  onStart,
  onStop,
  onStartRecording,
  onStopRecording,
  onMarkSyncEvent,
  onOpenSettings,
  onLogout,
}: TopBarProps) {
  const spatialSummary = summarizeTargetSpatial(radialTarget, nodes, targetState);
  const liveModeBadge = status.isProcessing ? (
    <Badge variant="default" className="gap-1 bg-green-600 animate-pulse">
      <Wifi className="h-3 w-3" />
      LIVE • ESP32
    </Badge>
  ) : null;

  return (
    <div className="border-b bg-card/95 backdrop-blur">
      <div className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 md:px-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2 md:gap-3">
          <h1 className="shrink-0 text-lg font-semibold tracking-tight">Phantom Scan</h1>
          <div className="flex shrink-0 items-center gap-1.5" data-testid="status-indicator">
          {isConnected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-green-500" />
              <span className="text-xs text-green-500">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-destructive" />
              <span className="text-xs text-destructive">Disconnected</span>
            </>
          )}
          </div>
          <Badge
            variant="outline"
            className="h-8 shrink-0 border-green-500/30 bg-green-500/10 text-xs text-green-300"
          >
            ESP32 ONLY
          </Badge>
          {liveModeBadge}
        </div>

        {/* Inline stats: no order-3/w-full so the bar stays a single row and
            only wraps when it truly runs out of space. Sample/frame counters
            are debug-grade — hidden below lg. */}
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground xl:flex-1 xl:justify-center">
          <span className="hidden lg:inline">Samples:</span>
          <span className="hidden font-mono lg:inline" data-testid="text-samples-count">
            {status.samplesReceived.toLocaleString()}
          </span>
          <span className="hidden text-muted-foreground/50 lg:inline">|</span>
          <span className="hidden lg:inline">Frames:</span>
          <span className="hidden font-mono lg:inline" data-testid="text-frames-count">
            {status.framesProcessed.toLocaleString()}
          </span>

          {/* Active Case indicator */}
          {status.isProcessing && status.sessionName && (
            <Badge variant="outline" className="max-w-full gap-1 overflow-hidden border-blue-500/20 bg-blue-500/10 text-blue-500">
              <span className="shrink-0">Case:</span>
              <span className="truncate">{status.sessionName}</span>
            </Badge>
          )}

          {/* Motion indicator: live MotionGate verdict — orange "Motion"
              badge when this frame's variance beats the threshold. */}
          {status.isProcessing && (
            motionStatus.motionDetected ? (
              <Badge variant="default" className="gap-1 bg-orange-500">
                <Circle className="h-2 w-2 fill-current" />
                Motion
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1 text-muted-foreground">
                No Motion
              </Badge>
            )
          )}

          {/* Target zone badge: "NONE" until the state machine vouches for a
              visible target, then the spatial zone ("Near N1", "Between…"). */}
          {status.isProcessing && (
            <Badge variant="outline" className="gap-1 border-cyan-500/30 text-cyan-300">
              Target: {targetState?.target_visible ? (spatialSummary?.zoneLabel ?? targetState.state.toUpperCase()) : "NONE"}
            </Badge>
          )}
        </div>

        <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2">
          <Badge variant="outline" className="gap-1.5 border-primary/25 bg-primary/10 text-primary">
            <Shield className="h-3.5 w-3.5" />
            <span className="max-w-24 truncate sm:max-w-32">{operatorName ?? "operator"}</span>
          </Badge>

          {/* Recording button */}
          {recordingStatus.isRecording ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={onStopRecording}
              className="gap-1.5"
              data-testid="btn-stop-recording"
            >
              <Circle className="h-3 w-3 fill-red-400 text-red-400 animate-pulse" />
              REC ({recordingStatus.sampleCount})
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={onStartRecording}
              className="gap-1.5"
              data-testid="btn-start-recording"
            >
              <Circle className="h-3 w-3 text-red-500" />
              Record
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={onMarkSyncEvent}
            disabled={!recordingStatus.isRecording}
            className="gap-1.5"
            title="Mark a live sync event for video / ground-truth alignment"
          >
            <Circle className="h-3 w-3" />
            <span className="hidden xl:inline">Sync</span>
          </Button>

          {/* Download last recording */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => window.open("/api/recording/download", "_blank")}
            title="Download last recording"
            data-testid="btn-download-recording"
          >
            <Download className="h-4 w-4" />
          </Button>

          {/* Session Report link */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.href = "/report"}
            className="gap-1.5"
            title="View session report"
            data-testid="btn-report"
          >
            <FileText className="h-3.5 w-3.5" />
            <span className="hidden 2xl:inline">Report</span>
          </Button>

          {/* Session History link */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.href = "/history"}
            className="gap-1.5"
            title="View session history"
            data-testid="btn-history"
          >
            <Database className="h-3.5 w-3.5" />
            <span className="hidden 2xl:inline">History</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.href = "/activity"}
            className="gap-1.5"
            title="View operator activity"
          >
            <ScrollText className="h-3.5 w-3.5" />
            <span className="hidden 2xl:inline">Activity</span>
          </Button>

          {/* Start/Stop processing via ScanController */}
          <ScanController
            isProcessing={status.isProcessing}
            onStart={onStart}
            onStop={onStop}
          />

          {/* Open Settings Sheet */}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenSettings}
            title="Signal Processing Settings"
            data-testid="btn-settings"
          >
            <Settings className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="gap-1.5"
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden xl:inline">Logout</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
