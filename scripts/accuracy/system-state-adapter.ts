/**
 * Adapts the system's presence/movement verdict into a common SystemSample
 * stream for scoring, from either a replayed recording CSV (mode A) or a
 * live read-only tap on the dashboard's /ws targetState broadcast (mode B).
 *
 * F1-invariant scoring rule: the scoreable "is_human" verdict is the
 * deterministic TargetState.state, restricted to "idle" | "moving" — the
 * two-node, position-confident states. "degraded" (single-node evidence) is
 * an honest UI label but is NOT a confident human-presence claim, so it
 * scores as a miss, same as "stale"/"none" (build prompt §4.3/§4.4). This
 * never reads the RuView AI-advisory channel (advisoryIdentity/humanProb) —
 * only the F1-owned deterministic field.
 */
import * as fs from "fs";
import WebSocket from "ws";
import { parseRecordingCsv } from "../join-groundtruth";
import type { TargetState } from "../../shared/schema";

export type SystemStateKind = TargetState["state"];

export interface SystemSample {
  /** Milliseconds since this stream's own clock origin (recording session or capture start). */
  sessionTsMs: number;
  state: SystemStateKind;
  isHumanVerdict: boolean;
  targetVisible: boolean;
  nodeMode: string;
  node1Fps: number;
  node2Fps: number;
}

export interface SessionMeta {
  raw: Record<string, unknown>;
  sessionName?: string;
  motionThreshold: number | null;
  scalarMotionThreshold: number | null;
  fusedMotionThreshold: number | null;
}

export interface SystemStateLog {
  samples: SystemSample[];
  /** session_ts_ms of the first row with sync_marker=1, or null (see A4). */
  syncMarkerSessionTsMs: number | null;
  sessionMeta: SessionMeta | null;
}

/** F1-invariant scoring rule — see module doc. Exported so tests can assert
 * degraded/stale never count as a positive without duplicating the literal. */
export function isHumanVerdict(state: SystemStateKind): boolean {
  return state === "idle" || state === "moving";
}

export function parseSystemStateReplayCsv(csvText: string): SystemStateLog {
  const { metaLines, rows } = parseRecordingCsv(csvText);

  let sessionMeta: SessionMeta | null = null;
  const metaLine = metaLines.find((line) => line.startsWith("# phantom_session_meta"));
  if (metaLine) {
    const jsonStart = metaLine.indexOf("{");
    if (jsonStart >= 0) {
      try {
        const raw = JSON.parse(metaLine.slice(jsonStart)) as Record<string, unknown>;
        sessionMeta = {
          raw,
          sessionName: typeof raw.session_name === "string" ? raw.session_name : undefined,
          motionThreshold: typeof raw.motion_threshold === "number" ? raw.motion_threshold : null,
          scalarMotionThreshold:
            typeof raw.scalar_motion_threshold === "number" ? raw.scalar_motion_threshold : null,
          fusedMotionThreshold:
            typeof raw.fused_motion_threshold === "number" ? raw.fused_motion_threshold : null,
        };
      } catch {
        sessionMeta = null;
      }
    }
  }

  const samples: SystemSample[] = [];
  let syncMarkerSessionTsMs: number | null = null;

  for (const row of rows) {
    const sessionTsMs = Number.parseFloat(row.session_ts_ms ?? "");
    if (!Number.isFinite(sessionTsMs)) continue;

    const state = (row.target_state || "none") as SystemStateKind;
    samples.push({
      sessionTsMs,
      state,
      isHumanVerdict: isHumanVerdict(state),
      targetVisible: row.target_visible === "1",
      nodeMode: row.node_mode || "single_node",
      node1Fps: Number.parseFloat(row.node1_fps ?? "") || 0,
      node2Fps: Number.parseFloat(row.node2_fps ?? "") || 0,
    });

    if (row.sync_marker === "1" && syncMarkerSessionTsMs === null) {
      syncMarkerSessionTsMs = sessionTsMs;
    }
  }

  return { samples, syncMarkerSessionTsMs, sessionMeta };
}

export function loadSystemStateReplayCsv(path: string): SystemStateLog {
  return parseSystemStateReplayCsv(fs.readFileSync(path, "utf-8"));
}

export interface LiveCaptureOptions {
  wsUrl: string;
  durationMs: number;
  onSample?: (sample: SystemSample & { wallClockMs: number }) => void;
}

export interface LiveCaptureResult {
  samples: Array<SystemSample & { wallClockMs: number }>;
  /** Host Date.now() when the socket connected — the live-mode sync anchor:
   * both this tap and groundtruth-logger.ts stamp events with the SAME host
   * clock, so no cross-clock offset exists by construction (unlike replay
   * mode, where the recording uses a device-relative session clock against a
   * separately-clocked video/keypress log). See time-aligner.ts doc. */
  captureStartWallClockMs: number;
  captureEndWallClockMs: number;
}

/**
 * Read-only tap on the dashboard's /ws targetState broadcast (F2: never a
 * control path — this only listens). Node fps is not carried on the
 * targetState message, so live-mode pkt/s preflight (P0) is not
 * automatically gated here; see report-generator.ts evaluatePreconditions.
 */
export function captureLiveSystemState(options: LiveCaptureOptions): Promise<LiveCaptureResult> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(options.wsUrl);
    const samples: Array<SystemSample & { wallClockMs: number }> = [];
    const captureStartWallClockMs = Date.now();
    let settled = false;

    const finish = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        ws.close();
      } catch {
        // socket already closing/closed — nothing to do.
      }
      resolve({ samples, captureStartWallClockMs, captureEndWallClockMs: Date.now() });
    };

    const timer = setTimeout(finish, options.durationMs);

    ws.on("message", (raw: Buffer | string) => {
      let msg: { type?: string; data?: Record<string, unknown> };
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        return;
      }
      if (msg.type !== "targetState" || !msg.data) return;

      const state = (msg.data.state as SystemStateKind) || "none";
      const wallClockMs = Date.now();
      const sample: SystemSample & { wallClockMs: number } = {
        sessionTsMs: wallClockMs,
        state,
        isHumanVerdict: isHumanVerdict(state),
        targetVisible: msg.data.target_visible === true,
        nodeMode: (msg.data.node_mode as string) || "single_node",
        node1Fps: 0,
        node2Fps: 0,
        wallClockMs,
      };
      samples.push(sample);
      options.onSample?.(sample);
    });

    ws.on("error", (err: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });
  });
}
