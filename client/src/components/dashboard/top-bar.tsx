import { Radio, Wifi, WifiOff, Play, Square, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ThemeToggle } from "@/components/theme-toggle";
import type { SystemStatus, DataSource } from "@shared/schema";

interface TopBarProps {
  status: SystemStatus;
  isConnected: boolean;
  onStart: () => void;
  onStop: () => void;
  onDataSourceChange: (source: DataSource) => void;
}

export function TopBar({
  status,
  isConnected,
  onStart,
  onStop,
  onDataSourceChange,
}: TopBarProps) {
  return (
    <header className="h-16 border-b bg-card flex items-center justify-between px-6 gap-4 flex-wrap">
      <div className="flex items-center gap-3">
        <Radio className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-semibold">Wi-Vi Dashboard</h1>
        <Badge
          variant={isConnected ? "default" : "destructive"}
          className="gap-1"
          data-testid="badge-connection-status"
        >
          {isConnected ? (
            <>
              <Wifi className="h-3 w-3" />
              Connected
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3" />
              Disconnected
            </>
          )}
        </Badge>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Data Source:</span>
          <Select
            value={status.dataSource}
            onValueChange={(v) => onDataSourceChange(v as DataSource)}
          >
            <SelectTrigger
              className="w-32"
              data-testid="select-data-source"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="demo">Demo</SelectItem>
              <SelectItem value="file">File</SelectItem>
              <SelectItem value="usrp">USRP</SelectItem>
              <SelectItem value="esp32">ESP32</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Samples:</span>
          <span className="font-mono" data-testid="text-samples-count">
            {status.samplesReceived.toLocaleString()}
          </span>
          <span className="mx-2">|</span>
          <span>Frames:</span>
          <span className="font-mono" data-testid="text-frames-count">
            {status.framesProcessed.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {status.isProcessing ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={onStop}
              data-testid="button-stop"
            >
              <Square className="h-4 w-4 mr-1" />
              Stop
            </Button>
          ) : (
            <Button
              variant="default"
              size="sm"
              onClick={onStart}
              data-testid="button-start"
            >
              <Play className="h-4 w-4 mr-1" />
              Start
            </Button>
          )}
          <Button
            variant="outline"
            size="icon"
            onClick={() => window.location.reload()}
            data-testid="button-reset"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
