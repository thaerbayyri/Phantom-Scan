import test from "node:test";
import assert from "node:assert/strict";
import type { RoomGeometry } from "./room-geometry";
import {
  WALKER_SPEED_MPS,
  buildWalkerFrame,
  walkerAt,
  walkerCycleSeconds,
} from "./demo-walker";

const room: RoomGeometry = {
  roomWidthM: 4,
  roomDepthM: 6,
  anchors: {
    1: { x: -2, z: -3 },
    2: { x: 2, z: -3 },
    3: { x: 2, z: 3 },
    4: { x: -2, z: 3 },
  },
  source: "test",
};

test("walker stays inside the room for two full laps", () => {
  const cycle = walkerCycleSeconds(room);
  for (let t = 0; t <= cycle * 2; t += 0.25) {
    const p = walkerAt(t, room);
    assert.ok(Math.abs(p.x) <= room.roomWidthM / 2, `x=${p.x} at t=${t}`);
    assert.ok(Math.abs(p.z) <= room.roomDepthM / 2, `z=${p.z} at t=${t}`);
  }
});

test("walker path is deterministic and loops seamlessly", () => {
  const cycle = walkerCycleSeconds(room);
  assert.deepEqual(walkerAt(7.3, room), walkerAt(7.3, room));
  const a = walkerAt(1.0, room);
  const b = walkerAt(1.0 + cycle, room);
  assert.ok(Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.z - b.z) < 1e-9);
});

test("walker moves at the nominal speed and pauses at least once per lap", () => {
  const cycle = walkerCycleSeconds(room);
  let sawMoving = false;
  let sawPause = false;
  for (let t = 0; t < cycle; t += 0.1) {
    const { speed } = walkerAt(t, room);
    if (speed === 0) sawPause = true;
    if (Math.abs(speed - WALKER_SPEED_MPS) < 1e-9) sawMoving = true;
    assert.ok(speed <= WALKER_SPEED_MPS + 1e-9);
  }
  assert.ok(sawMoving, "never walked");
  assert.ok(sawPause, "never paused");
});

test("walker frame is labelled synthetic end to end", () => {
  const frame = buildWalkerFrame(3, 1_000_000, room);

  assert.equal(frame.targetState.source_mode, "synthetic");
  assert.equal(frame.targetState.node_mode, "fused_room");
  assert.equal(frame.targetState.target_visible, true);
  assert.ok(frame.nodes.length === 4);
  for (const node of frame.nodes) {
    assert.equal(node.source, "synthetic");
    assert.equal(node.active, true);
    assert.ok(node.motion >= 0 && node.motion <= 1, `motion=${node.motion}`);
  }
});

test("walker frame radialTarget is self-consistent with its position", () => {
  const { radialTarget: t } = buildWalkerFrame(5, 2_000_000, room);

  assert.equal(t.label, "human");
  assert.equal(t.positionBasis, "fused_room_centroid");
  assert.ok(t.positionUncertaintyM !== undefined && t.positionUncertaintyM > 0);
  assert.ok(Math.abs(t.r - Math.hypot(t.x, t.z)) < 1e-9);
  assert.ok(Math.abs(t.theta - Math.atan2(t.x, t.z)) < 1e-9);
  assert.ok(Math.abs(t.speed - Math.hypot(t.vx, t.vz)) < 1e-9);
});

test("the node nearest the walker shows the most motion", () => {
  const frame = buildWalkerFrame(2, 3_000_000, room);
  const { x, z } = frame.radialTarget;
  const nearest = frame.nodes.reduce((best, n) =>
    Math.hypot(n.x - x, n.z - z) < Math.hypot(best.x - x, best.z - z) ? n : best,
  );
  const strongest = frame.nodes.reduce((best, n) => (n.motion > best.motion ? n : best));
  assert.equal(strongest.node_id, nearest.node_id);
});

test("walker frame state follows the walker: moving while walking, idle while paused", () => {
  const cycle = walkerCycleSeconds(room);
  const states = new Set<string>();
  for (let t = 0; t < cycle; t += 0.1) {
    states.add(buildWalkerFrame(t, 4_000_000, room).targetState.state);
  }
  assert.ok(states.has("moving"));
  assert.ok(states.has("idle"));
});

test("walker frame carries scripted vitals in a plausible, time-varying human range", () => {
  const seen = new Set<number>();
  for (let t = 0; t < 120; t += 1) {
    const { vitalSigns } = buildWalkerFrame(t, 1, room);
    assert.ok(vitalSigns.heartRateBpm >= 60 && vitalSigns.heartRateBpm <= 85, `hr=${vitalSigns.heartRateBpm}`);
    assert.ok(vitalSigns.respirationRateRpm >= 12 && vitalSigns.respirationRateRpm <= 20, `rr=${vitalSigns.respirationRateRpm}`);
    assert.equal(vitalSigns.vitalsReliable, true);
    seen.add(vitalSigns.heartRateBpm);
  }
  assert.ok(seen.size > 1, "vitals should drift, not sit on one number");
  assert.deepEqual(buildWalkerFrame(7, 1, room).vitalSigns, buildWalkerFrame(7, 99, room).vitalSigns);
});

test("walker signal field covers the room grid with finite values", () => {
  const { signalField } = buildWalkerFrame(1, 5_000_000, room);
  assert.equal(signalField.roomWidthM, room.roomWidthM);
  assert.equal(signalField.roomDepthM, room.roomDepthM);
  assert.equal(signalField.values.length, signalField.gridWidth * signalField.gridDepth);
  assert.ok(signalField.values.every((v) => Number.isFinite(v) && v >= 0));
});
