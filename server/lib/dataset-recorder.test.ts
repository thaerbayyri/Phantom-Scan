import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import {
  DATASET_LABELS,
  DatasetRecorder,
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
  assert.equal(rows[0].schema, 1);
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
