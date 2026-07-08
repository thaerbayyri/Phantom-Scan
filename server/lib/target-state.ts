import type { DataSource, MotionStatus, RadialTarget, TargetState } from "@shared/schema";

export const LIVE_TARGET_STALE_TIMEOUT_MS = 1_500;
export const LIVE_TARGET_CLEAR_TIMEOUT_MS = 5_000;

/**
 * Is a queued hardware sample still fresh enough to process as "live"?
 *
 * Samples are stamped with host Date.now() at UDP receipt. After a node
 * disconnect, up to 1000 backlog samples could otherwise keep the pipeline
 * painting a ghost target for ~50 s (1 sample per 50 ms tick); dropping
 * anything older than the live stale window kills that replay.
 */
export function isSampleFresh(
  sample: { timestamp: number },
  nowMs: number,
  staleMs: number = LIVE_TARGET_STALE_TIMEOUT_MS,
): boolean {
  return sample.timestamp >= nowMs - staleMs;
}

type SourceMode = TargetState["source_mode"];
type NodeMode = TargetState["node_mode"];
type StateKind = TargetState["state"];

export interface BuildTargetStateInput {
  dataSource: DataSource;
  nowMs: number;
  lastTruthfulUpdateMs?: number;
  nodeMode?: NodeMode;
  radialTarget?: RadialTarget | null;
  motionStatus?: MotionStatus | null;
  reason?: string;
}

export type LiveHoldState = "startup" | "live" | "stale_hold" | "cleared";

export function resolveSourceMode(dataSource: DataSource): SourceMode {
  void dataSource;
  return "live";
}

export function resolveNodeMode(sourceMode: SourceMode): NodeMode {
  void sourceMode;
  return "single_node";
}

export function emptyTargetState(input: BuildTargetStateInput): TargetState {
  const sourceMode = resolveSourceMode(input.dataSource);
  const nodeMode = input.nodeMode ?? resolveNodeMode(sourceMode);
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
  const nodeMode = input.nodeMode ?? resolveNodeMode(sourceMode);
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
  if (nodeMode === "single_node") {
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
    // Compass degrees (0 = north, 90 = east) — see radialTargetSchema / shared/bearing.ts.
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
