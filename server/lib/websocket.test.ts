import test from "node:test";
import assert from "node:assert/strict";
import { WebSocket } from "ws";
import { SignalProcessingServer } from "./websocket";

/**
 * PS-AUDIT-014 (F1): poseFrame/targetIdentity/vitalSigns must be gated on
 * client.isAI, and targetIdentity/vitalSigns must NEVER be writable by any
 * client message (even an AI one) — only the deterministic pipeline may
 * write currentTargetIdentity/currentVitalSigns. These tests drive the
 * private handleMessage/clients/status surface directly since there is no
 * public API for injecting a WS message in-process.
 */

type Captured = { type: string; data: unknown };

function makeClient(id: string, opts: { isAI?: boolean } = {}) {
  const sent: Captured[] = [];
  const ws = {
    readyState: WebSocket.OPEN,
    send(raw: string) {
      sent.push(JSON.parse(raw));
    },
  };
  return { id, ws, sent, isAI: opts.isAI };
}

function wireClient(server: any, client: ReturnType<typeof makeClient>) {
  server.clients.set(client.id, { ws: client.ws, id: client.id, isAI: client.isAI });
}

function newProcessingServer(): any {
  const server: any = new SignalProcessingServer();
  server.status.isProcessing = true;
  return server;
}

test("non-AI client's targetIdentity produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  const bystander = makeClient("bystander");
  wireClient(server, attacker);
  wireClient(server, bystander);

  server.currentTargetIdentity = null;
  server.handleMessage("attacker", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 0.99, mechanicalProb: 0.01 },
  });

  assert.equal(server.currentTargetIdentity, null, "authoritative field must be untouched");
  assert.equal(attacker.sent.length, 0, "attacker must not receive any broadcast from its own message");
  assert.equal(bystander.sent.length, 0, "no other client should see the injected identity");
});

test("non-AI client's vitalSigns produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  wireClient(server, attacker);

  server.currentVitalSigns = null;
  server.handleMessage("attacker", {
    type: "vitalSigns",
    data: { heartRateBpm: 999, respirationRateRpm: 999, vitalsReliable: true },
  });

  assert.equal(server.currentVitalSigns, null);
  assert.equal(attacker.sent.length, 0);
});

test("non-AI client's poseFrame produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  wireClient(server, attacker);

  server.currentPoseFrame = null;
  server.handleMessage("attacker", { type: "poseFrame", data: { timestamp: 1, keypoints: [] } });

  assert.equal(server.currentPoseFrame, null);
  assert.equal(attacker.sent.length, 0);
});

test("AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  server.currentTargetIdentity = null;
  const payload = { label: "human", humanProb: 0.99, mechanicalProb: 0.01 };
  server.handleMessage("ai", { type: "targetIdentity", data: payload });

  assert.equal(server.currentTargetIdentity, null, "F1: no client message may write the authoritative channel");
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryIdentity");
  assert.deepEqual(dashboard.sent[0].data, payload);
  // The old, authoritative-looking type name must never be broadcast from a client message.
  assert.ok(!dashboard.sent.some((m) => m.type === "targetIdentity"));
});

test("AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  server.currentVitalSigns = null;
  const payload = { heartRateBpm: 72, respirationRateRpm: 15, vitalsReliable: true };
  server.handleMessage("ai", { type: "vitalSigns", data: payload });

  assert.equal(server.currentVitalSigns, null);
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryVitalSigns");
  assert.deepEqual(dashboard.sent[0].data, payload);
});

test("AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists)", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  const payload = { timestamp: 123, keypoints: [{ x: 0, y: 0, z: 0 }] };
  server.handleMessage("ai", { type: "poseFrame", data: payload });

  assert.deepEqual(server.currentPoseFrame, payload);
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "poseFrame");
});

test("registerAIClient sets isAI, unblocking the gated message types", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai");
  wireClient(server, ai);

  server.handleMessage("ai", { type: "registerAIClient", data: null });
  assert.equal(server.clients.get("ai").isAI, true);

  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  server.handleMessage("ai", { type: "vitalSigns", data: { heartRateBpm: 60, respirationRateRpm: 12, vitalsReliable: true } });

  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryVitalSigns");
});

test("new-client snapshot (sendLiveSnapshotToClient) always serves the deterministic value, never an injected one", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  const ai = makeClient("ai", { isAI: true });
  wireClient(server, attacker);
  wireClient(server, ai);

  // Both an injection attempt and a legitimate AI advisory message arrive first.
  server.handleMessage("attacker", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 1, mechanicalProb: 0 },
  });
  server.handleMessage("ai", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 1, mechanicalProb: 0 },
  });

  // Only the deterministic pipeline writes this — simulate its tick directly.
  const deterministic = { label: "mechanical", humanProb: 0.1, mechanicalProb: 0.9 };
  server.currentTargetIdentity = deterministic;

  const newClient = makeClient("newcomer");
  wireClient(server, newClient);
  server.sendLiveSnapshotToClient("newcomer");

  const identityMsg = newClient.sent.find((m) => m.type === "targetIdentity");
  assert.ok(identityMsg, "snapshot must include a targetIdentity message");
  assert.deepEqual(identityMsg!.data, deterministic, "snapshot must reflect only the deterministic write, never the injected/advisory data");
});
