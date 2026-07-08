/**
 * Canonical angle conventions for the radar scene (single source of truth).
 *
 * World frame: +x = east, +z = north, y = up (see NODE_ANCHORS in schema.ts).
 *
 * Two distinct angle kinds flow through RadialTarget:
 *
 *  - `theta` — COMPASS BEARING: `atan2(x, z)`; 0 = north (+z), +π/2 = east (+x),
 *    clockwise-positive viewed from above with north up.
 *    Encode: x = r·sin(theta), z = r·cos(theta).
 *
 *  - `angle` — DIRECTION OF TRAVEL, math convention: `atan2(vz, vx)`;
 *    0 = east (+x), +π/2 = north (+z), counter-clockwise positive.
 *    Decode to a world vector as (cos → x, sin → z).
 *
 * Every renderer and text mapper MUST use these helpers instead of inlining
 * trig — three divergent inline mappers previously produced mirrored E/W text
 * and a motion arrow 90° off from the heading cone.
 */

export type Cardinal = "N" | "NE" | "E" | "SE" | "S" | "SW" | "W" | "NW";

const CARDINALS: Cardinal[] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const CARDINALS_LONG = [
  "north",
  "north-east",
  "east",
  "south-east",
  "south",
  "south-west",
  "west",
  "north-west",
] as const;

/** Compass bearing (radians) of a world position: 0 = north (+z), +π/2 = east (+x). */
export function compassBearingRad(x: number, z: number): number {
  return Math.atan2(x, z);
}

function cardinalIndex(bearingRad: number): number {
  const deg = (bearingRad * 180) / Math.PI;
  // Normalize to [0, 360) then bucket into 45° sectors centered on the cardinals.
  const norm = ((deg % 360) + 360) % 360;
  return Math.round(norm / 45) % 8;
}

/** Short cardinal label ("N".."NW") for a compass bearing in radians. */
export function bearingToCardinal(bearingRad: number): Cardinal {
  return CARDINALS[cardinalIndex(bearingRad)];
}

/** Long cardinal label ("north".."north-west") for a compass bearing in radians. */
export function bearingToCardinalLong(
  bearingRad: number,
): (typeof CARDINALS_LONG)[number] {
  return CARDINALS_LONG[cardinalIndex(bearingRad)];
}

/**
 * Convert a math-convention travel `angle` (0 = east, CCW positive) to a
 * compass bearing (0 = north, CW positive). Normalized to (-π, π].
 */
export function travelAngleToBearingRad(angle: number): number {
  const bearing = Math.PI / 2 - angle;
  return Math.atan2(Math.sin(bearing), Math.cos(bearing));
}

/** World-space unit vector for a math-convention travel angle: (cos → x, sin → z). */
export function headingVectorFromAngle(angle: number): { dx: number; dz: number } {
  return { dx: Math.cos(angle), dz: Math.sin(angle) };
}
