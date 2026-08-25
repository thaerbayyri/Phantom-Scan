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
  RadialTarget,
  TargetIdentity,
  TargetDebug,
  TargetState,
  VitalSigns,
  PoseFrame,
  SensorNode,
  NodeFeatureState,
  SignalField,
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
  radialTarget: RadialTarget | null;
  targetIdentity: TargetIdentity | null;
  targetDebug: TargetDebug | null;
  targetState: TargetState | null;
  vitalSigns: VitalSigns | null;
  // AI sidecar advisory output only (PS-REMED-WP3-FOLLOWUP-01). Never the
  // deterministic verdict — see server/lib/websocket.ts's isAI-gated relay.
  advisoryIdentity: TargetIdentity | null;
  advisoryVitalSigns: VitalSigns | null;
  // Wall-clock (ms) of the last AI-sidecar baseline calibration ack, or null
  // if none has happened this session. Advisory-only bookkeeping, same as
  // advisoryIdentity/advisoryVitalSigns above.
  lastCalibratedAt: number | null;
  poseFrame: PoseFrame | null;
  nodes: SensorNode[];
  nodeFeatures: NodeFeatureState[];
  // fused_room only (3-4 active nodes) — spatial intensity grid for the
  // dashboard's floor-glow visualization. Null outside fused_room.
  signalField: SignalField | null;
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
  fusedTargetMotionThreshold: 0.6,
};

const defaultStatus: SystemStatus = {
  connected: false,
  dataSource: "esp32",
  samplesReceived: 0,
  framesProcessed: 0,
  lastUpdate: Date.now(),
  isProcessing: false,
  synthetic_enabled: false,
  source: "live",
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
  lastFile: undefined,
  lastSyncAtMs: undefined,
};

const defaultTargetState: TargetState = {
  state: "none",
  source_mode: "live",
  node_mode: "single_node",
  target_visible: false,
  position_confident: false,
  motion_score: 0,
  confidence: 0,
  last_update_ms: Date.now(),
  data_age_ms: 0,
  stale: false,
  reason: "client_idle",
};

function buildClearedTargetState(reason: string): TargetState {
  return {
    ...defaultTargetState,
    last_update_ms: Date.now(),
    reason,
  };
}

/**
 * One-shot wipe of everything target-related in client state (dot, identity,
 * vitals, pose, point cloud) used on stop/disconnect/source-change and by the
 * staleness watchdog, so a dead data path can never leave a ghost on screen.
 */
function buildClearedSceneState(
  reason: string,
  opts: { clearNodes?: boolean } = {},
) {
  return {
    pointCloud: [] as PointCloudPoint[],
    radialTarget: null as RadialTarget | null,
    targetIdentity: null as TargetIdentity | null,
    targetDebug: null as TargetDebug | null,
    targetState: buildClearedTargetState(reason),
    vitalSigns: null as VitalSigns | null,
    advisoryIdentity: null as TargetIdentity | null,
    advisoryVitalSigns: null as VitalSigns | null,
    poseFrame: null as PoseFrame | null,
    nodeFeatures: [] as NodeFeatureState[],
    signalField: null as SignalField | null,
    // Node beacons are only cleared on socket death: on Stop the server
    // intentionally keeps sending quiesced beacons (honest node presence).
    ...(opts.clearNodes ? { nodes: [] as SensorNode[] } : {}),
  };
}

/**
 * Single source of live detection state for the whole dashboard. Opens the
 * /ws socket, routes every server broadcast (radialTarget, targetState,
 * nodes, motionStatus, vitals, charts…) into React state, auto-reconnects
 * every 2 s, and runs the 5 s staleness watchdog. Components never talk to
 * the socket directly — they consume this hook's state.
 */
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
    radialTarget: null,
    targetIdentity: null,
    targetDebug: null,
    targetState: defaultTargetState,
    vitalSigns: null,
    advisoryIdentity: null,
    advisoryVitalSigns: null,
    lastCalibratedAt: null,
    poseFrame: null,
    nodes: [],
    nodeFeatures: [],
    signalField: null,
    isConnected: false,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // Client-side staleness watchdog: wall-clock of the last target-bearing
  // message ARRIVAL (radialTarget or targetState — the server keeps emitting
  // targetState during the intentional empty-room gate, so an idle room does
  // not trip the watchdog; only a frozen/silent server does).
  const lastTargetMsgRef = useRef<number>(Date.now());

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
        setState((prev) => ({
          ...prev,
          isConnected: false,
          ...buildClearedSceneState("websocket_closed", { clearNodes: true }),
        }));
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setState((prev) => ({
          ...prev,
          error: "Connection error",
          isConnected: false,
          ...buildClearedSceneState("websocket_error", { clearNodes: true }),
        }));
      };
    } catch (e) {
      console.error("Failed to create WebSocket:", e);
      setState((prev) => ({
        ...prev,
        error: "Failed to connect",
        isConnected: false,
        targetState: buildClearedTargetState("connect_failed"),
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

      // "trackedTarget" messages are intentionally ignored: no client consumer
      // (fused/radial target is the rendered position source).

      // The rendered target position/velocity (fused or single-node). Null
      // means the server explicitly cleared the target. Also feeds the
      // staleness watchdog timestamp.
      case "radialTarget":
        lastTargetMsgRef.current = Date.now();
        setState((prev) => ({
          ...prev,
          radialTarget: message.data as RadialTarget | null,
        }));
        break;

      case "targetIdentity":
        setState((prev) => ({
          ...prev,
          targetIdentity: (message.data as TargetIdentity | null) ?? null,
        }));
        break;

      // Presence state machine (none/stale/idle/moving/degraded) — the gates
      // in shared/target-presentation.ts read this to decide what may render.
      case "targetState":
        lastTargetMsgRef.current = Date.now();
        setState((prev) => ({
          ...prev,
          targetState: message.data as TargetState,
        }));
        break;

      case "targetDebug":
        setState((prev) => ({
          ...prev,
          targetDebug: message.data as TargetDebug,
        }));
        break;

      case "vitalSigns":
        setState((prev) => ({
          ...prev,
          vitalSigns: message.data as VitalSigns,
        }));
        break;

      // AI sidecar advisory identity/vitals only — relayed by the server
      // exclusively from isAI-registered clients (PS-REMED-WP3-FOLLOWUP-01).
      // Never written into targetIdentity/vitalSigns; the deterministic
      // pipeline remains the only writer of those authoritative fields.
      case "advisoryIdentity":
        setState((prev) => ({
          ...prev,
          advisoryIdentity: (message.data as TargetIdentity | null) ?? null,
        }));
        break;

      case "advisoryVitalSigns":
        setState((prev) => ({
          ...prev,
          advisoryVitalSigns: (message.data as VitalSigns | null) ?? null,
        }));
        break;

      case "poseFrame":
        setState((prev) => ({
          ...prev,
          poseFrame: message.data as PoseFrame,
        }));
        break;

      // Per-node beacons: anchor position, motion glow 0..1, active flag,
      // target distance to this node, and approach/recede trend.
      case "nodes":
        setState((prev) => ({
          ...prev,
          nodes: (message.data as SensorNode[]) ?? [],
        }));
        break;

      case "nodeFeatures":
        setState((prev) => ({
          ...prev,
          nodeFeatures: (message.data as NodeFeatureState[]) ?? [],
        }));
        break;

      // fused_room spatial intensity grid — see RadialScene's SignalFieldGrid.
      case "signalField":
        setState((prev) => ({
          ...prev,
          signalField: (message.data as SignalField) ?? null,
        }));
        break;

      // Ack from the AI sidecar that it reset its activity-state motion
      // baseline (see scripts/ai_inference.py classify_activity /
      // _run_calibration). Does not touch any deterministic/model weight.
      case "calibrationAck":
        setState((prev) => ({
          ...prev,
          lastCalibratedAt: Date.now(),
        }));
        break;

      case "reportReady":
        console.log("Report is ready and available from history/report views.");
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
      ...buildClearedSceneState("scan_started"),
      status: { ...prev.status, isProcessing: true, sessionName: customName },
    }));
  }, [sendMessage]);

  const stopProcessing = useCallback(() => {
    console.log("[WS] stopProcessing called");
    pendingToggleRef.current = Date.now();
    sendMessage("stopProcessing", null);
    setState((prev) => ({
      ...prev,
      ...buildClearedSceneState("scan_stopped"),
      status: { ...prev.status, isProcessing: false },
    }));
  }, [sendMessage]);

  const setDataSource = useCallback(
    (source: string) => {
      sendMessage("setDataSource", source);
      setState((prev) => ({
        ...prev,
        ...buildClearedSceneState(`source_changed_${source}`),
        status: {
          ...prev.status,
          dataSource: source as SystemStatus["dataSource"],
          source: "live",
          synthetic_enabled: false,
        },
      }));
    },
    [sendMessage]
  );

  const startRecording = useCallback(() => {
    sendMessage("startRecording", null);
  }, [sendMessage]);

  const stopRecording = useCallback(() => {
    sendMessage("stopRecording", null);
  }, [sendMessage]);

  const markSyncEvent = useCallback(() => {
    sendMessage("markSyncEvent", null);
  }, [sendMessage]);

  // Asks the AI sidecar to reset the rolling motion baseline its
  // walking/rapid_change activity heuristic compares against, so ambient
  // room noise (fan, HVAC) captured right now stops reading as motion.
  // Relayed server-side to AI clients only (server/lib/websocket.ts); no
  // deterministic/model weight is touched.
  const calibrateBaseline = useCallback(() => {
    sendMessage("calibrateBaseline", null);
  }, [sendMessage]);

  useEffect(() => {
    connect();
    // Defense-in-depth staleness watchdog: if the socket stays open but the
    // server freezes (no radialTarget/targetState for >5 s), clear the scene
    // instead of rendering the last target forever. Server-side freshness
    // (isSampleFresh + stale/clear timers) remains the primary mechanism.
    const watchdog = setInterval(() => {
      if (Date.now() - lastTargetMsgRef.current <= 5000) return;
      setState((prev) => {
        if (!prev.isConnected || prev.radialTarget === null) return prev;
        return { ...prev, ...buildClearedSceneState("client_watchdog_stale") };
      });
    }, 1000);
    return () => {
      clearInterval(watchdog);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      // Detach handlers before closing: WebSocket.close() is async, so a
      // late-firing onclose/onerror on this dead socket would otherwise still
      // run — including scheduling a new setTimeout(connect, 2000) — spawning
      // a zombie connection that reconnects forever with no owner to clean it
      // up (e.g. navigating from the Dashboard route to /history and back).
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
      }
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
    markSyncEvent,
    calibrateBaseline,
    reconnect: connect,
  };
}
