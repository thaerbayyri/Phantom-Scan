import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_ROOM_GEOMETRY,
  geometricDiversity,
  loadRoomGeometry,
  parseRoomGeometry,
} from "./room-geometry";

const VALID = {
  roomWidthM: 5,
  roomDepthM: 4,
  anchors: {
    "1": { x: -2.5, z: -2 },
    "2": { x: 2.5, z: -2 },
    "3": { x: 2.5, z: 2 },
    "4": { x: -2.5, z: 2 },
  },
};

test("defaults reproduce the historical 4 m x 6 m corner layout", () => {
  assert.equal(DEFAULT_ROOM_GEOMETRY.roomWidthM, 4);
  assert.equal(DEFAULT_ROOM_GEOMETRY.roomDepthM, 6);
  assert.deepEqual(DEFAULT_ROOM_GEOMETRY.anchors[1], { x: -2, z: -3 });
  assert.deepEqual(DEFAULT_ROOM_GEOMETRY.anchors[3], { x: 2, z: 3 });
});

test("parseRoomGeometry accepts a valid config and keys anchors by numeric node id", () => {
  const geo = parseRoomGeometry(VALID, "test");
  assert.equal(geo.roomWidthM, 5);
  assert.deepEqual(Object.keys(geo.anchors).map(Number), [1, 2, 3, 4]);
  assert.deepEqual(geo.anchors[2], { x: 2.5, z: -2 });
  assert.equal(geo.source, "test");
});

test("parseRoomGeometry rejects non-finite / oversized dimensions", () => {
  assert.throws(() => parseRoomGeometry({ ...VALID, roomWidthM: 0 }, "t"), /roomWidthM/);
  assert.throws(() => parseRoomGeometry({ ...VALID, roomDepthM: 80 }, "t"), /roomDepthM/);
  assert.throws(
    () => parseRoomGeometry({ ...VALID, anchors: { ...VALID.anchors, "1": { x: Number.NaN, z: 0 } } }, "t"),
    /anchors/,
  );
});

test("parseRoomGeometry rejects node ids outside the canonical 1-4 set", () => {
  assert.throws(
    () => parseRoomGeometry({ ...VALID, anchors: { ...VALID.anchors, "7": { x: 0, z: 0 } } }, "t"),
    /node id 7/,
  );
});

test("parseRoomGeometry rejects anchors outside the room bounds", () => {
  assert.throws(
    () => parseRoomGeometry({ ...VALID, anchors: { ...VALID.anchors, "3": { x: 9, z: 0 } } }, "t"),
    /outside the room/,
  );
});

test("parseRoomGeometry rejects 3+ collinear anchors (no 2-D localization possible)", () => {
  assert.throws(
    () =>
      parseRoomGeometry(
        {
          roomWidthM: 6,
          roomDepthM: 4,
          anchors: { "1": { x: -2, z: 0 }, "2": { x: 0, z: 0 }, "3": { x: 2, z: 0 } },
        },
        "t",
      ),
    /collinear/,
  );
});

test("geometricDiversity is 1 for a square layout, ~0.8 for 4x6 corners, low when 3 nodes share a corner", () => {
  const square = { 1: { x: -2, z: -2 }, 2: { x: 2, z: -2 }, 3: { x: 2, z: 2 }, 4: { x: -2, z: 2 } };
  assert.ok(Math.abs(geometricDiversity(square) - 1) < 1e-6);
  const rect = geometricDiversity(DEFAULT_ROOM_GEOMETRY.anchors);
  assert.ok(rect > 0.7 && rect < 0.9, `4x6 corners diversity=${rect}`);
  const lopsided = { 1: { x: -2, z: -3 }, 2: { x: -1.8, z: -3 }, 3: { x: -2, z: -2.8 }, 4: { x: 2, z: 3 } };
  assert.ok(geometricDiversity(lopsided) < 0.6);
});

test("loadRoomGeometry falls back to defaults when no config file exists", () => {
  const geo = loadRoomGeometry({}, () => undefined);
  assert.deepEqual(geo.anchors, DEFAULT_ROOM_GEOMETRY.anchors);
  assert.equal(geo.source, "defaults");
});

test("loadRoomGeometry reads PHANTOM_ROOM_CONFIG and fails fast when that file is missing", () => {
  const files: Record<string, string> = { "custom.json": JSON.stringify(VALID) };
  const read = (p: string) => files[p];
  const geo = loadRoomGeometry({ PHANTOM_ROOM_CONFIG: "custom.json" }, read);
  assert.equal(geo.roomWidthM, 5);
  assert.throws(() => loadRoomGeometry({ PHANTOM_ROOM_CONFIG: "missing.json" }, read), /missing\.json/);
});

test("loadRoomGeometry reports invalid JSON with the file path", () => {
  const read = () => "{ not json";
  assert.throws(() => loadRoomGeometry({ PHANTOM_ROOM_CONFIG: "bad.json" }, read), /bad\.json/);
});
