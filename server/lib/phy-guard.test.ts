import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import { parseCsiPacket } from "./udp-server";
import { PhyGuard, shouldLogPhyMismatch } from "./phy-guard";

// Same vector as tests/test_csi_header_offsets.py (built by hand from the firmware layout in csi_collector.c).
const VECTOR_HEX = "010011c501020104008509000004030201d1a4060200000001000000443322110102030405060708";

function build(opts: { node?: number; nSub?: number; freq?: number; seq?: number; rssi?: number; noise?: number; channel?: number } = {}): Buffer {
  const { node = 2, nSub = 4, freq = 2437, seq = 0x01020304, rssi = -47, noise = -92, channel = 6 } = opts;
  const b = Buffer.alloc(32 + 2 * nSub);
  b.writeUInt32LE(0xc5110001, 0);
  b[4] = 1;
  b[5] = node;
  b[6] = 1;
  b.writeUInt16LE(nSub, 7);
  b.writeUInt32LE(freq, 9);
  b.writeUInt32LE(seq, 13);
  b.writeInt8(rssi, 17);
  b.writeInt8(noise, 18);
  b[19] = channel;
  b.writeBigUInt64LE(0x0000000100000002n, 20);
  b.writeUInt32LE(0x11223344, 28);
  for (let i = 0; i < 2 * nSub; i++) b[32 + i] = i + 1;
  return b;
}

test("the hand-built frame equals the pinned vector and parseCsiPacket reads every field from the firmware offset", () => {
  assert.equal(build().toString("hex"), VECTOR_HEX);
  const p = parseCsiPacket(Buffer.from(VECTOR_HEX, "hex"));
  assert.ok(p);
  assert.deepEqual(
    [p.schemaVersion, p.nodeId, p.numAntennas, p.numSubcarriers, p.freqMhz, p.seq, p.rssi, p.noiseDbm, p.channel, p.deviceTsMs],
    [1, 2, 1, 4, 2437, 0x01020304, -47, -92, 6, 0x11223344],
  );
  assert.equal(p.deviceTsUs, 0x0000000100000002n);
  assert.deepEqual(Array.from(p.iqData), [1, 2, 3, 4, 5, 6, 7, 8]);
});

test("RSSI is a signed byte at offset 17 including the extremes, and neighbouring bytes do not leak into it", () => {
  for (const rssi of [-128, -100, -47, -1, 0, 1, 127]) assert.equal(parseCsiPacket(build({ rssi }))?.rssi, rssi);
  const raw = build();
  raw[16] = 0x55;
  raw[19] = 11;
  const p = parseCsiPacket(raw);
  assert.deepEqual([p?.rssi, p?.noiseDbm, p?.channel], [-47, -92, 11]);
});

test("PhyGuard locks the first tuple per node and flags subcarrier-count, channel and frequency changes", () => {
  const g = new PhyGuard();
  const t = { nSubcarriers: 51, channel: 6, freqMhz: 2437 };
  assert.deepEqual(g.observe(1, t), []);                                   // first frame locks
  assert.deepEqual(g.observe(1, { ...t }), []);
  assert.deepEqual(g.observe(1, { ...t, nSubcarriers: 52 }), ["nSubcarriers"]);
  assert.deepEqual(g.observe(1, { ...t, channel: 11, freqMhz: 2462 }), ["channel", "freqMhz"]);
  assert.deepEqual(g.observe(2, { nSubcarriers: 52, channel: 11, freqMhz: 2462 }), []);   // node 2 has its own lock
  const s = g.snapshot()["1"];
  assert.equal(s.frames, 4);
  assert.equal(s.mismatchedFrames, 2);
  assert.deepEqual(s.mismatchByField, { nSubcarriers: 1, channel: 1, freqMhz: 1 });
  assert.equal(s.firstMismatchFrame, 3);
  assert.deepEqual(s.locked, t);
});

test("reset forgets the lock; the log policy is first mismatch then every 1000th, never per frame", () => {
  const g = new PhyGuard();
  g.observe(1, { nSubcarriers: 51, channel: 6, freqMhz: 2437 });
  g.reset(1);
  assert.deepEqual(g.observe(1, { nSubcarriers: 52, channel: 6, freqMhz: 2437 }), []);   // re-locked on the new tuple
  const base = { locked: { nSubcarriers: 1, channel: 1, freqMhz: 1 }, frames: 5000, mismatchByField: { nSubcarriers: 0, channel: 0, freqMhz: 0 }, firstMismatchFrame: 1 };
  assert.equal(shouldLogPhyMismatch({ ...base, mismatchedFrames: 1 }), true);
  assert.equal(shouldLogPhyMismatch({ ...base, mismatchedFrames: 2 }), false);
  assert.equal(shouldLogPhyMismatch({ ...base, mismatchedFrames: 1000 }), true);
});

test("the guard is wired in SHADOW mode: the observe block in the UDP path contains no return, and says frames are not dropped", () => {
  const src = fs.readFileSync("server/lib/udp-server.ts", "utf-8");
  const start = src.indexOf("phyGuard.observe(");
  const end = src.indexOf("// Forward only accepted raw packets", start);
  assert.ok(start > 0 && end > start);
  const block = src.slice(start, end);
  assert.ok(!/\breturn\b/.test(block), "shadow mode must never drop a frame");
  assert.ok(block.includes("NOT dropped"));
});
