import { Circle, Wifi, WifiOff, Download, FileText, Database, Settings, Cpu, Terminal, LogOut, Shield, ScrollText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SystemStatus, DataSource, MotionStatus, RecordingStatus, TargetState } from "@shared/schema";
import { ScanController } from "./scan-controller";

interface TopBarProps {
  status: SystemStatus;
  operatorName?: string;
  isConnected: boolean;
  motionStatus: MotionStatus;
  recordingStatus: RecordingStatus;
  targetState?: TargetState | null;
  onStart: (name?: string) => void;
  onStop: () => void;
  onDataSourceChange: (source: DataSource) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onOpenSettings: () => void;
  onOpenHardware: () => void;
  onOpenSystemControl: () => void;
  onLogout: () => void;
}

export function TopBar({
  status,
  operatorName,
  isConnected,
  motionStatus,
  recordingStatus,
  targetState,
  onStart,
  onStop,
  onDataSourceChange,
  onStartRecording,
  onStopRecording,
  onOpenSettings,
  onOpenHardware,
  onOpenSystemControl,
  onLogout,
}: TopBarProps) {
  const liveModeBadge = status.dataSource === "esp32" && status.isProcessing ? (
    <Badge variant="default" className="gap-1 bg-green-600 animate-pulse">
      <Wifi className="h-3 w-3" />
      LIVE • ESP32
    </Badge>
  ) : status.isProcessing ? (
    <Badge variant="secondary" className="gap-1">
      DEMO
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
          <Select
            value={status.dataSource}
            onValueChange={(value) => onDataSourceChange(value as DataSource)}
          >
            <SelectTrigger className="h-8 w-28 shrink-0 text-xs" data-testid="select-data-source">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="demo">Demo</SelectItem>
              <SelectItem value="esp32">ESP32</SelectItem>
            </SelectContent>
          </Select>
          {liveModeBadge}
        </div>

        <div className="order-3 flex w-full min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground xl:order-none xl:w-auto xl:flex-1 xl:justify-center">
          <span>Samples:</span>
          <span className="font-mono" data-testid="text-samples-count">
            {status.samplesReceived.toLocaleString()}
          </span>
          <span className="text-muted-foreground/50">|</span>
          <span>Frames:</span>
          <span className="font-mono" data-testid="text-frames-count">
            {status.framesProcessed.toLocaleString()}
          </span>

          {/* Active Case indicator */}
          {status.isProcessing && status.sessionName && (
            <Badge variant="outline" className="max-w-full gap-1 overflow-hidden border-blue-500/20 bg-blue-500/10 text-blue-500">
              <span className="shrink-0">Case:</span>
              <span className="truncate">{status.sessionName}</span>
            </Badge>
          )}

          {/* Motion indicator */}
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

          {status.isProcessing && (
            <Badge variant="outline" className="gap-1 border-cyan-500/30 text-cyan-300">
              Target: {targetState?.target_visible ? targetState.state.toUpperCase() : "NONE"}
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

          {/* Hardware Config */}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenHardware}
            title="Hardware Node Config"
            data-testid="btn-hardware"
            className="gap-1.5"
          >
            <Cpu className="h-4 w-4" />
            <span className="hidden xl:inline">antena conf</span>
          </Button>

          {/* System Control Panel */}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenSystemControl}
            title="System Control Shell"
            data-testid="btn-system-control"
            className="gap-1.5"
          >
            <Terminal className="h-4 w-4" />
            <span className="hidden xl:inline">Terminal</span>
          </Button>

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
