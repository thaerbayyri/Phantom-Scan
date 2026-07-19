import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import express from "express";
import { createServer } from "http";
import { initializeAuth, resetAuthStateForTests } from "../../server/auth/service";
import { registerRoutes } from "../../server/routes";

/**
 * B4 — F2 firewall (dashboard/GCS must never write upstream to nodes,
 * serial, or firmware). The UI-invariant string-scan already exists in
 * Python (tests/test_invariants.py:39-45, verified present before writing
 * this file) but nothing exercised the actual route at the HTTP level. This
 * proves /api/esp32/configure always 403s — even for a fully authenticated
 * operator — so no dashboard code path can ever reach a real upstream write
 * through it, regardless of what the client sends.
 */

test("POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-behtest-f2-"));
  process.env.PHANTOM_OPERATOR_SEED_PATH = path.join(tempDir, "operator.json");
  process.env.PHANTOM_SESSION_SECRET = "behtest-f2-secret";
  resetAuthStateForTests();

  const app = express();
  const httpServer = createServer(app);
  app.use(express.json());
  const auth = initializeAuth(app);
  await registerRoutes(httpServer, app, auth);

  try {
    await new Promise<void>((resolve) => httpServer.listen(0, "127.0.0.1", () => resolve()));
    const address = httpServer.address();
    assert(address && typeof address === "object");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    // Authenticate first (loopback bootstrap).
    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "operator", password: "behtest-pass" }),
    });
    assert.equal(login.status, 200);
    const cookie = login.headers.get("set-cookie");
    assert(cookie);

    // An authenticated request with a plausible-looking upstream-write body
    // (target IP, SSID, command) must still 403 — the route is a permanent
    // stub, not something that could be "unlocked" by valid credentials.
    const response = await fetch(`${baseUrl}/api/esp32/configure`, {
      method: "POST",
      headers: { "Content-Type": "application/json", cookie },
      body: JSON.stringify({ targetIp: "192.168.1.99", ssid: "attacker-net", mode: "active" }),
    });
    assert.equal(response.status, 403);
    const body = await response.json() as { error: string };
    assert.match(body.error, /not exposed/i);
  } finally {
    await new Promise<void>((resolve, reject) =>
      httpServer.close((error) => (error ? reject(error) : resolve())),
    );
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
});

test("POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-behtest-f2-noauth-"));
  process.env.PHANTOM_OPERATOR_SEED_PATH = path.join(tempDir, "operator.json");
  process.env.PHANTOM_SESSION_SECRET = "behtest-f2-noauth-secret";
  resetAuthStateForTests();

  const app = express();
  const httpServer = createServer(app);
  app.use(express.json());
  const auth = initializeAuth(app);
  await registerRoutes(httpServer, app, auth);

  try {
    await new Promise<void>((resolve) => httpServer.listen(0, "127.0.0.1", () => resolve()));
    const address = httpServer.address();
    assert(address && typeof address === "object");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/api/esp32/configure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ targetIp: "192.168.1.99" }),
    });
    assert.equal(response.status, 401);
  } finally {
    await new Promise<void>((resolve, reject) =>
      httpServer.close((error) => (error ? reject(error) : resolve())),
    );
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
});
