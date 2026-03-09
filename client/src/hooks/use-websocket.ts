import { useState, useEffect, useCallback, useRef } from "react";
import type {
  SystemStatus,
  ChannelEstimate,
  ISARFrame,
  PointCloudPoint,
  HeatmapData,
  ProcessingConfig,
  SignalTrace,
  MotionStatus,
  DopplerFrame,
  RecordingStatus,
  TrackedTarget,
  RadialTarget,
  TargetIdentity,
  VitalSigns,
} from "@shared/schema";

interface WSState {
  status: SystemStatus;
  channelEstimate: ChannelEstimate | null;
  isarFrame: ISARFrame | null;
  pointCloud: PointCloudPoint[];
  heatmap: HeatmapData | null;
  config: ProcessingConfig;
  signalTrace: SignalTrace;
  motionStatus: MotionStatus;
  dopplerFrame: DopplerFrame | null;
  recordingStatus: RecordingStatus;
  trackedTarget: TrackedTarget | null;
  radialTarget: RadialTarget | null;
  targetIdentity: TargetIdentity | null;
  vitalSigns: VitalSigns | null;
  isConnected: boolean;
  error: string | null;
}

const defaultConfig: ProcessingConfig = {
  isarEnabled: true,
  arrayLength: 16,
  aoaRangeMin: -60,
  aoaRangeMax: 60,
  clutterRemovalEnabled: true,
  clutterWindowSize: 50,
  motionGateEnabled: false,
  motionThreshold: 0.05,
};

const defaultStatus: SystemStatus = {
  connected: false,
  dataSource: "demo",
  samplesReceived: 0,
  framesProcessed: 0,
  lastUpdate: Date.now(),
  isProcessing: false,
};

const defaultSignalTrace: SignalTrace = {
  timestamps: [],
  h1Magnitude: [],
  h2Magnitude: [],
  nulledMagnitude: [],
  dynamicMagnitude: [],
};

const defaultMotionStatus: MotionStatus = {
  motionDetected: false,
  variance: 0,
  threshold: 0.05,
};

const defaultRecordingStatus: RecordingStatus = {
  isRecording: false,
  sampleCount: 0,
  durationMs: 0,
};

export function useWebSocket() {
  const [state, setState] = useState<WSState>({
    status: defaultStatus,
    channelEstimate: null,
    isarFrame: null,
    pointCloud: [],
    heatmap: null,
    config: defaultConfig,
    signalTrace: defaultSignalTrace,
    motionStatus: defaultMotionStatus,
    dopplerFrame: null,
    recordingStatus: defaultRecordingStatus,
    trackedTarget: null,
    radialTarget: null,
    targetIdentity: null,
    vitalSigns: null,
    isConnected: false,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({ ...prev, isConnected: true, error: null }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, isConnected: false }));
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setState((prev) => ({
          ...prev,
          error: "Connection error",
          isConnected: false,
        }));
      };
    } catch (e) {
      console.error("Failed to create WebSocket:", e);
      setState((prev) => ({
        ...prev,
        error: "Failed to connect",
        isConnected: false,
      }));
    }
  }, []);
  // Cooldown to prevent server status race condition on start/stop
  const pendingToggleRef = useRef(0);

  const handleMessage = (message: { type: string; data: unknown }) => {
    switch (message.type) {
      case "status": {
        // If we recently pressed start/stop, ignore server status for 1s
        // to prevent the server's in-flight broadcasts from reverting our UI
        const now = Date.now();
        if (now - pendingToggleRef.current < 1000) {
          // Still update non-isProcessing fields
          setState((prev) => ({
            ...prev,
            status: {
              ...(message.data as SystemStatus),
              isProcessing: prev.status.isProcessing, // keep our local value
            },
          }));
        } else {
          setState((prev) => ({
            ...prev,
            status: message.data as SystemStatus,
          }));
        }
        break;
      }

      case "csiFrame": {
        const estimate = message.data as ChannelEstimate;
        setState((prev) => {
          const maxPoints = 100;
          const h1Mag = Math.sqrt(
            estimate.h1.re ** 2 + estimate.h1.im ** 2
          );
          const h2Mag = Math.sqrt(
            estimate.h2.re ** 2 + estimate.h2.im ** 2
          );
          const nulledMag = Math.sqrt(
            estimate.nulledSignal.re ** 2 + estimate.nulledSignal.im ** 2
          );

          const newTrace: SignalTrace = {
            timestamps: [
              ...prev.signalTrace.timestamps.slice(-maxPoints + 1),
              estimate.timestamp,
            ],
            h1Magnitude: [
              ...prev.signalTrace.h1Magnitude.slice(-maxPoints + 1),
              h1Mag,
            ],
            h2Magnitude: [
              ...prev.signalTrace.h2Magnitude.slice(-maxPoints + 1),
              h2Mag,
            ],
            nulledMagnitude: [
              ...prev.signalTrace.nulledMagnitude.slice(-maxPoints + 1),
              nulledMag,
            ],
            dynamicMagnitude: [
              ...prev.signalTrace.dynamicMagnitude.slice(-maxPoints + 1),
              h1Mag, // h1 is already dynamic (clutter-removed) when enabled
            ],
          };

          return { ...prev, channelEstimate: estimate, signalTrace: newTrace };
        });
        break;
      }

      case "isarFrame":
        setState((prev) => ({
          ...prev,
          isarFrame: message.data as ISARFrame,
        }));
        break;

      case "pointCloud":
        setState((prev) => ({
          ...prev,
          pointCloud: message.data as PointCloudPoint[],
        }));
        break;



      case "heatmap":
        setState((prev) => ({
          ...prev,
          heatmap: message.data as HeatmapData,
        }));
        break;

      case "config":
        setState((prev) => ({
          ...prev,
          config: message.data as ProcessingConfig,
        }));
        break;

      case "motionStatus":
        setState((prev) => ({
          ...prev,
          motionStatus: message.data as MotionStatus,
        }));
        break;

      case "dopplerFrame":
        setState((prev) => ({
          ...prev,
          dopplerFrame: message.data as DopplerFrame,
        }));
        break;

      case "recordingStatus":
        setState((prev) => ({
          ...prev,
          recordingStatus: message.data as RecordingStatus,
        }));
        break;

      case "trackedTarget":
        setState((prev) => ({
          ...prev,
          trackedTarget: message.data as TrackedTarget | null,
        }));
        break;

      case "radialTarget":
        setState((prev) => ({
          ...prev,
          radialTarget: message.data as RadialTarget | null,
        }));
        break;

      case "targetIdentity":
        setState((prev) => ({
          ...prev,
          targetIdentity: message.data as TargetIdentity,
        }));
        break;

      case "vitalSigns":
        setState((prev) => ({
          ...prev,
          vitalSigns: message.data as VitalSigns,
        }));
        break;

      case "reportReady":
        console.log("Report is ready, downloading...");
        window.open("/api/recording/download?format=pdf", "_blank");
        break;

      case "error":
        setState((prev) => ({
          ...prev,
          error: message.data as string,
        }));
        break;
    }
  };

  const sendMessage = useCallback((type: string, data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  const updateConfig = useCallback(
    (config: Partial<ProcessingConfig>) => {
      sendMessage("updateConfig", config);
      setState((prev) => ({
        ...prev,
        config: { ...prev.config, ...config },
      }));
    },
    [sendMessage]
  );

  const startProcessing = useCallback((customName?: string) => {
    console.log("[WS] startProcessing called");
    pendingToggleRef.current = Date.now();
    sendMessage("startProcessing", { customName });
    setState((prev) => ({
      ...prev,
      status: { ...prev.status, isProcessing: true, sessionName: customName },
    }));
  }, [sendMessage]);

  const stopProcessing = useCallback(() => {
    console.log("[WS] stopProcessing called");
    pendingToggleRef.current = Date.now();
    sendMessage("stopProcessing", null);
    setState((prev) => ({
      ...prev,
      status: { ...prev.status, isProcessing: false },
    }));
  }, [sendMessage]);

  const setDataSource = useCallback(
    (source: string) => {
      sendMessage("setDataSource", source);
    },
    [sendMessage]
  );

  const startRecording = useCallback(() => {
    sendMessage("startRecording", null);
  }, [sendMessage]);

  const stopRecording = useCallback(() => {
    sendMessage("stopRecording", null);
  }, [sendMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return {
    ...state,
    updateConfig,
    startProcessing,
    stopProcessing,
    setDataSource,
    startRecording,
    stopRecording,
    reconnect: connect,
  };
}
