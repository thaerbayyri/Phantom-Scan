import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import express from "express";
import { createServer } from "http";
import { generateOperatorSeed, initializeAuth, resetAuthStateForTests, verifyOperatorSeedPassword } from "./service";
import { AuditLogger } from "../audit/logger";

test("generateOperatorSeed creates a verifiable scrypt hash", () => {
  const seed = generateOperatorSeed("operator", "secret-pass");
  assert.equal(seed.username, "operator");
  assert.equal(seed.hash_scheme, "scrypt");
  assert.equal(verifyOperatorSeedPassword("secret-pass", seed), true);
  assert.equal(verifyOperatorSeedPassword("wrong-pass", seed), false);
});

test("AuditLogger writes and lists records in reverse chronological order", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-audit-"));
  const logger = new AuditLogger(tempDir);

  await logger.log({ event_type: "login_success", success: true, username: "operator" });
  await logger.log({ event_type: "logout", success: true, username: "operator" });

  const result = await logger.list({ limit: 10, offset: 0 });
  assert.equal(result.total, 2);
  assert.equal(result.records[0]?.event_type, "logout");
  assert.equal(result.records[1]?.event_type, "login_success");
});

test("AuditLogger accepts websocket-style request objects without req.get", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-audit-ws-"));
  const logger = new AuditLogger(tempDir);

  await logger.log({
    event_type: "unauthorized_access",
    success: false,
    req: {
      method: "GET",
      url: "/ws",
      headers: {
        "user-agent": "ws-test-client",
      },
      ip: "127.0.0.1",
    },
    details: {
      protocol: "websocket",
    },
  });

  const result = await logger.list({ limit: 10, offset: 0 });
  assert.equal(result.total, 1);
  assert.equal(result.records[0]?.route, "GET /ws");
  assert.equal(result.records[0]?.user_agent, "ws-test-client");
});

test("load path accepts operator files with npm banner noise before JSON", async () => {
  resetAuthStateForTests();
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-seed-noise-"));
  const seedPath = path.join(tempDir, "operator.json");
  const cleanSeed = generateOperatorSeed("operator", "secret-pass");
  const noisySeed = `> csi-signal-processing@1.1.0 auth:seed\n> tsx scripts/generate-operator-seed.ts operator secret-pass\n\n${JSON.stringify(cleanSeed, null, 2)}\n`;
  fs.writeFileSync(seedPath, noisySeed, "utf-8");

  process.env.PHANTOM_OPERATOR_SEED_PATH = seedPath;
  process.env.PHANTOM_SESSION_SECRET = "noise-test-secret";

  const app = express();
  const server = createServer(app);
  app.use(express.json());
  const auth = initializeAuth(app);
  app.get("/protected", auth.requireAuth, (_req, res) => {
    res.json({ ok: true });
  });

  try {
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
    const address = server.address();
    assert(address && typeof address === "object");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "operator", password: "secret-pass" }),
    });

    assert.equal(login.status, 200);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
});

test("initializeAuth bootstraps first operator on loopback when seed file is missing", async () => {
  resetAuthStateForTests();
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-bootstrap-"));
  const seedPath = path.join(tempDir, "operator.json");

  process.env.PHANTOM_OPERATOR_SEED_PATH = seedPath;
  process.env.PHANTOM_SESSION_SECRET = "bootstrap-test-secret";

  const app = express();
  const server = createServer(app);
  app.use(express.json());
  const auth = initializeAuth(app);
  app.get("/protected", auth.requireAuth, (_req, res) => {
    res.json({ ok: true });
  });

  try {
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
    const address = server.address();
    assert(address && typeof address === "object");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const before = await fetch(`${baseUrl}/api/auth/session`);
    const beforeJson = await before.json() as { authenticated: boolean; setup_required?: boolean };
    assert.equal(beforeJson.authenticated, false);
    assert.equal(beforeJson.setup_required, true);

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "operator", password: "secret-pass" }),
    });
    assert.equal(login.status, 200);
    assert.equal(fs.existsSync(seedPath), true);

    const cookie = login.headers.get("set-cookie");
    assert(cookie);

    const protectedResponse = await fetch(`${baseUrl}/protected`, {
      headers: { cookie },
    });
    assert.equal(protectedResponse.status, 200);

    const storedSeed = JSON.parse(fs.readFileSync(seedPath, "utf-8"));
    assert.equal(storedSeed.username, "operator");
    assert.equal(verifyOperatorSeedPassword("secret-pass", storedSeed), true);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
});

test("initializeAuth rejects first-operator bootstrap from non-loopback without token", async () => {
  resetAuthStateForTests();
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-bootstrap-denied-"));
  const seedPath = path.join(tempDir, "operator.json");

  process.env.PHANTOM_OPERATOR_SEED_PATH = seedPath;
  process.env.PHANTOM_SESSION_SECRET = "bootstrap-test-secret";

  const app = express();
  app.set("trust proxy", 1);
  const server = createServer(app);
  app.use(express.json());
  initializeAuth(app);

  try {
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
    const address = server.address();
    assert(address && typeof address === "object");
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For": "10.0.0.77",
      },
      body: JSON.stringify({ username: "operator", password: "secret-pass" }),
    });
    assert.equal(login.status, 403);
    assert.equal(fs.existsSync(seedPath), false);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
});
