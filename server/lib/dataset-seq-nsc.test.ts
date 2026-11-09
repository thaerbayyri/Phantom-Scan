import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { SignalProcessingServer } from "./websocket";
import { DatasetRecorder } from "./dataset-recorder";
import { csiSampleSchema } from "@shared/schema";

/**
 * PS-FIX-36 step 0, end to end inside the server: ingestSample -> acceptSample -> DatasetRecorder -> JSONL file.
 * No socket is opened and nothing is written outside a temp folder. The UDP handler's side (the sample carries seq and the raw
 * subcarrier count) is covered in udp-server-phy-guard-fault.test.ts; the recorder's own rules in dataset-recorder.test.ts.
 */

const AMPS = Array.from({ length: 51 }, (_, i) => 1.5 + i / 100);

function recordingServer(): { server: any; recorder: DatasetRecorder } {
  const server: any = new SignalProcessingServer();
  server.status.isProcessing = true;
  const recorder = new DatasetRecorder({ rootDir: fs.mkdtempSync(path.join(os.tmpdir(), "phantom-ds-seq-")) });
  server.datasetRecorder = recorder;
  server.handleMessage("dashboard", { type: "startDatasetRecording", data: { roomId: "lab", subjectId: "s1", label: "empty" } });
  assert.equal(recorder.isRecording, true);
  return { server, recorder };
}

function sample(extra: Record<string, unknown>, timestamp: number) {
  return { timestamp, h1: { re: 1, im: 1 }, h2: { re: 1, im: 1 }, rssi: -45, nodeId: 2, amplitudes: AMPS, ...extra };
}

function frameRows(recorder: DatasetRecorder): Array<Record<string, unknown>> {
  const done = recorder.stop();
  return done.files
    .flatMap((f) => fs.readFileSync(f, "utf-8").split("\n").filter(Boolean))
    .map((l) => JSON.parse(l) as Record<string, unknown>)
    .filter((r) => r.type === "frame");
}

test("samples with seq and numSubcarriers reach the recording as seq and nsc", () => {
  const { server, recorder } = recordingServer();
  const t0 = Date.now();
  server.ingestSample(sample({ seq: 1000, numSubcarriers: 128 }, t0));
  server.ingestSample(sample({ seq: 1003, numSubcarriers: 64 }, t0 + 15));
  const rows = frameRows(recorder);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map((r) => [r.seq, r.nsc]), [[1000, 128], [1003, 64]]);
  assert.deepEqual(rows.map((r) => r.n), [2, 2]);
  assert.equal((rows[0].a as number[]).length, 51, "the amplitude vector is unchanged");
});

test("samples without them (demo, replay, HTTP) record exactly the old frame shape", () => {
  const { server, recorder } = recordingServer();
  server.ingestSample(sample({}, Date.now()));
  const rows = frameRows(recorder);
  assert.equal(rows.length, 1);
  assert.deepEqual(Object.keys(rows[0]), ["type", "t", "n", "rssi", "a"]);
});

test("an invalid seq or count on a sample is dropped from the recording, the frame is still recorded", () => {
  const { server, recorder } = recordingServer();
  server.ingestSample(sample({ seq: -5, numSubcarriers: 0 }, Date.now()));
  const rows = frameRows(recorder);
  assert.equal(rows.length, 1);
  assert.equal("seq" in rows[0] || "nsc" in rows[0], false);
});

test("the sample schema accepts old samples unchanged, accepts the new optional fields and rejects invalid values", () => {
  const base = { timestamp: 1, h1: { re: 1, im: 0 }, h2: { re: 1, im: 0 } };
  assert.equal(csiSampleSchema.safeParse(base).success, true, "an old sample with neither field must still validate");
  assert.equal(csiSampleSchema.safeParse({ ...base, seq: 7, numSubcarriers: 128 }).success, true);
  assert.equal(csiSampleSchema.safeParse({ ...base, seq: 0 }).success, true);
  assert.equal(csiSampleSchema.safeParse({ ...base, seq: -1 }).success, false);
  assert.equal(csiSampleSchema.safeParse({ ...base, seq: 1.5 }).success, false);
  assert.equal(csiSampleSchema.safeParse({ ...base, numSubcarriers: 0 }).success, false);
  assert.equal(csiSampleSchema.safeParse({ ...base, someUnknownKey: "x" }).success, true, "unknown keys are tolerated (zod strips them)");
});
