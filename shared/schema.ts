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

// Processing configuration
export const processingConfigSchema = z.object({
  nullingEnabled: z.boolean().default(true),
  nullingThreshold: z.number().min(0).max(100).default(10),
  isarEnabled: z.boolean().default(true),
  arrayLength: z.number().min(2).max(128).default(16),
  aoaRangeMin: z.number().min(-90).max(90).default(-60),
  aoaRangeMax: z.number().min(-90).max(90).default(60),
  gestureEnabled: z.boolean().default(true),
  centroidThreshold: z.number().min(0).max(50).default(5),
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
});
export type SystemStatus = z.infer<typeof systemStatusSchema>;

// WebSocket message types
export const wsMessageTypeSchema = z.enum([
  "status",
  "csiFrame",
  "isarFrame",
  "pointCloud",
  "gesture",
  "heatmap",
  "config",
  "error",
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
    gestureEventSchema,
    heatmapDataSchema,
    processingConfigSchema,
    z.string(),
  ]),
});
export type StreamFrame = z.infer<typeof streamFrameSchema>;

// Signal trace for visualization
export const signalTraceSchema = z.object({
  timestamps: z.array(z.number()),
  h1Magnitude: z.array(z.number()),
  h2Magnitude: z.array(z.number()),
  nulledMagnitude: z.array(z.number()),
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
