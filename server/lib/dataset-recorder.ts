// ── Labelled CSI dataset recorder (training data capture) ──────────
//
// The existing session CSV (websocket.ts recordingBuffer) is capped at 5,000
// rows and strips the per-subcarrier amplitudes, so it cannot train anything.
// This recorder writes the REAL per-packet amplitude vector of every node,
// with an operator-supplied label, as rotating JSONL:
//
//   data/datasets/<roomId>/<roomId>__<subjectId>__<label>__<UTC stamp>.jsonl
//   (rotation parts: ...__<stamp>.part2.jsonl, .part3.jsonl, ...)
//
//   line 1   {"type":"header","schema":2,"roomId","subjectId","label","count",
//             "startedAtMs" (RECORDING start; same in every part, it names the files),
//             "partStartedAtMs" (this file's start),"part","geometry","geometryHash",
//             "notes","firmwareFilterMac","capture":{channel,bandwidthMHz,bssid,
//             firmwareVersion,firmwareHash,source},"annotation":{nodeMoved,roomNotEmpty,text},
//             "recorder":"dashboard"}
//   then     {"type":"frame","t":<host ms>,"n":<nodeId>,"rssi":<dBm>,"a":[…]}
//
// Schema 2 only ADDS fields to schema 1 (readers that ignore unknown keys keep working). Anything not
// supplied is null ("not recorded"), never guessed. Per-frame PHY (channel/noise/seq) is NOT recorded yet.
//
// Every part file starts with its own header so each file is self-describing.
// Labels are ground truth supplied by the operator for the whole recording —
// train/eval tooling (scripts/train/) must split by recording/session, never
// by frame. Files are local-only (data/datasets/ is gitignored).

import crypto from "crypto";
import fs from "fs";
import path from "path";

export const DATASET_LABELS = [
  "empty",
  "empty_fan",
  "still",
  "walking",
  "active",
  "two_people",
  "three_people",
] as const;
export type DatasetLabel = (typeof DATASET_LABELS)[number];

const LABEL_DEFAULT_COUNT: Record<DatasetLabel, number> = {
  empty: 0,
  empty_fan: 0,
  still: 1,
  walking: 1,
  active: 1,
  two_people: 2,
  three_people: 3,
};

const MAX_PEOPLE = 8;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const DEFAULT_MAX_FRAMES_PER_FILE = 100_000;
const FLUSH_EVERY_LINES = 200;
const SCHEMA_VERSION = 2;

/** Operator statement about conditions the amplitudes alone cannot reveal. null = not stated. */
export interface DatasetAnnotation {
  nodeMoved: boolean | null;
  roomNotEmpty: boolean | null;
  text: string;
}

export interface DatasetCapture {
  channel: number | null;
  bandwidthMHz: number | null;
  bssid: string | null;
  firmwareVersion: string | null;
  firmwareHash: string | null;
  /** "operator_env" when at least one value was supplied through PHANTOM_* variables, else "not_recorded". */
  source: "operator_env" | "not_recorded";
}

export interface DatasetStartRequest {
  roomId: string;
  subjectId: string;
  label: DatasetLabel;
  count: number;
  notes: string;
  annotation: DatasetAnnotation;
}

/** Deterministic JSON (object keys sorted recursively, no whitespace) so hashes agree across languages. */
export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return `{${Object.keys(obj)
      .sort()
      .map((k) => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

/** First 16 hex chars of sha256(canonical {roomWidthM, roomDepthM, anchors}); null when no geometry. */
export function geometryHash(geometry: unknown): string | null {
  if (!geometry || typeof geometry !== "object") return null;
  const g = geometry as Record<string, unknown>;
  const picked: Record<string, unknown> = {};
  for (const key of ["roomWidthM", "roomDepthM", "anchors"]) if (g[key] !== undefined) picked[key] = g[key];
  return crypto.createHash("sha256").update(canonicalJson(picked)).digest("hex").slice(0, 16);
}

/**
 * Capture conditions the operator knows but the amplitude stream does not carry. Invalid values become
 * null (never a guess, never a crash). Variables: PHANTOM_CAPTURE_CHANNEL, PHANTOM_CAPTURE_BANDWIDTH_MHZ,
 * PHANTOM_ROUTER_BSSID, PHANTOM_FIRMWARE_VERSION, PHANTOM_FIRMWARE_HASH.
 */
export function captureFromEnv(env: NodeJS.ProcessEnv): DatasetCapture {
  const channel = Number(env.PHANTOM_CAPTURE_CHANNEL);
  const bandwidth = Number(env.PHANTOM_CAPTURE_BANDWIDTH_MHZ);
  const bssid = (env.PHANTOM_ROUTER_BSSID ?? "").toLowerCase();
  const version = env.PHANTOM_FIRMWARE_VERSION ?? "";
  const hash = (env.PHANTOM_FIRMWARE_HASH ?? "").toLowerCase();
  const capture = {
    channel: Number.isInteger(channel) && channel >= 1 && channel <= 196 ? channel : null,
    bandwidthMHz: [20, 40, 80, 160].includes(bandwidth) ? bandwidth : null,
    bssid: /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/.test(bssid) ? bssid : null,
    firmwareVersion: /^[A-Za-z0-9._+-]{1,64}$/.test(version) ? version : null,
    firmwareHash: /^[0-9a-f]{7,64}$/.test(hash) ? hash : null,
  };
  const any = Object.values(capture).some((v) => v !== null);
  return { ...capture, source: any ? "operator_env" : "not_recorded" };
}

function triState(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

export interface DatasetFrame {
  /** Host receive time, ms. */
  tMs: number;
  nodeId: number;
  rssi: number;
  /** Per-subcarrier amplitudes (the live LLTF data-subcarrier vector). */
  amps: readonly number[];
}

export interface DatasetStatus {
  recording: boolean;
  roomId?: string;
  label?: DatasetLabel;
  frames: number;
  skipped: number;
  perNode: Record<string, number>;
  files: string[];
  startedAtMs?: number;
}

function requireSafeId(value: unknown, field: string, fallback?: string): string {
  const text = value === undefined || value === null || value === "" ? fallback : value;
  if (typeof text !== "string" || !SAFE_ID.test(text)) {
    throw new Error(`invalid ${field}: use 1-64 letters, digits, '_' or '-'`);
  }
  return text;
}

/** Validate an operator "start dataset recording" request (untrusted input). */
export function parseDatasetStart(raw: unknown): DatasetStartRequest {
  if (!raw || typeof raw !== "object") {
    throw new Error("invalid request: expected an object");
  }
  const body = raw as Record<string, unknown>;
  const label = body.label;
  if (typeof label !== "string" || !(DATASET_LABELS as readonly string[]).includes(label)) {
    throw new Error(`invalid label: expected one of ${DATASET_LABELS.join(", ")}`);
  }
  const typedLabel = label as DatasetLabel;
  const count = body.count === undefined ? LABEL_DEFAULT_COUNT[typedLabel] : body.count;
  if (typeof count !== "number" || !Number.isInteger(count) || count < 0 || count > MAX_PEOPLE) {
    throw new Error(`invalid count: expected an integer 0-${MAX_PEOPLE}`);
  }
  const notes = typeof body.notes === "string" ? body.notes.slice(0, 500) : "";
  const rawAnnotation = body.annotation && typeof body.annotation === "object" ? (body.annotation as Record<string, unknown>) : {};
  return {
    roomId: requireSafeId(body.roomId, "roomId"),
    subjectId: requireSafeId(body.subjectId, "subjectId", "unknown"),
    label: typedLabel,
    count,
    notes,
    annotation: {
      nodeMoved: triState(rawAnnotation.nodeMoved),
      roomNotEmpty: triState(rawAnnotation.roomNotEmpty),
      text: typeof rawAnnotation.text === "string" ? rawAnnotation.text.slice(0, 500) : "",
    },
  };
}

export interface DatasetRecorderOptions {
  rootDir?: string;
  maxFramesPerFile?: number;
  now?: () => number;
}

export interface DatasetStartContext {
  geometry?: unknown;
  firmwareFilterMac?: string;
  /** Defaults to captureFromEnv(process.env) when omitted. */
  capture?: DatasetCapture;
}

function compactStamp(ms: number): string {
  return new Date(ms).toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
}

export class DatasetRecorder {
  private readonly rootDir: string;
  private readonly maxFramesPerFile: number;
  private readonly now: () => number;

  private request: DatasetStartRequest | null = null;
  private context: DatasetStartContext = {};
  private baseName = "";
  private startedAtMs = 0;
  private fd: number | null = null;
  private part = 0;
  private framesInPart = 0;
  private frames = 0;
  private skipped = 0;
  private perNode: Record<string, number> = {};
  private files: string[] = [];
  private pending: string[] = [];

  constructor(options: DatasetRecorderOptions = {}) {
    this.rootDir = options.rootDir ?? path.resolve("data", "datasets");
    this.maxFramesPerFile = options.maxFramesPerFile ?? DEFAULT_MAX_FRAMES_PER_FILE;
    this.now = options.now ?? Date.now;
  }

  get isRecording(): boolean {
    return this.request !== null;
  }

  start(request: DatasetStartRequest, context: DatasetStartContext): DatasetStatus {
    if (this.request) {
      throw new Error("already recording a dataset");
    }
    this.request = request;
    this.context = context;
    this.startedAtMs = this.now();
    this.baseName = [request.roomId, request.subjectId, request.label, compactStamp(this.startedAtMs)].join("__");
    this.part = 0;
    this.frames = 0;
    this.skipped = 0;
    this.perNode = {};
    this.files = [];
    try {
      this.openNextPart();
    } catch (error: unknown) {
      this.request = null;
      throw error;
    }
    return this.status();
  }

  record(frame: DatasetFrame): void {
    if (!this.request) return;
    const finite = frame.amps.length > 0 && frame.amps.every((a) => Number.isFinite(a));
    if (!finite || !Number.isFinite(frame.tMs) || !Number.isFinite(frame.rssi)) {
      this.skipped++;
      return;
    }
    if (this.framesInPart >= this.maxFramesPerFile) {
      this.flush();
      this.openNextPart();
    }
    this.pending.push(
      JSON.stringify({ type: "frame", t: frame.tMs, n: frame.nodeId, rssi: frame.rssi, a: frame.amps }),
    );
    this.framesInPart++;
    this.frames++;
    const key = String(frame.nodeId);
    this.perNode[key] = (this.perNode[key] ?? 0) + 1;
    if (this.pending.length >= FLUSH_EVERY_LINES) this.flush();
  }

  stop(): DatasetStatus {
    const finished = this.status();
    // Always release the fd and clear state, even when the final flush fails
    // (disk full / unwritable): otherwise the recorder is stuck "recording".
    try {
      this.flush();
    } finally {
      if (this.fd !== null) {
        try {
          fs.closeSync(this.fd);
        } catch {
          /* fd already invalid — nothing left to release */
        }
        this.fd = null;
      }
      this.request = null;
      this.pending = [];
    }
    return { ...finished, recording: false };
  }

  status(): DatasetStatus {
    return {
      recording: this.request !== null,
      roomId: this.request?.roomId,
      label: this.request?.label,
      frames: this.frames,
      skipped: this.skipped,
      perNode: { ...this.perNode },
      files: [...this.files],
      startedAtMs: this.request ? this.startedAtMs : undefined,
    };
  }

  private openNextPart(): void {
    const request = this.request;
    if (!request) return;
    if (this.fd !== null) {
      fs.closeSync(this.fd);
      this.fd = null;
    }
    const part = this.part + 1; // committed only after the file really opens
    const dir = path.join(this.rootDir, request.roomId);
    fs.mkdirSync(dir, { recursive: true });
    const suffix = part === 1 ? "" : `.part${part}`;
    const file = path.join(dir, `${this.baseName}${suffix}.jsonl`);
    this.fd = fs.openSync(file, "wx");
    this.part = part;
    this.files.push(file);
    this.framesInPart = 0;
    const header = {
      type: "header",
      schema: SCHEMA_VERSION,
      roomId: request.roomId,
      subjectId: request.subjectId,
      label: request.label,
      count: request.count,
      notes: request.notes,
      startedAtMs: this.startedAtMs,
      partStartedAtMs: this.now(),
      part: this.part,
      geometry: this.context.geometry ?? null,
      geometryHash: geometryHash(this.context.geometry),
      firmwareFilterMac: this.context.firmwareFilterMac ?? null,
      capture: this.context.capture ?? captureFromEnv(process.env),
      annotation: request.annotation,
      recorder: "dashboard",
    };
    fs.writeSync(this.fd, `${JSON.stringify(header)}\n`);
  }

  private flush(): void {
    if (this.fd === null || this.pending.length === 0) return;
    const batch = this.pending;
    // Drop the batch whether or not the write succeeds: retrying a failing
    // write would grow the buffer without bound while the error persists.
    this.pending = [];
    fs.writeSync(this.fd, `${batch.join("\n")}\n`);
  }
}
