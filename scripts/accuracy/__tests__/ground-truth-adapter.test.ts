import test from "node:test";
import assert from "node:assert/strict";
import { parseGroundTruthCsv, isGroundTruthPositiveAt, groundTruthTimeBounds } from "../ground-truth-adapter";

test("parses present/absent/sync rows and resolves the sync marker", () => {
  const csv = [
    "t_start_ms,t_end_ms,label,subject_id",
    "0,0,sync,",
    "1200,15300,present,subject-1",
    "20000,25000,absent,",
  ].join("\n");

  const log = parseGroundTruthCsv(csv);

  assert.equal(log.syncMarkerMs, 0);
  assert.equal(log.rows.length, 3);
  assert.equal(isGroundTruthPositiveAt(log, 5_000), true);
  assert.equal(isGroundTruthPositiveAt(log, 500), false);
  // "absent" rows document a negative interval but are not what makes time
  // negative — absence is the default; presence must be explicitly claimed.
  assert.equal(isGroundTruthPositiveAt(log, 22_000), false);

  const bounds = groundTruthTimeBounds(log);
  assert.deepEqual(bounds, { startMs: 1_200, endMs: 25_000 });
});

test("rejects a row with an invalid label", () => {
  const csv = ["t_start_ms,t_end_ms,label,subject_id", "0,100,maybe,"].join("\n");
  assert.throws(() => parseGroundTruthCsv(csv), /invalid label/);
});

test("a log with zero present rows never reports positive at any sampled time", () => {
  const csv = ["t_start_ms,t_end_ms,label,subject_id", "0,0,sync,", "0,60000,absent,"].join("\n");
  const log = parseGroundTruthCsv(csv);
  for (let t = 0; t <= 60_000; t += 1_000) {
    assert.equal(isGroundTruthPositiveAt(log, t), false);
  }
});

test("groundTruthTimeBounds ignores sync rows and returns null when only sync rows exist", () => {
  const csv = ["t_start_ms,t_end_ms,label,subject_id", "500,500,sync,"].join("\n");
  const log = parseGroundTruthCsv(csv);
  assert.equal(groundTruthTimeBounds(log), null);
});
