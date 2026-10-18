// ── Room geometry (configurable node anchors) ──────────────────────
//
// Node anchor positions and room size used by every fused-mode computation
// (fuseTwoNodeTarget, fuseNodeTargets, signal-field grid, recording export).
// Previously hardcoded as a 4 m x 6 m rectangle with one node per corner;
// now loaded from a JSON file so the REAL measured layout can be entered:
//
//   PHANTOM_ROOM_CONFIG=<path>   explicit file (missing file = startup error)
//   config/room.json             used automatically when present
//   (neither)                    DEFAULT_* constants from shared/schema.ts
//
// World frame matches shared/bearing.ts: origin at room centre, +x = east,
// +z = north, metres. The room spans x ∈ [-W/2, W/2], z ∈ [-D/2, D/2].

import fs from "fs";
import { z } from "zod";
import {
  CANONICAL_NODE_HARDWARE_IDS,
  DEFAULT_NODE_ANCHORS,
  DEFAULT_ROOM_DEPTH_M,
  DEFAULT_ROOM_WIDTH_M,
} from "@shared/schema";

export interface NodeAnchorPosition {
  x: number;
  z: number;
}

export interface RoomGeometry {
  roomWidthM: number;
  roomDepthM: number;
  /** Keyed by runtime node id (1-4), in perimeter order 1→2→3→4. */
  anchors: Record<number, NodeAnchorPosition>;
  /**
   * The Wi-Fi router/AP every node's CSI link ends at. When set, position comes
   * from the node->router link model instead of an anchor centroid.
   */
  router?: NodeAnchorPosition;
  /** Where this geometry came from ("defaults" or a file path) — logged at startup. */
  source: string;
}

const MAX_DIMENSION_M = 50;
/** Anchors may sit slightly outside the nominal room box (wall-mounted boards). */
const BOUNDS_TOLERANCE_M = 0.5;
/** Twice the triangle area below which 3 anchors count as collinear (m²). */
const COLLINEAR_AREA2_EPS = 0.05;
const DEFAULT_CONFIG_PATH = "config/room.json";

const dimensionSchema = z.number().finite().positive().max(MAX_DIMENSION_M);
const anchorSchema = z.object({ x: z.number().finite(), z: z.number().finite() }).strict();

export const roomGeometryConfigSchema = z
  .object({
    roomWidthM: dimensionSchema,
    roomDepthM: dimensionSchema,
    anchors: z.record(z.string(), anchorSchema),
    router: anchorSchema.optional(),
  })
  .strict();

export const DEFAULT_ROOM_GEOMETRY: RoomGeometry = Object.freeze({
  roomWidthM: DEFAULT_ROOM_WIDTH_M,
  roomDepthM: DEFAULT_ROOM_DEPTH_M,
  anchors: DEFAULT_NODE_ANCHORS,
  source: "defaults",
});

function formatZodError(error: z.ZodError): string {
  return error.issues.map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("; ");
}

function hasNonCollinearTriple(points: NodeAnchorPosition[]): boolean {
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      for (let k = j + 1; k < points.length; k++) {
        const [a, b, c] = [points[i], points[j], points[k]];
        const area2 = Math.abs((b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x));
        if (area2 > COLLINEAR_AREA2_EPS) return true;
      }
    }
  }
  return false;
}

/**
 * Validate a raw (parsed-JSON) room config. Throws an Error naming `source`
 * and the offending field — fail fast at startup rather than localizing
 * against a silently wrong layout.
 */
export function parseRoomGeometry(raw: unknown, source: string): RoomGeometry {
  const parsed = roomGeometryConfigSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`[ROOM] invalid room config (${source}): ${formatZodError(parsed.error)}`);
  }
  const { roomWidthM, roomDepthM } = parsed.data;
  const halfW = roomWidthM / 2 + BOUNDS_TOLERANCE_M;
  const halfD = roomDepthM / 2 + BOUNDS_TOLERANCE_M;

  const anchors: Record<number, NodeAnchorPosition> = {};
  const ids = Object.keys(parsed.data.anchors)
    .map((key) => ({ key, id: Number(key) }))
    .sort((a, b) => a.id - b.id);
  if (ids.length === 0) {
    throw new Error(`[ROOM] invalid room config (${source}): anchors must define at least one node`);
  }
  for (const { key, id } of ids) {
    if (!Number.isInteger(id) || !(id in CANONICAL_NODE_HARDWARE_IDS)) {
      throw new Error(
        `[ROOM] invalid room config (${source}): node id ${key} is not one of ` +
          Object.keys(CANONICAL_NODE_HARDWARE_IDS).join(","),
      );
    }
    const anchor = parsed.data.anchors[key];
    if (Math.abs(anchor.x) > halfW || Math.abs(anchor.z) > halfD) {
      throw new Error(
        `[ROOM] invalid room config (${source}): node ${id} at (${anchor.x}, ${anchor.z}) is outside the room ` +
          `(${roomWidthM} x ${roomDepthM} m centred on the origin)`,
      );
    }
    anchors[id] = { x: anchor.x, z: anchor.z };
  }

  const points = Object.values(anchors);
  if (points.length >= 3 && !hasNonCollinearTriple(points)) {
    throw new Error(
      `[ROOM] invalid room config (${source}): ${points.length} anchors are collinear — ` +
        "2-D room fusion needs nodes spread around the room",
    );
  }
  const router = parsed.data.router;
  if (router && (Math.abs(router.x) > halfW || Math.abs(router.z) > halfD)) {
    throw new Error(
      `[ROOM] invalid room config (${source}): router at (${router.x}, ${router.z}) is outside the room ` +
        `(${roomWidthM} x ${roomDepthM} m centred on the origin)`,
    );
  }
  return { roomWidthM, roomDepthM, anchors, ...(router ? { router: { x: router.x, z: router.z } } : {}), source };
}

/**
 * RuView-style placement check (ruvsense multistatic.rs geometric_diversity):
 * ideal angular gap (2π/N) divided by the largest angular gap between nodes as
 * seen from their centroid. 1 = evenly surrounding; → 0 = all on one side.
 */
export function geometricDiversity(anchors: Record<number, NodeAnchorPosition>): number {
  const points = Object.values(anchors);
  if (points.length < 2) return 0;
  const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
  const cz = points.reduce((s, p) => s + p.z, 0) / points.length;
  const angles = points.map((p) => Math.atan2(p.z - cz, p.x - cx)).sort((a, b) => a - b);
  let maxGap = angles[0] + 2 * Math.PI - angles[angles.length - 1];
  for (let i = 1; i < angles.length; i++) {
    maxGap = Math.max(maxGap, angles[i] - angles[i - 1]);
  }
  return maxGap > 0 ? Math.min(1, (2 * Math.PI) / points.length / maxGap) : 0;
}

type ReadFile = (path: string) => string | undefined;

function readFileIfExists(path: string): string | undefined {
  try {
    return fs.readFileSync(path, "utf-8");
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT") return undefined;
    throw error;
  }
}

/**
 * Resolve the room geometry from env + filesystem. `read` returns undefined
 * for a missing file. An explicitly configured PHANTOM_ROOM_CONFIG that is
 * missing is an error; a missing default config/room.json is not.
 */
export function loadRoomGeometry(
  env: Record<string, string | undefined> = process.env,
  read: ReadFile = readFileIfExists,
): RoomGeometry {
  const explicitPath = env.PHANTOM_ROOM_CONFIG?.trim();
  const path = explicitPath || DEFAULT_CONFIG_PATH;
  const text = read(path);
  if (text === undefined) {
    if (explicitPath) {
      throw new Error(`[ROOM] PHANTOM_ROOM_CONFIG=${explicitPath} not found`);
    }
    return DEFAULT_ROOM_GEOMETRY;
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (error: unknown) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(`[ROOM] ${path} is not valid JSON: ${reason}`);
  }
  return parseRoomGeometry(raw, path);
}

let cachedGeometry: RoomGeometry | null = null;

/** Process-wide geometry, loaded once on first use. */
export function getRoomGeometry(): RoomGeometry {
  if (!cachedGeometry) {
    cachedGeometry = loadRoomGeometry();
  }
  return cachedGeometry;
}

/** Distance between two anchored nodes (default N1–N2, the fused_two_node axis); 0 if either is unanchored. */
export function nodePairSeparationM(geometry: RoomGeometry, a = 1, b = 2): number {
  const p = geometry.anchors[a];
  const q = geometry.anchors[b];
  return p && q ? Math.hypot(p.x - q.x, p.z - q.z) : 0;
}
