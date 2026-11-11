import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { INITIAL_ROOM_ID, INITIAL_SUBJECT_ID, canStartDatasetRecording } from "./dataset-recorder-ids";

test("dataset recorder panel: Room ID and Subject ID start empty, so Start is disabled at first", () => {
  assert.equal(INITIAL_ROOM_ID, "");
  assert.equal(INITIAL_SUBJECT_ID, "");
  assert.equal(canStartDatasetRecording(INITIAL_ROOM_ID, INITIAL_SUBJECT_ID), false);
});

test("dataset recorder panel: Start needs both fields non-empty", () => {
  assert.equal(canStartDatasetRecording("train-ep2-2026-11", ""), false);
  assert.equal(canStartDatasetRecording("", "p1"), false);
  assert.equal(canStartDatasetRecording("train-ep2-2026-11", "p1"), true);
  assert.equal(canStartDatasetRecording("room1", "none"), true);
});

test("dataset recorder panel: Room ID must match ^[a-z0-9-]+$", () => {
  for (const bad of ["Room1", "train ep2", "train_ep2", "room1/..", "room1 ", "räum"]) {
    assert.equal(canStartDatasetRecording(bad, "p1"), false, bad);
  }
});

test("dataset recorder panel: the component uses the empty initial values and the start gate, with no room1/s1 default", () => {
  const source = readFileSync(new URL("../components/dashboard/dataset-recorder-panel.tsx", import.meta.url), "utf8");
  assert.match(source, /useState\(INITIAL_ROOM_ID\)/);
  assert.match(source, /useState\(INITIAL_SUBJECT_ID\)/);
  assert.match(source, /canStartDatasetRecording\(roomId, subjectId\)/);
  assert.doesNotMatch(source, /useState\("room1"\)|useState\("s1"\)/);
});
