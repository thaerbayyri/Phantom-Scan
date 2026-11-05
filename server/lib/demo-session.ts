/**
 * Demo mode controller.
 *
 * Two clearly different demos share one lifecycle:
 *  - "synthetic": a scripted walker (demo-walker.ts). Never touches the
 *    detection pipeline; the host broadcasts its frames labelled synthetic.
 *  - "replay": a recorded session (demo-replay.ts) fed through the host's
 *    normal ingest path, so the REAL detector decides what it sees.
 *
 * The session owns timing and state only. Side effects (ingest, broadcast)
 * go through `DemoHost`, and the clock/timers are injectable for tests.
 */
import type { CSISample, DemoStatus } from "@shared/schema";
import { ReplayCursor, loadReplayClip, sampleFromFrame, type ReplayClip } from "./demo-replay";
import { buildWalkerFrame, walkerCycleSeconds, type WalkerFrame } from "./demo-walker";
import type { RoomGeometry } from "./room-geometry";

export type { DemoStatus };
export type DemoMode = NonNullable<DemoStatus["mode"]>;
export type DemoPhase = DemoStatus["phase"];

export interface DemoHost {
  /** Replay path: hand a recorded sample to the normal ingest pipeline. */
  ingestSample(sample: CSISample): void;
  /** Synthetic path: broadcast one simulated scene (labelled synthetic). */
  publishWalkerFrame(frame: WalkerFrame): void;
  onStatus(status: DemoStatus): void;
}

export interface DemoDeps {
  readonly room: RoomGeometry;
  readonly datasetDir: string;
  readonly tickMs?: number;
  readonly now?: () => number;
  readonly setIntervalFn?: (fn: () => void, ms: number) => ReturnType<typeof setInterval>;
  readonly clearIntervalFn?: (handle: ReturnType<typeof setInterval>) => void;
  readonly loadClip?: (datasetDir: string) => Promise<ReplayClip>;
}

export type DemoStartResult = { ok: true } | { ok: false; error: string };

const DEFAULT_TICK_MS = 50;
const STATUS_HEARTBEAT_MS = 1000;

export class DemoSession {
  private mode: DemoMode | null = null;
  private phase: DemoPhase = "idle";
  private clipLabel: string | null = null;
  private message: string | null = null;
  private durationS = 0;
  private startMs = 0;
  private lastStatusMs = 0;
  private lastStatusPhase: DemoPhase = "idle";
  private timer: ReturnType<typeof setInterval> | null = null;
  private cursor: ReplayCursor | null = null;
  private calibrationMs = 0;
  private token = 0;

  private readonly tickMs: number;
  private readonly now: () => number;
  private readonly setIntervalFn: NonNullable<DemoDeps["setIntervalFn"]>;
  private readonly clearIntervalFn: NonNullable<DemoDeps["clearIntervalFn"]>;
  private readonly loadClip: NonNullable<DemoDeps["loadClip"]>;

  constructor(
    private readonly host: DemoHost,
    private readonly deps: DemoDeps,
  ) {
    this.tickMs = deps.tickMs ?? DEFAULT_TICK_MS;
    this.now = deps.now ?? Date.now;
    this.setIntervalFn = deps.setIntervalFn ?? setInterval;
    this.clearIntervalFn = deps.clearIntervalFn ?? clearInterval;
    this.loadClip = deps.loadClip ?? ((dir) => loadReplayClip(dir));
  }

  isActive(): boolean {
    return this.mode !== null;
  }

  isSynthetic(): boolean {
    return this.mode === "synthetic";
  }

  isReplay(): boolean {
    return this.mode === "replay";
  }

  status(): DemoStatus {
    const elapsedMs = this.timer ? this.now() - this.startMs : 0;
    const positionS =
      this.mode === "replay" && this.cursor
        ? this.cursor.positionMs(elapsedMs) / 1000
        : this.durationS > 0
          ? (elapsedMs / 1000) % this.durationS
          : 0;
    return {
      active: this.mode !== null,
      mode: this.mode,
      phase: this.phase,
      clip: this.clipLabel,
      positionS,
      durationS: this.durationS,
      message: this.message,
    };
  }

  async start(mode: DemoMode): Promise<DemoStartResult> {
    if (this.mode !== null) {
      return { ok: false, error: "A demo is already running - stop it first" };
    }
    const token = ++this.token;
    this.mode = mode;
    this.message = null;
    this.cursor = null;

    if (mode === "synthetic") {
      this.clipLabel = "scripted walker";
      this.durationS = walkerCycleSeconds(this.deps.room);
      this.begin("running");
      return { ok: true };
    }

    this.clipLabel = null;
    this.durationS = 0;
    this.phase = "loading";
    this.emitStatus();

    let clip: ReplayClip;
    try {
      clip = await this.loadClip(this.deps.datasetDir);
    } catch (error: unknown) {
      if (token !== this.token) {
        return { ok: false, error: "Demo stopped before the recording finished loading" };
      }
      const reason = error instanceof Error ? error.message : String(error);
      this.reset("error", reason);
      return { ok: false, error: reason };
    }
    if (token !== this.token) {
      return { ok: false, error: "Demo stopped before the recording finished loading" };
    }

    this.cursor = new ReplayCursor(clip.frames, clip.calibrationMs, clip.durationMs);
    this.calibrationMs = clip.calibrationMs;
    this.clipLabel = clip.label;
    this.durationS = clip.durationMs / 1000;
    this.begin("calibrating");
    return { ok: true };
  }

  stop(): void {
    if (this.mode === null) return;
    this.token++;
    this.reset("idle", null);
  }

  private begin(phase: DemoPhase): void {
    this.startMs = this.now();
    this.phase = phase;
    this.timer = this.setIntervalFn(() => this.tick(), this.tickMs);
    this.emitStatus();
  }

  private reset(phase: DemoPhase, message: string | null): void {
    if (this.timer) {
      this.clearIntervalFn(this.timer);
      this.timer = null;
    }
    this.mode = null;
    this.cursor = null;
    this.phase = phase;
    this.message = message;
    this.clipLabel = null;
    this.durationS = 0;
    this.emitStatus();
  }

  private tick(): void {
    try {
      const nowMs = this.now();
      const elapsedMs = nowMs - this.startMs;
      if (this.mode === "synthetic") {
        this.host.publishWalkerFrame(buildWalkerFrame(elapsedMs / 1000, nowMs, this.deps.room));
      } else if (this.mode === "replay" && this.cursor) {
        for (const frame of this.cursor.advance(elapsedMs)) {
          this.host.ingestSample(sampleFromFrame(frame, nowMs));
        }
        this.phase = this.cursor.positionMs(elapsedMs) < this.calibrationMs ? "calibrating" : "running";
      }
      if (this.phase !== this.lastStatusPhase || nowMs - this.lastStatusMs >= STATUS_HEARTBEAT_MS) {
        this.emitStatus();
      }
    } catch (error: unknown) {
      const reason = error instanceof Error ? error.message : String(error);
      console.error(`[DEMO] tick failed, stopping demo: ${reason}`);
      this.token++;
      this.reset("error", reason);
    }
  }

  private emitStatus(): void {
    this.lastStatusMs = this.now();
    this.lastStatusPhase = this.phase;
    this.host.onStatus(this.status());
  }
}
