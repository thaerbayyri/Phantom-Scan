import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { dataDir } from "./data-dir";

function withEnv<T>(value: string | undefined, fn: () => T): T {
  const before = process.env.PHANTOM_DATA_DIR;
  if (value === undefined) delete process.env.PHANTOM_DATA_DIR;
  else process.env.PHANTOM_DATA_DIR = value;
  try {
    return fn();
  } finally {
    if (before === undefined) delete process.env.PHANTOM_DATA_DIR;
    else process.env.PHANTOM_DATA_DIR = before;
  }
}

test("default is unchanged: no variable gives exactly path.resolve('data', ...)", () => {
  withEnv(undefined, () => {
    assert.equal(dataDir(), path.resolve("data"));
    assert.equal(dataDir("sessions"), path.resolve("data", "sessions"));
    assert.equal(dataDir("datasets", "room1"), path.resolve("data", "datasets", "room1"));
  });
});

test("an empty value is treated as unset (default unchanged)", () => {
  withEnv("", () => assert.equal(dataDir("audit"), path.resolve("data", "audit")));
});

test("PHANTOM_DATA_DIR replaces the base for every subdirectory", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-data-"));
  withEnv(tmp, () => {
    assert.equal(dataDir(), path.resolve(tmp));
    assert.equal(dataDir("sessions"), path.join(path.resolve(tmp), "sessions"));
    assert.equal(dataDir("operator.json"), path.join(path.resolve(tmp), "operator.json"));
  });
});

test("a server module started with PHANTOM_DATA_DIR writes only there, never into data/sessions", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-data-"));
  const realSessions = path.resolve("data", "sessions");
  const before = fs.existsSync(realSessions) ? fs.readdirSync(realSessions).length : 0;
  const code = `
    import { sessionStore } from ${JSON.stringify(pathToFileURL(path.resolve("server/lib/session-store.ts")).href)};
    sessionStore.save({ id: "x", startTime: Date.UTC(2026, 10, 3), endTime: Date.UTC(2026, 10, 3) + 1000, durationS: 1, totalFrames: 3,
      targetClassification: "none", classificationConfidence: 0, avgDistanceCm: 0, avgSpeedMs: 0, dataSource: "esp32",
      classificationBreakdown: {}, spatialMetrics: { minDistanceCm: 0, maxDistanceCm: 0, avgDistanceCm: 0, boundingBox: { xMin: 0, xMax: 0, zMin: 0, zMax: 0 } },
      kinematicData: { avgSpeedMs: 0, maxSpeedMs: 0 }, eventTimeline: [] }, "data-dir-test");
  `;
  const r = spawnSync(process.execPath, ["--import", "tsx", "--input-type=module", "-e", code], { env: { ...process.env, PHANTOM_DATA_DIR: tmp }, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  const written = fs.readdirSync(path.join(tmp, "sessions")).sort();
  assert.ok(written.includes("_index.json") && written.some((f) => f.endsWith("2026-11-03.json")), `got ${written}`);
  const after = fs.existsSync(realSessions) ? fs.readdirSync(realSessions).length : 0;
  assert.equal(after, before, "the repo's data/sessions must not change");
});
