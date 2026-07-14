import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyPacketMagic,
  crc32IEEE,
  parseCsiPacket,
  parseEdgeVitalsPacket,
  parseFeatureStatePacket,
  SourcePinningGuard,
} from "./udp-server";
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

test("SourcePinningGuard accepts same IP with a new ephemeral port (ESP32 reboot)", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 59608 }, 1_000), true);
  // Reboot: same device IP, new source port — must be accepted and rebound.
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 56569 }, 2_000), true);
  assert.deepEqual(guard.getBindings()["1"], { address: "10.0.0.11", port: 56569 });
  assert.equal(guard.getRejectionCount(), 0);
});

test("SourcePinningGuard rejects a new IP while the pinned source is still active", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(2, { address: "10.0.0.20", port: 5005 }, 1_000), true);
  // Conflicting IP only 2 s after the pinned source last sent: spoof signal.
  assert.equal(guard.check(2, { address: "10.0.0.99", port: 5005 }, 3_000), false);
  assert.deepEqual(guard.getBindings()["2"], { address: "10.0.0.20", port: 5005 });
});

test("SourcePinningGuard rebinds a new IP after the pinned source goes stale (DHCP renumber)", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(2, { address: "10.0.0.20", port: 5005 }, 1_000), true);
  // 11 s of silence from the pinned source, then a new IP claims the node.
  const later = 1_000 + SourcePinningGuard.STALE_BINDING_MS + 1_000;
  assert.equal(guard.check(2, { address: "10.0.0.99", port: 6001 }, later), true);
  assert.deepEqual(guard.getBindings()["2"], { address: "10.0.0.99", port: 6001 });
  assert.equal(guard.getRejectionCount(), 0);
});

test("SourcePinningGuard bounds the security-event history", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 5005 }, 1_000), true);
  // Flood 250 conflicting packets while the pinned source stays fresh
  // (interleave accepted packets so the binding never goes stale).
  for (let i = 0; i < 250; i++) {
    const t = 1_000 + i * 10;
    guard.check(1, { address: "10.0.0.11", port: 5005 }, t);
    guard.check(1, { address: "10.0.0.99", port: 5005 }, t + 1);
  }
  assert.equal(guard.getRejectionCount(), 250);
  assert.equal(guard.getSecurityEvents().length, SourcePinningGuard.MAX_EVENTS);
});

function buildFeatureStatePacket(nodeId: number): Buffer {
  const buf = Buffer.alloc(56);
  buf.writeUInt32LE(0xc5110006, 0);
  buf.writeUInt8(nodeId, 4);
  buf.writeFloatLE(0.42, 16); // motion
  buf.writeFloatLE(0.88, 20); // presence
  buf.writeFloatLE(14.5, 24); // resp_bpm
  buf.writeFloatLE(0.7, 28);  // resp_conf
  buf.writeFloatLE(62.0, 32); // hr_bpm
  buf.writeFloatLE(0.35, 36); // hr_conf
  return buf;
}

test("parseFeatureStatePacket decodes the RuView 0xC5110006 layout", () => {
  const parsed = parseFeatureStatePacket(buildFeatureStatePacket(2));
  assert(parsed);
  assert.equal(parsed.nodeId, 2);
  assert.ok(Math.abs(parsed.motion - 0.42) < 1e-6);
  assert.ok(Math.abs(parsed.presence - 0.88) < 1e-6);
  assert.ok(Math.abs(parsed.respBpm - 14.5) < 1e-4);
  assert.ok(Math.abs(parsed.respConf - 0.7) < 1e-6);
  assert.ok(Math.abs(parsed.hrBpm - 62.0) < 1e-4);
  assert.ok(Math.abs(parsed.hrConf - 0.35) < 1e-6);
});

test("parseFeatureStatePacket rejects short packets and wrong magic", () => {
  assert.equal(parseFeatureStatePacket(buildFeatureStatePacket(1).subarray(0, 40)), null);
  const wrongMagic = buildFeatureStatePacket(1);
  wrongMagic.writeUInt32LE(0xc5110001, 0);
  assert.equal(parseFeatureStatePacket(wrongMagic), null);
});

// 32-byte edge_vitals_pkt_t from this repo's own firmware
// (firmware/esp32-csi-node/main/edge_processing.h).
function buildEdgeVitalsPacket(nodeId: number): Buffer {
  const buf = Buffer.alloc(32);
  buf.writeUInt32LE(0xc5110002, 0);
  buf.writeUInt8(nodeId, 4);
  buf.writeUInt8(0b101, 5);        // flags: presence + motion
  buf.writeUInt16LE(1450, 6);      // breathing_rate = 14.5 BPM * 100
  buf.writeUInt32LE(620000, 8);    // heartrate = 62.0 BPM * 10000
  buf.writeInt8(-55, 12);          // rssi
  buf.writeUInt8(1, 13);           // n_persons
  buf.writeFloatLE(0.42, 16);      // motion_energy
  buf.writeFloatLE(0.88, 20);      // presence_score
  buf.writeUInt32LE(123456, 24);   // timestamp_ms
  return buf;
}

test("parseEdgeVitalsPacket decodes the firmware 0xC5110002 layout", () => {
  const parsed = parseEdgeVitalsPacket(buildEdgeVitalsPacket(2));
  assert(parsed);
  assert.equal(parsed.nodeId, 2);
  assert.ok(Math.abs(parsed.motion - 0.42) < 1e-6);
  assert.ok(Math.abs(parsed.presence - 0.88) < 1e-6);
  assert.ok(Math.abs(parsed.respBpm - 14.5) < 1e-4);
  assert.equal(parsed.respConf, 1);
  assert.ok(Math.abs(parsed.hrBpm - 62.0) < 1e-4);
  assert.equal(parsed.hrConf, 1);
});

test("parseEdgeVitalsPacket zeroes confidence for zero BPM estimates", () => {
  const pkt = buildEdgeVitalsPacket(1);
  pkt.writeUInt16LE(0, 6);
  pkt.writeUInt32LE(0, 8);
  const parsed = parseEdgeVitalsPacket(pkt);
  assert(parsed);
  assert.equal(parsed.respBpm, 0);
  assert.equal(parsed.respConf, 0);
  assert.equal(parsed.hrBpm, 0);
  assert.equal(parsed.hrConf, 0);
});

test("parseEdgeVitalsPacket rejects short packets and wrong magic", () => {
  assert.equal(parseEdgeVitalsPacket(buildEdgeVitalsPacket(1).subarray(0, 20)), null);
  const wrongMagic = buildEdgeVitalsPacket(1);
  wrongMagic.writeUInt32LE(0xc5110006, 0);
  assert.equal(parseEdgeVitalsPacket(wrongMagic), null);
});

test("parseEdgeVitalsPacket propagates the board-reported RSSI", () => {
  const parsed = parseEdgeVitalsPacket(buildEdgeVitalsPacket(2));
  assert(parsed);
  assert.equal(parsed.rssi, -55);
});

test("parseFeatureStatePacket leaves rssi undefined (packet carries none)", () => {
  const parsed = parseFeatureStatePacket(buildFeatureStatePacket(1));
  assert(parsed);
  assert.equal(parsed.rssi, undefined);
});

// Full 60-byte rv_feature_state as emitted by the new firmware: every field
// populated, quality flags @52, IEEE CRC32 over bytes 0..55 @56.
function buildFullFeatureStatePacket(nodeId: number): Buffer {
  const buf = Buffer.alloc(60);
  buf.writeUInt32LE(0xc5110006, 0);
  buf.writeUInt8(nodeId, 4);
  buf.writeUInt8(2, 5);            // mode
  buf.writeUInt16LE(321, 6);       // seq
  buf.writeBigUInt64LE(987654321n, 8); // ts_us
  buf.writeFloatLE(0.031, 16);     // motion_score
  buf.writeFloatLE(0.031, 20);     // presence_score
  buf.writeFloatLE(13.2, 24);      // respiration_bpm
  buf.writeFloatLE(0.55, 28);      // respiration_conf
  buf.writeFloatLE(71.5, 32);      // heartbeat_bpm
  buf.writeFloatLE(0.42, 36);      // heartbeat_conf
  buf.writeFloatLE(0, 40);         // anomaly_score
  buf.writeFloatLE(0, 44);         // env_shift_score
  buf.writeFloatLE(0, 48);         // node_coherence
  buf.writeUInt16LE(0b111, 52);    // quality_flags: resp+hr+presence valid
  buf.writeUInt32LE(crc32IEEE(buf, 56), 56);
  return buf;
}

test("parseFeatureStatePacket accepts a full 60-byte packet with valid CRC32", () => {
  const parsed = parseFeatureStatePacket(buildFullFeatureStatePacket(1));
  assert(parsed);
  assert.equal(parsed.nodeId, 1);
  assert.ok(Math.abs(parsed.motion - 0.031) < 1e-6);
  assert.ok(Math.abs(parsed.respBpm - 13.2) < 1e-4);
  assert.ok(Math.abs(parsed.respConf - 0.55) < 1e-6);
  assert.ok(Math.abs(parsed.hrBpm - 71.5) < 1e-4);
  assert.ok(Math.abs(parsed.hrConf - 0.42) < 1e-6);
});

test("parseFeatureStatePacket rejects a 60-byte packet with corrupted CRC32", () => {
  const pkt = buildFullFeatureStatePacket(1);
  pkt.writeUInt32LE((pkt.readUInt32LE(56) ^ 0xdeadbeef) >>> 0, 56);
  assert.equal(parseFeatureStatePacket(pkt), null);
});

test("classifyPacketMagic distinguishes every known packet type", () => {
  assert.equal(classifyPacketMagic(buildAdr018Packet()), "csi");
  assert.equal(classifyPacketMagic(buildHeartbeatPacket()), "heartbeat");
  assert.equal(classifyPacketMagic(buildEdgeVitalsPacket(1)), "vitals");
  assert.equal(classifyPacketMagic(buildFeatureStatePacket(1)), "feature_state");
  const compressed = Buffer.alloc(12);
  compressed.writeUInt32LE(0xc5110003, 0);
  assert.equal(classifyPacketMagic(compressed), "compressed");
  const junk = Buffer.alloc(8);
  junk.writeUInt32LE(0x12345678, 0);
  assert.equal(classifyPacketMagic(junk), "unknown");
  assert.equal(classifyPacketMagic(Buffer.alloc(2)), "unknown");
});

test("SourcePinningGuard accepts feature-state from the pinned source and tags events", () => {
  const guard = new SourcePinningGuard();
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 5005 }, 1_000, "csi_frame"), true);
  // Same IP, second firmware socket (different ephemeral port): silent rebind.
  assert.equal(guard.check(1, { address: "10.0.0.11", port: 6001 }, 1_500, "feature_state"), true);
  // Foreign IP while the pin is fresh: rejected, event tagged feature_state.
  assert.equal(guard.check(1, { address: "10.0.0.99", port: 6001 }, 2_000, "feature_state"), false);
  const events = guard.getSecurityEvents();
  assert.equal(events[events.length - 1].packet_kind, "feature_state");
});
