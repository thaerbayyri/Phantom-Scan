import { Circle, Wifi, WifiOff, Download, FileText, Database, Settings, Cpu, Terminal, TerminalSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SystemStatus, DataSource, MotionStatus, RecordingStatus } from "@shared/schema";
import { ScanController } from "./scan-controller";

interface TopBarProps {
  status: SystemStatus;
  isConnected: boolean;
  motionStatus: MotionStatus;
  recordingStatus: RecordingStatus;
  onStart: (name?: string) => void;
  onStop: () => void;
  onDataSourceChange: (source: DataSource) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onOpenSettings: () => void;
  onOpenHardware: () => void;
  onOpenSystemControl: () => void;
  onOpenDiagnostic: () => void;
}

export function TopBar({
  status,
  isConnected,
  motionStatus,
  recordingStatus,
  onStart,
  onStop,
  onDataSourceChange,
  onStartRecording,
  onStopRecording,
  onOpenSettings,
  onOpenHardware,
  onOpenSystemControl,
  onOpenDiagnostic,
}: TopBarProps) {
  return (
    <div className="h-14 border-b bg-card flex items-center justify-between px-4">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Phantom Scan</h1>
        <div className="flex items-center gap-1.5" data-testid="status-indicator">
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
          <SelectTrigger className="w-28 h-8 text-xs" data-testid="select-data-source">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="demo">Demo</SelectItem>
            <SelectItem value="esp32">ESP32</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>Samples:</span>
        <span className="font-mono" data-testid="text-samples-count">
          {status.samplesReceived.toLocaleString()}
        </span>
        <span className="mx-1">|</span>
        <span>Frames:</span>
        <span className="font-mono" data-testid="text-frames-count">
          {status.framesProcessed.toLocaleString()}
        </span>
        <span className="mx-1">|</span>

        {/* Data source indicator */}
        {status.dataSource === "esp32" && status.isProcessing ? (
          <Badge variant="default" className="gap-1 bg-green-600 animate-pulse">
            <Wifi className="h-3 w-3" />
            LIVE • ESP32
          </Badge>
        ) : status.isProcessing ? (
          <Badge variant="secondary" className="gap-1">
            DEMO
          </Badge>
        ) : null}

        {/* Active Case indicator */}
        {status.isProcessing && status.sessionName && (
          <Badge variant="outline" className="gap-1 bg-blue-500/10 text-blue-500 border-blue-500/20">
            Case: {status.sessionName}
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
      </div>

      <div className="flex items-center gap-2">
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
          Report
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
          History
        </Button>

        {/* Start/Stop processing via ScanController */}
        <ScanController
          isProcessing={status.isProcessing}
          onStart={onStart}
          onStop={onStop}
        />

        {/* WSL Diagnostic Terminal */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenDiagnostic}
          title="Diagnostic Virtual Terminal"
          className="gap-1.5"
        >
          <TerminalSquare className="h-4 w-4" />
          Diagnostic
        </Button>

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
          antena conf
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
          Terminal
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
      </div>
    </div>
  );
}
