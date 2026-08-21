import test from "node:test";
import assert from "node:assert/strict";
import { resolveAlignment, systemToGroundTruthMs, NoSyncMarkerError } from "../time-aligner";

test("resolveAlignment recovers a known constant offset from a single sync event", () => {
  const alignment = resolveAlignment([{ groundTruthMs: 5_200, systemMs: 5_000 }]);
  assert.equal(alignment.offsetMs, 200);
  assert.equal(alignment.driftPpm, 0);
  assert.equal(systemToGroundTruthMs(10_000, alignment), 10_200);
});

test("resolveAlignment recovers known offset and drift from two sync events", () => {
  const trueOffsetMs = 300;
  const trueDriftPpm = 100;
  const toGroundTruthMs = (systemMs: number) => systemMs * (1 + trueDriftPpm / 1_000_000) + trueOffsetMs;

  const events = [
    { systemMs: 0, groundTruthMs: toGroundTruthMs(0) },
    { systemMs: 60_000, groundTruthMs: toGroundTruthMs(60_000) },
  ];
  const alignment = resolveAlignment(events);

  assert.ok(Math.abs(alignment.offsetMs - trueOffsetMs) < 1e-6, `offsetMs=${alignment.offsetMs}`);
  assert.ok(Math.abs(alignment.driftPpm - trueDriftPpm) < 1e-6, `driftPpm=${alignment.driftPpm}`);
});

test("A4 — resolveAlignment refuses with NoSyncMarkerError when no sync event exists", () => {
  assert.throws(() => resolveAlignment([]), NoSyncMarkerError);
  assert.throws(() => resolveAlignment([]), /TO_BE_MEASURED — no sync marker/);
});
