import test from "node:test";
import assert from "node:assert/strict";
import type { RadialTarget, TargetState } from "@shared/schema";
import {
  canPresentAxisMotionVector,
  canPresentIllustrativeBody,
  canPresentLiveTargetPosition,
  canPresentVolumetricTarget,
  canPresentTruthfulTarget,
  getLivePositionCaveat,
} from "@shared/target-presentation";

const radialTarget: RadialTarget = {
  x: 1.2,
  z: 2.4,
  r: 2.68,
  theta: Math.PI / 6,
  vx: 0.1,
  vz: 0.2,
  isMoving: true,
  angle: Math.PI / 8,
  speed: 0.3,
  confidence: 0.82,
  label: "human",
  humanProb: 0.91,
  distanceCm: 268,
  wallDistance: 4.6,
};

function buildTargetState(
  overrides: Partial<TargetState> = {},
): TargetState {
  return {
    state: "degraded",
    source_mode: "live",
    node_mode: "single_node",
    target_visible: false,
    position_confident: false,
    motion_score: 0.2,
    confidence: 0.3,
    last_update_ms: 1_000,
    data_age_ms: 200,
    stale: false,
    reason: "live_degraded_target",
    ...overrides,
  };
}

test("live esp32 degraded targets still present a live position marker", () => {
  const targetState = buildTargetState();

  assert.equal(
    canPresentLiveTargetPosition({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    true,
  );
  assert.equal(
    canPresentTruthfulTarget({
      radialTarget,
      targetState,
    }),
    false,
  );
});

test("truthful live targets remain fully visible", () => {
  const targetState = buildTargetState({
    state: "moving",
    target_visible: true,
    position_confident: true,
    confidence: 0.82,
  });

  assert.equal(
    canPresentLiveTargetPosition({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    true,
  );
  assert.equal(
    canPresentTruthfulTarget({
      radialTarget,
      targetState,
    }),
    true,
  );
});

test("stale or cleared targets do not present a live position", () => {
  assert.equal(
    canPresentLiveTargetPosition({
      dataSource: "esp32",
      radialTarget,
      targetState: buildTargetState({
        state: "stale",
        stale: true,
        reason: "stale_hold_gap",
      }),
    }),
    false,
  );
  assert.equal(
    canPresentLiveTargetPosition({
      dataSource: "esp32",
      radialTarget: null,
      targetState: buildTargetState({
        state: "none",
        reason: "awaiting_live_samples",
      }),
    }),
    false,
  );
});

test("fused live targets expose the on-axis honesty caveat", () => {
  const targetState = buildTargetState({
    state: "moving",
    node_mode: "fused_two_node",
    target_visible: true,
    position_confident: true,
  });

  assert.deepEqual(
    getLivePositionCaveat({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    {
      primary: "ON-AXIS ESTIMATE - NOT ROOM POSITION",
      secondary: "front/back ambiguous - off-axis subjects project onto the baseline",
    },
  );
});

test("single-node live targets expose the distinct bearing caveat", () => {
  const targetState = buildTargetState({
    state: "degraded",
    node_mode: "single_node",
    target_visible: true,
  });

  assert.deepEqual(
    getLivePositionCaveat({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    {
      primary: "SINGLE-NODE BEARING - UNVALIDATED",
      secondary: "single-antenna AoA plus PDP, not a lower-resolution fused estimate",
    },
  );
});

test("caveat clears together with stale or missing live position", () => {
  assert.equal(
    getLivePositionCaveat({
      dataSource: "esp32",
      radialTarget,
      targetState: buildTargetState({
        state: "stale",
        target_visible: false,
        stale: true,
      }),
    }),
    null,
  );
  assert.equal(
    getLivePositionCaveat({
      dataSource: "esp32",
      radialTarget: null,
      targetState: buildTargetState({
        state: "none",
        target_visible: false,
      }),
    }),
    null,
  );
});

test("live esp32 truthful targets stay on the abstract marker path", () => {
  const targetState = buildTargetState({
    state: "moving",
    node_mode: "fused_two_node",
    target_visible: true,
    position_confident: true,
  });

  assert.equal(
    canPresentVolumetricTarget({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    false,
  );
});

test("truthful live targets do not use volumetric presentation", () => {
  const targetState = buildTargetState({
    state: "moving",
    node_mode: "fused_two_node",
    target_visible: true,
    position_confident: true,
  });

  assert.equal(
    canPresentVolumetricTarget({
      dataSource: "esp32",
      radialTarget,
      targetState,
    }),
    false,
  );
});

test("illustrative body is allowed only where the live position marker is allowed", () => {
  const movingState = buildTargetState({
    state: "moving",
    node_mode: "fused_room",
    target_visible: true,
    position_confident: true,
  });
  const input = { dataSource: "esp32" as const, radialTarget, targetState: movingState };

  assert.equal(canPresentIllustrativeBody(input), true);
  // unlabeled targets get a body too (the label is a classifier opinion, not a claim)
  assert.equal(
    canPresentIllustrativeBody({ ...input, radialTarget: { ...radialTarget, label: "unknown" } }),
    true,
  );
});

test("illustrative body is withheld for mechanical targets, empty rooms and aged-out targets", () => {
  const movingState = buildTargetState({ state: "moving", target_visible: true });

  assert.equal(
    canPresentIllustrativeBody({
      dataSource: "esp32",
      radialTarget: { ...radialTarget, label: "mechanical" },
      targetState: movingState,
    }),
    false,
  );
  assert.equal(
    canPresentIllustrativeBody({ dataSource: "esp32", radialTarget: null, targetState: movingState }),
    false,
  );
  for (const state of ["none", "stale"] as const) {
    assert.equal(
      canPresentIllustrativeBody({
        dataSource: "esp32",
        radialTarget,
        targetState: buildTargetState({ state, target_visible: false }),
      }),
      false,
      `state=${state}`,
    );
  }
});

test("illustrative body never re-enables the volumetric/AI-pose gate", () => {
  const movingState = buildTargetState({ state: "moving", target_visible: true });
  const input = { dataSource: "esp32" as const, radialTarget, targetState: movingState };

  assert.equal(canPresentIllustrativeBody(input), true);
  assert.equal(canPresentVolumetricTarget(input), false);
});

test("axis motion vector only renders when projected speed is present", () => {
  const targetState = buildTargetState({
    state: "moving",
    node_mode: "fused_two_node",
    target_visible: true,
  });

  assert.equal(
    canPresentAxisMotionVector({
      dataSource: "esp32",
      radialTarget: { ...radialTarget, speed: 0, isMoving: true },
      targetState,
    }),
    false,
  );

  assert.equal(
    canPresentAxisMotionVector({
      dataSource: "esp32",
      radialTarget: { ...radialTarget, speed: 0.2, isMoving: true },
      targetState,
    }),
    true,
  );
});
