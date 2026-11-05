import test from "node:test";
import assert from "node:assert/strict";
import type { TargetState, VitalSigns } from "@shared/schema";
import { getVitalsBadge } from "./vitals-status";

function state(overrides: Partial<TargetState> = {}): TargetState {
  return {
    state: "moving",
    source_mode: "live",
    node_mode: "fused_room",
    target_visible: true,
    position_confident: true,
    motion_score: 0.4,
    confidence: 0.8,
    last_update_ms: 1_000,
    data_age_ms: 10,
    stale: false,
    ...overrides,
  };
}

const reliable: VitalSigns = { heartRateBpm: 72, respirationRateRpm: 16, vitalsReliable: true };
const empty: VitalSigns = { heartRateBpm: 0, respirationRateRpm: 0, vitalsReliable: false };

test("no target state at all reads NO TARGET", () => {
  assert.equal(getVitalsBadge(null, null), "NO TARGET");
  assert.equal(getVitalsBadge(undefined, reliable), "NO TARGET");
});

test("an invisible target reads NO TARGET even if stale vitals are still around", () => {
  assert.equal(getVitalsBadge(state({ target_visible: false, state: "none" }), reliable), "NO TARGET");
});

test("a visible live target with no vitals yet reads CALIBRATING", () => {
  assert.equal(getVitalsBadge(state(), null), "CALIBRATING");
  assert.equal(getVitalsBadge(state(), empty), "CALIBRATING");
  assert.equal(getVitalsBadge(state({ source_mode: "replay" }), null), "CALIBRATING");
});

test("a visible live target with a vitals reading shows no badge", () => {
  assert.equal(getVitalsBadge(state(), reliable), null);
  // an unreliable-but-present reading is still a reading (the numbers are dimmed instead)
  assert.equal(getVitalsBadge(state(), { ...reliable, vitalsReliable: false }), null);
});

test("simulated demo vitals are always flagged SIMULATED", () => {
  assert.equal(getVitalsBadge(state({ source_mode: "synthetic" }), reliable), "SIMULATED");
  assert.equal(getVitalsBadge(state({ source_mode: "synthetic" }), null), "SIMULATED");
});

test("NO TARGET outranks SIMULATED when the simulated walker is not visible", () => {
  assert.equal(
    getVitalsBadge(state({ source_mode: "synthetic", target_visible: false, state: "none" }), null),
    "NO TARGET",
  );
});
