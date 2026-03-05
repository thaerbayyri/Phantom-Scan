import type { Express } from "express";
import { createServer, type Server } from "http";
import { signalServer } from "./lib/websocket";
import { sessionStore } from "./lib/session-store";
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
        timestamp: Date.now(),
        isProcessing: signalServer.getStatus().isProcessing
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

  // Session report endpoint
  app.get("/api/report", (req, res) => {
    try {
      const report = signalServer.getSessionReport();
      res.json(report);
    } catch (error) {
      console.error("Report generation error:", error);
      res.status(500).json({ error: "Failed to generate report" });
    }
  });

  // ── Session history endpoints ──────────────────────────────────

  // List sessions (with optional search/filter)
  app.get("/api/sessions", (req, res) => {
    try {
      const search = req.query.search as string | undefined;
      const classification = req.query.classification as string | undefined;
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 50;
      const offset = req.query.offset ? parseInt(req.query.offset as string, 10) : 0;
      const result = sessionStore.list({ search, classification, limit, offset });
      res.json(result);
    } catch (error) {
      console.error("Session list error:", error);
      res.status(500).json({ error: "Failed to list sessions" });
    }
  });

  // Get single session by ID
  app.get("/api/sessions/:id", (req, res) => {
    try {
      const session = sessionStore.getById(req.params.id);
      if (!session) {
        return res.status(404).json({ error: "Session not found" });
      }
      res.json(session);
    } catch (error) {
      console.error("Session get error:", error);
      res.status(500).json({ error: "Failed to get session" });
    }
  });

  // Delete a session
  app.delete("/api/sessions/:id", (req, res) => {
    try {
      const deleted = sessionStore.delete(req.params.id);
      if (!deleted) {
        return res.status(404).json({ error: "Session not found" });
      }
      res.json({ success: true });
    } catch (error) {
      console.error("Session delete error:", error);
      res.status(500).json({ error: "Failed to delete session" });
    }
  });

  return httpServer;
}
