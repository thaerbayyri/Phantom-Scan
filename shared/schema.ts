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
export const dataSourceSchema = z.enum(["demo", "file", "usrp", "esp32", "hardware"]);
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
});
export type RadialTarget = z.infer<typeof radialTargetSchema>;

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
