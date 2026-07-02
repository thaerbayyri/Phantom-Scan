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
});
export type CSISample = z.infer<typeof csiSampleSchema>;

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
export const aoaSpectrumPointSchema = z.object({
  angle: z.number(), // degrees
  power: z.number(), // dB
});
export type AoASpectrumPoint = z.infer<typeof aoaSpectrumPointSchema>;

// ISAR frame containing AoA results
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

// Motion status
export const motionStatusSchema = z.object({
  motionDetected: z.boolean(),
  variance: z.number(),
  threshold: z.number(),
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
  motionThreshold: z.number().min(0).max(1).default(0.05),
});
export type ProcessingConfig = z.infer<typeof processingConfigSchema>;

// Data source configuration
export const dataSourceSchema = z.enum(["demo", "esp32"]);
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
});
export type TargetIdentity = z.infer<typeof targetIdentitySchema>;

// Radial target (ESP-centric coordinate system)
export const radialTargetSchema = z.object({
  x: z.number(),        // Cartesian x = r·cos(θ)
  z: z.number(),        // Cartesian z = r·sin(θ)
  r: z.number(),        // Radial distance from ESP32 (meters)
  theta: z.number(),    // Bearing angle in radians
  vx: z.number(),       // Velocity x-component (m/s)
  vz: z.number(),       // Velocity z-component (m/s)
  isMoving: z.boolean(),
  angle: z.number(),    // Direction of travel (radians)
  speed: z.number(),    // Velocity magnitude
  confidence: z.number(),
  // Classification & ranging
  label: z.enum(["human", "mechanical", "unknown"]).default("unknown"),
  humanProb: z.number().default(0.5),
  distanceCm: z.number().default(200),   // Distance in centimeters
  wallDistance: z.number().default(5.0), // First wall reflection distance (m)
  // Two-node fusion: 0 → at node 1, 0.5 → midpoint, 1 → at node 2 (RuView balance).
  // Present only in fused_two_node mode; x/z are placed on the N1–N2 line from it.
  balance: z.number().optional(),
});
export type RadialTarget = z.infer<typeof radialTargetSchema>;

export const targetStateSchema = z.object({
  state: z.enum(["none", "stale", "idle", "moving", "degraded"]),
  source_mode: z.enum(["live", "replay", "synthetic"]),
  node_mode: z.enum(["single_node", "fused_two_node"]),
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

// ── Two-node ESP32-S3 geometry (RuView-style anchors) ──────────────────
// Fixed node anchor positions in radar/world meters (origin at center, +Z = north).
// 3 m apart on the E–W axis, centered — the target's balance-fused position slides
// along the line between them. Single source of truth for server + client.
export const NODE_ANCHORS: Record<number, { x: number; z: number }> = {
  1: { x: -1.5, z: 0 },
  2: { x: 1.5, z: 0 },
};
export const NODE_SEPARATION_M = 3;

// A sensor node marker broadcast to the UI: anchor position + live activity.
export const sensorNodeSchema = z.object({
  node_id: z.number(),
  x: z.number(),
  z: z.number(),
  motion: z.number(),            // 0..1 saturated, DISPLAY ONLY (glow intensity)
  active: z.boolean(),           // seen within the live freshness window
  rssi: z.number(),              // last RSSI seen for this node (dBm)
  source: z.enum(["live", "synthetic"]),
});
export type SensorNode = z.infer<typeof sensorNodeSchema>;

export const targetDebugSchema = z.object({
  hardware_queue_length: z.number(),
  last_sample_rx_ms: z.number().nullable(),
  last_processed_sample_ms: z.number().nullable(),
  last_truthful_target_update_ms: z.number().nullable(),
  target_reason: z.string().optional(),
  radial_target_present: z.boolean(),
  tracked_target_present: z.boolean(),
  hold_state: z.enum(["startup", "live", "stale_hold", "cleared"]),
});
export type TargetDebug = z.infer<typeof targetDebugSchema>;

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
  "trackedTarget",
  "radialTarget",
  "targetIdentity",
  "reportReady",
  "vitalSigns",
  "poseFrame",
  "targetState",
  "targetDebug",
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
