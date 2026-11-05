import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import {
  DATASET_LABELS,
  DatasetRecorder,
  canonicalJson,
  captureFromEnv,
  geometryHash,
  parseDatasetStart,
  type DatasetFrame,
} from "./dataset-recorder";

function tempRoot(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "phantom-dataset-"));
}

function readJsonl(file: string): Array<Record<string, unknown>> {
  return fs
    .readFileSync(file, "utf-8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

const FRAME: DatasetFrame = { tMs: 1000, nodeId: 2, rssi: -48, amps: [1.5, 2.5, 3.5] };

test("parseDatasetStart accepts a valid request and derives the count from the label", () => {
  const req = parseDatasetStart({ roomId: "lab-1", subjectId: "s1", label: "walking" });
  assert.equal(req.label, "walking");
  assert.equal(req.count, 1);
  assert.equal(parseDatasetStart({ roomId: "lab-1", label: "empty" }).count, 0);
  assert.equal(parseDatasetStart({ roomId: "lab-1", label: "two_people" }).count, 2);
  assert.equal(parseDatasetStart({ roomId: "lab-1", label: "two_people", count: 3 }).count, 3);
});

test("parseDatasetStart rejects unknown labels, unsafe ids and out-of-range counts", () => {
  assert.throws(() => parseDatasetStart({ roomId: "lab", label: "dancing" }), /label/);
  assert.throws(() => parseDatasetStart({ roomId: "../etc", label: "empty" }), /roomId/);
  assert.throws(() => parseDatasetStart({ roomId: "lab", subjectId: "a/b", label: "empty" }), /subjectId/);
  assert.throws(() => parseDatasetStart({ roomId: "lab", label: "walking", count: 99 }), /count/);
  assert.throws(() => parseDatasetStart(null), /request/);
  assert.ok(DATASET_LABELS.includes("empty_fan"));
});

test("recorder writes a header then frame rows under data/datasets/<room>/", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root, now: () => 1_700_000_000_000 });
  const info = rec.start(parseDatasetStart({ roomId: "lab-1", subjectId: "s1", label: "walking" }), {
    geometry: { roomWidthM: 4, roomDepthM: 6 },
  });
  rec.record(FRAME);
  rec.record({ ...FRAME, tMs: 1020, nodeId: 3 });
  const done = rec.stop();

  assert.equal(done.frames, 2);
  assert.ok(info.files[0].startsWith(path.join(root, "lab-1")));
  const rows = readJsonl(done.files[0]);
  assert.equal(rows[0].type, "header");
  assert.equal(rows[0].label, "walking");
  assert.equal(rows[0].roomId, "lab-1");
  assert.equal(rows[0].schema, 2);
  assert.deepEqual(rows[1], { type: "frame", t: 1000, n: 2, rssi: -48, a: [1.5, 2.5, 3.5] });
  assert.equal((rows[2] as { n: number }).n, 3);
});

test("recorder rotates to a new part file with its own header after maxFramesPerFile", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root, maxFramesPerFile: 3 });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  for (let i = 0; i < 7; i++) rec.record({ ...FRAME, tMs: i });
  const done = rec.stop();
  assert.equal(done.files.length, 3);
  assert.equal(done.frames, 7);
  for (const file of done.files) {
    assert.equal(readJsonl(file)[0].type, "header", `${file} must start with a header`);
  }
  const counts = done.files.map((f) => readJsonl(f).filter((r) => r.type === "frame").length);
  assert.deepEqual(counts, [3, 3, 1]);
});

test("record is a no-op when not recording, and a second start is refused", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root });
  rec.record(FRAME); // must not throw or create files
  assert.deepEqual(fs.readdirSync(root), []);
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  assert.throws(() => rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {}), /already recording/);
  rec.stop();
  assert.equal(rec.status().recording, false);
});

test("frames with non-finite amplitudes are skipped and counted, not written", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  rec.record({ ...FRAME, amps: [1, Number.NaN] });
  rec.record({ ...FRAME, amps: [] });
  rec.record(FRAME);
  const done = rec.stop();
  assert.equal(done.frames, 1);
  assert.equal(done.skipped, 2);
});

test("per-node frame counts are tracked for the operator", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  rec.record({ ...FRAME, nodeId: 1 });
  rec.record({ ...FRAME, nodeId: 1 });
  rec.record({ ...FRAME, nodeId: 4 });
  assert.deepEqual(rec.status().perNode, { "1": 2, "4": 1 });
  rec.stop();
});

test("stop() always closes the file and clears recording state even if the final flush fails", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  rec.record(FRAME);
  // Break the underlying fd so the pending flush throws.
  fs.closeSync((rec as unknown as { fd: number }).fd);
  assert.throws(() => rec.stop());
  assert.equal(rec.isRecording, false, "recorder must be reusable after a failed stop");
  assert.equal(rec.status().recording, false);
  assert.doesNotThrow(() => rec.start(parseDatasetStart({ roomId: "lab2", label: "empty" }), {}));
  rec.stop();
});

test("a failed flush drops the pending buffer instead of growing without bound", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  fs.closeSync((rec as unknown as { fd: number }).fd);
  let threw = 0;
  for (let i = 0; i < 450; i++) {
    try {
      rec.record(FRAME);
    } catch {
      threw++;
    }
  }
  assert.ok(threw >= 1, "a write failure must surface");
  assert.ok((rec as unknown as { pending: string[] }).pending.length < 200, "pending buffer must not accumulate");
  try { rec.stop(); } catch { /* expected: fd already closed */ }
});

// ── PS-FIX-03: header schema 2 ─────────────────────────────────────────────

const GEOMETRY = { roomWidthM: 4, roomDepthM: 6, anchors: { "1": { x: -2, z: -3 } } };
// Same literal as tests/test_record_dataset.py: both recorders must hash the same geometry identically.
const GEOMETRY_HASH = "5ad06de70373cbe1";

test("canonicalJson ignores key order and geometryHash matches the Python recorder's value", () => {
  assert.equal(canonicalJson({ b: 1, a: { d: [2, { z: 1, y: 2 }], c: null } }), '{"a":{"c":null,"d":[2,{"y":2,"z":1}]},"b":1}');
  assert.equal(geometryHash(GEOMETRY), GEOMETRY_HASH);
  assert.equal(geometryHash({ anchors: { "1": { z: -3, x: -2 } }, roomDepthM: 6, roomWidthM: 4 }), GEOMETRY_HASH);
  assert.equal(geometryHash({ ...GEOMETRY, router: { x: 9, z: 9 } }), GEOMETRY_HASH, "router is not part of the hash");
  assert.equal(geometryHash(undefined), null);
});

test("schema-2 header carries geometry hash, capture, annotation and recorder; unknowns are null, never guessed", () => {
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root, now: () => 1_700_000_000_000 });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), { geometry: GEOMETRY, capture: captureFromEnv({}) });
  rec.record(FRAME);
  const h = readJsonl(rec.stop().files[0])[0] as Record<string, any>;
  assert.equal(h.schema, 2);
  assert.equal(h.geometryHash, GEOMETRY_HASH);
  assert.equal(h.recorder, "dashboard");
  assert.deepEqual(h.annotation, { nodeMoved: null, roomNotEmpty: null, text: "" });
  assert.deepEqual(h.capture, { channel: null, bandwidthMHz: null, bssid: null, firmwareVersion: null, firmwareHash: null, source: "not_recorded" });
  assert.equal(h.startedAtMs, 1_700_000_000_000);
  assert.equal(h.partStartedAtMs, 1_700_000_000_000);
  assert.equal(h.type, "header");
  assert.equal(h.roomId, "lab"); // schema-1 fields unchanged
});

test("every part header keeps the recording startedAtMs but has its own partStartedAtMs", () => {
  const root = tempRoot();
  let clock = 1_000;
  const rec = new DatasetRecorder({ rootDir: root, maxFramesPerFile: 2, now: () => (clock += 1000) });
  rec.start(parseDatasetStart({ roomId: "lab", label: "empty" }), {});
  for (let i = 0; i < 5; i++) rec.record({ ...FRAME, tMs: i });
  const headers = rec.stop().files.map((f) => readJsonl(f)[0] as Record<string, any>);
  assert.equal(headers.length, 3);
  assert.equal(new Set(headers.map((h) => h.startedAtMs)).size, 1, "startedAtMs names the recording and is shared");
  const starts = headers.map((h) => h.partStartedAtMs as number);
  assert.ok(starts[0] < starts[1] && starts[1] < starts[2], `partStartedAtMs must increase: ${starts}`);
  assert.deepEqual(headers.map((h) => h.part), [1, 2, 3]);
});

test("captureFromEnv accepts valid operator values and nulls invalid ones", () => {
  const ok = captureFromEnv({
    PHANTOM_CAPTURE_CHANNEL: "6", PHANTOM_CAPTURE_BANDWIDTH_MHZ: "20", PHANTOM_ROUTER_BSSID: "AA:BB:CC:00:11:22",
    PHANTOM_FIRMWARE_VERSION: "v0.8.13-esp32", PHANTOM_FIRMWARE_HASH: "428D3A5",
  });
  assert.deepEqual(ok, { channel: 6, bandwidthMHz: 20, bssid: "aa:bb:cc:00:11:22", firmwareVersion: "v0.8.13-esp32", firmwareHash: "428d3a5", source: "operator_env" });
  const bad = captureFromEnv({
    PHANTOM_CAPTURE_CHANNEL: "abc", PHANTOM_CAPTURE_BANDWIDTH_MHZ: "30", PHANTOM_ROUTER_BSSID: "not-a-mac",
    PHANTOM_FIRMWARE_VERSION: "has space", PHANTOM_FIRMWARE_HASH: "zzz",
  });
  assert.deepEqual(bad, { channel: null, bandwidthMHz: null, bssid: null, firmwareVersion: null, firmwareHash: null, source: "not_recorded" });
  assert.equal(captureFromEnv({ PHANTOM_CAPTURE_CHANNEL: "6.5" }).channel, null);
});

test("operator annotation (node moved / room not empty) is validated and written to every header", () => {
  const req = parseDatasetStart({ roomId: "lab", label: "empty", annotation: { nodeMoved: true, roomNotEmpty: "yes", text: "N1 nudged" } });
  assert.deepEqual(req.annotation, { nodeMoved: true, roomNotEmpty: null, text: "N1 nudged" });
  assert.deepEqual(parseDatasetStart({ roomId: "lab", label: "empty", annotation: "oops" }).annotation, { nodeMoved: null, roomNotEmpty: null, text: "" });
  assert.equal(parseDatasetStart({ roomId: "lab", label: "empty", annotation: { text: "x".repeat(900) } }).annotation.text.length, 500);
  const root = tempRoot();
  const rec = new DatasetRecorder({ rootDir: root, maxFramesPerFile: 1 });
  rec.start(req, {});
  rec.record(FRAME);
  rec.record(FRAME);
  for (const f of rec.stop().files) assert.deepEqual((readJsonl(f)[0] as Record<string, any>).annotation, req.annotation);
});
