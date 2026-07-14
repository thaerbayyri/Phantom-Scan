/**
 * Turns the numeric target (position/balance/trends) into the human-readable
 * sentences shown on the identity card and top bar: zone ("Near N1",
 * "Between N1 and N2"), per-node distances, and a motion phrase ("Toward N2",
 * "Holding at midpoint", "Crossing the midpoint").
 */
import type { RadialTarget, SensorNode, TargetState } from "./schema";
import { bearingToCardinalLong, travelAngleToBearingRad } from "./bearing";

export interface NodeDistanceSummary {
  nodeId: number;
  distanceM: number;
}

export interface TargetSpatialSummary {
  zoneLabel: string;
  detailLabel: string;
  motionLabel: string;
  nearestNodeId: number | null;
  distances: NodeDistanceSummary[];
  presentationMode: "fused_axis" | "single_node";
  balanceZone?: "near_n1" | "midpoint" | "near_n2";
  projectionLabel?: string;
}

function roundDistance(distanceM: number): string {
  return `${distanceM.toFixed(1)} m`;
}

export function summarizeTargetSpatial(
  radialTarget: RadialTarget | null | undefined,
  nodes: SensorNode[] = [],
  targetState: TargetState | null | undefined,
): TargetSpatialSummary | null {
  if (!radialTarget || !targetState || nodes.length === 0) {
    return null;
  }

  // Straight-line distance from the target to each node anchor, plus which
  // node the target is currently approaching (from the server-side trend).
  const distances = nodes
    .map((node) => ({
      nodeId: node.node_id,
      distanceM: Math.hypot(radialTarget.x - node.x, radialTarget.z - node.z),
    }))
    .sort((a, b) => a.nodeId - b.nodeId);

  const nearest = distances.reduce<NodeDistanceSummary | null>(
    (best, current) => (best === null || current.distanceM < best.distanceM ? current : best),
    null,
  );
  const approaching = nodes.find((node) => node.trend === "approaching");

  // Fused two-node mode: zone comes from the balance value (≤0.2 near N1,
  // ≥0.8 near N2, else midpoint); the motion phrase prefers the approach
  // trend, falling back to balance-zone wording when idle.
  if (targetState.node_mode === "fused_two_node" && radialTarget.balance !== undefined && distances.length >= 2) {
    const balanceZone =
      radialTarget.balance <= 0.2
        ? "near_n1"
        : radialTarget.balance >= 0.8
          ? "near_n2"
          : "midpoint";
    const zoneLabel =
      balanceZone === "near_n1"
        ? `Near N${distances[0].nodeId}`
        : balanceZone === "near_n2"
          ? `Near N${distances[1].nodeId}`
          : `Between N${distances[0].nodeId} and N${distances[1].nodeId}`;
    const detailLabel = distances
      .map((distance) => `N${distance.nodeId} ${roundDistance(distance.distanceM)}`)
      .join(" • ");
    const motionLabel = radialTarget.isMoving
      ? approaching
        ? `Toward N${approaching.node_id}`
        : balanceZone === "midpoint"
          ? "Crossing the midpoint"
          : "Moving on the node axis"
      : balanceZone === "midpoint"
        ? "Holding at midpoint"
        : `Holding near N${nearest?.nodeId ?? distances[0].nodeId}`;

    return {
      zoneLabel,
      detailLabel,
      motionLabel,
      nearestNodeId: nearest?.nodeId ?? null,
      distances,
      presentationMode: "fused_axis",
      balanceZone,
      projectionLabel: "axis-only estimate",
    };
  }

  if (!nearest) {
    return null;
  }

  // Single-node fallback: only a nearest-node distance and a cardinal
  // direction of travel can be honestly stated.
  return {
    zoneLabel: `Around N${nearest.nodeId}`,
    detailLabel: `${roundDistance(nearest.distanceM)} from N${nearest.nodeId}`,
    motionLabel: radialTarget.isMoving
      ? `Moving ${bearingToCardinalLong(travelAngleToBearingRad(radialTarget.angle))} around the node field`
      : `Holding near N${nearest.nodeId}`,
    nearestNodeId: nearest.nodeId,
    distances,
    presentationMode: "single_node",
  };
}
