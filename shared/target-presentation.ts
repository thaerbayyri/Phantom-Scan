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

export function canPresentTruthfulTarget(
  input: Pick<TargetPresentationInput, "radialTarget" | "targetState">,
): boolean {
  return Boolean(input.radialTarget && input.targetState?.target_visible);
}

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

export function canPresentVolumetricTarget(
  input: TargetPresentationInput,
): boolean {
  void input;
  return false;
}

export function canPresentAxisMotionVector(
  input: TargetPresentationInput,
): boolean {
  if (!canPresentLiveTargetPosition(input) || !input.radialTarget) {
    return false;
  }

  return input.radialTarget.speed > 0.05;
}
