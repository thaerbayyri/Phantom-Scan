/**
 * Target presence/movement STATE MACHINE.
 *
 * Converts the fused radial target + motion gate output into the `TargetState`
 * contract broadcast to the dashboard: state ∈ none | stale | idle | moving |
 * degraded. This is the single place that decides which presence label the UI
 * may show, and how long a vanished target may linger before being cleared.
 */
import type { DataSource, MotionStatus, RadialTarget, TargetState } from "@shared/schema";

/** After 1.5 s without a truthful update the target is marked stale (UI stops trusting position). */
export const LIVE_TARGET_STALE_TIMEOUT_MS = 1_500;
/** After 5 s without a truthful update the target is fully cleared from the scene. */
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
  /** Demo mode only: label the state "replay"/"synthetic" instead of "live". */
  sourceMode?: SourceMode;
}

/**
 * Lifecycle of the live target between updates:
 * startup (never saw one) → live (fresh) → stale_hold (1.5–5 s old, position
 * frozen but flagged) → cleared (>5 s, scene wiped so no ghost remains).
 */
export type LiveHoldState = "startup" | "live" | "stale_hold" | "cleared";

/** Only live hardware is supported as a source in this build (no replay/synthetic modes). */
export function resolveSourceMode(dataSource: DataSource): SourceMode {
  void dataSource;
  return "live";
}

/** Default node mode when the caller doesn't specify one; websocket.ts overrides with fused_two_node when both nodes are fresh. */
export function resolveNodeMode(sourceMode: SourceMode): NodeMode {
  void sourceMode;
  return "single_node";
}

/**
 * TargetState for "no detectable target": target_visible=false, no position.
 * `state` is "stale" if we HAD a target that aged out, "none" if the room is
 * simply empty; `reason` tells the UI/debug panel why nothing is drawn.
 */
export function emptyTargetState(input: BuildTargetStateInput): TargetState {
  const sourceMode = input.sourceMode ?? resolveSourceMode(input.dataSource);
  const nodeMode = input.nodeMode ?? resolveNodeMode(sourceMode);
  const lastUpdate = input.lastTruthfulUpdateMs ?? input.nowMs;
  const dataAge = Math.max(0, input.nowMs - lastUpdate);
  // "stale" means recently aged out (within the hold/clear window this same
  // lifecycle uses elsewhere — see resolveLiveHoldState). Past the clear
  // timeout, dataAge only keeps growing forever with nothing to reset it, so
  // without this upper bound a room that had exactly one detection at the
  // start of an hours-long session would report "stale" — never "none" —
  // for the rest of it, even though it is by then indistinguishable from a
  // room that was simply always empty.
  const stale =
    dataAge >= LIVE_TARGET_STALE_TIMEOUT_MS && dataAge < LIVE_TARGET_CLEAR_TIMEOUT_MS;
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

/**
 * THE presence/movement classifier. Maps the fused radial target (or its
 * absence) into the exact state shown on the dashboard:
 *   - no target            → none / stale (via emptyTargetState)
 *   - target but too old   → stale
 *   - single-node evidence → degraded (position not trustworthy)
 *   - two-node + moving    → moving
 *   - two-node + still     → idle
 */
export function buildTargetState(input: BuildTargetStateInput): TargetState {
  if (!input.radialTarget) {
    return emptyTargetState(input);
  }

  const sourceMode = input.sourceMode ?? resolveSourceMode(input.dataSource);
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

  // MOVEMENT decision: either the fused target itself reports motion (speed
  // along the axis) OR the variance-based MotionGate fired this frame.
  const positionConfident = input.radialTarget.confidence >= 0.45;
  const isMoving = input.radialTarget.isMoving || (input.motionStatus?.motionDetected ?? false);

  // Single-node evidence can never claim a confident position, so it is always
  // reported as "degraded" no matter how strong the motion is.
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

/**
 * Ages the last truthful detection into the hold lifecycle (see LiveHoldState).
 * websocket.ts polls this every frame to decide whether to keep, flag, or wipe
 * the on-screen target when packets stop arriving (node unplugged, WiFi drop).
 */
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
