import test from "node:test";
import assert from "node:assert/strict";
import type { DemoStatus } from "@shared/schema";
import { describeDemoBanner } from "./demo-banner";

function status(overrides: Partial<DemoStatus> = {}): DemoStatus {
  return {
    active: true,
    mode: "synthetic",
    phase: "running",
    clip: "scripted walker",
    positionS: 12,
    durationS: 40,
    message: null,
    ...overrides,
  };
}

test("no banner when the demo is idle or unknown", () => {
  assert.equal(describeDemoBanner(null), null);
  assert.equal(describeDemoBanner(status({ active: false, mode: null, phase: "idle" })), null);
});

test("simulated demo says it is scripted and not a measurement", () => {
  const banner = describeDemoBanner(status());
  assert.ok(banner);
  assert.equal(banner.tone, "simulated");
  assert.match(banner.headline, /DEMO/);
  assert.match(banner.headline, /SIMULATED/);
  assert.match(banner.detail, /not a measurement/i);
});

test("replay demo names the recording and warns it may show no target", () => {
  const banner = describeDemoBanner(
    status({ mode: "replay", phase: "running", clip: "room1 still recording" }),
  );
  assert.ok(banner);
  assert.equal(banner.tone, "replay");
  assert.match(banner.headline, /REPLAY/);
  assert.match(banner.headline, /room1 still recording/);
  assert.match(banner.detail, /real detector/i);
  assert.match(banner.detail, /may show no target/i);
});

test("replay demo reports calibration progress while the baselines warm up", () => {
  const banner = describeDemoBanner(
    status({ mode: "replay", phase: "calibrating", positionS: 12.4, durationS: 150 }),
  );
  assert.ok(banner);
  assert.match(banner.detail, /calibrating/i);
});

test("loading a recording is shown as such", () => {
  const banner = describeDemoBanner(status({ mode: "replay", phase: "loading", clip: null }));
  assert.ok(banner);
  assert.match(banner.headline, /loading/i);
});

test("a failed demo start surfaces the reason as an error banner", () => {
  const banner = describeDemoBanner(
    status({ active: false, mode: null, phase: "error", message: 'Demo replay needs a "empty" recording' }),
  );
  assert.ok(banner);
  assert.equal(banner.tone, "error");
  assert.match(banner.detail, /empty/);
});
