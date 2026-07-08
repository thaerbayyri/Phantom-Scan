import { test } from "node:test";
import assert from "node:assert/strict";
import {
  compassBearingRad,
  bearingToCardinal,
  bearingToCardinalLong,
  travelAngleToBearingRad,
  headingVectorFromAngle,
} from "@shared/bearing";

const D = Math.PI / 180;

test("compassBearingRad: cardinal positions", () => {
  assert.equal(compassBearingRad(0, 1), 0); // north
  assert.equal(compassBearingRad(1, 0), Math.PI / 2); // east
  assert.equal(compassBearingRad(0, -1), Math.PI); // south
  assert.equal(compassBearingRad(-1, 0), -Math.PI / 2); // west
});

test("bearingToCardinal: sector centers and boundaries", () => {
  assert.equal(bearingToCardinal(0), "N");
  assert.equal(bearingToCardinal(90 * D), "E");
  assert.equal(bearingToCardinal(180 * D), "S");
  assert.equal(bearingToCardinal(-90 * D), "W");
  assert.equal(bearingToCardinal(45 * D), "NE");
  assert.equal(bearingToCardinal(-135 * D), "SW");
  // Boundaries: ±22.5° is the N/NE and N/NW edge.
  assert.equal(bearingToCardinal(22 * D), "N");
  assert.equal(bearingToCardinal(23 * D), "NE");
  assert.equal(bearingToCardinal(-22 * D), "N");
  assert.equal(bearingToCardinal(-23 * D), "NW");
  // Wraparound at ±180°.
  assert.equal(bearingToCardinal(179 * D), "S");
  assert.equal(bearingToCardinal(-179 * D), "S");
});

test("bearingToCardinalLong matches short mapper sectors", () => {
  assert.equal(bearingToCardinalLong(0), "north");
  assert.equal(bearingToCardinalLong(90 * D), "east");
  assert.equal(bearingToCardinalLong(-45 * D), "north-west");
});

test("travelAngleToBearingRad: math angle to compass bearing", () => {
  // Travel east (angle 0) = bearing +90°.
  assert.ok(Math.abs(travelAngleToBearingRad(0) - Math.PI / 2) < 1e-12);
  // Travel north (angle +90°) = bearing 0.
  assert.ok(Math.abs(travelAngleToBearingRad(Math.PI / 2)) < 1e-12);
  // Travel west (angle π) = bearing -90°.
  assert.ok(Math.abs(travelAngleToBearingRad(Math.PI) - -Math.PI / 2) < 1e-12);
  assert.equal(bearingToCardinal(travelAngleToBearingRad(0)), "E");
  assert.equal(bearingToCardinal(travelAngleToBearingRad(Math.PI)), "W");
});

test("headingVectorFromAngle: regression for motion-vector decode", () => {
  // angle 0 (east) → +x, no z. This is the fused "toward node 2" arrow.
  let v = headingVectorFromAngle(0);
  assert.ok(Math.abs(v.dx - 1) < 1e-12 && Math.abs(v.dz) < 1e-12);
  // angle π (west) → -x. Fused "toward node 1" arrow.
  v = headingVectorFromAngle(Math.PI);
  assert.ok(Math.abs(v.dx - -1) < 1e-12 && Math.abs(v.dz) < 1e-12);
  // angle π/2 (north) → +z.
  v = headingVectorFromAngle(Math.PI / 2);
  assert.ok(Math.abs(v.dx) < 1e-12 && Math.abs(v.dz - 1) < 1e-12);
});
