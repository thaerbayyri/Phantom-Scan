/**
 * Simulated-walker generator for Demo mode.
 *
 * Everything here is SYNTHETIC: a scripted person walking a fixed loop through
 * the configured room. It exists so the dashboard can show what a successful
 * detection looks like (radar dot, uncertainty ring, node glow, signal field,
 * illustrative skeleton) without hardware. It is not a measurement and never
 * touches the detection pipeline - every produced message is labelled
 * `source_mode: "synthetic"` / `SensorNode.source: "synthetic"`.
 *
 * Pure and deterministic: the same (time, room) always yields the same frame.
 */
import type { RadialTarget, SensorNode, SignalField, TargetState, VitalSigns } from "@shared/schema";
import { compassBearingRad } from "@shared/bearing";
import { computeRadialTrends } from "./node-fusion";
import type { RoomGeometry } from "./room-geometry";
import { buildTargetState } from "./target-state";

/** Nominal indoor walking speed used by the scripted walker. */
export const WALKER_SPEED_MPS = 0.8;
const PAUSE_S = 2.5;
const POSITION_UNCERTAINTY_M = 0.6;
const WALKER_CONFIDENCE = 0.8;
const WALKER_HUMAN_PROB = 0.9;
const MOTION_FALLOFF_M = 2.2;
const PAUSED_MOTION_SCALE = 0.35;
const SIGNAL_FIELD_GRID = 20;

/** Loop corners as fractions of the room half-extents; index -> pause there. */
const LOOP_FRACTIONS: ReadonlyArray<readonly [number, number]> = [
  [-0.6, -0.65],
  [0.6, -0.65],
  [0.6, 0.1],
  [0.6, 0.65],
  [-0.6, 0.65],
  [-0.6, -0.1],
];
const PAUSE_AT_CORNER: ReadonlySet<number> = new Set([2, 5]);

interface Point {
  readonly x: number;
  readonly z: number;
}

interface WalkLeg {
  readonly kind: "walk";
  readonly from: Point;
  readonly to: Point;
  readonly durationS: number;
  readonly headingRad: number;
}

interface PauseLeg {
  readonly kind: "pause";
  readonly at: Point;
  readonly durationS: number;
  readonly headingRad: number;
}

type Leg = WalkLeg | PauseLeg;

export interface WalkerPose {
  readonly x: number;
  readonly z: number;
  readonly vx: number;
  readonly vz: number;
  readonly speed: number;
  /** Direction of travel, math convention (0 = east, counter-clockwise). */
  readonly headingRad: number;
}

export interface WalkerFrame {
  readonly radialTarget: RadialTarget;
  readonly targetState: TargetState;
  readonly nodes: SensorNode[];
  readonly signalField: SignalField;
  /** Scripted (never measured) vitals; the dashboard flags them SIMULATED. */
  readonly vitalSigns: VitalSigns;
}

function buildLegs(room: RoomGeometry): Leg[] {
  const halfW = room.roomWidthM / 2;
  const halfD = room.roomDepthM / 2;
  const corners: Point[] = LOOP_FRACTIONS.map(([fx, fz]) => ({ x: fx * halfW, z: fz * halfD }));
  const legs: Leg[] = [];
  corners.forEach((from, i) => {
    const to = corners[(i + 1) % corners.length];
    const length = Math.hypot(to.x - from.x, to.z - from.z);
    const headingRad = Math.atan2(to.z - from.z, to.x - from.x);
    legs.push({ kind: "walk", from, to, durationS: length / WALKER_SPEED_MPS, headingRad });
    if (PAUSE_AT_CORNER.has((i + 1) % corners.length)) {
      legs.push({ kind: "pause", at: to, durationS: PAUSE_S, headingRad });
    }
  });
  return legs;
}

/** Duration of one full lap including pauses. */
export function walkerCycleSeconds(room: RoomGeometry): number {
  return buildLegs(room).reduce((sum, leg) => sum + leg.durationS, 0);
}

/** Where the scripted walker is `tSec` seconds into the (looping) script. */
export function walkerAt(tSec: number, room: RoomGeometry): WalkerPose {
  const legs = buildLegs(room);
  const cycle = legs.reduce((sum, leg) => sum + leg.durationS, 0);
  let remaining = ((tSec % cycle) + cycle) % cycle;

  for (const leg of legs) {
    if (remaining > leg.durationS) {
      remaining -= leg.durationS;
      continue;
    }
    if (leg.kind === "pause") {
      return { x: leg.at.x, z: leg.at.z, vx: 0, vz: 0, speed: 0, headingRad: leg.headingRad };
    }
    const frac = remaining / leg.durationS;
    return {
      x: leg.from.x + (leg.to.x - leg.from.x) * frac,
      z: leg.from.z + (leg.to.z - leg.from.z) * frac,
      vx: Math.cos(leg.headingRad) * WALKER_SPEED_MPS,
      vz: Math.sin(leg.headingRad) * WALKER_SPEED_MPS,
      speed: WALKER_SPEED_MPS,
      headingRad: leg.headingRad,
    };
  }

  // Unreachable (remaining < cycle), but keep the type total.
  const start = legs[0] as WalkLeg;
  return { x: start.from.x, z: start.from.z, vx: 0, vz: 0, speed: 0, headingRad: start.headingRad };
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function buildNodes(room: RoomGeometry, pose: WalkerPose): SensorNode[] {
  const trends = computeRadialTrends(
    { x: pose.x, z: pose.z },
    { vx: pose.vx, vz: pose.vz },
    room.anchors,
  );
  const scale = pose.speed > 0 ? 1 : PAUSED_MOTION_SCALE;
  return Object.keys(room.anchors)
    .map(Number)
    .sort((a, b) => a - b)
    .map((nodeId) => {
      const anchor = room.anchors[nodeId];
      const distanceM = Math.hypot(pose.x - anchor.x, pose.z - anchor.z);
      return {
        node_id: nodeId,
        x: anchor.x,
        z: anchor.z,
        motion: clamp01(Math.exp(-distanceM / MOTION_FALLOFF_M) * scale),
        active: true,
        rssi: Math.round(-45 - 4 * distanceM),
        source: "synthetic" as const,
        distanceM,
        trend: trends[nodeId] ?? "stable",
      };
    });
}

function buildSignalField(room: RoomGeometry, nodes: SensorNode[]): SignalField {
  const gridWidth = SIGNAL_FIELD_GRID;
  const gridDepth = SIGNAL_FIELD_GRID;
  const cellW = room.roomWidthM / gridWidth;
  const cellD = room.roomDepthM / gridDepth;
  const values: number[] = new Array(gridWidth * gridDepth);
  for (let gz = 0; gz < gridDepth; gz++) {
    const cz = -room.roomDepthM / 2 + (gz + 0.5) * cellD;
    for (let gx = 0; gx < gridWidth; gx++) {
      const cx = -room.roomWidthM / 2 + (gx + 0.5) * cellW;
      let num = 0;
      let den = 0;
      for (const node of nodes) {
        const d = Math.max(0.25, Math.hypot(cx - node.x, cz - node.z));
        const w = 1 / (d * d);
        num += node.motion * w;
        den += w;
      }
      values[gz * gridWidth + gx] = den > 0 ? num / den : 0;
    }
  }
  return {
    gridWidth,
    gridDepth,
    cellSizeM: cellW,
    cellDepthM: cellD,
    roomWidthM: room.roomWidthM,
    roomDepthM: room.roomDepthM,
    values,
  };
}

const VITALS_HR_BASE_BPM = 72;
const VITALS_HR_SWING_BPM = 4;
const VITALS_HR_PERIOD_S = 17;
const VITALS_RR_BASE_RPM = 16;
const VITALS_RR_SWING_RPM = 1.5;
const VITALS_RR_PERIOD_S = 23;

/** Slowly drifting, plausible resting vitals. Scripted for the demo only. */
function buildSimulatedVitals(tSec: number): VitalSigns {
  return {
    heartRateBpm: Math.round(VITALS_HR_BASE_BPM + VITALS_HR_SWING_BPM * Math.sin((2 * Math.PI * tSec) / VITALS_HR_PERIOD_S)),
    respirationRateRpm: Math.round(VITALS_RR_BASE_RPM + VITALS_RR_SWING_RPM * Math.sin((2 * Math.PI * tSec) / VITALS_RR_PERIOD_S)),
    vitalsReliable: true,
  };
}

/** One complete simulated scene: target, state, node glow, signal field and vitals. */
export function buildWalkerFrame(tSec: number, nowMs: number, room: RoomGeometry): WalkerFrame {
  const pose = walkerAt(tSec, room);
  const radialTarget: RadialTarget = {
    x: pose.x,
    z: pose.z,
    r: Math.hypot(pose.x, pose.z),
    theta: compassBearingRad(pose.x, pose.z),
    vx: pose.vx,
    vz: pose.vz,
    isMoving: pose.speed > 0,
    angle: pose.headingRad,
    speed: Math.hypot(pose.vx, pose.vz),
    confidence: WALKER_CONFIDENCE,
    label: "human",
    humanProb: WALKER_HUMAN_PROB,
    distanceCm: Math.hypot(pose.x, pose.z) * 100,
    wallDistance: Math.max(0.3, room.roomWidthM / 2 - pose.x),
    positionBasis: "fused_room_centroid",
    positionUncertaintyM: POSITION_UNCERTAINTY_M,
  };
  const nodes = buildNodes(room, pose);
  const targetState = buildTargetState({
    dataSource: "esp32",
    nowMs,
    lastTruthfulUpdateMs: nowMs,
    nodeMode: "fused_room",
    radialTarget,
    sourceMode: "synthetic",
  });
  return {
    radialTarget,
    targetState,
    nodes,
    signalField: buildSignalField(room, nodes),
    vitalSigns: buildSimulatedVitals(tSec),
  };
}
