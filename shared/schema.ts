import { z } from "zod";

// Complex number representation
export const complexNumberSchema = z.object({
  re: z.number(),
  im: z.number(),
});
export type ComplexNumber = z.infer<typeof complexNumberSchema>;

// Raw CSI sample from hardware
export const csiSampleSchema = z.object({
  timestamp: z.number(),
  h1: complexNumberSchema,
  h2: complexNumberSchema,
  rssi: z.number().optional(),
  subcarrierIndex: z.number().optional(),
  nodeId: z.number().optional(),
  // Canonical hardware identity carried alongside the runtime node id at the
  // authority ingest boundary (PS-AUDIT-005 mapping layer).
  hardwareId: z.number().optional(),
  // Per-subcarrier amplitudes (antenna 0) for this frame. Feeds the
  // per-subcarrier temporal-std motion energy that drives Phantom Balance Fusion —
  // the scalar h1 alone (max-power subcarrier, index jumps per frame) is too
  // noisy to localize with.
  amplitudes: z.array(z.number()).optional(),
});
export type CSISample = z.infer<typeof csiSampleSchema>;

// Canonical hardware IDs (single source of truth, PS-AUDIT-005). The wire
// protocol keeps the runtime node id as u8 (1-4); the live authority maps it
// immediately to these stable board identities.
export const CANONICAL_NODE_HARDWARE_IDS: Record<number, number> = {
  1: 29052,
  2: 44260,
  3: 51234,
  4: 67891,
};

export const HARDWARE_ID_TO_RUNTIME_NODE_ID: Record<number, number> = {
  29052: 1,
  44260: 2,
  51234: 3,
  67891: 4,
};

export function mapRuntimeNodeIdToHardwareId(nodeId: number): number | undefined {
  return CANONICAL_NODE_HARDWARE_IDS[nodeId];
}

// Channel estimates after processing
export const channelEstimateSchema = z.object({
  timestamp: z.number(),
  h1: complexNumberSchema,
  h2: complexNumberSchema,
  precodingRatio: complexNumberSchema, // p = -h1/h2
  nulledSignal: complexNumberSchema,
});
export type ChannelEstimate = z.infer<typeof channelEstimateSchema>;

// AoA spectrum point
//
// HONESTY NOTE: "angle"/"AoA" naming is kept for wire-compatibility only.
// On this single-antenna-per-node hardware, this is a temporal MUSIC
// signature index/bin, not a physical spatial angle. See the HONESTY NOTE
// above `computeMUSICSpectrum` in server/lib/signal-processing.ts and the
// relabeled aoa-spectrum.tsx panel for the canonical explanation.
export const aoaSpectrumPointSchema = z.object({
  angle: z.number(), // degrees
  power: z.number(), // dB
});
export type AoASpectrumPoint = z.infer<typeof aoaSpectrumPointSchema>;

// ISAR frame containing AoA results
//
// HONESTY NOTE: field/type names ("AoA", "peakAngle") are kept for
// wire-compatibility only. This hardware has 1 antenna per node, so these
// values are a temporal MUSIC signature, not a physical spatial angle. See
// server/lib/signal-processing.ts's HONESTY NOTE and aoa-spectrum.tsx.
export const isarFrameSchema = z.object({
  timestamp: z.number(),
  spectrum: z.array(aoaSpectrumPointSchema),
  peakAngle: z.number(),
  peakPower: z.number(),
});
export type ISARFrame = z.infer<typeof isarFrameSchema>;

// 3D point cloud point
export const pointCloudPointSchema = z.object({
  x: z.number(),
  y: z.number(),
  z: z.number(),
  amplitude: z.number(),
  timestamp: z.number(),
});
export type PointCloudPoint = z.infer<typeof pointCloudPointSchema>;

// Gesture event
export const gestureEventSchema = z.object({
  timestamp: z.number(),
  gestureType: z.enum(["0", "1", "unknown"]),
  centroidShift: z.number(),
  confidence: z.number(),
});
export type GestureEvent = z.infer<typeof gestureEventSchema>;

// Heatmap data (Time vs Angle)
//
// HONESTY NOTE: the "angles" field name is kept for wire-compatibility only.
// On this single-antenna-per-node hardware these are temporal MUSIC
// signature bins, not physical spatial angles. See server/lib/signal-
// processing.ts's HONESTY NOTE and aoa-spectrum.tsx for the canonical
// explanation.
export const heatmapDataSchema = z.object({
  times: z.array(z.number()),
  angles: z.array(z.number()),
  intensities: z.array(z.array(z.number())), // 2D array [time][angle]
});
export type HeatmapData = z.infer<typeof heatmapDataSchema>;

// Vitals (Heart Rate & Respiration)
export const vitalSignsSchema = z.object({
  heartRateBpm: z.number(),
  respirationRateRpm: z.number(),
  vitalsReliable: z.boolean(),
});
export type VitalSigns = z.infer<typeof vitalSignsSchema>;

// Motion status — per-frame output of the variance MotionGate, broadcast
// every frame and shown as the "Motion / No Motion" badge in the top bar.
export const motionStatusSchema = z.object({
  motionDetected: z.boolean(), // variance > threshold this frame
  variance: z.number(),        // amplitude variance over the 30-sample window
  threshold: z.number(),       // active gate (auto-calibrated 3σ or manual)
});
export type MotionStatus = z.infer<typeof motionStatusSchema>;

// Doppler spectrogram frame
export const dopplerFrameSchema = z.object({
  times: z.array(z.number()),
  frequencies: z.array(z.number()),
  intensities: z.array(z.array(z.number())), // 2D [time][freq]
});
export type DopplerFrame = z.infer<typeof dopplerFrameSchema>;

// Recording status
export const recordingStatusSchema = z.object({
  isRecording: z.boolean(),
  sampleCount: z.number(),
  durationMs: z.number(),
  lastFile: z.string().optional(),
  lastSyncAtMs: z.number().optional(),
});
export type RecordingStatus = z.infer<typeof recordingStatusSchema>;

// Processing configuration
export const processingConfigSchema = z.object({
  isarEnabled: z.boolean().default(true),
  arrayLength: z.number().min(2).max(128).default(16),
  aoaRangeMin: z.number().min(-90).max(90).default(-60),
  aoaRangeMax: z.number().min(-90).max(90).default(60),
  clutterRemovalEnabled: z.boolean().default(true),
  clutterWindowSize: z.number().min(10).max(200).default(50),
  motionGateEnabled: z.boolean().default(false),
  // Manual override for the MotionGate (moving/still); when the gate is
  // disabled the auto-calibrated 3σ floor is used instead.
  motionThreshold: z.number().min(0).max(1).default(0.05),
  // Presence gate for two-node fusion: max(motion1, motion2) must clear this
  // for a target to exist at all (see node-fusion.ts DEFAULT_MOTION_THRESHOLD).
  fusedTargetMotionThreshold: z.number().min(0).max(1).default(0.6),
});
export type ProcessingConfig = z.infer<typeof processingConfigSchema>;

// Data source configuration
export const dataSourceSchema = z.enum(["esp32"]);
export type DataSource = z.infer<typeof dataSourceSchema>;

// Hardware ingestion sample (for REST API)
export const hardwareIngestSchema = z.object({
  samples: z.array(csiSampleSchema),
});
export type HardwareIngest = z.infer<typeof hardwareIngestSchema>;

// Single sample ingestion
export const singleSampleIngestSchema = csiSampleSchema;
export type SingleSampleIngest = z.infer<typeof singleSampleIngestSchema>;

// System status
export const systemStatusSchema = z.object({
  connected: z.boolean(),
  dataSource: dataSourceSchema,
  samplesReceived: z.number(),
  framesProcessed: z.number(),
  lastUpdate: z.number(),
  isProcessing: z.boolean(),
  sessionName: z.string().optional(),
  authority: z.boolean().optional(),
  synthetic_enabled: z.boolean().optional(),
  source: z.enum(["live", "replay", "synthetic"]).optional(),
});
export type SystemStatus = z.infer<typeof systemStatusSchema>;

// Tracked target
export const trackedTargetSchema = z.object({
  id: z.number(),
  x: z.number(),
  y: z.number(),
  z: z.number(),
  vx: z.number(),
  vy: z.number(),
  vz: z.number(),
  intensity: z.number(), // mapped to opacity
  confidence: z.number(), // based on cluster density/size
  isMoving: z.boolean().optional(),
  angle: z.number().optional()
});
export type TrackedTarget = z.infer<typeof trackedTargetSchema>;

// Target identity classification (human vs mechanical)
export const targetIdentitySchema = z.object({
  label: z.enum(["human", "mechanical", "unknown"]),
  humanProb: z.number(),
  mechanicalProb: z.number(),
  periodicity: z.number().optional(),
  highFreqRatio: z.number().optional(),
  // Advisory-only, motion-energy heuristic (AI sidecar). NOT derived from pose
  // or body shape. "rapid_change" flags an abrupt CSI motion-energy jump —
  // this is deliberately not labeled as a fall signal: the same signature
  // equally fits sitting down, leaving the sensing field, or a moved
  // reflector (door/curtain), and this hardware cannot discriminate those.
  activityState: z.enum(["stationary", "walking", "rapid_change", "unknown"]).optional(),
});
export type TargetIdentity = z.infer<typeof targetIdentitySchema>;

// Labelled dataset recording progress (server/lib/dataset-recorder.ts),
// broadcast as "datasetStatus" on start/stop.
export const datasetStatusSchema = z.object({
  recording: z.boolean(),
  roomId: z.string().optional(),
  label: z.string().optional(),
  frames: z.number(),
  skipped: z.number(),
  perNode: z.record(z.string(), z.number()),
  files: z.array(z.string()),
  startedAtMs: z.number().optional(),
});
export type DatasetStatus = z.infer<typeof datasetStatusSchema>;

// AI sidecar output, relayed ONLY as "advisoryIdentity" (F1: never written to
// the authoritative targetIdentity channel, never gates presence). Validated
// at the WS boundary before relay. presenceProb is null when no calibrated
// presence model is loaded; advisoryActivity/advisoryCount come from per-room
// models trained on labelled recordings (scripts/train/) and are absent when
// no model exists for this room.
export const advisoryActivitySchema = z.enum(["empty", "still", "walking", "active", "unknown"]);
export type AdvisoryActivity = z.infer<typeof advisoryActivitySchema>;
export const advisoryIdentitySchema = targetIdentitySchema.extend({
  advisoryLabel: z.enum(["human", "mechanical", "unknown"]).optional(),
  presenceProb: z.number().min(0).max(1).nullable().optional(),
  presenceCalibrated: z.boolean().optional(),
  advisoryActivity: advisoryActivitySchema.optional(),
  advisoryActivityConfidence: z.number().min(0).max(1).optional(),
  advisoryCount: z.number().int().min(0).max(8).nullable().optional(),
  advisoryCountConfidence: z.number().min(0).max(1).optional(),
  countLowConfidence: z.boolean().optional(),
  // advisoryCount === 2 with this set means "two or more" (the count model's top class).
  countIsLowerBound: z.boolean().optional(),
  countModelId: z.string().max(80).optional(),
  modelId: z.string().max(80).optional(),
  roomId: z.string().max(80).optional(),
  nodesFused: z.array(z.number().int()).max(8).optional(),
});
export type AdvisoryIdentity = z.infer<typeof advisoryIdentitySchema>;

// AI sidecar vitals, relayed ONLY as "advisoryVitalSigns". Rates are null
// when the estimate is unreliable — never a fabricated fallback value.
export const advisoryVitalSignsSchema = z.object({
  heartRateBpm: z.number().nullable(),
  respirationRateRpm: z.number().nullable(),
  vitalsReliable: z.boolean(),
});
export type AdvisoryVitalSigns = z.infer<typeof advisoryVitalSignsSchema>;

// Radial target — CANONICAL COORDINATE CONVENTIONS (see shared/bearing.ts).
// World frame: +x = east, +z = north, y = up. Origin at the array center.
//   theta — COMPASS bearing: atan2(x, z); 0 = north (+z), +π/2 = east (+x),
//           clockwise-positive from above. Encode x = r·sin(θ), z = r·cos(θ).
//   angle — direction of TRAVEL, math convention: atan2(vz, vx); 0 = east,
//           +π/2 = north. Decode to a world vector as (cos → x, sin → z).
// Single-node caveat: theta derives from one node's MUSIC AoA and is only a
// true compass bearing if that node's boresight faces north (antenna-relative;
// surfaced to users via the SINGLE-NODE BEARING caveat in target-presentation).
export const radialTargetSchema = z.object({
  x: z.number(),        // world east (m); = r·sin(theta)
  z: z.number(),        // world north (m); = r·cos(theta)
  r: z.number(),        // Radial distance from array center (meters)
  theta: z.number(),    // Compass bearing (radians, 0 = north, +π/2 = east)
  vx: z.number(),       // Velocity x-component (m/s)
  vz: z.number(),       // Velocity z-component (m/s)
  isMoving: z.boolean(),
  angle: z.number(),    // Direction of travel (radians, math convention: 0 = east)
  speed: z.number(),    // Velocity magnitude
  confidence: z.number(),
  // Classification & ranging
  label: z.enum(["human", "mechanical", "unknown"]).default("unknown"),
  humanProb: z.number().default(0.5),
  distanceCm: z.number().default(200),   // Distance in centimeters
  wallDistance: z.number().default(5.0), // First wall reflection distance (m)
  // Two-node fusion: 0 → at node 1, 0.5 → midpoint, 1 → at node 2 (Phantom Balance Fusion).
  // Present only in fused_two_node mode; x/z are placed on the N1–N2 line from it.
  // This is the DISPLAY value (contrast+bias-shaped) — see balanceLinear below
  // for the canonical undecorated ratio (PS-AUDIT-003/011, ADR-054).
  balance: z.number().optional(),
  // Canonical/authoritative balance = r2/(r1+r2), independent of the display
  // contrast exponent and nearest-node bias. Cross-check value only — never
  // drives x/z placement, which remains driven by `balance` above.
  balanceLinear: z.number().optional(),
  // Item 1 (PhantomScan_Research_Gap_Analysis.md): whether the deterministic
  // ACF/DFT MicroDopplerClassifier corroborated, contradicted, or was
  // inconclusive/not-evaluated for this tick's presence decision. The
  // classifier only ever SUPPRESSES a presence claim the energy/motion gate
  // already made — see evaluateClassifierCorroboration in node-fusion.ts.
  classifierCorroboration: z
    .enum(["confirmed", "contradicted", "inconclusive", "not_evaluated"])
    .optional(),
  // Phase-1 bug audit: whether x/z is grounded in real two-node/N-node
  // cross-node fusion geometry, or derived from the single-antenna MUSIC AoA
  // angle that tracking.ts documents as carrying no physically valid spatial
  // aperture on this hardware. Lets a consumer of `radialTarget` alone (e.g.
  // recording-export.ts) tell the two apart without cross-referencing the
  // separately-broadcast `targetState.node_mode`. `fused_room_centroid` is the
  // 3-4 node perturbation-weighted 2-D centroid (fuseNodeTargets) — not
  // ranging, and confined to the anchors' convex hull.
  positionBasis: z
    .enum(["fused_1d", "fused_room_centroid", "synthetic_single_node_aoa"])
    .default("fused_1d"),
});
export type RadialTarget = z.infer<typeof radialTargetSchema>;

// Target presence/movement state machine (built in server/lib/target-state.ts):
//   none     — empty room / nothing detectable
//   stale    — last detection aged past 1.5 s; position no longer trusted
//   idle     — target present (fused) but not moving
//   moving   — target present (fused) and in motion
//   degraded — only one node live; presence evidence but untrustworthy position
export const targetStateSchema = z.object({
  state: z.enum(["none", "stale", "idle", "moving", "degraded"]),
  source_mode: z.enum(["live", "replay", "synthetic"]),
  // single_node: 1 node live. fused_two_node: exactly 2 nodes live — 1-D
  // on-axis placement (fuseTwoNodeTarget). fused_room: 3-4 nodes live —
  // perturbation-weighted centroid across all active anchors (fuseNodeTargets).
  node_mode: z.enum(["single_node", "fused_two_node", "fused_room"]),
  target_visible: z.boolean(),
  position_confident: z.boolean(),
  position: z
    .object({
      x: z.number(),
      y: z.number(),
      z: z.number(),
    })
    .optional(),
  bearing_deg: z.number().optional(),
  range_m: z.number().optional(),
  motion_score: z.number(),
  confidence: z.number(),
  last_update_ms: z.number(),
  data_age_ms: z.number(),
  stale: z.boolean(),
  reason: z.string().optional(),
});
export type TargetState = z.infer<typeof targetStateSchema>;

// ── Multi-node ESP32-S3 geometry (DEFAULT anchors) ────────────────
// Default node anchor positions in radar/world meters (origin at room center,
// +Z = north). Nodes 1-4 sit one per corner of a DEFAULT_ROOM_WIDTH_M x
// DEFAULT_ROOM_DEPTH_M rectangle, in perimeter order 1->2->3->4->1 (this order
// matters — it's what lets the client draw a clean room-boundary polygon
// instead of a crossed shape). With only 2 nodes live (fused_two_node), the
// target slides along that pair's line; with 3-4 live (fused_room) it's a
// weighted centroid across all active anchors.
//
// These are only the FALLBACK layout. The live server resolves the real
// geometry from config/room.json or PHANTOM_ROOM_CONFIG
// (server/lib/room-geometry.ts) and broadcasts anchor positions in `nodes`
// and room dimensions in `signalField` — clients must render from those.
export const DEFAULT_ROOM_WIDTH_M = 4;
export const DEFAULT_ROOM_DEPTH_M = 6;
export const DEFAULT_NODE_ANCHORS: Readonly<Record<number, { x: number; z: number }>> = Object.freeze({
  1: { x: -DEFAULT_ROOM_WIDTH_M / 2, z: -DEFAULT_ROOM_DEPTH_M / 2 },
  2: { x: DEFAULT_ROOM_WIDTH_M / 2, z: -DEFAULT_ROOM_DEPTH_M / 2 },
  3: { x: DEFAULT_ROOM_WIDTH_M / 2, z: DEFAULT_ROOM_DEPTH_M / 2 },
  4: { x: -DEFAULT_ROOM_WIDTH_M / 2, z: DEFAULT_ROOM_DEPTH_M / 2 },
});

// A sensor node marker broadcast to the UI: anchor position + live activity.
export const sensorNodeSchema = z.object({
  node_id: z.number(),
  x: z.number(),
  z: z.number(),
  motion: z.number(),            // 0..1 saturated, DISPLAY ONLY (glow intensity)
  active: z.boolean(),           // seen within the live freshness window
  rssi: z.number(),              // last RSSI seen for this node (dBm)
  source: z.enum(["live", "synthetic"]),
  // Straight-line distance from the fused target to THIS node (meters). Only
  // set while a live fused target exists. Under fused_two_node this is an
  // on-axis distance (honest limit: assumes the person is on the N1-N2 line,
  // an off-axis person reads a wrong on-line distance); under fused_room it
  // is a true straight-line distance to this node's anchor.
  distanceM: z.number().optional(),
  // Is the fused target moving toward or away from THIS node (sign of
  // d(balance)/dt with a deadband)? "stable" when idle or below deadband.
  trend: z.enum(["approaching", "receding", "stable"]).default("stable"),
});
export type SensorNode = z.infer<typeof sensorNodeSchema>;

// Firmware DSP feature state (Phantom Scan feature-state packet, 0xC5110006, 1 Hz per node).
// Board-computed metrics shown ALONGSIDE the host-DSP estimates for
// cross-checking — never fed into the host-side fusion/target math.
export const nodeFeatureStateSchema = z.object({
  node_id: z.number(),
  motion: z.number(),            // firmware motion score (0..1-ish, verbatim)
  presence: z.number(),          // firmware presence score (verbatim)
  resp_bpm: z.number(),          // respiration estimate (breaths/min)
  resp_conf: z.number(),         // respiration confidence 0..1
  hr_bpm: z.number(),            // heartbeat estimate (beats/min)
  hr_conf: z.number(),           // heartbeat confidence 0..1
  age_ms: z.number(),            // ms since the packet was received (server clock)
  rssi: z.number().optional(),   // board-reported RSSI dBm (0xC5110002 only)
});
export type NodeFeatureState = z.infer<typeof nodeFeatureStateSchema>;

// nodeFeatures WS payload: latest fresh feature state per node.
export const nodeFeatureStatesSchema = z.array(nodeFeatureStateSchema);

// Per-node CSI signal summary: the max-power subcarrier's amplitude and
// phase from the most recent frame (same representative sample already used
// as the amplitude-window fallback in recordNodeAmplitude) — a live
// diagnostic readout, not a spatial measurement.
export const nodeSignalStateSchema = z.object({
  node_id: z.number(),
  amplitude: z.number(),
  phase_deg: z.number(),
  age_ms: z.number(), // ms since the sample was received (server clock)
});
export type NodeSignalState = z.infer<typeof nodeSignalStateSchema>;

// nodeSignal WS payload: latest signal summary per node.
export const nodeSignalStatesSchema = z.array(nodeSignalStateSchema);

export const targetDebugSchema = z.object({
  hardware_queue_length: z.number(),
  last_sample_rx_ms: z.number().nullable(),
  last_processed_sample_ms: z.number().nullable(),
  last_truthful_target_update_ms: z.number().nullable(),
  target_reason: z.string().optional(),
  radial_target_present: z.boolean(),
  tracked_target_present: z.boolean(),
  hold_state: z.enum(["startup", "live", "stale_hold", "cleared"]),
  // Live-trial monitoring (Stage 0 preflight gate): per-node ingest rate and
  // current saturated motion, so hardware runs are checkable from diagnostics.
  node_fps: z.record(z.string(), z.number()).optional(),
  node_motion: z.record(z.string(), z.number()).optional(),
  // fused_room adaptive-baseline presence (server/lib/node-baseline.ts):
  // debounced room tier and each node's rise above its own empty-room level.
  room_tier: z.enum(["absent", "present_still", "present_moving", "active"]).optional(),
  node_rise: z.record(z.string(), z.number()).optional(),
});
export type TargetDebug = z.infer<typeof targetDebugSchema>;

// Spatial signal-intensity grid over the room (fused_room mode only) — an
// inverse-distance-weighted spread of each active node's motion/perturbation
// value across the configured room (roomWidthM x roomDepthM, centred on the
// origin), for the dashboard's floor-glow visualization. NOT a physical RF
// field measurement (same perturbation-proxy honesty as the rest of the
// fusion math) — it's a rendering aid, never fed back into localization.
// `values` is row-major, length gridWidth*gridDepth. Cells are rectangular:
// `cellSizeM` is the x (width) cell size, `cellDepthM` the z (depth) size.
export const signalFieldSchema = z.object({
  gridWidth: z.number(),
  gridDepth: z.number(),
  cellSizeM: z.number(),
  cellDepthM: z.number(),
  roomWidthM: z.number(),
  roomDepthM: z.number(),
  values: z.array(z.number()),
});
export type SignalField = z.infer<typeof signalFieldSchema>;

// 3D Pose Keypoint
export const poseKeypointSchema = z.object({
  name: z.string(),
  x: z.number(),
  y: z.number(),
  z: z.number(),
  confidence: z.number(),
});
export type PoseKeypoint = z.infer<typeof poseKeypointSchema>;

// Pose Frame containing the 17 keypoints
export const poseFrameSchema = z.object({
  timestamp: z.number(),
  keypoints: z.array(poseKeypointSchema),
});
export type PoseFrame = z.infer<typeof poseFrameSchema>;

// WebSocket message types
export const wsMessageTypeSchema = z.enum([
  "datasetStatus",
  "status",
  "csiFrame",
  "isarFrame",
  "pointCloud",
  "heatmap",
  "config",
  "error",
  "motionStatus",
  "dopplerFrame",
  "recordingStatus",
  "markSyncEvent",
  "setGroundTruthPoint",
  "clearGroundTruthPoint",
  "trackedTarget",
  "radialTarget",
  "targetIdentity",
  "reportReady",
  "vitalSigns",
  "poseFrame",
  "targetState",
  "targetDebug",
  "nodes",
  "nodeFeatures",
  "nodeSignal",
  "signalField",
]);
export type WSMessageType = z.infer<typeof wsMessageTypeSchema>;

// Complete frame sent over WebSocket
export const streamFrameSchema = z.object({
  type: wsMessageTypeSchema,
  timestamp: z.number(),
  data: z.union([
    systemStatusSchema,
    channelEstimateSchema,
    isarFrameSchema,
    z.array(pointCloudPointSchema),
    heatmapDataSchema,
    processingConfigSchema,
    vitalSignsSchema,
    z.string(),
    poseFrameSchema,
    targetStateSchema,
    targetDebugSchema,
    z.array(sensorNodeSchema),
    nodeFeatureStatesSchema,
    nodeSignalStatesSchema,
    signalFieldSchema,
  ]),
});
export type StreamFrame = z.infer<typeof streamFrameSchema>;

// Signal trace for visualization
export const signalTraceSchema = z.object({
  timestamps: z.array(z.number()),
  h1Magnitude: z.array(z.number()),
  h2Magnitude: z.array(z.number()),
  nulledMagnitude: z.array(z.number()),
  dynamicMagnitude: z.array(z.number()),
});
export type SignalTrace = z.infer<typeof signalTraceSchema>;

export const authSessionSchema = z.object({
  authenticated: z.boolean(),
  username: z.string().optional(),
  session_type: z.literal("session_cookie"),
  setup_required: z.boolean().optional(),
});
export type AuthSession = z.infer<typeof authSessionSchema>;

export const auditRecordSchema = z.object({
  ts: z.string(),
  event_type: z.string(),
  username: z.string().optional(),
  success: z.boolean(),
  ip: z.string().optional(),
  user_agent: z.string().optional(),
  route: z.string().optional(),
  session_id: z.string().optional(),
  details: z.record(z.unknown()).optional(),
});
export type AuditRecord = z.infer<typeof auditRecordSchema>;

// Default user table (kept for compatibility)
import { sql } from "drizzle-orm";
import { pgTable, text, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";

export const users = pgTable("users", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  username: text("username").notNull().unique(),
  password: text("password").notNull(),
});

export const insertUserSchema = createInsertSchema(users).pick({
  username: true,
  password: true,
});

export type InsertUser = z.infer<typeof insertUserSchema>;
export type User = typeof users.$inferSelect;
