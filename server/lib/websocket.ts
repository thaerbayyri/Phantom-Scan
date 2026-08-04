import { WebSocketServer, WebSocket } from "ws";
import type { Server } from "http";
import { randomUUID } from "crypto";
import type {
  ProcessingConfig,
  SystemStatus,
  DataSource,
  CSISample,
  ChannelEstimate,
  RadialTarget,
  TargetIdentity,
  TargetDebug,
  TargetState,
  TrackedTarget,
  VitalSigns,
  PoseFrame,
  SensorNode,
  NodeFeatureState,
} from "@shared/schema";
import { NODE_ANCHORS, NODE_SEPARATION_M } from "@shared/schema";
import { compassBearingRad } from "@shared/bearing";

/**
 * Per-node amplitude window for motion/balance (ms). Shorter = faster target
 * response and sharper node-to-node contrast; longer = smoother but laggier.
 * At the measured 20-40 fps a 1.5 s window still holds 30-60 frames — plenty
 * for the per-subcarrier temporal std. Override via PHANTOM_MOTION_WINDOW_MS.
 */
const MOTION_WINDOW_MS = Number.parseInt(
  process.env.PHANTOM_MOTION_WINDOW_MS ?? "1500",
  10,
);
import {
  fuseTwoNodeTarget,
  computeNodeMotionFromMatrix,
  computeNodeTrends,
  computeFallbackVelocity,
  computeGainNormalizedPerturbation,
  DEFAULT_MOTION_THRESHOLD,
  type FusedTarget,
  type NodeTrend,
} from "./node-fusion";
import {
  computeMUSICSpectrum,
  findSpectrumPeak,
  aoaToPoint,
  HeatmapAccumulator,
  BackgroundSubtractor,
  MotionGate,
  DopplerComputer,
  MicroDopplerClassifier,
  PDPRanger,
} from "./signal-processing";
import { TrackingProcessor } from "./tracking";
import { magnitude, conj, mul, phase } from "./complex";
import { VitalsComputer } from "./vitals";
import {
  buildTargetState,
  emptyTargetState,
  resolveLiveHoldState,
  isSampleFresh,
} from "./target-state";
import { loadRuntimeSettings, saveRuntimeSettings } from "./runtime-settings";
import {
  buildRecordingRow,
  buildRecordingSessionMeta,
  serializeRecordingCsv,
  type GroundTruthTag,
  type RecordingRow,
  type RecordingSessionMeta,
} from "./recording-export";
import * as fs from "fs";
import * as path from "path";
import { sessionStore } from "./session-store";
import { spawn } from "child_process";
import type { AuthService } from "../auth/service";
import { authenticateWebSocketRequest } from "../auth/ws-auth";
import { auditLogger } from "../audit/logger";

interface WSClient {
  ws: WebSocket;
  id: string;
  username?: string;
  isAI?: boolean;
}

export class SignalProcessingServer {
  private wss: WebSocketServer | null = null;
  private clients: Map<string, WSClient> = new Map();
  private processingInterval: NodeJS.Timeout | null = null;
  private isStopping: boolean = false;

  // Operator-adjusted detector calibration (motion thresholds) survives a
  // restart via runtime-settings.ts; everything else stays code-default.
  private config: ProcessingConfig = {
    isarEnabled: true,
    arrayLength: 16,
    aoaRangeMin: -60,
    aoaRangeMax: 60,
    clutterRemovalEnabled: true,
    clutterWindowSize: 50,
    motionGateEnabled: false,
    motionThreshold: loadRuntimeSettings().motionThreshold ?? 0.05,
    fusedTargetMotionThreshold:
      loadRuntimeSettings().fusedTargetMotionThreshold ?? DEFAULT_MOTION_THRESHOLD,
  };

  private status: SystemStatus = {
    connected: false,
    dataSource: "esp32",
    samplesReceived: 0,
    framesProcessed: 0,
    lastUpdate: Date.now(),
    isProcessing: false,
    sessionName: "",
    synthetic_enabled: false,
    source: "live",
  };

  // Processing engines
  // Time × subcarrier amplitude waterfall (index grid 0..63): real CSI data,
  // unlike the MUSIC pseudo-spectrum which has no spatial meaning on
  // single-antenna boards.
  private heatmapAccumulator = new HeatmapAccumulator(0, 63, 64);
  private backgroundSubtractor = new BackgroundSubtractor(50);
  private motionGate = new MotionGate();
  private dopplerComputer = new DopplerComputer();
  private trackingProcessor = new TrackingProcessor();
  private microDopplerClassifier = new MicroDopplerClassifier();
  private pdpRanger = new PDPRanger();
  private vitalsComputer = new VitalsComputer();

  // Buffers
  private sampleBuffer: { re: number; im: number }[] = [];
  private pointCloudHistory: {
    x: number;
    y: number;
    z: number;
    amplitude: number;
    timestamp: number;
  }[] = [];
  private hardwareSampleQueue: CSISample[] = [];
  private hardwareNodeLastSeenMs: Map<number, number> = new Map();
  private nextHardwareQueueIndex = 0;

  // Two-node fusion (Phantom Balance Fusion) state. Each window entry is one packet's
  // per-subcarrier amplitude frame (falls back to a 1-element frame from the
  // scalar h1 when the packet carried no vector).
  private nodeAmpWindow: Map<number, { t: number; amps: number[] }[]> = new Map();
  private nodeLastRssi: Map<number, number> = new Map();
  private prevFusedX: number | null = null;
  private prevFusedMs = 0;
  private lastNodeFpsLogMs = 0;
  private lastIdleDebugMs = 0;
  // Single per-tick fused snapshot: BOTH the radialTarget broadcast (x) and
  // buildSensorNodes (distanceM/trend) read this same value so the target dot
  // and the node distance labels can never disagree within a tick.
  private fusedSnapshot: {
    balance: number;
    x: number;
    velMps: number; // signed: >0 toward N2
    trends: { 1: NodeTrend; 2: NodeTrend };
    atMs: number;
  } | null = null;

  // Recording state
  private isRecording = false;
  private recordingBuffer: RecordingRow[] = [];
  private recordingStartTime = 0;
  private lastRecordingFile?: string;
  private recordingSessionMeta: RecordingSessionMeta | null = null;
  private pendingSyncMarker = false;
  private lastSyncAtMs?: number;
  private activeGroundTruthTag: GroundTruthTag | null = null;

  private currentSessionName: string = "";
  private currentTrackedTarget: TrackedTarget | null = null;
  private currentRadialTarget: RadialTarget | null = null;
  private currentTargetIdentity: TargetIdentity | null = null;
  private currentVitalSigns: VitalSigns | null = null;
  private currentPoseFrame: PoseFrame | null = null;
  private currentTargetState: TargetState = emptyTargetState({
    dataSource: "esp32",
    nowMs: Date.now(),
    reason: "startup_idle",
  });
  private currentTargetDebug: TargetDebug = {
    hardware_queue_length: 0,
    last_sample_rx_ms: null,
    last_processed_sample_ms: null,
    last_truthful_target_update_ms: null,
    target_reason: "startup_idle",
    radial_target_present: false,
    tracked_target_present: false,
    hold_state: "startup",
  };
  private lastSampleRxMs: number | null = null;
  private lastProcessedSampleMs: number | null = null;
  private lastTruthfulTargetUpdateMs = 0;

  // Radial tracking state
  private radialAngle = 0;

  // Fallback (non-Kalman, non-fused) velocity state — Area 5/NEW-1. Separate
  // from prevRadialX/Z above (which track the final resolved position across
  // all modes for angle continuity) so a primary-tracker hit or a mode/gap
  // discontinuity can invalidate just this path without disturbing the other.
  private fallbackVelPrevX: number | null = null;
  private fallbackVelPrevZ: number | null = null;
  private fallbackVelPrevMs = 0;
  private prevNodeModeForFallback: TargetState["node_mode"] | null = null;

  // ── Session report accumulation ──
  private reportStartTime = 0;
  private reportDistances: number[] = [];
  private reportSpeeds: number[] = [];
  private reportLabels: string[] = [];
  private reportPositionsX: number[] = [];
  private reportPositionsZ: number[] = [];
  private reportEvents: { time: number; elapsed: number; description: string; distance?: number }[] = [];
  private reportLastLabel = "";
  private reportLastMoving = false;
  private reportFrameCount = 0;
  private reportDistanceZone: "close" | "mid" | "far" = "mid";
  private reportLastEventTime = 0;
  private reportLastSummaryFrame = 0;
  private reportPeakSpeed = 0;

  initialize(server: Server, auth: AuthService) {
    this.wss = new WebSocketServer({ noServer: true });

    server.on("upgrade", async (request, socket, head) => {
      if (request.url !== "/ws") {
        return;
      }

      try {
        const authenticated = await authenticateWebSocketRequest(request, auth);
        if (!authenticated) {
          socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
          socket.destroy();
          return;
        }

        this.wss?.handleUpgrade(request, socket, head, (ws) => {
          this.wss?.emit("connection", ws, request, authenticated.username);
        });
      } catch (error) {
        console.error("[WS] Upgrade authentication failed:", error);
        socket.write("HTTP/1.1 500 Internal Server Error\r\n\r\n");
        socket.destroy();
      }
    });

    this.wss.on("connection", (ws: WebSocket, request, username?: string) => {
      const clientId = randomUUID();
      this.clients.set(clientId, { ws, id: clientId, username });

      console.log(`Client connected: ${clientId} (${username ?? "unknown"})`);

      // Send initial state
      this.sendToClient(clientId, "status", this.status);
      this.sendToClient(clientId, "config", this.config);
      this.sendLiveSnapshotToClient(clientId);
      this.sendToClient(clientId, "targetState", this.currentTargetState);
      this.sendToClient(clientId, "targetDebug", this.currentTargetDebug);
      this.sendToClient(clientId, "recordingStatus", {
        isRecording: this.isRecording,
        sampleCount: this.recordingBuffer.length,
        durationMs: this.isRecording
          ? Date.now() - this.recordingStartTime
          : 0,
      });

      ws.on("message", (data: Buffer) => {
        try {
          const message = JSON.parse(data.toString());
          this.handleMessage(clientId, message);
        } catch (e) {
          console.error("Failed to parse message:", e);
        }
      });

      ws.on("close", () => {
        console.log(`Client disconnected: ${clientId}`);
        this.clients.delete(clientId);
      });

      ws.on("error", (error: Error) => {
        console.error(`WebSocket error for ${clientId}:`, error);
        this.clients.delete(clientId);
      });
    });

    console.log("WebSocket server initialized");
  }

  private handleMessage(
    clientId: string,
    message: { type: string; data: unknown }
  ) {
    console.log(`[WS] handleMessage from ${clientId}: ${message.type}`);
    const client = this.clients.get(clientId);
    switch (message.type) {
      case "startProcessing":
        this.currentSessionName = (message.data as any)?.customName || "";
        this.status.sessionName = this.currentSessionName;
        this.startProcessing();
        void this.auditClientAction(client, "processing_started", {
          sessionName: this.currentSessionName || undefined,
          dataSource: this.status.dataSource,
        });
        break;
      case "stopProcessing":
        this.stopProcessing();
        void this.auditClientAction(client, "processing_stopped");
        break;
      case "updateConfig":
        this.updateConfig(message.data as Partial<ProcessingConfig>);
        void this.auditClientAction(client, "config_updated");
        break;
      case "setDataSource":
        this.setDataSource(message.data as DataSource);
        void this.auditClientAction(client, "data_source_changed", { dataSource: message.data });
        break;
      case "startRecording":
        this.startRecording();
        void this.auditClientAction(client, "recording_started");
        break;
      case "stopRecording":
        this.stopRecording();
        void this.auditClientAction(client, "recording_stopped");
        break;
      case "markSyncEvent":
        this.markSyncEvent();
        void this.auditClientAction(client, "recording_sync_marked");
        break;
      case "setGroundTruthPoint":
        this.setGroundTruthPoint(message.data);
        void this.auditClientAction(client, "ground_truth_point_set");
        break;
      case "clearGroundTruthPoint":
        this.activeGroundTruthTag = null;
        void this.auditClientAction(client, "ground_truth_point_cleared");
        break;
      case "registerAIClient":
        if (client) {
          client.isAI = true;
          console.log(`[WS] Registered AI Inference client: ${clientId}`);
        }
        break;
      case "poseFrame":
        // PS-AUDIT-014: only a client that completed "registerAIClient" may
        // publish pose frames — there is no deterministic source for this
        // channel, so any authenticated client could otherwise inject a
        // fake skeleton into every connected dashboard. Also only relay
        // while actively processing (prevents OOM during idle).
        if (client?.isAI && this.status.isProcessing) {
          this.currentPoseFrame = (message.data as PoseFrame) ?? null;
          this.broadcast("poseFrame", message.data);
        } else if (client && !client.isAI) {
          console.warn(`[WS][SEC] non-AI client ${clientId} sent poseFrame — ignored (PS-AUDIT-014)`);
        }
        break;
      case "targetIdentity":
        // F1 / PS-AUDIT-014: currentTargetIdentity (and the "targetIdentity"
        // broadcast) must have exactly one writer — the deterministic
        // micro-Doppler classifier in processFrame(). A client message must
        // NEVER write it, even from a registered AI client, or a model
        // output could occupy the same channel as the deterministic verdict.
        // AI advisory identity is relayed under a distinct type instead, so
        // it can never be mistaken for the authoritative classification.
        if (client?.isAI && this.status.isProcessing) {
          this.broadcast("advisoryIdentity", message.data);
        } else if (client && !client.isAI) {
          console.warn(`[WS][SEC] non-AI client ${clientId} sent targetIdentity — ignored (PS-AUDIT-014)`);
        }
        break;
      case "vitalSigns":
        // Same F1 rule as targetIdentity: currentVitalSigns is written only
        // by the deterministic VitalsComputer / board-DSP fallback in
        // processFrame(). AI advisory vitals are relayed under a distinct
        // type and never touch the authoritative channel.
        if (client?.isAI && this.status.isProcessing) {
          this.broadcast("advisoryVitalSigns", message.data);
        } else if (client && !client.isAI) {
          console.warn(`[WS][SEC] non-AI client ${clientId} sent vitalSigns — ignored (PS-AUDIT-014)`);
        }
        break;
    }
  }

  private async auditClientAction(client: WSClient | undefined, eventType: string, details?: Record<string, unknown>) {
    if (!client?.username) {
      return;
    }

    await auditLogger.log({
      event_type: eventType,
      success: true,
      username: client.username,
      details: {
        protocol: "websocket",
        ...details,
      },
    });
  }

  private startProcessing() {
    console.log(`[WS] startProcessing called, isProcessing=${this.status.isProcessing}, interval=${!!this.processingInterval}`);
    if (this.status.isProcessing) return;

    // Defensively clear any stale interval
    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
    }

    this.isStopping = false;
    this.status.isProcessing = true;
    this.heatmapAccumulator.reset();
    this.backgroundSubtractor.reset();
    this.motionGate.reset();
    this.dopplerComputer.reset();
    this.trackingProcessor.reset();
    this.sampleBuffer = [];
    this.pointCloudHistory = [];
    this.nextHardwareQueueIndex = 0;
    this.lastTruthfulTargetUpdateMs = 0;
    this.clearTargetArtifacts("processing_started");

    // Reset report accumulation
    this.reportStartTime = Date.now();
    this.reportDistances = [];
    this.reportSpeeds = [];
    this.reportLabels = [];
    this.reportPositionsX = [];
    this.reportPositionsZ = [];
    this.reportEvents = [];
    this.reportLastLabel = "";
    this.reportLastMoving = false;
    this.reportFrameCount = 0;
    this.reportDistanceZone = "mid";
    this.reportLastEventTime = 0;
    this.reportLastSummaryFrame = 0;
    this.reportPeakSpeed = 0;

    // Session start event
    this.reportEvents.push({
      time: Date.now(),
      elapsed: 0,
      description: `Session started — data source: ${this.status.dataSource}`,
    });

    this.broadcast("status", this.status);

    // Session header: log the active anchor geometry so replays/reports are
    // interpretable (same discipline as adapter logging).
    console.log(
      `[NODES] anchors N1=(${NODE_ANCHORS[1].x},${NODE_ANCHORS[1].z}) ` +
        `N2=(${NODE_ANCHORS[2].x},${NODE_ANCHORS[2].z}) sep=${NODE_SEPARATION_M}m`,
    );

    // Process at ~20 FPS
    this.processingInterval = setInterval(() => {
      this.processFrame();
    }, 50);

    // Auto-start recording
    this.startRecording();

    console.log("[WS] Processing started, interval created");
  }

  private stopProcessing() {
    console.log(`[WS] stopProcessing called, isProcessing=${this.status.isProcessing}, interval=${!!this.processingInterval}`);

    // Always try to clear the interval, even if isProcessing is false
    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
      console.log("[WS] Interval cleared");
    }

    // Auto-stop recording
    this.stopRecording();

    // Auto-save session to persistent storage
    if (this.reportFrameCount > 0 && this.reportStartTime > 0) {
      try {
        // Add session stopped event
        const elapsed = (Date.now() - this.reportStartTime) / 1000;
        this.reportEvents.push({
          time: Date.now(),
          elapsed,
          description: `Session ended — ${this.reportFrameCount} frames processed in ${elapsed.toFixed(1)}s`,
        });

        const report = this.getSessionReport() as any;
        report.dataSource = this.status.dataSource;
        sessionStore.save(report, this.currentSessionName);
      } catch (err) {
        console.error("[SESSION] Failed to save session:", err);
      }
    }

    this.isStopping = true;
    this.status.isProcessing = false;
    this.status.sessionName = "";
    this.status.lastUpdate = Date.now();
    this.clearTargetArtifacts("processing_stopped");
    // Quiesce the radar immediately: beacons drop motion glow and
    // distance/trend labels (buildSensorNodes returns idle nodes when stopped).
    this.broadcastNodes();

    this.broadcast("status", this.status);

    this.isStopping = false;

    console.log("[WS] Processing stopped, isProcessing=false broadcast sent");
  }
  private updateConfig(updates: Partial<ProcessingConfig>) {
    this.config = { ...this.config, ...updates };
    if (updates.clutterWindowSize !== undefined) {
      this.backgroundSubtractor.setWindowSize(updates.clutterWindowSize);
    }

    // Persist operator-adjusted motion thresholds so a restart doesn't revert
    // to the code default (see runtime-settings.ts).
    if (
      updates.fusedTargetMotionThreshold !== undefined ||
      updates.motionThreshold !== undefined
    ) {
      saveRuntimeSettings({
        fusedTargetMotionThreshold: updates.fusedTargetMotionThreshold,
        motionThreshold: updates.motionThreshold,
      });
    }

    this.broadcast("config", this.config);
  }

  private setDataSource(source: DataSource) {
    void source;
    this.status.dataSource = "esp32";
    this.status.source = "live";
    this.status.synthetic_enabled = false;
    this.status.lastUpdate = Date.now();

    // Clear buffers when switching modes
    this.sampleBuffer = [];
    this.hardwareSampleQueue = [];
    this.hardwareNodeLastSeenMs.clear();
    this.nextHardwareQueueIndex = 0;
    this.backgroundSubtractor.reset();
    this.motionGate.reset();
    this.dopplerComputer.reset();
    this.trackingProcessor.reset();
    this.vitalsComputer.reset();
    this.lastTruthfulTargetUpdateMs = 0;
    this.clearTargetArtifacts(`data_source_${source}`);

    this.broadcast("status", this.status);
  }

  // ── Recording ──────────────────────────────────────────────────

  private startRecording() {
    if (this.isRecording) return;
    this.isRecording = true;
    this.recordingBuffer = [];
    this.recordingStartTime = Date.now();
    this.recordingSessionMeta = buildRecordingSessionMeta({
      sessionName: this.currentSessionName || "session",
      recordingStartMs: this.recordingStartTime,
      node1Fps: this.nodeFpsFor(1),
      node2Fps: this.nodeFpsFor(2),
      scalarMotionThreshold: this.config.motionThreshold,
      fusedMotionThreshold: this.config.fusedTargetMotionThreshold,
    });
    this.pendingSyncMarker = false;
    this.lastSyncAtMs = undefined;

    console.log("[REC] Recording started");
    this.broadcastRecordingStatus();
  }

  private stopRecording() {
    if (!this.isRecording) return;
    this.isRecording = false;

    const sampleCount = this.recordingBuffer.length;
    const durationMs = Date.now() - this.recordingStartTime;

    // Serialize to CSV
    if (sampleCount > 0) {
      try {
        this.lastRecordingFile = this.serializeToCSV();
        console.log(
          `[REC] Recording saved: ${sampleCount} samples, ${(durationMs / 1000).toFixed(1)}s → ${this.lastRecordingFile}`
        );
        this.triggerReportGeneration(this.lastRecordingFile);
      } catch (err) {
        console.error("[REC] Failed to save recording:", err);
      }
    } else {
      console.log("[REC] No samples recorded");
    }

    this.broadcastRecordingStatus();
  }

  private triggerReportGeneration(csvPath: string) {
    console.log(`[REPORT] Triggering auto-report generation for: ${csvPath}`);
    const scriptPath = path.resolve("scripts", "reporting", "session_reporter.py");
    const python = this.resolvePythonCommand();
    const pythonProc = spawn(python.command, [...python.args, scriptPath, csvPath], {
      shell: false,
    });

    pythonProc.stdout.on('data', (data: Buffer) => {
      console.log(`[REPORT] STDOUT: ${data.toString().trim()}`);
    });

    pythonProc.stderr.on('data', (data: Buffer) => {
      console.error(`[REPORT] STDERR: ${data.toString().trim()}`);
    });

    pythonProc.on('close', (code: number) => {
      console.log(`[REPORT] Python process exited with code ${code}`);
      if (code === 0) {
        this.broadcast("reportReady", { file: csvPath });
      }
    });
  }

  private resolvePythonCommand(): { command: string; args: string[] } {
    if (process.env.PHANTOM_PYTHON) {
      return { command: process.env.PHANTOM_PYTHON, args: [] };
    }

    if (process.env.PYTHON) {
      return { command: process.env.PYTHON, args: [] };
    }

    if (process.platform === "win32") {
      return { command: "py", args: ["-3"] };
    }

    return { command: "python3", args: [] };
  }

  private broadcastRecordingStatus() {
    this.broadcast("recordingStatus", {
      isRecording: this.isRecording,
      sampleCount: this.recordingBuffer.length,
      durationMs: this.isRecording
        ? Date.now() - this.recordingStartTime
        : 0,
      lastFile: this.lastRecordingFile ? path.basename(this.lastRecordingFile) : undefined,
      lastSyncAtMs: this.lastSyncAtMs,
    });
  }

  private serializeToCSV(): string {
    const dir = path.resolve("data", "sessions");
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const safeName = (this.currentSessionName || "session").replace(/[^a-z0-9_-]/gi, '_');
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const filePath = path.join(dir, `${safeName}_${ts}.csv`);

    const csv = serializeRecordingCsv(
      this.recordingBuffer,
      this.recordingSessionMeta ?? buildRecordingSessionMeta({
        sessionName: this.currentSessionName || "session",
        recordingStartMs: this.recordingStartTime,
        node1Fps: this.nodeFpsFor(1),
        node2Fps: this.nodeFpsFor(2),
        scalarMotionThreshold: this.config.motionThreshold,
        fusedMotionThreshold: this.config.fusedTargetMotionThreshold,
      }),
    );

    fs.writeFileSync(filePath, csv, "utf-8");
    this.recordingBuffer = [];
    this.recordingSessionMeta = null;

    return filePath;
  }

  // ── Main processing pipeline ───────────────────────────────────

  /**
   * The ~20 FPS detection loop (one queued hardware sample per tick).
   * Full stage order: live-gap/freshness guards → background subtraction →
   * MotionGate → vitals phase → Doppler → MUSIC AoA → point cloud →
   * DBSCAN+Kalman tracking → micro-Doppler classification → PDP ranging →
   * two-node fusion (presence gate) → buildTargetState → WebSocket broadcasts.
   * Everything the frontend renders about the target originates here.
   */
  private processFrame() {
    if (!this.status.isProcessing || this.isStopping) {
      return;
    }

    let sample: CSISample;

    // Ghost-target fix: with zero fresh nodes (none seen ≤1.5 s) there is no
    // live truth — purge any backlog and take the live-gap path immediately,
    // instead of replaying up to ~50 s of stale queued samples.
    if (this.activeHardwareNodeIds().length === 0) {
      if (this.hardwareSampleQueue.length > 0) {
        this.hardwareSampleQueue = [];
        this.nextHardwareQueueIndex = 0;
      }
      this.handleLiveGap();
      this.status.lastUpdate = Date.now();
      if (this.status.framesProcessed % 20 === 0) {
        this.broadcast("status", this.status);
      }
      return;
    }

    // Drop stale backlog samples at dequeue: only frames received within the
    // live stale window may drive the pipeline.
    const nowMs = Date.now();
    let queuedSample = this.dequeueHardwareSample();
    while (queuedSample && !isSampleFresh(queuedSample, nowMs)) {
      queuedSample = this.dequeueHardwareSample();
    }
    if (queuedSample) {
      sample = queuedSample;
      this.lastProcessedSampleMs = Date.now();
    } else {
      this.handleLiveGap();
      this.status.lastUpdate = Date.now();
      if (this.status.framesProcessed % 20 === 0) {
        this.broadcast("status", this.status);
      }
      return;
    }

    // Bound the backlog: keep only the newest 1000 samples so a burst can
    // never make the pipeline lag arbitrarily far behind real time.
    if (this.hardwareSampleQueue.length > 1000) {
      this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
      this.nextHardwareQueueIndex = Math.min(
        this.nextHardwareQueueIndex,
        this.hardwareSampleQueue.length - 1
      );
    }

    this.status.samplesReceived++;

    // ── 1. Background subtraction (clutter removal) ──
    let h1Proc = sample.h1;
    let h2Proc = sample.h2;
    let dynamicAmplitude = 0;

    if (this.config.clutterRemovalEnabled) {
      const dynamic = this.backgroundSubtractor.process(sample.h1, sample.h2);
      h1Proc = dynamic.h1Dynamic;
      h2Proc = dynamic.h2Dynamic;
      dynamicAmplitude = magnitude(h1Proc);
    } else {
      dynamicAmplitude = magnitude(sample.h1);
    }

    // ── 2. Motion gate ──
    const motionResult = this.motionGate.update(
      dynamicAmplitude,
      this.config.motionGateEnabled ? this.config.motionThreshold : undefined
    );

    // Broadcast motion status every frame
    this.broadcast("motionStatus", motionResult);

    // Motion-gate now affects motion classification only.
    // A stationary but truthful target should remain visible as idle/degraded,
    // not disappear entirely.

    // ── 3. Bypass Nulling (pass-through clutter-removed signal) ──
    const estimate: ChannelEstimate = {
      timestamp: sample.timestamp,
      h1: sample.h1,
      h2: sample.h2,
      precodingRatio: { re: 0, im: 0 },
      nulledSignal: h1Proc,
    };

    this.broadcast("csiFrame", estimate);

    // ── 3.5 Vitals Phase Extraction ──
    // Multiply H1 by the conjugate of H2 to remove CFO and extract relative phase
    const h1_conj_h2 = mul(h1Proc, conj(h2Proc));
    const currentPhase = phase(h1_conj_h2);
    this.vitalsComputer.push(currentPhase);

    // ── 4. Doppler spectrogram ──
    this.dopplerComputer.addSample(estimate.timestamp, dynamicAmplitude);
    if (this.status.framesProcessed % 3 === 0) {
      // Broadcast every 3rd frame to reduce load
      this.broadcast("dopplerFrame", this.dopplerComputer.getData());
    }

    // ── 5. MUSIC spectrum (on clutter-removed signal buffer) ──
    this.sampleBuffer.push(estimate.nulledSignal);
    if (this.sampleBuffer.length > this.config.arrayLength) {
      this.sampleBuffer.shift();
    }

    let currentRadX = 0;
    let currentRadZ = 0;
    let currentSpeed = 0;
    let currentLabel = "";
    let currentDistanceCm = 0;

    if (
      this.config.isarEnabled &&
      this.sampleBuffer.length >= this.config.arrayLength
    ) {
      const spectrum = computeMUSICSpectrum(
        this.sampleBuffer,
        this.config.aoaRangeMin,
        this.config.aoaRangeMax
      );

      const peak = findSpectrumPeak(spectrum);

      const isarFrame = {
        timestamp: estimate.timestamp,
        spectrum,
        peakAngle: peak.angle,
        peakPower: peak.power,
      };

      this.broadcast("isarFrame", isarFrame);

      // Heatmap: time × subcarrier amplitude waterfall from the real
      // per-subcarrier vector (dB). Skipped when a packet carried no vector.
      if (sample.amplitudes && sample.amplitudes.length > 0) {
        this.heatmapAccumulator.addSpectrum(
          estimate.timestamp,
          sample.amplitudes.map((a, i) => ({
            angle: i,
            power: 20 * Math.log10(Math.max(a, 1e-3)),
          })),
        );
        this.broadcast("heatmap", this.heatmapAccumulator.getData());
      }

      // ── 6. Point cloud from spectrum ──
      const pointCloud: {
        x: number;
        y: number;
        z: number;
        amplitude: number;
        timestamp: number;
      }[] = [];
      const maxPower = Math.max(...spectrum.map((s) => s.power));
      const pThreshold = maxPower - 10;

      for (const sp of spectrum) {
        if (sp.power > pThreshold) {
          const relPower = Math.max(0, sp.power - pThreshold) / 10;
          const dist = 1 + (1 - relPower) * 4;
          const thetaRad = (sp.angle * Math.PI) / 180;
          pointCloud.push({
            x: -dist * Math.sin(thetaRad),
            z: dist * Math.cos(thetaRad),
            // Single-antenna CSI carries no elevation information — points
            // stay on the ground plane instead of a fabricated sine wobble.
            y: 0,
            amplitude: Math.pow(10, sp.power / 20),
            timestamp: estimate.timestamp,
          });
        }
      }

      // Broadcast point cloud
      this.pointCloudHistory.push(...pointCloud);
      if (this.pointCloudHistory.length > 200) {
        this.pointCloudHistory = this.pointCloudHistory.slice(-200);
      }
      this.broadcast("pointCloud", this.pointCloudHistory);

      // ── 7. Advanced Tracking (DBSCAN + Kalman) ──
      const trackedTarget = this.trackingProcessor.process(pointCloud);
      if (trackedTarget) {
        this.currentTrackedTarget = trackedTarget;
        this.broadcast("trackedTarget", trackedTarget);
      } else {
        this.currentTrackedTarget = null;
        this.broadcast("trackedTarget", null);
      }

      // ── 10. Micro-Doppler Classification ──
      const dynamicAmp = magnitude({
        re: h1Proc.re - sample.h1.re,
        im: h1Proc.im - sample.h1.im,
      });
      const classification = this.microDopplerClassifier.push(dynamicAmp);

      // ── 11. PDP Ranging ──
      const pdpResult = this.pdpRanger.push(h1Proc, h2Proc, sample.rssi ?? -50);

      // ── 9. Radial Target (ESP-Centric Coordinates) ──
      // Use MUSIC peak angle as bearing θ, tracked target distance as r
      const thetaRad = (peak.angle * Math.PI) / 180;
      // Distance estimate: use actual PDP ranging distance in meters
      const r = pdpResult.distanceCm / 100;

      // Polar → Cartesian (array center at origin; +x = east, +z = north).
      // MUSIC AoA sign: positive AoA maps west (-x) per antenna calibration.
      // The broadcast `theta` is recomputed from x/z as a compass bearing
      // (shared/bearing.ts) so it stays consistent with position by construction.
      const rawRadX = -r * Math.sin(thetaRad);
      const rawRadZ = r * Math.cos(thetaRad);

      let radX = rawRadX;
      let radZ = rawRadZ;
      let targetVx = 0;
      let targetVz = 0;
      let speed = 0;

      // Computed early (moved up from below the fallback block) so the
      // fallback path can detect a fused_two_node <-> single_node flip
      // before deciding whether to trust its own dt-tracking state.
      const nodeMode = this.resolveLiveNodeMode();
      if (this.prevNodeModeForFallback !== null && this.prevNodeModeForFallback !== nodeMode) {
        this.invalidateFallbackVelocity();
      }
      this.prevNodeModeForFallback = nodeMode;

      if (trackedTarget) {
        // Use smooth coordinates and bounded velocity from Kalman Filter
        radX = trackedTarget.x;
        radZ = trackedTarget.z;
        targetVx = trackedTarget.vx;
        targetVz = trackedTarget.vz;
        speed = Math.sqrt(targetVx * targetVx + targetVz * targetVz);
        // Primary tracker succeeded this tick — the fallback path below can
        // be skipped for many ticks with none of the other reset conditions
        // firing, so invalidate now: a later primary-miss must never diff
        // against a stale sample from before this gap (NEW-1, 5th condition).
        this.invalidateFallbackVelocity();
      } else {
        // Fallback: instantaneous physics from the raw (non-Kalman) position.
        // computeFallbackVelocity is pure/unit-tested (node-fusion.test.ts);
        // this class only owns the prev-sample state and the invalidation
        // triggers (mode flip above, primary-tracker success above, and the
        // 5s hard-clear/1.5s stale-hold lifecycle via clearTargetArtifacts).
        const nowFallbackMs = Date.now();
        const prevSample =
          this.fallbackVelPrevX === null || this.fallbackVelPrevZ === null
            ? null
            : { x: this.fallbackVelPrevX, z: this.fallbackVelPrevZ, atMs: this.fallbackVelPrevMs };
        const result = computeFallbackVelocity(prevSample, { x: rawRadX, z: rawRadZ }, nowFallbackMs);
        targetVx = result.vx;
        targetVz = result.vz;
        speed = result.speed;
        this.fallbackVelPrevX = rawRadX;
        this.fallbackVelPrevZ = rawRadZ;
        this.fallbackVelPrevMs = nowFallbackMs;
      }

      // ── 9b. Two-node fusion (Phantom Balance Fusion) — replaces the single-node guess ──
      // In fused_two_node mode the target is placed on the N1–N2 line by the
      // cross-node motion ratio. `r`/`theta` become display-only; `distanceCm`
      // stays physically meaningful (range to the nearest node).
      const fused = nodeMode === "fused_two_node" ? this.computeFusedTarget() : null;
      let fusedBalance: number | undefined;
      let fusedBalanceLinear: number | undefined;
      let fusedDistanceCm = pdpResult.distanceCm;
      let fusedConfidence: number | undefined;
      if (fused) {
        radX = fused.x;
        radZ = fused.z;
        // Snapshot is the single source both broadcasts read this tick.
        const velMps = this.updateFusedSnapshot(fused.balance, fused.x);
        targetVx = velMps;
        targetVz = 0;
        speed = Math.abs(velMps); // m/s along the axis
        fusedBalance = fused.balance;
        fusedBalanceLinear = fused.balanceLinear;
        fusedDistanceCm = fused.distToNearestNodeM * 100;
        fusedConfidence = fused.maxMotion; // position/signal confidence (NOT humanProb)
      }

      // MOVING/STILL decision for this frame. `projectedMotion` is a separate
      // speed gate that only controls whether the heading arrow is allowed to
      // rotate (lower 0.035 m/s bar in fused mode because axis velocity is
      // already damped). `isMoving` trusts the two-node fusion result when
      // present: fuseTwoNodeTarget() only returns non-null after real
      // cross-node perturbation already cleared fusedTargetMotionThreshold,
      // so a fused target is by construction moving — falling back to the
      // decoupled single-antenna MotionGate here (as before) silently
      // downgraded real motion to "idle". Single-node mode is unaffected
      // (fused is always null there, and its state is hardcoded "degraded"
      // regardless of isMoving).
      const projectedMotion = speed > (fused ? 0.035 : 0.05);
      const isMoving = fused ? true : motionResult.motionDetected;

      // Direction of travel (smooth): exponential blend of the travel angle
      // (30% per frame) with wrap-around handling so the arrow turns smoothly
      // instead of snapping between noisy instantaneous headings.
      if (projectedMotion && speed > 0.02) {
        const rawAngle = Math.atan2(targetVz, targetVx);
        const angleDiff = rawAngle - this.radialAngle;
        const wrapped = Math.atan2(Math.sin(angleDiff), Math.cos(angleDiff));
        this.radialAngle += wrapped * 0.3;
      }

      // Broadcast target identity
      this.currentTargetIdentity = classification;
      this.broadcast("targetIdentity", classification);

      const radialTarget: RadialTarget = {
        x: radX,
        z: radZ,
        // r/theta are derived from x/z so they can never disagree with the
        // rendered position. theta = compass bearing (0 = north, +π/2 = east).
        r: fused ? Math.hypot(radX, radZ) : r,
        theta: compassBearingRad(radX, radZ),
        vx: targetVx,
        vz: targetVz,
        isMoving,
        angle: this.radialAngle,
        speed,
        confidence: fused ? fusedConfidence! : trackedTarget ? trackedTarget.confidence : 0.8,
        label: classification.label,
        humanProb: classification.humanProb,
        distanceCm: fusedDistanceCm,
        wallDistance: pdpResult.wallDistance,
        balance: fusedBalance,
        balanceLinear: fusedBalanceLinear,
      };

      if (nodeMode === "fused_two_node" && !fused) {
        // Two nodes active but this window's cross-node perturbation didn't
        // clear the motion gate. Reset the node-specific balance/trend
        // labels immediately, but HOLD the last known target through the
        // same live→stale_hold(1.5s)→cleared(5s) lifecycle used for a live
        // gap — a single sub-threshold window (a pause mid-stride, a turn)
        // must not instantly wipe the whole scene. Only a sustained absence
        // of real detections empties the room (empty-room negative-control
        // gate still holds after the 5s clear timeout).
        this.clearFusedSnapshot();
        this.holdOrClearTarget({
          hold: "fused_below_motion_threshold_hold",
          staleHold: "fused_below_motion_threshold_stale_hold",
          cleared: "fused_below_motion_threshold_cleared",
          empty: "fused_below_motion_threshold",
        });
      } else {
        this.currentRadialTarget = radialTarget;
        this.broadcast("radialTarget", radialTarget);
        this.lastTruthfulTargetUpdateMs = Date.now();
        this.broadcastTargetState(
          buildTargetState({
            dataSource: this.status.dataSource,
            nowMs: this.lastTruthfulTargetUpdateMs,
            lastTruthfulUpdateMs: this.lastTruthfulTargetUpdateMs,
            nodeMode,
            radialTarget,
            motionStatus: motionResult,
          }),
        );
      }

      // ── Report data accumulation ──
      // (reportFrameCount is incremented once per processed frame at the end
      // of processFrame — counting here too double-counted ISAR frames.)
      this.reportDistances.push(pdpResult.distanceCm);
      this.reportSpeeds.push(speed);
      this.reportPositionsX.push(radX);
      this.reportPositionsZ.push(radZ);
      this.reportLabels.push(classification.label);

      const now = Date.now();
      const elapsed = (now - this.reportStartTime) / 1000;
      const distM = pdpResult.distanceCm / 100;

      // ── Event: First classification detected ──
      if (classification.label !== "unknown" && this.reportLastLabel === "") {
        this.reportEvents.push({
          time: now, elapsed,
          description: `First classification: '${classification.label}' detected at ${distM.toFixed(1)}m`,
          distance: pdpResult.distanceCm,
        });
      }

      // ── Event: Classification change ──
      if (classification.label !== "unknown" && this.reportLastLabel !== "" && classification.label !== this.reportLastLabel) {
        this.reportEvents.push({
          time: now, elapsed,
          description: `Classification changed: '${this.reportLastLabel}' → '${classification.label}'`,
          distance: pdpResult.distanceCm,
        });
      }
      if (classification.label !== "unknown") {
        this.reportLastLabel = classification.label;
      }

      // ── Event: Motion start/stop ──
      if (isMoving && !this.reportLastMoving) {
        this.reportEvents.push({ time: now, elapsed, description: "Target started moving", distance: pdpResult.distanceCm });
      } else if (!isMoving && this.reportLastMoving) {
        this.reportEvents.push({ time: now, elapsed, description: "Target stopped — stationary", distance: pdpResult.distanceCm });
      }
      this.reportLastMoving = isMoving;

      // ── Event: Distance zone transitions ──
      const newZone: "close" | "mid" | "far" = distM < 1.5 ? "close" : distM > 4.0 ? "far" : "mid";
      if (newZone !== this.reportDistanceZone && (now - this.reportLastEventTime > 2000)) {
        const zoneNames = { close: "Close range (<1.5m)", mid: "Mid range (1.5–4m)", far: "Far range (>4m)" };
        this.reportEvents.push({
          time: now, elapsed,
          description: `Entered ${zoneNames[newZone]} — distance: ${distM.toFixed(2)}m`,
          distance: pdpResult.distanceCm,
        });
        this.reportDistanceZone = newZone;
        this.reportLastEventTime = now;
      }

      // ── Event: Speed spike ──
      if (speed > this.reportPeakSpeed * 1.5 && speed > 5 && (now - this.reportLastEventTime > 3000)) {
        this.reportEvents.push({
          time: now, elapsed,
          description: `Speed spike detected: ${speed.toFixed(1)} m/s (new peak)`,
          distance: pdpResult.distanceCm,
        });
        this.reportLastEventTime = now;
      }
      if (speed > this.reportPeakSpeed) {
        this.reportPeakSpeed = speed;
      }

      // ── Event: Periodic summary every 200 frames (~10s) ──
      if (this.reportFrameCount - this.reportLastSummaryFrame >= 200) {
        const recentDist = this.reportDistances.slice(-200);
        const recentSpeed = this.reportSpeeds.slice(-200);
        const avgD = recentDist.reduce((s, v) => s + v, 0) / recentDist.length / 100;
        const avgS = recentSpeed.reduce((s, v) => s + v, 0) / recentSpeed.length;
        this.reportEvents.push({
          time: now, elapsed,
          description: `Position update — avg distance: ${avgD.toFixed(2)}m, avg speed: ${avgS.toFixed(1)} m/s, zone: ${newZone}`,
          distance: pdpResult.distanceCm,
        });
        this.reportLastSummaryFrame = this.reportFrameCount;
      }

      currentRadX = radX;
      currentRadZ = radZ;
      currentSpeed = speed;
      currentLabel = classification.label;
      currentDistanceCm = pdpResult.distanceCm;
    }

    if (
      (!this.config.isarEnabled || this.sampleBuffer.length < this.config.arrayLength) &&
      this.currentTargetState.target_visible
    ) {
      this.clearTargetArtifacts("insufficient_window");
      this.broadcastTargetState(
        emptyTargetState({
          dataSource: this.status.dataSource,
          nowMs: Date.now(),
          lastTruthfulUpdateMs: this.lastTruthfulTargetUpdateMs || undefined,
          nodeMode: this.resolveLiveNodeMode(),
          motionStatus: motionResult,
          reason: "insufficient_window",
        }),
      );
    }

    // ── Record sample with metadata if recording ──
    if (this.isRecording) {
      // Cap at 5000 samples to prevent unbounded memory growth
      if (this.recordingBuffer.length < 5000) {
        const motion1 = this.nodeMotionFor(1).motion;
        const motion2 = this.nodeMotionFor(2).motion;
        this.recordingBuffer.push(
          buildRecordingRow({
            sample: {
              ...sample,
              amplitudes: undefined,
            },
            sessionStartMs: this.recordingStartTime,
            radialTarget: this.currentRadialTarget,
            targetState: this.currentTargetState,
            fusedSnapshot: this.fusedSnapshot,
            nodeMotion: { 1: motion1, 2: motion2 },
            nodeFps: { 1: this.nodeFpsFor(1), 2: this.nodeFpsFor(2) },
            syncMarker: this.pendingSyncMarker,
            groundTruthTag: this.activeGroundTruthTag,
          }),
        );
        this.pendingSyncMarker = false;
      }
      // Broadcast recording status every 50 samples
      if (this.recordingBuffer.length % 50 === 0) {
        this.broadcastRecordingStatus();
      }
    }

    this.reportFrameCount++;
    this.status.framesProcessed++;
    this.status.lastUpdate = Date.now();

    if (this.status.framesProcessed % 10 === 0) {
      // ~2 Hz node-marker refresh (positions + per-node motion glow).
      this.broadcastNodes();
    }

    if (this.status.framesProcessed % 20 === 0) {
      this.broadcast("status", this.status);

      // Calculate and broadcast vitals. With single-antenna boards h2 is a
      // duplicate of h1, so the host phase (H1·conj(H2)) is identically zero
      // and host vitals can never become reliable — fall back to the
      // board-computed firmware vitals when they are fresh and confident.
      let vitals = this.vitalsComputer.computeVitals();
      if (!vitals.vitalsReliable) {
        const board = this.boardVitalsFallback();
        if (board) vitals = board;
      }
      this.currentVitalSigns = vitals;
      this.broadcast("vitalSigns", vitals);
    }
  }

  /**
   * Best fresh board-DSP vitals (0xC5110002/0xC5110006 packets) as a
   * VitalSigns substitute when the host-side phase pipeline cannot deliver
   * (single-antenna hardware). Returns null when no board reports confident
   * vitals within the freshness window.
   */
  private boardVitalsFallback(): VitalSigns | null {
    // 0.3 floor: with real board confidences (autocorr peak ratios from the
    // new firmware) a noise-floor estimate must not surface as "reliable"
    // vitals. Old firmware reports conf 1 for any estimate, which passes.
    const feats = this.buildNodeFeatureStates().filter(
      (f) =>
        (f.resp_conf >= 0.3 && f.resp_bpm > 0) ||
        (f.hr_conf >= 0.3 && f.hr_bpm > 0),
    );
    if (feats.length === 0) return null;
    const best = feats.reduce((a, b) =>
      b.resp_conf + b.hr_conf > a.resp_conf + a.hr_conf ? b : a,
    );
    return {
      heartRateBpm: Math.round(best.hr_bpm),
      respirationRateRpm: Math.round(best.resp_bpm),
      vitalsReliable: true,
    };
  }

  // ── Messaging ──────────────────────────────────────────────────

  private sendToClient(clientId: string, type: string, data: unknown) {
    const client = this.clients.get(clientId);
    if (client && client.ws.readyState === WebSocket.OPEN) {
      client.ws.send(JSON.stringify({ type, data }));
    }
  }

  private broadcast(type: string, data: unknown) {
    const message = JSON.stringify({ type, data });
    const clients = Array.from(this.clients.values());
    for (const client of clients) {
      if (client.ws.readyState === WebSocket.OPEN) {
        client.ws.send(message);
      }
    }
  }

  private sendLiveSnapshotToClient(clientId: string) {
    this.sendToClient(clientId, "pointCloud", this.pointCloudHistory);
    this.sendToClient(clientId, "trackedTarget", this.currentTrackedTarget);
    this.sendToClient(clientId, "radialTarget", this.currentRadialTarget);
    this.sendToClient(clientId, "targetIdentity", this.currentTargetIdentity);
    this.sendToClient(clientId, "poseFrame", this.currentPoseFrame);
    this.sendToClient(clientId, "vitalSigns", this.currentVitalSigns);
    this.sendToClient(clientId, "nodes", this.buildSensorNodes());
    this.sendToClient(clientId, "nodeFeatures", this.buildNodeFeatureStates());
  }

  /**
   * Ages the last truthful target through the hold lifecycle instead of
   * wiping it instantly: keep broadcasting it while live/stale_hold (≤5 s),
   * wipe every target artifact once "cleared", or report an empty state when
   * nothing was ever seen. Shared by handleLiveGap() (no fresh samples at
   * all) and the fused-two-node sub-threshold path (samples ARE arriving,
   * but this window's cross-node perturbation didn't clear the motion gate)
   * — both are "no fresh truthful detection this tick" and should degrade
   * the same way, not vanish on the very first miss.
   */
  private holdOrClearTarget(reasons: {
    hold: string;
    staleHold: string;
    cleared: string;
    empty: string;
  }) {
    const nowMs = Date.now();
    const holdState = resolveLiveHoldState(this.lastTruthfulTargetUpdateMs || null, nowMs);

    if (this.currentRadialTarget && holdState !== "cleared") {
      this.broadcastTargetState(
        buildTargetState({
          dataSource: this.status.dataSource,
          nowMs,
          lastTruthfulUpdateMs: this.lastTruthfulTargetUpdateMs,
          nodeMode: this.resolveLiveNodeMode(),
          radialTarget: this.currentRadialTarget,
          motionStatus: undefined,
          reason: holdState === "stale_hold" ? reasons.staleHold : reasons.hold,
        }),
      );
      return;
    }

    if (holdState === "cleared") {
      this.clearTargetArtifacts(reasons.cleared);
      return;
    }

    this.broadcastTargetState(
      emptyTargetState({
        dataSource: this.status.dataSource,
        nowMs,
        lastTruthfulUpdateMs: this.lastTruthfulTargetUpdateMs || undefined,
        nodeMode: this.resolveLiveNodeMode(),
        reason: reasons.empty,
      }),
    );
  }

  /**
   * Called when no fresh sample is available this tick (node silent/unplugged).
   * Prevents a disconnected node from painting a frozen ghost target.
   */
  private handleLiveGap() {
    this.holdOrClearTarget({
      hold: "live_gap_hold",
      staleHold: "stale_hold_gap",
      cleared: "live_gap_cleared",
      empty: "awaiting_live_samples",
    });
  }

  private nodeFpsFor(nodeId: number): number {
    // Same wall-clock cutoff as nodeMotionFor: a silent node's fps must decay
    // to 0 rather than freezing at its last live value.
    const cutoff = Date.now() - MOTION_WINDOW_MS;
    const win = (this.nodeAmpWindow.get(nodeId) ?? []).filter((s) => s.t >= cutoff);
    if (win.length < 2) return 0;
    const spanS = (win[win.length - 1].t - win[0].t) / 1000;
    return spanS > 0 ? Math.round((win.length / spanS) * 10) / 10 : 0;
  }

  private updateTargetDebug() {
    const nowMs = Date.now();
    this.currentTargetDebug = {
      hardware_queue_length: this.hardwareSampleQueue.length,
      last_sample_rx_ms: this.lastSampleRxMs,
      last_processed_sample_ms: this.lastProcessedSampleMs,
      last_truthful_target_update_ms: this.lastTruthfulTargetUpdateMs || null,
      target_reason: this.currentTargetState.reason,
      radial_target_present: Boolean(this.currentRadialTarget),
      tracked_target_present: Boolean(this.currentTrackedTarget),
      hold_state: resolveLiveHoldState(this.lastTruthfulTargetUpdateMs || null, nowMs),
      node_fps: { "1": this.nodeFpsFor(1), "2": this.nodeFpsFor(2) },
      node_motion: {
        "1": Math.round(this.nodeMotionFor(1).motion * 1000) / 1000,
        "2": Math.round(this.nodeMotionFor(2).motion * 1000) / 1000,
      },
    };
    this.broadcast("targetDebug", this.currentTargetDebug);
  }

  /**
   * Full scene wipe: null out and broadcast-null every target-related channel
   * (point cloud, tracked/radial target, identity, pose, vitals) and publish an
   * empty TargetState carrying `reason`, so every client removes the target at
   * the same instant instead of each aging it out independently.
   */
  private clearTargetArtifacts(reason: string) {
    this.clearFusedSnapshot();
    this.invalidateFallbackVelocity();
    this.pointCloudHistory = [];
    this.currentTrackedTarget = null;
    this.currentRadialTarget = null;
    this.currentTargetIdentity = null;
    this.currentVitalSigns = null;
    this.currentPoseFrame = null;
    this.broadcast("pointCloud", []);
    this.broadcast("trackedTarget", null);
    this.broadcast("radialTarget", null);
    this.broadcast("targetIdentity", null);
    this.broadcast("poseFrame", null);
    this.broadcast("vitalSigns", null);
    this.currentTargetState = emptyTargetState({
      dataSource: this.status.dataSource,
      nowMs: Date.now(),
      lastTruthfulUpdateMs: this.lastTruthfulTargetUpdateMs || undefined,
      nodeMode: this.resolveLiveNodeMode(),
      reason,
    });
    this.broadcast("targetState", this.currentTargetState);
    this.updateTargetDebug();
  }

  private broadcastTargetState(targetState: TargetState) {
    this.currentTargetState = targetState;
    this.broadcast("targetState", targetState);
    this.updateTargetDebug();
  }

  /** Node IDs whose last UDP packet is ≤1.5 s old — the definition of a "live" node. */
  private activeHardwareNodeIds(nowMs = Date.now()): number[] {
    const active: number[] = [];
    for (const [nodeId, lastSeenMs] of Array.from(this.hardwareNodeLastSeenMs.entries())) {
      if (nowMs - lastSeenMs <= 1500) {
        active.push(nodeId);
      }
    }
    return active.sort((a, b) => a - b);
  }

  /** fused_two_node only when BOTH boards are live; otherwise single_node (UI shows "degraded"). */
  private resolveLiveNodeMode(): TargetState["node_mode"] {
    return this.activeHardwareNodeIds().length >= 2
      ? "fused_two_node"
      : "single_node";
  }

  // ── Two-node fusion (Phantom Balance Fusion) ───────────────────────────────
  private recordNodeAmplitude(sample: CSISample): void {
    const nodeId = sample.nodeId ?? 1;
    if (nodeId !== 1 && nodeId !== 2) return; // only the two anchored nodes
    const t = sample.timestamp ?? Date.now();
    let win = this.nodeAmpWindow.get(nodeId);
    if (!win) {
      win = [];
      this.nodeAmpWindow.set(nodeId, win);
    }
    // Prefer the full per-subcarrier vector; fall back to a
    // 1-element frame from the scalar h1 for legacy/synthetic senders.
    const amps =
      sample.amplitudes && sample.amplitudes.length > 0
        ? sample.amplitudes
        : [magnitude(sample.h1)];
    win.push({ t, amps });
    const cutoff = t - MOTION_WINDOW_MS; // fixed window by timestamp (yield-independent)
    while (win.length && win[0].t < cutoff) win.shift();
    this.nodeLastRssi.set(nodeId, sample.rssi ?? -100);
  }

  private nodeMotionFor(nodeId: number) {
    // Wall-clock eviction on READ, not just on ingest: a silent (unplugged)
    // node stops receiving packets, so ingest-side eviction never runs and the
    // frozen window would keep reporting the unplug transient as motion.
    const cutoff = Date.now() - MOTION_WINDOW_MS;
    const win = (this.nodeAmpWindow.get(nodeId) ?? []).filter((s) => s.t >= cutoff);
    return computeNodeMotionFromMatrix(win.map((s) => s.amps));
  }

  /**
   * Run the two-node detector for this tick: per-node motion from the 1.5 s
   * amplitude windows → fuseTwoNodeTarget (presence gate + balance position).
   * Returns null for an empty room; maxMotion doubles as position confidence.
   */
  private computeFusedTarget(): (FusedTarget & { maxMotion: number }) | null {
    const m1 = this.nodeMotionFor(1);
    const m2 = this.nodeMotionFor(2);
    const fused = fuseTwoNodeTarget({
      // Gain-normalized (per-node absStd/mean), not raw absStd — PS-BEHTEST-004:
      // raw absStd scales linearly with any per-node gain/RSSI mismatch, which
      // biased balance toward whichever board had higher effective gain. See
      // ADR-056.
      r1: computeGainNormalizedPerturbation(m1.absStd, m1.mean),
      r2: computeGainNormalizedPerturbation(m2.absStd, m2.mean),
      motion1: m1.motion,
      motion2: m2.motion,
      anchors: { 1: NODE_ANCHORS[1], 2: NODE_ANCHORS[2] },
      motionThreshold: this.config.fusedTargetMotionThreshold,
    });
    if (!fused) return null;
    return { ...fused, maxMotion: Math.max(m1.motion, m2.motion) };
  }

  /**
   * Update the per-tick fused snapshot from a fresh balance sample.
   * Returns the signed axis velocity (m/s, >0 toward N2). Both broadcasts
   * (radialTarget and nodes) must read `this.fusedSnapshot`, never recompute.
   */
  private updateFusedSnapshot(balance: number, x: number): number {
    const now = Date.now();
    let velMps = 0;
    if (this.prevFusedX !== null && this.prevFusedMs > 0) {
      const dt = (now - this.prevFusedMs) / 1000;
      if (dt > 0) {
        // Near the endpoints the biased balance compresses displacement, which
        // under-reports speed; boost velocity up to +35% as |balance-0.5|→0.5
        // so approach/recede trends still trigger close to a node.
        const endpointStrength = Math.min(1, Math.abs(balance - 0.5) * 2);
        const endpointBoost = 1 + Math.pow(endpointStrength, 0.8) * 0.35;
        velMps = ((x - this.prevFusedX) / dt) * endpointBoost;
      }
    }
    this.prevFusedX = x;
    this.prevFusedMs = now;

    const prevTrends = this.fusedSnapshot?.trends ?? { 1: "stable" as NodeTrend, 2: "stable" as NodeTrend };
    this.fusedSnapshot = {
      balance,
      x,
      velMps,
      trends: computeNodeTrends(velMps, prevTrends),
      atMs: now,
    };
    return velMps;
  }

  private clearFusedSnapshot(): void {
    this.fusedSnapshot = null;
    this.prevFusedX = null;
    this.prevFusedMs = 0;
  }

  /**
   * Reset Area 5's fallback-velocity dt tracking so the next fallback sample
   * starts fresh (velMps=0, then re-seed) instead of diffing its position
   * against a stale previous sample across a gap it never witnessed.
   */
  private invalidateFallbackVelocity(): void {
    this.fallbackVelPrevX = null;
    this.fallbackVelPrevZ = null;
    this.fallbackVelPrevMs = 0;
  }

  private buildSensorNodes(): SensorNode[] {
    const processing = this.status.isProcessing;
    const active = new Set(this.activeHardwareNodeIds());
    // Read the SAME per-tick snapshot the radialTarget broadcast used; a stale
    // snapshot (no fused update within the live window) drops the readout.
    // When the scan is STOPPED the radar must quiesce: beacons stay (honest
    // node presence via active/rssi) but show no motion glow and no target
    // distance/trend labels.
    const snap =
      processing && this.fusedSnapshot && Date.now() - this.fusedSnapshot.atMs <= 1500
        ? this.fusedSnapshot
        : null;
    const nodes: SensorNode[] = [];
    for (const key of [1, 2] as const) {
      const anchor = NODE_ANCHORS[key];
      const motion = !processing
        ? 0
        : this.nodeMotionFor(key).motion;
      nodes.push({
        node_id: key,
        x: anchor.x,
        z: anchor.z,
        motion,
        active: active.has(key),
        rssi: this.nodeLastRssi.get(key) ?? -100,
        source: "live",
        // Along-axis distance from the fused target to THIS node.
        distanceM: snap ? Math.abs(snap.x - anchor.x) : undefined,
        trend: snap ? snap.trends[key] : "stable",
      });
    }
    return nodes;
  }

  // ── Firmware DSP feature-state (Phantom Scan feature-state packet, 0xC5110006, 1 Hz per node) ──
  // Board-side metrics kept STRICTLY separate from the host-DSP fusion path;
  // broadcast for side-by-side cross-checking in the UI only.
  private nodeFeatureStates = new Map<
    number,
    {
      rxMs: number;
      motion: number;
      presence: number;
      respBpm: number;
      respConf: number;
      hrBpm: number;
      hrConf: number;
      rssi?: number;
    }
  >();
  /** A silent board's firmware metrics must not persist past this age. */
  private static readonly NODE_FEATURE_FRESH_MS = 5000;

  ingestNodeFeatureState(feat: {
    nodeId: number;
    motion: number;
    presence: number;
    respBpm: number;
    respConf: number;
    hrBpm: number;
    hrConf: number;
    rssi?: number;
  }): void {
    this.nodeFeatureStates.set(feat.nodeId, { rxMs: Date.now(), ...feat });
    if (feat.rssi !== undefined) {
      this.nodeLastRssi.set(feat.nodeId, feat.rssi);
    }
    // 1 Hz per node on the wire — broadcasting on receipt is cheap and keeps
    // the card live even when the processing tick is idle.
    this.broadcast("nodeFeatures", this.buildNodeFeatureStates());
  }

  private buildNodeFeatureStates(): NodeFeatureState[] {
    const now = Date.now();
    const out: NodeFeatureState[] = [];
    for (const [nodeId, s] of Array.from(this.nodeFeatureStates.entries())) {
      const age = now - s.rxMs;
      if (age > SignalProcessingServer.NODE_FEATURE_FRESH_MS) continue;
      out.push({
        node_id: nodeId,
        motion: s.motion,
        presence: s.presence,
        resp_bpm: s.respBpm,
        resp_conf: s.respConf,
        hr_bpm: s.hrBpm,
        hr_conf: s.hrConf,
        age_ms: age,
        ...(s.rssi !== undefined ? { rssi: s.rssi } : {}),
      });
    }
    return out.sort((a, b) => a.node_id - b.node_id);
  }

  private broadcastNodes(): void {
    this.broadcast("nodes", this.buildSensorNodes());
    // Rebroadcast firmware metrics on the node tick so a board that goes
    // silent ages out client-side (its own 1 Hz receipts stop arriving).
    this.broadcast("nodeFeatures", this.buildNodeFeatureStates());

    // fps sanity: warn (≤ every 10 s) if an active node isn't near the ~40 fps
    // the 3 s window assumes. Ties to the firmware self-ping lineage question.
    const now = Date.now();
    if (now - this.lastNodeFpsLogMs > 10000) {
      for (const key of [1, 2] as const) {
        const win = this.nodeAmpWindow.get(key);
        if (win && win.length > 5) {
          const spanS = Math.max(0.001, (win[win.length - 1].t - win[0].t) / 1000);
          const fps = win.length / spanS;
          if (fps < 20) {
            console.warn(
              `[NODES] node ${key} ~${fps.toFixed(0)} fps (<20) — 3 s window assumes ~40 fps; check firmware self-ping yield`,
            );
          }
        }
      }
      this.lastNodeFpsLogMs = now;
    }
  }

  private markSyncEvent() {
    if (!this.isRecording) {
      this.broadcast("error", "Start recording before marking sync.");
      return;
    }

    this.pendingSyncMarker = true;
    this.lastSyncAtMs = Date.now();
    this.broadcastRecordingStatus();
    console.log("[REC] Sync marker armed for next recorded row");
  }

  private setGroundTruthPoint(data: unknown) {
    if (!data || typeof data !== "object") {
      return;
    }

    const candidate = data as {
      xM?: unknown;
      yM?: unknown;
      pointId?: unknown;
      source?: unknown;
    };

    if (
      typeof candidate.xM !== "number" ||
      typeof candidate.yM !== "number" ||
      (candidate.source !== "dwell" && candidate.source !== "video")
    ) {
      return;
    }

    this.activeGroundTruthTag = {
      xM: candidate.xM,
      yM: candidate.yM,
      pointId: typeof candidate.pointId === "string" ? candidate.pointId : undefined,
      source: candidate.source,
    };
  }

  private dequeueHardwareSample(): CSISample | undefined {
    if (this.hardwareSampleQueue.length === 0) {
      this.nextHardwareQueueIndex = 0;
      return undefined;
    }

    if (this.nextHardwareQueueIndex >= this.hardwareSampleQueue.length) {
      this.nextHardwareQueueIndex = 0;
    }

    const [sample] = this.hardwareSampleQueue.splice(this.nextHardwareQueueIndex, 1);
    const currentNodeId = sample?.nodeId ?? 1;
    const nextDifferentIndex = this.hardwareSampleQueue.findIndex(
      (queued) => (queued.nodeId ?? 1) !== currentNodeId
    );
    this.nextHardwareQueueIndex = nextDifferentIndex >= 0 ? nextDifferentIndex : 0;
    return sample;
  }

  // ── Public API ─────────────────────────────────────────────────

  getStatus(): SystemStatus {
    return this.status;
  }

  getConfig(): ProcessingConfig {
    return this.config;
  }

  getLastRecordingFile(): string | undefined {
    return this.lastRecordingFile;
  }

  private broadcastToAI(type: string, data: unknown) {
    const message = JSON.stringify({ type, data });
    const clients = Array.from(this.clients.values());
    for (const client of clients) {
      if (client.isAI && client.ws.readyState === WebSocket.OPEN) {
        client.ws.send(message);
      }
    }
  }

  // Hardware ingestion methods

  /**
   * Entry point for every parsed CSI sample from udp-server.ts. Queues it for
   * processFrame, stamps the node as "seen" (drives active/fused-mode logic),
   * appends its amplitude vector to the per-node motion window, and forwards
   * the raw sample to any connected AI sidecar client.
   */
  ingestSample(sample: CSISample): void {
    // Forward raw sample to the AI inference client
    this.broadcastToAI("rawSample", sample);

    this.hardwareSampleQueue.push(sample);
    this.hardwareNodeLastSeenMs.set(sample.nodeId ?? 1, Date.now());
    this.recordNodeAmplitude(sample);
    this.lastSampleRxMs = Date.now();
    this.status.connected = true;
    this.status.lastUpdate = this.lastSampleRxMs;
    // While stopped, don't broadcast targetDebug per UDP packet (~80/s churn
    // that makes the UI look alive); throttle to 1/s. Full rate when scanning.
    if (this.status.isProcessing) {
      this.updateTargetDebug();
    } else if (this.lastSampleRxMs - this.lastIdleDebugMs >= 1000) {
      this.lastIdleDebugMs = this.lastSampleRxMs;
      this.updateTargetDebug();
    }

    const qLen = this.hardwareSampleQueue.length;
    if (qLen === 1 || qLen % 100 === 0) {
      console.log(
        `[ESP32] Queue: ${qLen} | h1=(${sample.h1.re.toFixed(2)}, ${sample.h1.im.toFixed(2)}) h2=(${sample.h2.re.toFixed(2)}, ${sample.h2.im.toFixed(2)}) rssi=${sample.rssi ?? "N/A"}`
      );
    }

    if (this.hardwareSampleQueue.length > 1000) {
      this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
    }
  }

  ingestSamples(samples: CSISample[]): void {
    for (const sample of samples) {
      this.ingestSample(sample);
    }
  }

  getQueueLength(): number {
    return this.hardwareSampleQueue.length;
  }

  getSessionReport(): object {
    const now = Date.now();
    const durationS = this.reportStartTime > 0 ? (now - this.reportStartTime) / 1000 : 0;

    // Classification majority vote
    const labelCounts: Record<string, number> = {};
    for (const l of this.reportLabels) {
      if (l !== "unknown") labelCounts[l] = (labelCounts[l] || 0) + 1;
    }
    const dominantLabel = Object.entries(labelCounts).sort((a, b) => b[1] - a[1])[0];
    const totalValid = Object.values(labelCounts).reduce((s, v) => s + v, 0);

    // Spatial metrics
    const distances = this.reportDistances;
    const minDist = distances.length > 0 ? Math.min(...distances) : 0;
    const maxDist = distances.length > 0 ? Math.max(...distances) : 0;
    const avgDist = distances.length > 0 ? distances.reduce((s, v) => s + v, 0) / distances.length : 0;

    // Kinematic
    const speeds = this.reportSpeeds;
    const avgSpeed = speeds.length > 0 ? speeds.reduce((s, v) => s + v, 0) / speeds.length : 0;
    const maxSpeed = speeds.length > 0 ? Math.max(...speeds) : 0;

    // Bounding box
    const posX = this.reportPositionsX;
    const posZ = this.reportPositionsZ;

    // Deduplicate consecutive identical events
    const deduped = this.reportEvents.filter((e, i) =>
      i === 0 || e.description !== this.reportEvents[i - 1].description || (e.time - this.reportEvents[i - 1].time) > 2000
    );

    // Format events
    const events = deduped.map(e => {
      const min = Math.floor(e.elapsed / 60);
      const sec = Math.floor(e.elapsed % 60);
      return {
        ...e,
        elapsedFormatted: `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`,
      };
    });

    return {
      sessionId: `session-${this.reportStartTime}`,
      startTime: this.reportStartTime,
      endTime: now,
      durationS: Math.round(durationS * 10) / 10,
      totalFrames: this.reportFrameCount,
      isActive: this.status.isProcessing,
      targetClassification: dominantLabel ? dominantLabel[0] : "unknown",
      classificationConfidence: dominantLabel && totalValid > 0 ? Math.round((dominantLabel[1] / totalValid) * 1000) / 1000 : 0,
      classificationBreakdown: labelCounts,
      spatialMetrics: {
        minDistanceCm: Math.round(minDist * 10) / 10,
        maxDistanceCm: Math.round(maxDist * 10) / 10,
        avgDistanceCm: Math.round(avgDist * 10) / 10,
        boundingBox: {
          xMin: posX.length > 0 ? Math.round(Math.min(...posX) * 100) / 100 : 0,
          xMax: posX.length > 0 ? Math.round(Math.max(...posX) * 100) / 100 : 0,
          zMin: posZ.length > 0 ? Math.round(Math.min(...posZ) * 100) / 100 : 0,
          zMax: posZ.length > 0 ? Math.round(Math.max(...posZ) * 100) / 100 : 0,
        },
      },
      kinematicData: {
        avgSpeedMs: Math.round(avgSpeed * 1000) / 1000,
        maxSpeedMs: Math.round(maxSpeed * 1000) / 1000,
      },
      eventTimeline: events,
    };
  }
}

export const signalServer = new SignalProcessingServer();
