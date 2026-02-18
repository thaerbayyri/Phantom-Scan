import type { Express } from "express";
import { createServer, type Server } from "http";
import { signalServer } from "./lib/websocket";
import type { ProcessingConfig, CSISample } from "@shared/schema";
import * as fs from "fs";
import * as path from "path";
import { csiSampleSchema, hardwareIngestSchema } from "@shared/schema";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  // Initialize WebSocket server for real-time signal processing
  signalServer.initialize(httpServer);

  // REST API endpoints for configuration and status
  app.get("/api/status", (req, res) => {
    res.json(signalServer.getStatus());
  });

  app.get("/api/config", (req, res) => {
    res.json(signalServer.getConfig());
  });

  app.post("/api/config", (req, res) => {
    const config = req.body as Partial<ProcessingConfig>;
    // Config updates are handled via WebSocket, but this endpoint exists for REST clients
    res.json({ success: true, message: "Use WebSocket for config updates" });
  });

  // Health check endpoint
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", timestamp: Date.now() });
  });

  // Hardware CSI ingestion endpoint - single sample
  app.post("/api/csi/ingest", (req, res) => {
    try {
      const result = csiSampleSchema.safeParse(req.body);
      if (!result.success) {
        return res.status(400).json({
          error: "Invalid CSI sample format",
          details: result.error.issues
        });
      }

      signalServer.ingestSample(result.data);
      res.json({
        success: true,
        queueLength: signalServer.getQueueLength(),
        timestamp: Date.now()
      });
    } catch (error) {
      console.error("CSI ingestion error:", error);
      res.status(500).json({ error: "Ingestion failed" });
    }
  });

  // Hardware CSI ingestion endpoint - batch samples
  app.post("/api/csi/ingest/batch", (req, res) => {
    try {
      const result = hardwareIngestSchema.safeParse(req.body);
      if (!result.success) {
        return res.status(400).json({
          error: "Invalid batch format",
          details: result.error.issues
        });
      }

      signalServer.ingestSamples(result.data.samples);
      res.json({
        success: true,
        samplesIngested: result.data.samples.length,
        queueLength: signalServer.getQueueLength(),
        timestamp: Date.now()
      });
    } catch (error) {
      console.error("Batch CSI ingestion error:", error);
      res.status(500).json({ error: "Batch ingestion failed" });
    }
  });

  // Get ingestion queue status
  app.get("/api/csi/queue", (req, res) => {
    res.json({
      queueLength: signalServer.getQueueLength(),
      status: signalServer.getStatus(),
      timestamp: Date.now()
    });
  });

  // Download last recorded session CSV
  app.get("/api/recording/download", (req, res) => {
    const filePath = signalServer.getLastRecordingFile();
    if (!filePath) {
      return res.status(404).json({ error: "No recording available" });
    }

    console.log(`[DOWNLOAD] Attempting to serve: ${filePath}`);

    try {
      if (!fs.existsSync(filePath)) {
        console.error(`[DOWNLOAD] File not found at path: ${filePath}`);
        return res.status(404).json({ error: "Recording file not found" });
      }

      res.setHeader("Content-Type", "text/csv");
      res.setHeader(
        "Content-Disposition",
        `attachment; filename="${path.basename(filePath)}"`
      );

      const stream = fs.createReadStream(filePath);
      stream.on('error', (err) => {
        console.error("[DOWNLOAD] Stream error:", err);
        if (!res.headersSent) {
          res.status(500).json({ error: "Stream failed" });
        }
      });
      stream.pipe(res);

    } catch (error) {
      console.error("[DOWNLOAD] Critical error:", error);
      if (!res.headersSent) {
        res.status(500).json({ error: "Download failed", details: String(error) });
      }
    }
  });

  return httpServer;
}
