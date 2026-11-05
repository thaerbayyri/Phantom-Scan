/**
 * Recording replay for Demo mode.
 *
 * Streams a short lead-in from a labelled "empty" dataset recording (so the
 * per-node baselines can calibrate) followed by a body clip, and hands the
 * frames to the NORMAL ingest path with timestamps rebased to "now" (live
 * freshness gates drop anything older than the stale window). Nothing here
 * influences the detector: whatever the real pipeline concludes from the
 * recording - including "nobody there" - is what the dashboard shows.
 *
 * Dataset format (docs/DATASET_PROTOCOL.md): JSONL, one header line then
 * {"type":"frame","t":<epoch ms>,"n":<node 1-4>,"rssi":<dBm>,"a":[<amplitudes>]}.
 */
import { createReadStream, readdirSync } from "node:fs";
import { basename, join } from "node:path";
import { createInterface } from "node:readline";
import type { CSISample } from "@shared/schema";

export const DEFAULT_CALIBRATION_S = 30;
export const DEFAULT_BODY_S = 120;
export const DEMO_CALIBRATION_LABEL = "empty";
export const DEMO_BODY_LABEL = "still";

const MIN_NODE_ID = 1;
const MAX_NODE_ID = 4;
const MISSING_RSSI_DBM = -100;

export class DemoClipError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DemoClipError";
  }
}

export interface ReplayFrame {
  /** Milliseconds from the start of the clip. */
  readonly relMs: number;
  readonly nodeId: number;
  readonly rssi: number;
  readonly amplitudes: number[];
}

export interface ReplayClip {
  readonly frames: ReplayFrame[];
  /** Length of the baseline-calibration lead-in; looping returns here, not to 0. */
  readonly calibrationMs: number;
  readonly durationMs: number;
  readonly label: string;
}

interface ParsedFrame {
  readonly t: number;
  readonly nodeId: number;
  readonly rssi: number;
  readonly amplitudes: number[];
}

function parseFrameLine(line: string): ParsedFrame | null {
  if (!line) return null;
  let raw: unknown;
  try {
    raw = JSON.parse(line);
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const o = raw as Record<string, unknown>;
  if (o.type !== "frame") return null;
  const { t, n, rssi, a } = o;
  if (typeof t !== "number" || !Number.isFinite(t)) return null;
  if (typeof n !== "number" || !Number.isInteger(n) || n < MIN_NODE_ID || n > MAX_NODE_ID) return null;
  if (!Array.isArray(a) || a.length === 0 || !a.every((v) => typeof v === "number" && Number.isFinite(v))) {
    return null;
  }
  return {
    t,
    nodeId: n,
    rssi: typeof rssi === "number" && Number.isFinite(rssi) ? rssi : MISSING_RSSI_DBM,
    amplitudes: a as number[],
  };
}

/** Read frames from the start of a recording until `maxSeconds` of recorded time have passed. */
export async function readClipHead(file: string, maxSeconds: number): Promise<ReplayFrame[]> {
  const maxMs = maxSeconds * 1000;
  const frames: ReplayFrame[] = [];
  const stream = createReadStream(file, { encoding: "utf8" });
  const lines = createInterface({ input: stream, crlfDelay: Infinity });
  let t0: number | null = null;
  try {
    for await (const line of lines) {
      const parsed = parseFrameLine(line);
      if (!parsed) continue;
      t0 ??= parsed.t;
      const relMs = parsed.t - t0;
      if (relMs > maxMs) break;
      frames.push({ relMs, nodeId: parsed.nodeId, rssi: parsed.rssi, amplitudes: parsed.amplitudes });
    }
  } finally {
    lines.close();
    stream.destroy();
  }
  return frames.sort((a, b) => a.relMs - b.relMs);
}

/** First recording in `dir` carrying `__<label>__` in its name (continuation parts excluded). */
export function findDatasetFile(dir: string, label: string): string | null {
  let names: string[];
  try {
    names = readdirSync(dir);
  } catch {
    return null;
  }
  const match = names
    .filter((name) => name.includes(`__${label}__`) && name.endsWith(".jsonl") && !/\.part\d+\.jsonl$/.test(name))
    .sort()[0];
  return match ? join(dir, match) : null;
}

export interface LoadClipOptions {
  readonly calibrationS?: number;
  readonly bodyS?: number;
}

function describeClip(bodyFile: string): string {
  const [room = "dataset", , bodyLabel = "recording"] = basename(bodyFile).split("__");
  return `${room} ${bodyLabel} recording`;
}

/** Calibration lead-in (empty room) followed by the body clip, on one timeline. */
export async function loadReplayClip(dir: string, options: LoadClipOptions = {}): Promise<ReplayClip> {
  const calibrationS = options.calibrationS ?? DEFAULT_CALIBRATION_S;
  const bodyS = options.bodyS ?? DEFAULT_BODY_S;

  const calibrationFile = findDatasetFile(dir, DEMO_CALIBRATION_LABEL);
  if (!calibrationFile) {
    throw new DemoClipError(
      `Demo replay needs a "${DEMO_CALIBRATION_LABEL}" recording in ${dir} (set PHANTOM_DEMO_DATASET_DIR)`,
    );
  }
  const bodyFile = findDatasetFile(dir, DEMO_BODY_LABEL);
  if (!bodyFile) {
    throw new DemoClipError(
      `Demo replay needs a "${DEMO_BODY_LABEL}" recording in ${dir} (set PHANTOM_DEMO_DATASET_DIR)`,
    );
  }

  const [calibration, body] = await Promise.all([
    readClipHead(calibrationFile, calibrationS),
    readClipHead(bodyFile, bodyS),
  ]);
  if (calibration.length === 0 || body.length === 0) {
    throw new DemoClipError(`Demo replay recordings in ${dir} contain no usable CSI frames`);
  }

  const calibrationMs = calibrationS * 1000;
  const frames = [...calibration, ...body.map((frame) => ({ ...frame, relMs: frame.relMs + calibrationMs }))];
  return {
    frames,
    calibrationMs,
    durationMs: frames[frames.length - 1].relMs,
    label: describeClip(bodyFile),
  };
}

/**
 * Turn a recorded frame into an ingest sample stamped "now". Recordings are
 * amplitude-only (no I/Q), so the scalar h1/h2 - used only by the single-node
 * AoA path, never by fused_room - carry the dominant amplitude with zero phase.
 */
export function sampleFromFrame(frame: ReplayFrame, nowMs: number): CSISample {
  const peak = frame.amplitudes.reduce((max, v) => (v > max ? v : max), 0);
  return {
    timestamp: nowMs,
    nodeId: frame.nodeId,
    rssi: frame.rssi,
    amplitudes: [...frame.amplitudes],
    h1: { re: peak, im: 0 },
    h2: { re: peak, im: 0 },
  };
}

/**
 * Walks a clip in real time. `advance(elapsedMs)` takes the absolute time since
 * the demo started and returns the frames that became due since the last call;
 * once the clip ends it wraps to `loopFromMs` (the end of calibration), so the
 * baselines are not re-taught on every lap.
 */
export class ReplayCursor {
  private index = 0;
  private lapShiftMs = 0;
  private readonly loopFromMs: number;

  constructor(
    private readonly frames: readonly ReplayFrame[],
    loopFromMs: number,
    private readonly durationMs: number,
  ) {
    // A degenerate loop window would wrap forever without advancing time.
    this.loopFromMs = durationMs > loopFromMs ? loopFromMs : 0;
  }

  advance(elapsedMs: number): ReplayFrame[] {
    const due: ReplayFrame[] = [];
    for (;;) {
      const local = elapsedMs - this.lapShiftMs;
      while (this.index < this.frames.length && this.frames[this.index].relMs <= local) {
        due.push(this.frames[this.index++]);
      }
      if (local < this.durationMs) break;
      this.lapShiftMs += this.durationMs - this.loopFromMs;
      this.index = this.firstIndexAtOrAfter(this.loopFromMs);
    }
    return due;
  }

  /** Position within the current lap, for the progress readout. */
  positionMs(elapsedMs: number): number {
    return elapsedMs - this.lapShiftMs;
  }

  private firstIndexAtOrAfter(relMs: number): number {
    const idx = this.frames.findIndex((frame) => frame.relMs >= relMs);
    return idx === -1 ? this.frames.length : idx;
  }
}
