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
} from "./signal-processing";
import { magnitude } from "./complex";

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
  };

  private status: SystemStatus = {
    connected: false,
    dataSource: "demo",
    samplesReceived: 0,
    framesProcessed: 0,
    lastUpdate: Date.now(),
    isProcessing: false,
  };

  private demoGenerator = new DemoDataGenerator();
  private gestureDetector = new GestureDetector(5);
  private heatmapAccumulator = new HeatmapAccumulator();
  private sampleBuffer: { re: number; im: number }[] = [];
  private pointCloudHistory: { x: number; y: number; z: number; amplitude: number; timestamp: number }[] = [];
  private hardwareSampleQueue: CSISample[] = [];

  initialize(server: Server) {
    this.wss = new WebSocketServer({ server, path: "/ws" });

    this.wss.on("connection", (ws: WebSocket) => {
      const clientId = Math.random().toString(36).substring(7);
      this.clients.set(clientId, { ws, id: clientId });

      console.log(`Client connected: ${clientId}`);

      // Send initial state
      this.sendToClient(clientId, "status", this.status);
      this.sendToClient(clientId, "config", this.config);

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
    }
  }

  private startProcessing() {
    if (this.status.isProcessing) return;

    this.isStopping = false;
    this.status.isProcessing = true;
    this.demoGenerator.reset();
    this.gestureDetector.reset();
    this.heatmapAccumulator.reset();
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

    // Set stopping flag immediately to prevent any in-flight frames
    this.isStopping = true;

    // Clear interval to stop new frames
    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
    }

    // Update status
    this.status.isProcessing = false;
    this.status.lastUpdate = Date.now();

    // Broadcast immediately
    this.broadcast("status", this.status);

    // Reset stopping flag after broadcast
    this.isStopping = false;

    console.log("Processing stopped");
  }

  private updateConfig(updates: Partial<ProcessingConfig>) {
    this.config = { ...this.config, ...updates };

    if (updates.centroidThreshold !== undefined) {
      this.gestureDetector.updateThreshold(updates.centroidThreshold);
    }

    this.broadcast("config", this.config);
  }

  private setDataSource(source: DataSource) {
    this.status.dataSource = source;
    
    // Clear sample buffer and hardware queue when switching modes
    this.sampleBuffer = [];
    this.hardwareSampleQueue = [];
    
    this.broadcast("status", this.status);
  }

  private processFrame() {
    // Guard: don't process if stopped or stopping
    if (!this.status.isProcessing || this.isStopping) {
      return;
    }

    let sample: CSISample;
    
    // Get sample based on data source
    if (this.status.dataSource === "hardware") {
      // Hardware mode: consume from queue
      const queuedSample = this.hardwareSampleQueue.shift();
      if (!queuedSample) {
        // No samples in queue, skip this frame
        return;
      }
      sample = queuedSample;
      
      // Limit queue size to prevent memory issues (keep last 1000)
      if (this.hardwareSampleQueue.length > 1000) {
        this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
      }
    } else {
      // Demo mode: generate sample
      sample = this.demoGenerator.generateSample();
    }
    
    this.status.samplesReceived++;

    // Apply nulling
    let estimate = applyNulling(sample, this.config);

    if (!this.config.nullingEnabled) {
      estimate = {
        ...estimate,
        nulledSignal: sample.h1,
      };
    }

    this.broadcast("csiFrame", estimate);

    // Add to sample buffer for MUSIC
    this.sampleBuffer.push(estimate.nulledSignal);
    if (this.sampleBuffer.length > this.config.arrayLength) {
      this.sampleBuffer.shift();
    }

    // Compute ISAR/MUSIC spectrum
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

      // Generate point cloud
      const amplitude = magnitude(estimate.nulledSignal);
      const point = aoaToPoint(peak.angle, amplitude, estimate.timestamp);

      this.pointCloudHistory.push(point);
      if (this.pointCloudHistory.length > 50) {
        this.pointCloudHistory.shift();
      }

      this.broadcast("pointCloud", this.pointCloudHistory);

      // Gesture detection
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

    // Periodically broadcast status
    if (this.status.framesProcessed % 20 === 0) {
      this.broadcast("status", this.status);
    }
  }

  private sendToClient(clientId: string, type: string, data: unknown) {
    const client = this.clients.get(clientId);
    if (client && client.ws.readyState === WebSocket.OPEN) {
      client.ws.send(JSON.stringify({ type, data }));
    }
  }

  private broadcast(type: string, data: unknown) {
    const message = JSON.stringify({ type, data });
    for (const client of this.clients.values()) {
      if (client.ws.readyState === WebSocket.OPEN) {
        client.ws.send(message);
      }
    }
  }

  getStatus(): SystemStatus {
    return this.status;
  }

  getConfig(): ProcessingConfig {
    return this.config;
  }

  // Hardware ingestion methods
  ingestSample(sample: CSISample): void {
    // Add to queue - will be consumed by processFrame when in hardware mode
    this.hardwareSampleQueue.push(sample);
    
    // Limit queue size to prevent memory issues
    if (this.hardwareSampleQueue.length > 1000) {
      this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
    }
  }

  ingestSamples(samples: CSISample[]): void {
    for (const sample of samples) {
      this.hardwareSampleQueue.push(sample);
    }
    
    // Limit queue size
    if (this.hardwareSampleQueue.length > 1000) {
      this.hardwareSampleQueue = this.hardwareSampleQueue.slice(-1000);
    }
  }

  getQueueLength(): number {
    return this.hardwareSampleQueue.length;
  }
}

export const signalServer = new SignalProcessingServer();
