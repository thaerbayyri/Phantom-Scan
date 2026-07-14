/**
 * Truthfulness gates for PRESENTING the target. Shared by server and client
 * so both sides agree on when a detection may be drawn, when the motion
 * arrow may appear, and which honesty caveat must accompany the position.
 * These predicates are the client-side "kill switches": if they say no, the
 * radar renders an empty scene regardless of what data has arrived.
 */
import type { DataSource, RadialTarget, TargetState } from "./schema";

interface TargetPresentationInput {
  dataSource: DataSource;
  radialTarget: RadialTarget | null | undefined;
  targetState: TargetState | null | undefined;
}

export interface TargetPresentationCaveat {
  primary: string;
  secondary: string;
}

/** A target exists AND the state machine says it is currently visible. */
export function canPresentTruthfulTarget(
  input: Pick<TargetPresentationInput, "radialTarget" | "targetState">,
): boolean {
  return Boolean(input.radialTarget && input.targetState?.target_visible);
}

/**
 * May the dot be drawn at a position? Blocks "none" and "stale" states
 * outright — a vanished or aged-out target must never keep painting a
 * position, no matter what the last radialTarget message contained.
 */
export function canPresentLiveTargetPosition(
  input: TargetPresentationInput,
): boolean {
  if (!input.radialTarget || !input.targetState) {
    return false;
  }

  if (input.targetState.state === "none" || input.targetState.state === "stale") {
    return false;
  }

  if (input.targetState.target_visible) {
    return true;
  }

  return input.dataSource === "esp32";
}

/**
 * Honesty label that must accompany a rendered position: fused mode is an
 * on-axis projection (front/back ambiguous), single-node mode is an
 * unvalidated bearing. Null when nothing is being presented.
 */
export function getLivePositionCaveat(
  input: TargetPresentationInput,
): TargetPresentationCaveat | null {
  if (!canPresentLiveTargetPosition(input) || input.dataSource !== "esp32" || !input.targetState) {
    return null;
  }

  if (input.targetState.node_mode === "fused_two_node") {
    return {
      primary: "ON-AXIS ESTIMATE - NOT ROOM POSITION",
      secondary: "front/back ambiguous - off-axis subjects project onto the baseline",
    };
  }

  return {
    primary: "SINGLE-NODE BEARING - UNVALIDATED",
    secondary: "single-antenna AoA plus PDP, not a lower-resolution fused estimate",
  };
}

/** Volumetric (human-mesh) rendering is deliberately disabled — the system cannot honestly claim body shape from CSI. */
export function canPresentVolumetricTarget(
  input: TargetPresentationInput,
): boolean {
  void input;
  return false;
}

/**
 * May the movement arrow be drawn? Requires a presentable position AND
 * speed > 0.05 m/s, so sub-noise velocities don't render a phantom motion
 * vector on a stationary target.
 */
export function canPresentAxisMotionVector(
  input: TargetPresentationInput,
): boolean {
  if (!canPresentLiveTargetPosition(input) || !input.radialTarget) {
    return false;
  }

  return input.radialTarget.speed > 0.05;
}
