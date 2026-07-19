import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import path from "path";
import { parseCsiPacket } from "../../server/lib/udp-server";

/**
 * B6 — runtime replay through THE AUTHORITY's real ingest path, using a
 * committed real capture (not hand-built synthetic packets). Scope
 * decision, stated explicitly rather than silently narrowed: this proves
 * every real captured CSI frame in the fixture round-trips through
 * parseCsiPacket() (THE AUTHORITY's actual wire parser) with exact field
 * fidelity — the AUTHORITY-specific part of B6. It does NOT re-run the
 * fusion/motion pipeline on this real data, because that pipeline's
 * amplitude-extraction step is private to SignalProcessingServer's
 * processing loop (server/lib/websocket.ts) and isn't exported for reuse;
 * exporting it would be a product change, which this test-only pass must
 * not make. Fusion-math invariants are instead covered on synthetic inputs
 * by tests/behavioral/fusion-invariants.test.ts and the existing 20 tests
 * in server/lib/node-fusion.test.ts. See
 * PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md for what would close this gap
 * (either exporting the amplitude pipeline for testability, or a live
 * TS-server + real-UDP-replay harness).
 */

function reconstructAdr018Frame(record: Record<string, unknown>): Buffer {
  const header = Buffer.alloc(32);
  header.writeUInt32LE(0xc5110001, 0);
  header.writeUInt8(1, 4); // schema version
  header.writeUInt8(record.node_id as number, 5);
  header.writeUInt8(record.n_antennas as number, 6);
  header.writeUInt16LE(record.n_subcarriers as number, 7);
  header.writeUInt32LE(record.freq_mhz as number, 9);
  header.writeUInt32LE((record.seq as number) >>> 0, 13);
  header.writeInt8(record.rssi_dbm as number, 17);
  header.writeInt8(record.noise_dbm as number, 18);
  header.writeUInt8(record.channel as number, 19);
  header.writeBigUInt64LE(BigInt(record.device_ts_us as number), 20);
  header.writeUInt32LE((record.device_ts_ms as number) >>> 0, 28);
  const iq = Buffer.from(record.iq_hex as string, "hex");
  return Buffer.concat([header, iq]);
}

test("real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity", () => {
  const fixturePath = path.resolve(
    "data", "sessions", "74b9bc7d51744175959d483941aa8e1a.jsonl",
  );
  const raw = fs.readFileSync(fixturePath, "utf-8");
  const lines = raw.split("\n").filter((l) => l.trim().length > 0);

  let csiFrameCount = 0;
  let parseFailures = 0;
  const nodeIds = new Set<number>();

  for (const line of lines) {
    const record = JSON.parse(line) as Record<string, unknown>;
    if (record.record_type !== "csi_frame") continue;
    csiFrameCount++;

    const packet = reconstructAdr018Frame(record);
    const parsed = parseCsiPacket(packet);
    if (!parsed) {
      parseFailures++;
      continue;
    }
    assert.equal(parsed.nodeId, record.node_id);
    assert.equal(parsed.seq, (record.seq as number) >>> 0);
    assert.equal(parsed.freqMhz, record.freq_mhz);
    assert.equal(parsed.channel, record.channel);
    assert.equal(parsed.numAntennas, record.n_antennas);
    assert.equal(parsed.numSubcarriers, record.n_subcarriers);
    assert.equal(parsed.iqData.toString("hex"), record.iq_hex);
    nodeIds.add(record.node_id as number);
  }

  assert.ok(csiFrameCount > 0, "fixture must contain at least one csi_frame record");
  assert.equal(parseFailures, 0, "every real captured frame must parse cleanly through THE AUTHORITY's live parser");
  assert.deepEqual([...nodeIds].sort(), [1, 2], "fixture should exercise both nodes");
});
