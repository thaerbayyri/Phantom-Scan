import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import path from "path";
import {
  classifyCsiDatagram,
  parsePhyTrailer,
  phyTrailerChecksum,
  PHY_TRAILER_MAGIC_LE,
  PHY_TRAILER_SIZE,
  stripPhyTrailer,
} from "./csi-phy-trailer";
import { classifyPacketMagic, parseCsiPacket } from "./udp-server";
import { reduceCsiFrame } from "./csi-subcarriers";

interface GoldenTrailer {
  name: string;
  hex: string;
  fields: Record<string, unknown>;
}

const golden: { trailers: GoldenTrailer[] } = JSON.parse(
  fs.readFileSync(path.resolve("tests", "fixtures", "phy_trailer_golden.json"), "utf-8"),
);
const goldenFrame = Buffer.from(
  fs.readFileSync(path.resolve("tests", "fixtures", "adr018_phy_trailer_frame.hex"), "utf-8").trim(),
  "hex",
);

function byName(name: string): GoldenTrailer {
  const t = golden.trailers.find((g) => g.name === name);
  assert.ok(t, `golden trailer ${name} exists`);
  return t;
}

/** Same synthetic v1 frame the golden fixture was generated from: node 2, 64 subcarriers, 128 I/Q bytes. */
function buildPlainFrame(): Buffer {
  const h = Buffer.alloc(32);
  h.writeUInt32LE(0xc5110001, 0);
  h.writeUInt8(1, 4);
  h.writeUInt8(2, 5);
  h.writeUInt8(1, 6);
  h.writeUInt16LE(64, 7);
  h.writeUInt32LE(2417, 9);
  h.writeUInt32LE(1000, 13);
  h.writeInt8(-30, 17);
  h.writeInt8(-92, 18);
  h.writeUInt8(2, 19);
  h.writeBigUInt64LE(123456789n, 20);
  h.writeUInt32LE(123456, 28);
  const iq = Buffer.alloc(128);
  for (let i = 0; i < 128; i++) {
    iq.writeInt8(((i * 7) % 251) - 125, i);
  }
  return Buffer.concat([h, iq]);
}

test("golden trailers parse to the exact documented fields", () => {
  for (const g of golden.trailers) {
    assert.deepEqual(parsePhyTrailer(Buffer.from(g.hex, "hex")), g.fields, g.name);
  }
});

test("golden trailer hex strings are identical in the firmware host test (no drift)", () => {
  const c = fs.readFileSync(
    path.resolve("firmware", "esp32-csi-node", "main", "test", "test_csi_phy_trailer_pure.c"),
    "utf-8",
  );
  const inC = [...c.matchAll(/#define GOLDEN_\w+\s+"([0-9a-f]{32})"/g)].map((m) => m[1]).sort();
  const inJson = golden.trailers.map((g) => g.hex).sort();
  assert.deepEqual(inC, inJson);
});

test("trailer magic and size constants match the C header", () => {
  const h = fs.readFileSync(
    path.resolve("firmware", "esp32-csi-node", "main", "csi_phy_trailer_pure.h"),
    "utf-8",
  );
  assert.match(h, /#define CSI_PHY_TRAILER_MAGIC 0x31584850u/);
  assert.match(h, /#define CSI_PHY_TRAILER_SIZE\s+16u/);
  assert.equal(PHY_TRAILER_MAGIC_LE, 0x31584850);
  assert.equal(PHY_TRAILER_SIZE, 16);
  assert.equal(Buffer.from("PHX1").readUInt32LE(0), PHY_TRAILER_MAGIC_LE);
});

test("parsePhyTrailer rejects short input, wrong magic and a bad checksum", () => {
  const good = Buffer.from(byName("ht_ampdu_qos").hex, "hex");
  assert.equal(parsePhyTrailer(good.subarray(0, 15)), null);
  const badMagic = Buffer.from(good);
  badMagic[0] ^= 0x01;
  assert.equal(parsePhyTrailer(badMagic), null);
  const badSum = Buffer.from(good);
  badSum[6] ^= 0x10;
  assert.equal(parsePhyTrailer(badSum), null);
  assert.equal(phyTrailerChecksum(good), good[15]);
});

test("the golden full frame is exactly the plain v1 frame plus the golden trailer", () => {
  const plain = buildPlainFrame();
  const trailer = Buffer.from(byName("ht_ampdu_qos").hex, "hex");
  assert.equal(goldenFrame.length, 176);
  assert.deepEqual(goldenFrame, Buffer.concat([plain, trailer]));
});

test("dispatch: a trailer frame is recognised before the plain v1 shape", () => {
  const c = classifyCsiDatagram(goldenFrame);
  assert.equal(c.shape, "csi_v1_phy_trailer");
  assert.equal(c.plainLength, 160);
  assert.equal(c.trailer?.rxSeq, 2587);
  assert.equal(classifyCsiDatagram(buildPlainFrame()).shape, "csi_v1");
});

test("dispatch: I/Q bytes that look like a trailer are never misread (length must be exactly plain + 16)", () => {
  // A plain frame whose last 16 I/Q bytes are a perfectly valid trailer: same length as plain, so it stays csi_v1.
  const plain = buildPlainFrame();
  Buffer.from(byName("ht40_stbc_sgi").hex, "hex").copy(plain, plain.length - 16);
  const c = classifyCsiDatagram(plain);
  assert.equal(c.shape, "csi_v1");
  assert.equal(c.trailer, null);
  assert.equal(stripPhyTrailer(plain), plain);
});

test("dispatch: bad trailers and odd lengths fall back to plain v1 or not-csi, never throw", () => {
  const plain = buildPlainFrame();
  const junk = Buffer.concat([plain, Buffer.alloc(16, 0xab)]);
  assert.equal(classifyCsiDatagram(junk).shape, "csi_v1"); // right length, no magic: extra bytes ignored like today
  const truncated = goldenFrame.subarray(0, goldenFrame.length - 1);
  assert.equal(classifyCsiDatagram(truncated).shape, "csi_v1"); // 15 bytes of trailer: not a trailer
  assert.equal(classifyCsiDatagram(truncated).trailer, null);
  assert.equal(classifyCsiDatagram(plain.subarray(0, 100)).shape, "not_csi_v1"); // shorter than 32 + iq
  assert.equal(classifyCsiDatagram(Buffer.alloc(10)).shape, "not_csi_v1");
  const v2 = Buffer.from(goldenFrame);
  v2.writeUInt8(2, 4); // schema version 2 is not v1
  assert.equal(classifyCsiDatagram(v2).shape, "not_csi_v1");
  const zeroSc = Buffer.from(goldenFrame);
  zeroSc.writeUInt16LE(0, 7);
  assert.equal(classifyCsiDatagram(zeroSc).shape, "not_csi_v1");
  const wrongMagic = Buffer.from(goldenFrame);
  wrongMagic.writeUInt32LE(0xc51100a1, 0); // heartbeat magic
  assert.equal(classifyCsiDatagram(wrongMagic).shape, "not_csi_v1");
});

test("backward compatible: the live v1 parser accepts a trailer frame and returns the same header fields", () => {
  const plain = buildPlainFrame();
  const a = parseCsiPacket(plain);
  const b = parseCsiPacket(goldenFrame);
  assert.ok(a && b);
  const { iqData: iqA, ...restA } = a;
  const { iqData: iqB, ...restB } = b;
  assert.deepEqual(restB, restA);
  assert.deepEqual(iqB.subarray(0, 128), iqA); // the I/Q block is byte-identical; the trailer sits after it
  assert.equal(iqB.length, 128 + PHY_TRAILER_SIZE);
  assert.equal(classifyPacketMagic(goldenFrame), "csi"); // the magic dispatch is unchanged
});

test("backward compatible: reduceCsiFrame gives identical amplitudes and h1/h2 with or without the trailer", () => {
  const a = parseCsiPacket(buildPlainFrame());
  const b = parseCsiPacket(goldenFrame);
  assert.ok(a && b);
  assert.deepEqual(
    reduceCsiFrame(b.iqData, b.numSubcarriers, b.numAntennas),
    reduceCsiFrame(a.iqData, a.numSubcarriers, a.numAntennas),
  );
});

test("stripPhyTrailer returns the plain frame for a trailer frame and the same buffer otherwise", () => {
  assert.deepEqual(stripPhyTrailer(goldenFrame), buildPlainFrame());
  const plain = buildPlainFrame();
  assert.equal(stripPhyTrailer(plain), plain);
});

test("bytes per second at 4 nodes x 67 fps: the trailer adds 4,288 B/s on top of the I/Q length case", () => {
  const fps = 4 * 67;
  const cases = [
    { iq: 128, v1: 42_880, ext: 47_168 }, // LLTF only
    { iq: 256, v1: 77_184, ext: 81_472 }, // LLTF + HT-LTF
    { iq: 384, v1: 111_488, ext: 115_776 }, // LLTF + HT-LTF + STBC-HT-LTF
  ];
  for (const c of cases) {
    assert.equal(fps * (32 + c.iq), c.v1);
    assert.equal(fps * (32 + c.iq + PHY_TRAILER_SIZE), c.ext);
    assert.equal(c.ext - c.v1, 4_288);
  }
});
