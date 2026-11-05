/**
 * Item D (PS-FIX-08 hardening): a PHY-guard FAULT must never drop or delay a frame, and must not flood the log.
 *
 * This runs the REAL UDP handler (startUDPServer) on the isolated test port 5099 ONLY. It never binds 5000 or 5005: UDP_PORT is set before
 * ./udp-server is evaluated (that module reads it at load), the bound port is asserted, and the server is closed if it is anything else.
 * The sidecar-forward address is pointed at a dead port (5098); the handler forwards raw frames there and nothing listens, which is fine.
 * The singleton signalServer.ingestSample is replaced by a recorder, so nothing reaches the detector and no session file is written.
 */
process.env.UDP_PORT = "5099";
process.env.PY_SIDECAR_PORT = "5098";
process.env.PY_SIDECAR_HOST = "127.0.0.1";

import test, { after, before } from "node:test";
import assert from "node:assert/strict";
import dgram from "dgram";

const TEST_PORT = 5099;
const WAIT_MS = 2000;
const MAX_INGEST_LATENCY_MS = 500;
const N_SUB = 64;

let nextSeq = 1;
/** An ADR-018 32-byte-header frame (offsets as in csi_collector.c; same layout the phy-guard tests pin). */
function frame(node = 1): Buffer {
  const b = Buffer.alloc(32 + 2 * N_SUB);
  b.writeUInt32LE(0xc5110001, 0);
  b[4] = 1;
  b[5] = node;
  b[6] = 1;
  b.writeUInt16LE(N_SUB, 7);
  b.writeUInt32LE(2437, 9);
  b.writeUInt32LE(nextSeq++, 13);
  b.writeInt8(-47, 17);
  b.writeInt8(-92, 18);
  b[19] = 6;
  b.writeBigUInt64LE(BigInt(nextSeq) * 1000n, 20);
  b.writeUInt32LE(nextSeq * 30, 28);
  for (let i = 0; i < 2 * N_SUB; i++) b[32 + i] = ((i * 7) % 61) + 3;
  return b;
}

async function waitFor(cond: () => boolean, ms = WAIT_MS): Promise<boolean> {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (cond()) return true;
    await new Promise((r) => setTimeout(r, 5));
  }
  return cond();
}

type AnyFn = (...args: unknown[]) => unknown;
const ingested: Array<{ nodeId?: number; rssi?: number; at: number }> = [];
const consoleErrors: string[] = [];
let udpServer: dgram.Socket | undefined;
let client: dgram.Socket | undefined;
let phyGuardRef: { observe: AnyFn } | undefined;
let signalServerRef: { ingestSample: AnyFn } | undefined;
let originalObserve: AnyFn | undefined;
let originalIngest: AnyFn | undefined;
let originalConsoleError: typeof console.error | undefined;

before(async () => {
  assert.equal(process.env.UDP_PORT, String(TEST_PORT), "the test must only ever use the isolated port");
  const { startUDPServer } = await import("./udp-server");
  const { signalServer } = await import("./websocket");
  const { phyGuard } = await import("./phy-guard");
  signalServerRef = signalServer as unknown as { ingestSample: AnyFn };
  phyGuardRef = phyGuard as unknown as { observe: AnyFn };
  originalIngest = signalServerRef.ingestSample;
  originalObserve = phyGuardRef.observe;
  signalServerRef.ingestSample = (s: unknown) => {
    const sample = s as { nodeId?: number; rssi?: number };
    ingested.push({ nodeId: sample.nodeId, rssi: sample.rssi, at: Date.now() });
  };
  originalConsoleError = console.error;
  console.error = (...a: unknown[]) => {
    consoleErrors.push(a.map(String).join(" "));
  };
  const server = startUDPServer();
  await new Promise<void>((resolve, reject) => {
    server.once("listening", () => resolve());
    server.once("error", reject);
  });
  const port = (server.address() as { port: number }).port;
  if (port !== TEST_PORT) {
    server.close();
    throw new Error(`refusing to run: the UDP handler bound port ${port}, not the isolated test port ${TEST_PORT}`);
  }
  udpServer = server;
  client = dgram.createSocket("udp4");
});

after(async () => {
  if (phyGuardRef && originalObserve) phyGuardRef.observe = originalObserve;
  if (signalServerRef && originalIngest) signalServerRef.ingestSample = originalIngest;
  if (originalConsoleError) console.error = originalConsoleError;
  client?.close();
  await new Promise<void>((resolve) => {
    if (!udpServer) return resolve();
    udpServer.once("close", () => resolve());
    udpServer.close();
  });
});

function send(buf: Buffer): Promise<void> {
  return new Promise((resolve, reject) => client!.send(buf, TEST_PORT, "127.0.0.1", (err) => (err ? reject(err) : resolve())));
}

test("a healthy guard: the frame is ingested and no guard fault is logged (baseline)", async () => {
  const before = ingested.length;
  await send(frame(1));
  assert.ok(await waitFor(() => ingested.length >= before + 1), "the baseline frame was not ingested");
  assert.equal(consoleErrors.filter((m) => m.includes("[PHY] guard fault")).length, 0);
});

test("a THROWING PHY guard cannot drop or delay a frame: every frame is still ingested, promptly", async () => {
  phyGuardRef!.observe = () => {
    throw new Error("injected guard fault");
  };
  const start = ingested.length;
  const sentAt = Date.now();
  for (let i = 0; i < 5; i++) await send(frame(1));
  assert.ok(await waitFor(() => ingested.length >= start + 5), `only ${ingested.length - start} of 5 frames were ingested with a throwing guard`);
  const got = ingested.slice(start, start + 5);
  assert.ok(got.every((s) => s.nodeId === 1 && s.rssi === -47), "an ingested sample was altered");
  assert.ok(got[0].at - sentAt < MAX_INGEST_LATENCY_MS, `first frame took ${got[0].at - sentAt} ms with a throwing guard`);
});

test("the guard fault is logged once, not per frame (5 faults, 1 log line)", async () => {
  const faults = consoleErrors.filter((m) => m.includes("[PHY] guard fault"));
  assert.equal(faults.length, 1, `expected exactly one fault log line, got ${faults.length}`);
  assert.match(faults[0], /injected guard fault/);
  assert.match(faults[0], /frame still ingested|ingested/);
});

test("after the fault clears, ingestion carries on and the counter does not leak into the healthy path", async () => {
  phyGuardRef!.observe = originalObserve!;
  const start = ingested.length;
  const errorsBefore = consoleErrors.length;
  await send(frame(1));
  assert.ok(await waitFor(() => ingested.length >= start + 1));
  assert.equal(consoleErrors.length, errorsBefore, "a healthy frame logged an error");
});

test("fault log policy: the 1st fault and every 1000th, never the others", async () => {
  const { shouldLogPhyGuardFault } = await import("./phy-guard");
  assert.equal(shouldLogPhyGuardFault(1), true);
  for (const n of [2, 3, 10, 999, 1001, 1999, 2001]) assert.equal(shouldLogPhyGuardFault(n), false, `n=${n}`);
  assert.equal(shouldLogPhyGuardFault(1000), true);
  assert.equal(shouldLogPhyGuardFault(2000), true);
  assert.equal(shouldLogPhyGuardFault(0), false);
});

test("the test never bound the live ports", () => {
  assert.equal((udpServer!.address() as { port: number }).port, TEST_PORT);
  assert.notEqual(TEST_PORT, 5005);
  assert.notEqual(TEST_PORT, 5000);
});
