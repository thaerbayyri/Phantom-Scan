import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { WebSocket } from "ws";
import { SignalProcessingServer } from "./websocket";
import { sessionStore } from "./session-store";

/**
 * Demo mode wiring on the server: start/stop messages, source labelling,
 * the live-vs-demo separation and clean unwinding. Drives the private
 * handleMessage/clients surface like websocket.test.ts does.
 */

// These tests start and stop scans; keep them away from the operator's real
// session history (data/sessions) no matter what a code path decides to save.
const realSessionSave = sessionStore.save;
(sessionStore as any).save = () => undefined;
test.after(() => {
  (sessionStore as any).save = realSessionSave;
});

type Captured = { type: string; data: any };

function makeClient(id: string) {
  const sent: Captured[] = [];
  const ws = {
    readyState: WebSocket.OPEN,
    send(raw: string) {
      sent.push(JSON.parse(raw));
    },
  };
  return { id, ws, sent };
}

function newServer(): { server: any; client: ReturnType<typeof makeClient> } {
  const server: any = new SignalProcessingServer();
  const client = makeClient("operator");
  server.clients.set(client.id, { ws: client.ws, id: client.id });
  return { server, client };
}

async function waitFor(predicate: () => boolean, timeoutMs = 2000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() > deadline) throw new Error("waitFor timed out");
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

function last(sent: Captured[], type: string): Captured | undefined {
  return [...sent].reverse().find((m) => m.type === type);
}

function ingestLive(server: any, nodeId: number): void {
  server.ingestSample({
    timestamp: Date.now(),
    h1: { re: 1, im: 1 },
    h2: { re: 1, im: 1 },
    rssi: -40,
    nodeId,
    amplitudes: [1, 1, 1, 1],
  });
}

function frameLine(t: number, n: number): string {
  return JSON.stringify({ type: "frame", t, n, rssi: -40, a: [1, 2, 3, 4] });
}

test("synthetic demo labels every message synthetic and unwinds to live on stop", async () => {
  const { server, client } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
    await waitFor(() => client.sent.some((m) => m.type === "radialTarget" && m.data));

    assert.equal(server.status.source, "synthetic");
    assert.equal(server.isDemoActive(), true);
    assert.equal(last(client.sent, "status")?.data.source, "synthetic");
    assert.equal(last(client.sent, "demoStatus")?.data.mode, "synthetic");
    const state = last(client.sent, "targetState")?.data;
    assert.equal(state.source_mode, "synthetic");
    assert.equal(state.target_visible, true);
    assert.equal(last(client.sent, "radialTarget")?.data.label, "human");
    assert.ok(last(client.sent, "nodes")?.data.every((n: any) => n.source === "synthetic"));
    assert.ok(last(client.sent, "vitalSigns")?.data.heartRateBpm > 0, "demo shows scripted vitals");

    server.handleMessage("operator", { type: "stopDemo", data: null });

    assert.equal(server.isDemoActive(), false);
    assert.equal(server.status.source, "live");
    assert.equal(server.status.isProcessing, false, "demo started processing, so it must stop it");
    assert.equal(last(client.sent, "status")?.data.source, "live");
    assert.equal(last(client.sent, "demoStatus")?.data.active, false);
    const after = last(client.sent, "targetState")?.data;
    assert.equal(after.source_mode, "live");
    assert.equal(after.target_visible, false);
  } finally {
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
  }
});

test("external samples are dropped while a demo runs", async () => {
  const { server, client } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
    await waitFor(() => server.isDemoActive());

    ingestLive(server, 1);
    assert.equal(server.getQueueLength(), 0);
    assert.equal(server.hardwareNodeLastSeenMs.size, 0, "a dropped sample must not mark a node live");
    assert.ok(client.sent.length > 0);
  } finally {
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
  }
});

test("demo is refused while live ESP32 nodes are streaming", async () => {
  const { server, client } = newServer();
  ingestLive(server, 1);

  server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
  await waitFor(() => client.sent.some((m) => m.type === "error"));

  assert.match(last(client.sent, "error")?.data, /Live ESP32 nodes are streaming/);
  assert.equal(server.isDemoActive(), false);
  assert.equal(server.status.source, "live");
  assert.equal(server.getQueueLength(), 1, "the live sample must be untouched");
});

test("startDemo rejects an unknown mode and a second concurrent start", async () => {
  const { server, client } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "bogus" } });
    await waitFor(() => client.sent.some((m) => m.type === "error"));
    assert.match(last(client.sent, "error")?.data, /synthetic.*replay/);
    assert.equal(server.isDemoActive(), false);

    server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
    await waitFor(() => server.isDemoActive());
    client.sent.length = 0;
    server.handleMessage("operator", { type: "startDemo", data: { mode: "replay" } });
    await waitFor(() => client.sent.some((m) => m.type === "error"));
    assert.match(last(client.sent, "error")?.data, /already running/);
    assert.equal(server.status.source, "synthetic", "the running demo must be unaffected");
  } finally {
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
  }
});

test("stopProcessing also ends a running demo", async () => {
  const { server } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
    await waitFor(() => server.isDemoActive());

    server.handleMessage("operator", { type: "stopProcessing", data: null });

    assert.equal(server.isDemoActive(), false);
    assert.equal(server.status.source, "live");
  } finally {
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
  }
});

test("the last client disconnecting ends the demo", async () => {
  const { server } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
    await waitFor(() => server.isDemoActive());

    server.clients.delete("operator");
    server.stopDemoSession();

    assert.equal(server.isDemoActive(), false);
    assert.equal(server.status.source, "live");
  } finally {
    server.stopProcessing();
  }
});

test("a demo is refused while a scan is already running", async () => {
  const { server, client } = newServer();
  server.status.isProcessing = true;

  server.handleMessage("operator", { type: "startDemo", data: { mode: "synthetic" } });
  await waitFor(() => client.sent.some((m) => m.type === "error"));

  assert.match(last(client.sent, "error")?.data, /Stop the scan/);
  assert.equal(server.isDemoActive(), false);
  assert.equal(server.status.source, "live");
  assert.equal(server.status.isProcessing, true, "the operator's scan must be left running");
});

test("a demo never records and never saves a session into the real history", async () => {
  const dir = mkdtempSync(join(tmpdir(), "demo-ws-"));
  const header = JSON.stringify({ type: "header", schema: 1 });
  writeFileSync(
    join(dir, "room1__s1__empty__1.jsonl"),
    [header, ...[0, 1, 2, 3, 4, 5, 6, 7].map((n) => frameLine(1_000 + n, (n % 4) + 1))].join("\n") + "\n",
  );
  writeFileSync(join(dir, "room1__s2__still__1.jsonl"), [header, frameLine(1_000, 1)].join("\n") + "\n");
  const previous = process.env.PHANTOM_DEMO_DATASET_DIR;
  process.env.PHANTOM_DEMO_DATASET_DIR = dir;
  const saved: unknown[] = [];
  const originalSave = sessionStore.save;
  (sessionStore as any).save = (...args: unknown[]) => {
    saved.push(args);
  };
  const { server } = newServer();
  try {
    for (const mode of ["synthetic", "replay"] as const) {
      server.handleMessage("operator", { type: "startDemo", data: { mode } });
      await waitFor(() => server.isDemoActive() && server.status.isProcessing);
      if (mode === "replay") await waitFor(() => server.reportFrameCount > 0);

      assert.equal(server.isRecording, false, `${mode}: a demo must not start a recording`);

      server.handleMessage("operator", { type: "stopDemo", data: null });
      assert.equal(server.isDemoActive(), false);
      assert.equal(saved.length, 0, `${mode}: a demo must not write a session to the persistent store`);

      // A stray stop after the demo (server is back in live mode) must not
      // resurrect the demo's report counters into a saved session either.
      server.stopProcessing();
      assert.equal(saved.length, 0, `${mode}: demo report data must not outlive the demo`);
    }
  } finally {
    (sessionStore as any).save = originalSave;
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
    if (previous === undefined) delete process.env.PHANTOM_DEMO_DATASET_DIR;
    else process.env.PHANTOM_DEMO_DATASET_DIR = previous;
    rmSync(dir, { recursive: true, force: true });
  }
});

test("replay demo with no recordings reports why and returns to live", async () => {
  const dir = mkdtempSync(join(tmpdir(), "demo-ws-"));
  const previous = process.env.PHANTOM_DEMO_DATASET_DIR;
  process.env.PHANTOM_DEMO_DATASET_DIR = dir;
  try {
    const { server, client } = newServer();
    server.handleMessage("operator", { type: "startDemo", data: { mode: "replay" } });
    await waitFor(() => client.sent.some((m) => m.type === "error"));

    assert.match(last(client.sent, "error")?.data, /"empty" recording/);
    assert.equal(server.isDemoActive(), false);
    assert.equal(server.status.source, "live");
    assert.equal(server.status.isProcessing, false);
  } finally {
    if (previous === undefined) delete process.env.PHANTOM_DEMO_DATASET_DIR;
    else process.env.PHANTOM_DEMO_DATASET_DIR = previous;
    rmSync(dir, { recursive: true, force: true });
  }
});

test("replay demo feeds the real pipeline and labels the state replay", async () => {
  const dir = mkdtempSync(join(tmpdir(), "demo-ws-"));
  const header = JSON.stringify({ type: "header", schema: 1 });
  writeFileSync(
    join(dir, "room1__s1__empty__1.jsonl"),
    [header, ...[0, 1, 2, 3].map((n) => frameLine(1_000 + n, n + 1))].join("\n") + "\n",
  );
  writeFileSync(
    join(dir, "room1__s2__still__1.jsonl"),
    [header, frameLine(1_000, 1)].join("\n") + "\n",
  );
  const previous = process.env.PHANTOM_DEMO_DATASET_DIR;
  process.env.PHANTOM_DEMO_DATASET_DIR = dir;
  const { server, client } = newServer();
  try {
    server.handleMessage("operator", { type: "startDemo", data: { mode: "replay" } });
    await waitFor(() => server.status.samplesReceived > 0);

    assert.equal(server.status.source, "replay");
    assert.equal(last(client.sent, "demoStatus")?.data.mode, "replay");
    assert.equal(last(client.sent, "demoStatus")?.data.phase, "calibrating");
    assert.equal(last(client.sent, "targetState")?.data.source_mode, "replay");
    assert.ok(
      !client.sent.some((m) => m.type === "radialTarget" && m.data?.label === "human" && m.data?.humanProb === 0.9),
      "replay must not emit the scripted walker's target",
    );

    // After the demo the dashboard must not keep seeing replayed nodes as live,
    // or the Demo buttons stay disabled ("live nodes streaming") until a reload.
    server.handleMessage("operator", { type: "stopDemo", data: null });
    const nodesAfter = last(client.sent, "nodes")?.data as Array<{ active: boolean }>;
    assert.ok(nodesAfter.length > 0 && nodesAfter.every((n) => n.active === false), "nodes must read inactive after the demo");
  } finally {
    server.handleMessage("operator", { type: "stopDemo", data: null });
    server.stopProcessing();
    if (previous === undefined) delete process.env.PHANTOM_DEMO_DATASET_DIR;
    else process.env.PHANTOM_DEMO_DATASET_DIR = previous;
    rmSync(dir, { recursive: true, force: true });
  }
});
