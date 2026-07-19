import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyPacketMagic,
  parseCsiPacket,
  parseEdgeVitalsPacket,
  parseFeatureStatePacket,
} from "../../server/lib/udp-server";

/**
 * B1 — wire-protocol malformed-input hardening. Complements the existing
 * exhaustive round-trip / heartbeat / Fix-C / legacy-gating coverage already
 * in server/lib/udp-server.test.ts (verified present before writing this
 * file — see PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md's coverage matrix). This
 * file covers only the gaps that coverage didn't: truncation, declared-vs-
 * actual IQ length mismatch, oversized frames, non-1 schema version, direct
 * bad-magic rejection, and NaN/Inf poisoning of the vitals/feature-state
 * float fields.
 */

function buildAdr018Header(overrides: Partial<{
  magic: number;
  schemaVersion: number;
  nodeId: number;
  numAntennas: number;
  numSubcarriers: number;
}> = {}): Buffer {
  const header = Buffer.alloc(32);
  header.writeUInt32LE(overrides.magic ?? 0xc5110001, 0);
  header.writeUInt8(overrides.schemaVersion ?? 1, 4);
  header.writeUInt8(overrides.nodeId ?? 1, 5);
  header.writeUInt8(overrides.numAntennas ?? 1, 6);
  header.writeUInt16LE(overrides.numSubcarriers ?? 4, 7);
  header.writeUInt32LE(2412, 9);
  header.writeUInt32LE(17, 13);
  header.writeInt8(-55, 17);
  header.writeInt8(-90, 18);
  header.writeUInt8(1, 19);
  header.writeBigUInt64LE(123456789n, 20);
  header.writeUInt32LE(123456, 28);
  return header;
}

test("parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode", () => {
  // 25 bytes: too short for the ADR-018 branch (msg.length >= 32 required),
  // and live mode never falls into the legacy 20-byte-header path.
  const truncated = buildAdr018Header().subarray(0, 25);
  assert.equal(parseCsiPacket(truncated), null);
});

test("parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries", () => {
  const header = buildAdr018Header({ numAntennas: 2, numSubcarriers: 8 }); // expects 2*8*2=32 IQ bytes
  const shortIq = Buffer.from([1, 2, 3, 4]); // far fewer than declared
  const packet = Buffer.concat([header, shortIq]);
  assert.equal(parseCsiPacket(packet), null);
});

test("parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped)", () => {
  const header = buildAdr018Header({ numAntennas: 1, numSubcarriers: 4 }); // expects 8 IQ bytes minimum
  const oversizedIq = Buffer.alloc(50_000, 0xab); // far more than declared; still valid (declared <= actual)
  const packet = Buffer.concat([header, oversizedIq]);
  const parsed = parseCsiPacket(packet);
  assert(parsed);
  assert.equal(parsed.iqData.length, oversizedIq.length);
  // Documented observation, not a failure: the parser has no upper bound on
  // iqData length — a malicious/buggy sender's oversized datagram is parsed
  // successfully rather than rejected. Real exposure is bounded by the UDP
  // MTU (~65507 bytes), so this is noted in the report as low-severity, not
  // asserted as a defect here.
});

test("parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode", () => {
  const header = buildAdr018Header({ schemaVersion: 2 });
  const iq = Buffer.from([1, 2, 3, 4]);
  const packet = Buffer.concat([header, iq]);
  // Live mode (allowLegacy unset): schema-version-2 doesn't match the ADR-018
  // branch, and the legacy branch is gated off, so this must be rejected —
  // NOT silently reinterpreted under the legacy 20-byte field layout.
  assert.equal(parseCsiPacket(packet), null);
});

test("parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage)", () => {
  // Initial hypothesis when writing this test: a future ADR-018
  // schema_version=2 frame routed through compat mode would be silently
  // reinterpreted under the legacy 20-byte field layout and "succeed" with
  // garbage values. Verified against the actual parser: this does NOT
  // happen for realistic field values, because the legacy layout's
  // numAntennas/numSubcarriers land on different byte offsets than
  // ADR-018's — reinterpreting ADR-018's numAntennas(@6)/numSubcarriers(@7-8)
  // bytes under legacy's numAntennas(@5)/numSubcarriers(@6-7) offsets
  // produces a byte-shifted, near-arbitrary "expectedIqBytes" that is
  // almost always far larger than any real datagram's IQ payload, so the
  // existing `iqData.length < expectedIqBytes` guard rejects it. Confirmed
  // here with concrete values (ADR-018 numAntennas=1, numSubcarriers=4 ->
  // reinterpreted as legacy numAntennas=9 (the ADR-018 nodeId byte),
  // numSubcarriers=1025 -> expects 18,450 IQ bytes against 20 available).
  const header = buildAdr018Header({ schemaVersion: 2, nodeId: 9 });
  const iq = Buffer.from([1, 2, 3, 4, 5, 6, 7, 8]);
  const packet = Buffer.concat([header, iq]);
  const parsed = parseCsiPacket(packet, { allowLegacy: true });
  assert.equal(parsed, null, "the length cross-check incidentally protects against this misparse for realistic field values — not a guaranteed protection, since a pathological byte pattern could still coincidentally pass length validation, but not reproduced here");
});

test("parseCsiPacket rejects a garbage/unknown magic directly", () => {
  const packet = Buffer.alloc(32);
  packet.writeUInt32LE(0x00000000, 0);
  assert.equal(parseCsiPacket(packet), null);
  assert.equal(classifyPacketMagic(packet), "unknown");
});

test("parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser)", () => {
  const packet = Buffer.alloc(60);
  packet.writeUInt32LE(0xc5110006, 0);
  packet.writeUInt8(1, 4); // node id
  packet.writeFloatLE(NaN, 16); // motion
  packet.writeFloatLE(Infinity, 20); // presence
  packet.writeFloatLE(-Infinity, 24); // respBpm
  packet.writeFloatLE(0.5, 28); // respConf
  packet.writeFloatLE(0, 32); // hrBpm
  packet.writeFloatLE(0, 36); // hrConf
  // No CRC (56-59 byte packets predate the CRC and stay accepted).
  const parsed = parseFeatureStatePacket(packet.subarray(0, 56));
  assert(parsed);
  assert(Number.isNaN(parsed.motion), "parser passes NaN through structurally — documents that float sanity is a downstream concern, not the parser's");
  assert.equal(parsed.presence, Infinity);
  assert.equal(parsed.respBpm, -Infinity);
});

test("parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing", () => {
  const packet = Buffer.alloc(32);
  packet.writeUInt32LE(0xc5110002, 0);
  packet.writeUInt8(1, 4); // node id
  packet.writeUInt8(0, 5); // flags
  packet.writeUInt16LE(0, 6); // breathing (fixed-point, cannot encode NaN)
  packet.writeUInt32LE(0, 8); // heart (fixed-point)
  packet.writeInt8(-50, 12); // rssi
  packet.writeFloatLE(NaN, 16); // motion_energy
  packet.writeFloatLE(Infinity, 20); // presence_score
  const parsed = parseEdgeVitalsPacket(packet);
  assert(parsed);
  assert(Number.isNaN(parsed.motion));
  assert.equal(parsed.presence, Infinity);
});
