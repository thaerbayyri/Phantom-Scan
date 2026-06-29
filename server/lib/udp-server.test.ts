import test from "node:test";
import assert from "node:assert/strict";
import { parseCsiPacket } from "./udp-server";

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

test("parseCsiPacket accepts ADR-018 32-byte CSI frames", () => {
  const parsed = parseCsiPacket(buildAdr018Packet());
  assert(parsed);
  assert.equal(parsed.nodeId, 1);
  assert.equal(parsed.numAntennas, 1);
  assert.equal(parsed.numSubcarriers, 4);
  assert.equal(parsed.rssi, -55);
  assert.equal(parsed.iqData.length, 8);
});

test("parseCsiPacket ignores heartbeat packets", () => {
  const parsed = parseCsiPacket(buildHeartbeatPacket());
  assert.equal(parsed, null);
});
