import test from "node:test";
import assert from "node:assert/strict";
import { parseCsiPacket, SourcePinningGuard } from "./udp-server";
import fs from "fs";
import path from "path";

function loadFixture(name: string): Buffer {
  const hex = fs.readFileSync(path.resolve("tests", "fixtures", name), "utf-8").trim();
  return Buffer.from(hex, "hex");
}

function buildAdr018Packet(): Buffer {
  const iq = Buffer.from([10, 20, 30, 40, 50, 60, 70, 80]);
  const header = Buffer.alloc(32);
  header.writeUInt32LE(0xc5110001, 0);
  header.writeUInt8(1, 4); // schema version
  header.writeUInt8(1, 5); // node id
  header.writeUInt8(1, 6); // antennas
  header.writeUInt16LE(4, 7); // subcarriers
  header.writeUInt32LE(2412, 9); // freq
  header.writeUInt32LE(17, 13); // seq
  header.writeInt8(-55, 17); // rssi
  header.writeInt8(-90, 18); // noise
  header.writeUInt8(1, 19); // channel
  header.writeBigUInt64LE(123456789n, 20); // device ts us
  header.writeUInt32LE(123456, 28); // device ts ms
  return Buffer.concat([header, iq]);
}

function buildHeartbeatPacket(): Buffer {
  const packet = Buffer.alloc(40);
  packet.writeUInt32LE(0xc51100a1, 0);
  packet.writeUInt8(1, 4);
  packet.writeUInt8(1, 5);
  return packet;
}

function buildLegacyPacket(): Buffer {
  const iq = Buffer.from([9, 8, 7, 6]);
  const header = Buffer.alloc(20);
  header.writeUInt32LE(0xc5110001, 0);
  header.writeUInt8(2, 4); // node id, not schema version in legacy layout
  header.writeUInt8(1, 5); // antennas
  header.writeUInt16LE(2, 6); // subcarriers
  header.writeInt8(-61, 16); // rssi
  return Buffer.concat([header, iq]);
}

test("parseCsiPacket accepts ADR-018 32-byte CSI frames", () => {
  const parsed = parseCsiPacket(buildAdr018Packet());
  assert(parsed);
  assert.equal(parsed.nodeId, 1);
  assert.equal(parsed.numAntennas, 1);
  assert.equal(parsed.numSubcarriers, 4);
  assert.equal(parsed.rssi, -55);
  assert.equal(parsed.iqData.length, 8);
});

test("parseCsiPacket matches committed ADR-018 fixture fields", () => {
  const parsed = parseCsiPacket(loadFixture("adr018_frame.hex"));
  assert(parsed);
  assert.equal(parsed.schemaVersion, 1);
  assert.equal(parsed.nodeId, 2);
  assert.equal(parsed.seq, 17);
  assert.equal(parsed.freqMhz, 2412);
  assert.equal(parsed.noiseDbm, -90);
  assert.equal(parsed.channel, 1);
  assert.equal(parsed.deviceTsUs, 123456789n);
  assert.equal(parsed.deviceTsMs, 123456);
  assert.equal(parsed.numAntennas, 1);
  assert.equal(parsed.numSubcarriers, 4);
  assert.equal(parsed.rssi, -55);
  assert.deepEqual([...parsed.iqData], [1, 2, 3, 4, 5, 6, 7, 8]);
});

test("parseCsiPacket ignores heartbeat packets", () => {
  const parsed = parseCsiPacket(buildHeartbeatPacket());
  assert.equal(parsed, null);
});

test("parseCsiPacket ignores committed heartbeat fixture", () => {
  const parsed = parseCsiPacket(loadFixture("heartbeat_frame.hex"));
  assert.equal(parsed, null);
});

test("parseCsiPacket routes legacy packets after ADR-018 check", () => {
  const parsed = parseCsiPacket(buildLegacyPacket());
  assert(parsed);
  assert.equal(parsed.nodeId, 2);
  assert.equal(parsed.numAntennas, 1);
  assert.equal(parsed.numSubcarriers, 2);
  assert.equal(parsed.rssi, -61);
});

test("SourcePinningGuard rejects same node id from a foreign source", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 5005 }), true);
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 5005 }), true);
  assert.equal(guard.check(1, { address: "10.0.0.99", port: 5005 }), false);
  assert.deepEqual(guard.getBindings(), {
    "1": { address: "10.0.0.11", port: 5005 },
  });
  assert.equal(guard.getRejectionCount(), 1);
  assert.deepEqual(guard.getSecurityEvents(), [
    {
      record_type: "security_event",
      event_type: "node_source_mismatch",
      node_id: 1,
      expected_source: { ip: "10.0.0.11", port: 5005 },
      actual_source: { ip: "10.0.0.99", port: 5005 },
      packet_kind: "csi_frame",
    },
  ]);
});
