import type { DataSource, MotionStatus, RadialTarget, TargetState } from "@shared/schema";

export const LIVE_TARGET_STALE_TIMEOUT_MS = 1_500;
export const LIVE_TARGET_CLEAR_TIMEOUT_MS = 5_000;

type SourceMode = TargetState["source_mode"];
type NodeMode = TargetState["node_mode"];
type StateKind = TargetState["state"];

export interface BuildTargetStateInput {
  dataSource: DataSource;
  nowMs: number;
  lastTruthfulUpdateMs?: number;
  radialTarget?: RadialTarget | null;
  motionStatus?: MotionStatus | null;
  reason?: string;
}

export type LiveHoldState = "startup" | "live" | "stale_hold" | "cleared";

export function resolveSourceMode(dataSource: DataSource): SourceMode {
  if (dataSource === "demo") {
    return "synthetic";
  }
  if (dataSource === "file") {
    return "replay";
  }
  return "live";
}

export function resolveNodeMode(sourceMode: SourceMode): NodeMode {
  if (sourceMode === "synthetic") {
    return "fused_two_node";
  }
  return "single_node";
}

export function emptyTargetState(input: BuildTargetStateInput): TargetState {
  const sourceMode = resolveSourceMode(input.dataSource);
  const nodeMode = resolveNodeMode(sourceMode);
  const lastUpdate = input.lastTruthfulUpdateMs ?? input.nowMs;
  const dataAge = Math.max(0, input.nowMs - lastUpdate);
  const stale = dataAge >= LIVE_TARGET_STALE_TIMEOUT_MS;
  const state: StateKind = stale ? "stale" : "none";

  return {
    state,
    source_mode: sourceMode,
    node_mode: nodeMode,
    target_visible: false,
    position_confident: false,
    motion_score: input.motionStatus?.variance ?? 0,
    confidence: 0,
    last_update_ms: lastUpdate,
    data_age_ms: dataAge,
    stale,
    reason: input.reason ?? (stale ? "target_stale" : "no_truthful_target"),
  };
}

export function buildTargetState(input: BuildTargetStateInput): TargetState {
  if (!input.radialTarget) {
    return emptyTargetState(input);
  }

  const sourceMode = resolveSourceMode(input.dataSource);
  const nodeMode = resolveNodeMode(sourceMode);
  const lastUpdate = input.lastTruthfulUpdateMs ?? input.nowMs;
  const dataAge = Math.max(0, input.nowMs - lastUpdate);
  const stale = dataAge >= LIVE_TARGET_STALE_TIMEOUT_MS;

  if (stale) {
    return emptyTargetState({
      ...input,
      reason: input.reason ?? "target_stale",
    });
  }

  const positionConfident = input.radialTarget.confidence >= 0.45;
  const isMoving = input.radialTarget.isMoving || (input.motionStatus?.motionDetected ?? false);

  let state: StateKind;
  if (sourceMode !== "synthetic" && nodeMode === "single_node") {
    state = "degraded";
  } else {
    state = isMoving ? "moving" : "idle";
  }

  return {
    state,
    source_mode: sourceMode,
    node_mode: nodeMode,
    target_visible: true,
    position_confident: positionConfident,
    position: {
      x: input.radialTarget.x,
      y: 0,
      z: input.radialTarget.z,
    },
    bearing_deg: (input.radialTarget.theta * 180) / Math.PI,
    range_m: input.radialTarget.r,
    motion_score: input.motionStatus?.variance ?? (input.radialTarget.isMoving ? input.radialTarget.speed : 0),
    confidence: input.radialTarget.confidence,
    last_update_ms: lastUpdate,
    data_age_ms: dataAge,
    stale: false,
    reason: input.reason,
  };
}

export function resolveLiveHoldState(lastTruthfulUpdateMs: number | null | undefined, nowMs: number): LiveHoldState {
  if (!lastTruthfulUpdateMs) {
    return "startup";
  }

  const ageMs = Math.max(0, nowMs - lastTruthfulUpdateMs);
  if (ageMs >= LIVE_TARGET_CLEAR_TIMEOUT_MS) {
    return "cleared";
  }
  if (ageMs >= LIVE_TARGET_STALE_TIMEOUT_MS) {
    return "stale_hold";
  }
  return "live";
}
