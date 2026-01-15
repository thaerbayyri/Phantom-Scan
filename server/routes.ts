import type { Express } from "express";
import { createServer, type Server } from "http";
import { signalServer } from "./lib/websocket";
import type { ProcessingConfig } from "@shared/schema";

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

  return httpServer;
}
