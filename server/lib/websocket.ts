import { WebSocketServer, WebSocket } from "ws";
import type { Server } from "http";
import type {
  ProcessingConfig,
  SystemStatus,
  DataSource,
  CSISample,
} from "@shared/schema";
import {
  applyNulling,
  computeMUSICSpectrum,
  findSpectrumPeak,
  aoaToPoint,
  GestureDetector,
  HeatmapAccumulator,
  DemoDataGenerator,
  BackgroundSubtractor,
  MotionGate,
  DopplerComputer,
} from "./signal-processing";
import { TrackingProcessor } from "./tracking";
import { magnitude } from "./complex";
import * as fs from "fs";
import * as path from "path";

interface WSClient {
  ws: WebSocket;
  id: string;
}

export class SignalProcessingServer {
  private wss: WebSocketServer | null = null;
  private clients: Map<string, WSClient> = new Map();
  private processingInterval: NodeJS.Timeout | null = null;
  private isStopping: boolean = false;

  private config: ProcessingConfig = {
    nullingEnabled: true,
    nullingThreshold: 10,
    isarEnabled: true,
    arrayLength: 16,
    aoaRangeMin: -60,
    aoaRangeMax: 60,
    gestureEnabled: true,
    centroidThreshold: 5,
    clutterRemovalEnabled: true,
    clutterWindowSize: 50,
    motionGateEnabled: false,
    motionThreshold: 0.05,
  };

  private status: SystemStatus = {
    connected: false,
    dataSource: "demo",
    samplesReceived: 0,
    framesProcessed: 0,
    lastUpdate: Date.now(),
    isProcessing: false,
  };

  // Processing engines
  private demoGenerator = new DemoDataGenerator();
  private gestureDetector = new GestureDetector(5);
  private heatmapAccumulator = new HeatmapAccumulator();
  private backgroundSubtractor = new BackgroundSubtractor(50);
  private motionGate = new MotionGate();
  private dopplerComputer = new DopplerComputer();
  private trackingProcessor = new TrackingProcessor();

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

  // Recording state
  private isRecording = false;
  private recordingBuffer: CSISample[] = [];
  private recordingStartTime = 0;
  private lastRecordingFile = "";

  initialize(server: Server) {
    this.wss = new WebSocketServer({ server, path: "/ws" });

    this.wss.on("connection", (ws: WebSocket) => {
      const clientId = Math.random().toString(36).substring(7);
      this.clients.set(clientId, { ws, id: clientId });

      console.log(`Client connected: ${clientId}`);

      // Send initial state
      this.sendToClient(clientId, "status", this.status);
      this.sendToClient(clientId, "config", this.config);
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
    switch (message.type) {
      case "start":
        this.startProcessing();
        break;
      case "stop":
        this.stopProcessing();
        break;
      case "updateConfig":
        this.updateConfig(message.data as Partial<ProcessingConfig>);
        break;
      case "setDataSource":
        this.setDataSource(message.data as DataSource);
        break;
      case "startRecording":
        this.startRecording();
        break;
      case "stopRecording":
        this.stopRecording();
        break;
    }
  }

  private startProcessing() {
    if (this.status.isProcessing) return;

    this.isStopping = false;
    this.status.isProcessing = true;
    this.demoGenerator.reset();
    this.gestureDetector.reset();
    this.heatmapAccumulator.reset();
    this.backgroundSubtractor.reset();
    this.motionGate.reset();
    this.dopplerComputer.reset();
    this.trackingProcessor.reset();
    this.sampleBuffer = [];
    this.pointCloudHistory = [];

    this.broadcast("status", this.status);

    // Process at ~20 FPS
    this.processingInterval = setInterval(() => {
      this.processFrame();
    }, 50);

    console.log("Processing started");
  }

  private stopProcessing() {
    if (!this.status.isProcessing) return;

    this.isStopping = true;

    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
    }

    this.status.isProcessing = false;
    this.status.lastUpdate = Date.now();

    this.broadcast("status", this.status);

    this.isStopping = false;

    console.log("Processing stopped");
  }

  private updateConfig(updates: Partial<ProcessingConfig>) {
    this.config = { ...this.config, ...updates };

    if (updates.centroidThreshold !== undefined) {
      this.gestureDetector.updateThreshold(updates.centroidThreshold);
    }
    if (updates.clutterWindowSize !== undefined) {
      this.backgroundSubtractor.setWindowSize(updates.clutterWindowSize);
    }

    this.broadcast("config", this.config);
  }

  private setDataSource(source: DataSource) {
    this.status.dataSource = source;

    // Clear buffers when switching modes
    this.sampleBuffer = [];
    this.hardwareSampleQueue = [];
    this.backgroundSubtractor.reset();
    this.motionGate.reset();
    this.dopplerComputer.reset();
    this.trackingProcessor.reset();

    this.broadcast("status", this.status);
  }

  // ── Recording ──────────────────────────────────────────────────

  private startRecording() {
    if (this.isRecording) return;
    this.isRecording = true;
    this.recordingBuffer = [];
    this.recordingStartTime = Date.now();

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
      } catch (err) {
        console.error("[REC] Failed to save recording:", err);
      }
    } else {
      console.log("[REC] No samples recorded");
    }

    this.broadcastRecordingStatus();
  }

  private broadcastRecordingStatus() {
    this.broadcast("recordingStatus", {
      isRecording: this.isRecording,
      sampleCount: this.recordingBuffer.length,
      durationMs: this.isRecording
        ? Date.now() - this.recordingStartTime
        : 0,
      lastFile: this.lastRecordingFile ? path.basename(this.lastRecordingFile) : undefined,
    });
  }

  private serializeToCSV(): string {
    const dir = path.resolve("recordings");
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const filePath = path.join(dir, `csi_session_${ts}.csv`);

    const header =
      "timestamp,subcarrier_index,h1_re,h1_im,h2_re,h2_im,rssi\n";
    const rows = this.recordingBuffer.map(
      (s) =>
        `${s.timestamp},${s.subcarrierIndex ?? 0},${s.h1.re},${s.h1.im},${s.h2.re},${s.h2.im},${s.rssi ?? ""}`
    );

    fs.writeFileSync(filePath, header + rows.join("\n"), "utf-8");
    this.recordingBuffer = [];

    return filePath;
  }

  // ── Main processing pipeline ───────────────────────────────────

  private processFrame() {
    if (!this.status.isProcessing || this.isStopping) {
      return;
    }

    let sample: CSISample;

    // Get sample based on data source
    if (
      this.status.dataSource === "hardware" ||
      this.status.dataSource === "esp32"
    ) {
      const queuedSample = this.hardwareSampleQueue.shift();
      if (queuedSample) {
        sample = queuedSample;
      } else {
        // No hardware data yet — fall back to demo so the UI stays alive
        sample = this.demoGenerator.generateSample();
      }

      if (this.hardwareSampleQueue.length > 1000) {
        this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
      }
    } else {
      sample = this.demoGenerator.generateSample();
    }

    this.status.samplesReceived++;

    // ── Record raw sample if recording ──
    if (this.isRecording) {
      this.recordingBuffer.push({ ...sample });
      // Broadcast recording status every 50 samples
      if (this.recordingBuffer.length % 50 === 0) {
        this.broadcastRecordingStatus();
      }
    }

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

    // If motion gate is ON and no motion detected, broadcast but skip rendering
    if (this.config.motionGateEnabled && !motionResult.motionDetected) {
      this.status.framesProcessed++;
      this.status.lastUpdate = Date.now();
      if (this.status.framesProcessed % 20 === 0) {
        this.broadcast("status", this.status);
      }
      return;
    }

    // ── 3. Apply nulling (on clutter-removed signal) ──
    const processedSample: CSISample = {
      ...sample,
      h1: h1Proc,
      h2: h2Proc,
    };

    let estimate = applyNulling(processedSample, this.config);

    if (!this.config.nullingEnabled) {
      estimate = { ...estimate, nulledSignal: h1Proc };
    }

    this.broadcast("csiFrame", estimate);

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

      // Update heatmap
      this.heatmapAccumulator.addSpectrum(estimate.timestamp, spectrum);
      this.broadcast("heatmap", this.heatmapAccumulator.getData());

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
            x: dist * Math.sin(thetaRad),
            y: dist * Math.cos(thetaRad),
            z:
              dynamicAmplitude *
              Math.sin(this.status.framesProcessed * 0.05) *
              0.3,
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
        this.broadcast("trackedTarget", trackedTarget);
      } else {
        this.broadcast("trackedTarget", null);
      }

      // ── 8. Gesture recognition (on processed timestamps/features) ──
      if (this.config.gestureEnabled) {
        const gesture = this.gestureDetector.addSample(
          estimate.timestamp,
          peak.angle
        );
        if (gesture) {
          this.broadcast("gesture", gesture);
        }
      }
    }

    this.status.framesProcessed++;
    this.status.lastUpdate = Date.now();

    if (this.status.framesProcessed % 20 === 0) {
      this.broadcast("status", this.status);
    }
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

  // ── Public API ─────────────────────────────────────────────────

  getStatus(): SystemStatus {
    return this.status;
  }

  getConfig(): ProcessingConfig {
    return this.config;
  }

  getLastRecordingFile(): string {
    return this.lastRecordingFile;
  }

  // Hardware ingestion methods
  ingestSample(sample: CSISample): void {
    this.hardwareSampleQueue.push(sample);

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
      this.hardwareSampleQueue.push(sample);
    }

    if (this.hardwareSampleQueue.length > 1000) {
      this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
    }
  }

  getQueueLength(): number {
    return this.hardwareSampleQueue.length;
  }
}

export const signalServer = new SignalProcessingServer();
