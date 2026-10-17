import type { CSISample, RadialTarget, TargetState } from "@shared/schema";
import { getRoomGeometry, nodePairSeparationM } from "./room-geometry";
import type { ClassifierCorroboration, NodeTrend } from "./node-fusion";
import { TREND_DEADBAND_MPS } from "./node-fusion";

export type GroundTruthSource = "none" | "dwell" | "video";

export interface GroundTruthTag {
  xM: number;
  yM: number;
  pointId?: string;
  source: Exclude<GroundTruthSource, "none">;
}

export interface FusedSnapshotLike {
  balance: number;
  x: number;
  z: number;
  velMps: number;
  endpointIds: [number, number];
  trends: Record<number, NodeTrend>;
  atMs: number;
}

export interface RecordingSessionMeta {
  session_name: string;
  recording_start_ms: number;
  anchor_n1_x_m?: number;
  anchor_n1_z_m?: number;
  anchor_n2_x_m?: number;
  anchor_n2_z_m?: number;
  anchor_n3_x_m?: number;
  anchor_n3_z_m?: number;
  anchor_n4_x_m?: number;
  anchor_n4_z_m?: number;
  node_separation_m: number;
  motion_threshold: number;
  scalar_motion_threshold: number;
  fused_motion_threshold: number;
  trend_deadband_mps: number;
  node1_fps_start: number;
  node2_fps_start: number;
  firmware_build_id?: string;
  self_ping_status?: string;
  wall_cell?: string;
  wall_thickness_m?: number;
  room_geometry_id?: string;
  gt_source_method: string;
  position_contract: string;
}

export interface RecordingRow {
  timestamp: number;
  session_ts_ms: number;
  sync_marker: 0 | 1;
  subcarrier_index?: number;
  h1_re: number;
  h1_im: number;
  h2_re: number;
  h2_im: number;
  rssi?: number;
  x?: number;
  z?: number;
  x_disp_m?: number;
  z_disp_m?: number;
  speed?: number;
  label?: string;
  distance_cm?: number;
  distance_n1_m?: number;
  distance_n2_m?: number;
  distance_n3_m?: number;
  distance_n4_m?: number;
  balance?: number;
  // Phase-1 bug audit: authoritative/canonical balance (ADR-054) was computed
  // every tick (radialTarget.balanceLinear) but never made it into recorded
  // sessions — only the display value above was exported.
  balance_linear?: number;
  motion_n1?: number;
  motion_n2?: number;
  motion_n3?: number;
  motion_n4?: number;
  /** Unclamped, unscaled absStd/mean perturbation ratio per node — unlike
   * motion_nX (min(1.0, ratio * MOTION_SATURATION_SCALE)), this is never
   * clamped, so a saturated motion_nX (ratio at or above the ceiling) can
   * still be told apart from a genuinely-near-ceiling one. Needed to
   * re-derive MOTION_SATURATION_SCALE/DEFAULT_MOTION_THRESHOLD from real
   * data — motion_nX alone censors any value at or above the ceiling. */
  raw_perturbation_n1?: number;
  raw_perturbation_n2?: number;
  raw_perturbation_n3?: number;
  raw_perturbation_n4?: number;
  trend_n1: NodeTrend;
  trend_n2: NodeTrend;
  node_mode: TargetState["node_mode"];
  target_state: TargetState["state"];
  target_visible: 0 | 1;
  node1_fps: number;
  node2_fps: number;
  node3_fps?: number;
  node4_fps?: number;
  gt_x_m?: number;
  gt_y_m?: number;
  gt_point_id?: string;
  gt_source: GroundTruthSource;
  /** Item 1/2: unlike `label` (gated on target_visible), this is populated on
   * EVERY row — including suppressed/held ticks — so a negative-control
   * session can distinguish "energy gate never fired" from "energy gate
   * fired but the classifier vetoed it" purely from the recording. */
  classifier_corroboration: ClassifierCorroboration;
}

export interface BuildRecordingRowInput {
  sample: CSISample;
  sessionStartMs: number;
  radialTarget?: RadialTarget | null;
  targetState: TargetState;
  fusedSnapshot?: FusedSnapshotLike | null;
  nodeMotion: Record<number, number>;
  /** Unclamped absStd/mean per node — see RecordingRow.raw_perturbation_nX. */
  nodeRawPerturbation: Record<number, number>;
  nodeFps: Record<number, number>;
  syncMarker?: boolean;
  groundTruthTag?: GroundTruthTag | null;
  /** Item 1/2: this tick's classifier corroboration decision, captured
   * regardless of whether a target ended up visible this tick. */
  classifierCorroboration?: ClassifierCorroboration;
}

export const RECORDING_POSITION_CONTRACT =
  "x_disp_m/z_disp_m are authoritative room-meter display fields; legacy x/z are compatibility copies of the same visible position.";

export const RECORDING_COLUMNS: Array<keyof RecordingRow> = [
  "timestamp",
  "session_ts_ms",
  "sync_marker",
  "subcarrier_index",
  "h1_re",
  "h1_im",
  "h2_re",
  "h2_im",
  "rssi",
  "x",
  "z",
  "x_disp_m",
  "z_disp_m",
  "speed",
  "label",
  "distance_cm",
  "distance_n1_m",
  "distance_n2_m",
  "distance_n3_m",
  "distance_n4_m",
  "balance",
  "balance_linear",
  "motion_n1",
  "motion_n2",
  "motion_n3",
  "motion_n4",
  "raw_perturbation_n1",
  "raw_perturbation_n2",
  "raw_perturbation_n3",
  "raw_perturbation_n4",
  "trend_n1",
  "trend_n2",
  "node_mode",
  "target_state",
  "target_visible",
  "node1_fps",
  "node2_fps",
  "node3_fps",
  "node4_fps",
  "gt_x_m",
  "gt_y_m",
  "gt_point_id",
  "gt_source",
  "classifier_corroboration",
];

export function buildRecordingSessionMeta(input: {
  sessionName: string;
  recordingStartMs: number;
  node1Fps: number;
  node2Fps: number;
  scalarMotionThreshold: number;
  fusedMotionThreshold: number;
}): RecordingSessionMeta {
  const wallThickness = Number.parseFloat(
    process.env.PHANTOM_WALL_THICKNESS_M ?? "",
  );

  const room = getRoomGeometry();
  return {
    session_name: input.sessionName,
    recording_start_ms: input.recordingStartMs,
    anchor_n1_x_m: room.anchors[1]?.x,
    anchor_n1_z_m: room.anchors[1]?.z,
    anchor_n2_x_m: room.anchors[2]?.x,
    anchor_n2_z_m: room.anchors[2]?.z,
    anchor_n3_x_m: room.anchors[3]?.x,
    anchor_n3_z_m: room.anchors[3]?.z,
    anchor_n4_x_m: room.anchors[4]?.x,
    anchor_n4_z_m: room.anchors[4]?.z,
    node_separation_m: nodePairSeparationM(room),
    motion_threshold: input.fusedMotionThreshold,
    scalar_motion_threshold: input.scalarMotionThreshold,
    fused_motion_threshold: input.fusedMotionThreshold,
    trend_deadband_mps: TREND_DEADBAND_MPS,
    node1_fps_start: input.node1Fps,
    node2_fps_start: input.node2Fps,
    firmware_build_id: process.env.PHANTOM_FIRMWARE_BUILD_ID ?? "",
    self_ping_status: process.env.PHANTOM_SELF_PING_STATUS ?? "",
    wall_cell: process.env.PHANTOM_WALL_CELL ?? "",
    wall_thickness_m: Number.isFinite(wallThickness) ? wallThickness : undefined,
    room_geometry_id: process.env.PHANTOM_ROOM_GEOMETRY_ID ?? "",
    gt_source_method: "dwell_live_or_video_offline_join",
    position_contract: RECORDING_POSITION_CONTRACT,
  };
}

export function buildRecordingRow(input: BuildRecordingRowInput): RecordingRow {
  const visible = input.targetState.target_visible;
  const sessionTsMs = Math.max(0, input.sample.timestamp - input.sessionStartMs);
  const xDispM = visible ? input.radialTarget?.x : undefined;
  const zDispM = visible ? input.radialTarget?.z : undefined;
  const targetX = visible ? input.fusedSnapshot?.x ?? xDispM : undefined;
  const targetZ = visible ? input.fusedSnapshot?.z ?? zDispM : undefined;
  const anchors = getRoomGeometry().anchors;
  const distanceToNode = (nodeId: number): number | undefined => {
    const anchor = anchors[nodeId];
    return targetX !== undefined && targetZ !== undefined && anchor
      ? Math.hypot(targetX - anchor.x, targetZ - anchor.z)
      : undefined;
  };
  const distanceN1M = distanceToNode(1);
  const distanceN2M = distanceToNode(2);
  const distanceN3M = distanceToNode(3);
  const distanceN4M = distanceToNode(4);
  const gtSource = input.groundTruthTag?.source ?? "none";

  return {
    timestamp: input.sample.timestamp,
    session_ts_ms: sessionTsMs,
    sync_marker: input.syncMarker ? 1 : 0,
    subcarrier_index: input.sample.subcarrierIndex,
    h1_re: input.sample.h1.re,
    h1_im: input.sample.h1.im,
    h2_re: input.sample.h2.re,
    h2_im: input.sample.h2.im,
    rssi: input.sample.rssi,
    x: xDispM,
    z: zDispM,
    x_disp_m: xDispM,
    z_disp_m: zDispM,
    speed: visible ? input.radialTarget?.speed : undefined,
    label: visible ? input.radialTarget?.label : undefined,
    distance_cm: visible ? input.radialTarget?.distanceCm : undefined,
    distance_n1_m: distanceN1M,
    distance_n2_m: distanceN2M,
    distance_n3_m: distanceN3M,
    distance_n4_m: distanceN4M,
    balance: visible ? input.fusedSnapshot?.balance ?? input.radialTarget?.balance : undefined,
    balance_linear: visible ? input.radialTarget?.balanceLinear : undefined,
    motion_n1: input.nodeMotion[1],
    motion_n2: input.nodeMotion[2],
    motion_n3: input.nodeMotion[3],
    motion_n4: input.nodeMotion[4],
    raw_perturbation_n1: input.nodeRawPerturbation[1],
    raw_perturbation_n2: input.nodeRawPerturbation[2],
    raw_perturbation_n3: input.nodeRawPerturbation[3],
    raw_perturbation_n4: input.nodeRawPerturbation[4],
    trend_n1: visible ? input.fusedSnapshot?.trends[1] ?? "stable" : "stable",
    trend_n2: visible ? input.fusedSnapshot?.trends[2] ?? "stable" : "stable",
    node_mode: input.targetState.node_mode,
    target_state: input.targetState.state,
    target_visible: visible ? 1 : 0,
    node1_fps: input.nodeFps[1],
    node2_fps: input.nodeFps[2],
    node3_fps: input.nodeFps[3],
    node4_fps: input.nodeFps[4],
    gt_x_m: input.groundTruthTag?.xM,
    gt_y_m: input.groundTruthTag?.yM,
    gt_point_id: input.groundTruthTag?.pointId,
    gt_source: gtSource,
    classifier_corroboration: input.classifierCorroboration ?? "not_evaluated",
  };
}

export function serializeRecordingCsv(
  rows: RecordingRow[],
  meta: RecordingSessionMeta,
): string {
  const lines = [
    `# phantom_session_meta ${JSON.stringify(meta)}`,
    RECORDING_COLUMNS.join(","),
  ];
  for (const row of rows) {
    lines.push(
      RECORDING_COLUMNS.map((column) => csvEscape(formatCsvValue(row[column]))).join(","),
    );
  }
  return lines.join("\n");
}

function formatCsvValue(value: RecordingRow[keyof RecordingRow]): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : trimFloat(value);
  }
  return String(value);
}

function trimFloat(value: number): string {
  return value.toFixed(6).replace(/\.?0+$/, "");
}

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, "\"\"")}"`;
  }
  return value;
}
