import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  DemoClipError,
  ReplayCursor,
  findDatasetFile,
  loadReplayClip,
  readClipHead,
  sampleFromFrame,
  type ReplayFrame,
} from "./demo-replay";

function makeDir(): string {
  return mkdtempSync(join(tmpdir(), "demo-replay-"));
}

function frameLine(t: number, n: number, a: number[] = [1, 2, 3], rssi = -40): string {
  return JSON.stringify({ type: "frame", t, n, rssi, a });
}

function writeRecording(dir: string, name: string, lines: string[]): string {
  const file = join(dir, name);
  const header = JSON.stringify({ type: "header", schema: 1, roomId: "room1", label: "x" });
  writeFileSync(file, [header, ...lines].join("\n") + "\n");
  return file;
}

test("readClipHead keeps nodes 1-4, rebases time to the first frame and skips junk", async () => {
  const dir = makeDir();
  try {
    const file = writeRecording(dir, "a.jsonl", [
      frameLine(5_000, 1),
      "not json at all",
      frameLine(5_100, 5), // node outside 1-4
      JSON.stringify({ type: "frame", t: 5_150, n: 2, rssi: -40, a: [] }), // empty amplitudes
      frameLine(5_200, 2),
      frameLine(6_000, 3),
    ]);
    const frames = await readClipHead(file, 60);
    assert.deepEqual(frames.map((f) => [f.relMs, f.nodeId]), [[0, 1], [200, 2], [1_000, 3]]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("readClipHead stops after the requested number of seconds", async () => {
  const dir = makeDir();
  try {
    const file = writeRecording(dir, "a.jsonl", [
      frameLine(0, 1),
      frameLine(1_000, 1),
      frameLine(2_000, 1),
      frameLine(3_000, 1),
    ]);
    const frames = await readClipHead(file, 2);
    assert.deepEqual(frames.map((f) => f.relMs), [0, 1_000, 2_000]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("findDatasetFile matches the label and ignores .partN continuations", () => {
  const dir = makeDir();
  try {
    writeRecording(dir, "room1__s1__empty__2026.part2.jsonl", []);
    writeRecording(dir, "room1__s1__empty__2026.jsonl", []);
    writeRecording(dir, "room1__s1__walking__2026.jsonl", []);
    assert.equal(findDatasetFile(dir, "empty"), join(dir, "room1__s1__empty__2026.jsonl"));
    assert.equal(findDatasetFile(dir, "still"), null);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("loadReplayClip places the body after the calibration lead-in", async () => {
  const dir = makeDir();
  try {
    writeRecording(dir, "room1__s1__empty__1.jsonl", [frameLine(0, 1), frameLine(1_000, 2)]);
    writeRecording(dir, "room1__s2__still__1.jsonl", [frameLine(0, 3), frameLine(500, 4)]);
    const clip = await loadReplayClip(dir, { calibrationS: 1, bodyS: 10 });

    assert.equal(clip.calibrationMs, 1_000);
    const times = clip.frames.map((f) => f.relMs);
    assert.deepEqual([...times].sort((a, b) => a - b), times, "frames must be time-ordered");
    const body = clip.frames.filter((f) => f.nodeId >= 3);
    assert.ok(body.every((f) => f.relMs >= clip.calibrationMs));
    assert.equal(clip.durationMs, Math.max(...times));
    assert.match(clip.label, /room1/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("loadReplayClip reports a missing recording with an actionable error", async () => {
  const dir = makeDir();
  try {
    await assert.rejects(
      loadReplayClip(dir),
      (err: unknown) =>
        err instanceof DemoClipError && /empty/.test(err.message) && err.message.includes(dir),
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

function f(relMs: number, nodeId = 1): ReplayFrame {
  return { relMs, nodeId, rssi: -40, amplitudes: [1] };
}

test("ReplayCursor emits each due frame exactly once, in order", () => {
  const cursor = new ReplayCursor([f(0), f(100), f(250)], 0, 1_000);
  assert.deepEqual(cursor.advance(50).map((x) => x.relMs), [0]);
  assert.deepEqual(cursor.advance(50).map((x) => x.relMs), []);
  assert.deepEqual(cursor.advance(300).map((x) => x.relMs), [100, 250]);
});

test("ReplayCursor loops back to the loop point instead of restarting calibration", () => {
  const cursor = new ReplayCursor([f(0), f(400), f(600), f(900)], 400, 1_000);
  assert.deepEqual(cursor.advance(900).map((x) => x.relMs), [0, 400, 600, 900]);
  // 1100 ms elapsed = 100 ms past the end of the clip = lap-local 500, so the 400 frame
  // replays; the calibration frame (0) must not.
  assert.deepEqual(cursor.advance(1_100).map((x) => x.relMs), [400]);
  assert.deepEqual(cursor.advance(1_500).map((x) => x.relMs), [600, 900]);
});

test("ReplayCursor reports a lap-local position for the progress display", () => {
  const cursor = new ReplayCursor([f(0), f(900)], 400, 1_000);
  cursor.advance(900);
  assert.equal(cursor.positionMs(900), 900);
  cursor.advance(1_100);
  assert.equal(cursor.positionMs(1_100), 500);
});

test("sampleFromFrame stamps the sample with the current time and copies amplitudes", () => {
  const frame: ReplayFrame = { relMs: 10, nodeId: 3, rssi: -42, amplitudes: [1, 9, 4] };
  const sample = sampleFromFrame(frame, 123_456);

  assert.equal(sample.timestamp, 123_456);
  assert.equal(sample.nodeId, 3);
  assert.equal(sample.rssi, -42);
  assert.deepEqual(sample.amplitudes, [1, 9, 4]);
  assert.notEqual(sample.amplitudes, frame.amplitudes);
  assert.deepEqual(sample.h1, { re: 9, im: 0 });
  assert.deepEqual(sample.h2, { re: 9, im: 0 });
});
