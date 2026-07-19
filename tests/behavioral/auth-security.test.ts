import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import express from "express";
import { createServer } from "http";
import { initializeAuth, resetAuthStateForTests } from "../../server/auth/service";

/**
 * B5 — auth security gaps not already covered by server/auth/service.test.ts
 * (bootstrap success/loopback-restriction were already covered; verified
 * before writing this file). This file covers: protected-route 401 without
 * a session, and login rate-limiting (429) after repeated failed attempts.
 * Matches the existing real-HTTP-server-on-ephemeral-port test pattern from
 * service.test.ts rather than introducing a new harness style.
 */

async function withAuthServer<T>(
  fn: (baseUrl: string) => Promise<T>,
): Promise<T> {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-behtest-auth-"));
  const seedPath = path.join(tempDir, "operator.json");
  process.env.PHANTOM_OPERATOR_SEED_PATH = seedPath;
  process.env.PHANTOM_SESSION_SECRET = "behtest-secret";
  resetAuthStateForTests();

  const app = express();
  const server = createServer(app);
  app.use(express.json());
  const auth = initializeAuth(app);
  app.get("/protected", auth.requireAuth, (_req, res) => res.json({ ok: true }));

  try {
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
    const address = server.address();
    assert(address && typeof address === "object");
    return await fn(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
    delete process.env.PHANTOM_OPERATOR_SEED_PATH;
    delete process.env.PHANTOM_SESSION_SECRET;
    resetAuthStateForTests();
  }
}

test("protected route returns 401 without a session", async () => {
  await withAuthServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/protected`);
    assert.equal(response.status, 401);
    const body = await response.json() as { error: string };
    assert.equal(body.error, "Authentication required");
  });
});

test("protected route returns 401 with a garbage/forged cookie", async () => {
  await withAuthServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/protected`, {
      headers: { cookie: "phantom.sid=forged-not-a-real-session" },
    });
    assert.equal(response.status, 401);
  });
});

test("login is rate-limited (429) after repeated failed attempts against a real operator", async () => {
  await withAuthServer(async (baseUrl) => {
    // Bootstrap a real operator first (loopback, allowed).
    const bootstrap = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "operator", password: "correct-horse-battery" }),
    });
    assert.equal(bootstrap.status, 200);

    // Now hammer it with wrong-password attempts. LOGIN_MAX_ATTEMPTS is 5
    // (server/auth/service.ts, not exported) within LOGIN_WINDOW_MS — the
    // 6th attempt in the same window must be rejected with 429, not 401.
    let lastStatus = 0;
    for (let i = 0; i < 6; i++) {
      const attempt = await fetch(`${baseUrl}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "operator", password: "wrong-password" }),
      });
      lastStatus = attempt.status;
      if (i < 5) {
        assert.equal(attempt.status, 401, `attempt ${i + 1} should be a normal auth failure`);
      }
    }
    assert.equal(lastStatus, 429, "6th attempt within the window must be rate-limited");
  });
});
