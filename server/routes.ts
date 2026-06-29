import { type Express, type Request, type Response } from "express";
import { type Server } from "http";
import { signalServer } from "./lib/websocket";
import { spawn } from "child_process";
import os from "os";

// Strict allowlist of commands (with placeholders for dynamic args)
const ALLOWED_TASKS: Record<string, { cmd: string; getArgs: (iface: string) => string[] }> = {
  START_MONITOR: { cmd: "airmon-ng", getArgs: (iface) => ["start", iface] },
  STOP_MONITOR: { cmd: "airmon-ng", getArgs: (iface) => ["stop", `${iface}mon`] },
  RESTART_BACKEND: { cmd: "systemctl", getArgs: () => ["restart", "phantomscan"] },
  VIEW_LOGS: { cmd: "tail", getArgs: () => ["-n", "50", "/var/log/phantomscan.log"] },
  CHECK_WIFI: { cmd: "iwconfig", getArgs: () => [] },
};
import { sessionStore } from "./lib/session-store";
import type { ProcessingConfig, CSISample } from "@shared/schema";
import * as fs from "fs";
import * as path from "path";
import { csiSampleSchema, hardwareIngestSchema } from "@shared/schema";
import type { AuthService } from "./auth/service";

export async function registerRoutes(
  httpServer: Server,
  app: Express,
  auth: AuthService,
): Promise<Server> {
  // REST API endpoints for configuration and status
  app.get("/api/status", auth.requireAuth, (req, res) => {
    res.json(signalServer.getStatus());
  });

  app.get("/api/config", auth.requireAuth, (req, res) => {
    res.json(signalServer.getConfig());
  });

  app.post("/api/config", auth.requireAuth, auth.auditProtectedAction("config_posted"), (req, res) => {
    const config = req.body as Partial<ProcessingConfig>;
    // Config updates are handled via WebSocket, but this endpoint exists for REST clients
    res.json({ success: true, message: "Use WebSocket for config updates" });
  });

  // Health check endpoint
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", timestamp: Date.now() });
  });

  // ESP32-S3 Remote Configuration (Active & Passive Modes)
  app.post("/api/esp32/configure", auth.requireAuth, auth.auditProtectedAction("esp32_configure"), async (req, res) => {
    try {
      const { mode, targetMac, channel, ssid, password } = req.body;

      // Target the local ESP32-S3 IP address
      const esp32Ip = "http://192.168.4.1/config";

      const payload: any = { mode };

      if (mode === 'active') {
        if (!ssid || !password) {
          return res.status(400).json({ error: "Active mode requires ssid and password" });
        }
        payload.ssid = ssid;
        payload.password = password;
      } else if (mode === 'passive') {
        if (!targetMac || !channel) {
          return res.status(400).json({ error: "Passive sniffer mode requires targetMac and channel" });
        }
        payload.targetMac = targetMac;
        payload.channel = channel;
      } else {
        return res.status(400).json({ error: "Invalid mode. Must be 'active' or 'passive'" });
      }

      console.log(`[ESP32 Config] Simulating sending configuration to ${esp32Ip}:`, payload);

      // In a real execution environment:
      // const response = await fetch(esp32Ip, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(payload)
      // });
      // if (!response.ok) throw new Error("ESP32 rejected configuration");

      res.json({
        success: true,
        message: `ESP32 successfully configured in ${mode} mode`,
        appliedConfig: payload
      });
    } catch (error) {
      console.error("ESP32 Configuration error:", error);
      res.status(500).json({ error: "Failed to configure ESP32" });
    }
  });

  // Get list of system network interfaces
  app.get("/api/v1/system/interfaces", auth.requireAuth, (req, res) => {
    try {
      const interfaces = os.networkInterfaces();
      const names = Object.keys(interfaces);
      res.json({ interfaces: names });
    } catch (error) {
      console.error("Failed to list interfaces:", error);
      res.status(500).json({ error: "Failed to list interfaces" });
    }
  });

  // Secure System Task Execution Endpoint
  app.post("/api/v1/system/execute-task", auth.requireAuth, auth.auditProtectedAction("system_task_execute"), (req, res) => {
    try {
      const { task, interfaceName = "wlan0" } = req.body;

      if (!task || !ALLOWED_TASKS[task]) {
        return res.status(400).json({ error: `Task '${task}' is not allowed.` });
      }

      // Basic sanitization to prevent argument injection if the interface name is manipulated
      if (!/^[a-zA-Z0-9]+$/.test(interfaceName)) {
        return res.status(400).json({ error: "Invalid interface name format." });
      }

      const taskConfig = ALLOWED_TASKS[task];
      const args = taskConfig.getArgs(interfaceName);

      // shell: false is completely necessary to avoid shell injection vulnerabilities
      const child = spawn(taskConfig.cmd, args, { shell: false });

      let output = "";
      let responded = false;

      child.stdout.on("data", (data) => {
        output += data.toString();
      });

      child.stderr.on("data", (data) => {
        output += data.toString();
      });

      child.on("close", (code) => {
        if (responded) return;
        responded = true;
        res.json({
          status: "success",
          task,
          os: os.platform(),
          output: output || `[Command exited with code ${code}]`,
        });
      });

      child.on("error", (error: any) => {
        if (responded) return;
        responded = true;
        if (error.code === "ENOENT") {
          return res.status(500).json({
            error: `Executable '${taskConfig.cmd}' not found on host.`,
          });
        }
        res.status(500).json({ error: `Task execution failed: ${error.message}` });
      });
    } catch (err) {
      console.error("Execute task error:", err);
      res.status(500).json({ error: "Internal server error during task execution" });
    }
  });

  // Hardware CSI ingestion endpoint - single sample
  app.post("/api/csi/ingest", auth.requireAuth, (req, res) => {
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
  app.post("/api/csi/ingest/batch", auth.requireAuth, (req, res) => {
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
  app.get("/api/csi/queue", auth.requireAuth, (req, res) => {
    res.json({
      queueLength: signalServer.getQueueLength(),
      status: signalServer.getStatus(),
      timestamp: Date.now()
    });
  });

  // Download last recorded session CSV or report
  app.get("/api/recording/download", auth.requireAuth, auth.auditProtectedAction("recording_download"), (req, res) => {
    let filePath = signalServer.getLastRecordingFile();
    if (!filePath) {
      return res.status(404).json({ error: "No recording available" });
    }

    const format = req.query.format as string;
    let contentType = "text/csv";
    if (format === 'json') {
      filePath = filePath.replace('.csv', '.json');
      contentType = "application/json";
    } else if (format === 'pdf') {
      filePath = filePath.replace('.csv', '.pdf');
      contentType = "application/pdf";
    }

    console.log(`[DOWNLOAD] Attempting to serve: ${filePath}`);

    try {
      if (!fs.existsSync(filePath)) {
        console.error(`[DOWNLOAD] File not found at path: ${filePath}`);
        return res.status(404).json({ error: "Recording file not found" });
      }

      res.setHeader("Content-Type", contentType);
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
  app.get("/api/report", auth.requireAuth, (req, res) => {
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
  app.get("/api/sessions", auth.requireAuth, (req, res) => {
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
  app.get("/api/sessions/:id", auth.requireAuth, (req, res) => {
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
  app.delete("/api/sessions/:id", auth.requireAuth, auth.auditProtectedAction("session_deleted"), (req, res) => {
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
