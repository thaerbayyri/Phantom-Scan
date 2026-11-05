import test from "node:test";
import assert from "node:assert/strict";
import type { CSISample } from "@shared/schema";
import { DemoSession, type DemoHost, type DemoStatus } from "./demo-session";
import type { ReplayClip } from "./demo-replay";
import type { WalkerFrame } from "./demo-walker";
import type { RoomGeometry } from "./room-geometry";

const room: RoomGeometry = {
  roomWidthM: 4,
  roomDepthM: 6,
  anchors: { 1: { x: -2, z: -3 }, 2: { x: 2, z: -3 }, 3: { x: 2, z: 3 }, 4: { x: -2, z: 3 } },
  source: "test",
};

const clip: ReplayClip = {
  frames: [
    { relMs: 0, nodeId: 1, rssi: -40, amplitudes: [1, 2] },
    { relMs: 500, nodeId: 2, rssi: -41, amplitudes: [3, 4] },
    { relMs: 1_500, nodeId: 3, rssi: -42, amplitudes: [5, 6] },
  ],
  calibrationMs: 1_000,
  durationMs: 2_000,
  label: "room1 still recording",
};

interface Harness {
  readonly session: DemoSession;
  readonly samples: CSISample[];
  readonly frames: WalkerFrame[];
  readonly statuses: DemoStatus[];
  tick(advanceMs: number): void;
  readonly timerCleared: () => boolean;
}

function makeHarness(options: { loadClip?: () => Promise<ReplayClip> } = {}): Harness {
  let nowMs = 1_000_000;
  let callback: (() => void) | null = null;
  let cleared = false;
  const samples: CSISample[] = [];
  const frames: WalkerFrame[] = [];
  const statuses: DemoStatus[] = [];
  const host: DemoHost = {
    ingestSample: (s) => samples.push(s),
    publishWalkerFrame: (f) => frames.push(f),
    onStatus: (s) => statuses.push(s),
  };
  const session = new DemoSession(host, {
    room,
    datasetDir: "unused",
    now: () => nowMs,
    setIntervalFn: (fn) => {
      callback = fn;
      cleared = false;
      return 1 as unknown as ReturnType<typeof setInterval>;
    },
    clearIntervalFn: () => {
      callback = null;
      cleared = true;
    },
    loadClip: options.loadClip ?? (async () => clip),
  });
  return {
    session,
    samples,
    frames,
    statuses,
    tick(advanceMs) {
      nowMs += advanceMs;
      callback?.();
    },
    timerCleared: () => cleared,
  };
}

test("synthetic demo publishes labelled walker frames and stops cleanly", async () => {
  const h = makeHarness();
  const result = await h.session.start("synthetic");

  assert.deepEqual(result, { ok: true });
  assert.equal(h.session.isActive(), true);
  assert.equal(h.session.isSynthetic(), true);
  assert.equal(h.session.isReplay(), false);

  h.tick(50);
  h.tick(50);
  assert.equal(h.frames.length, 2);
  assert.equal(h.frames[0].targetState.source_mode, "synthetic");
  assert.equal(h.samples.length, 0, "synthetic mode must not touch the ingest path");

  h.session.stop();
  assert.equal(h.session.isActive(), false);
  assert.equal(h.timerCleared(), true);
  assert.equal(h.session.status().phase, "idle");
});

test("replay demo feeds recorded frames to ingest stamped with the current time", async () => {
  const h = makeHarness();
  assert.deepEqual(await h.session.start("replay"), { ok: true });
  assert.equal(h.session.isReplay(), true);
  assert.equal(h.frames.length, 0, "replay mode must not publish synthetic frames");

  h.tick(600); // frames at 0 and 500 are due
  assert.deepEqual(h.samples.map((s) => s.nodeId), [1, 2]);
  assert.ok(h.samples.every((s) => s.timestamp === 1_000_600));
  assert.equal(h.session.status().phase, "calibrating");
});

test("replay demo reports running once calibration has elapsed and loops without re-calibrating", async () => {
  const h = makeHarness();
  await h.session.start("replay");

  h.tick(1_600); // past calibration (1000) and the third frame (1500)
  assert.equal(h.session.status().phase, "running");
  assert.deepEqual(h.samples.map((s) => s.nodeId), [1, 2, 3]);

  h.tick(1_000); // wraps at 2000 back to the calibration boundary
  assert.equal(h.session.status().phase, "running");
  assert.deepEqual(h.samples.slice(3).map((s) => s.nodeId), [3]);
});

test("replay demo exposes clip label and duration in its status", async () => {
  const h = makeHarness();
  await h.session.start("replay");
  const status = h.session.status();

  assert.equal(status.active, true);
  assert.equal(status.mode, "replay");
  assert.equal(status.clip, "room1 still recording");
  assert.equal(status.durationS, 2);
});

test("a missing recording fails the start with a message and leaves the demo off", async () => {
  const h = makeHarness({
    loadClip: async () => {
      throw new Error("Demo replay needs a \"empty\" recording in /x");
    },
  });
  const result = await h.session.start("replay");

  assert.equal(result.ok, false);
  assert.match((result as { error: string }).error, /empty/);
  assert.equal(h.session.isActive(), false);
  assert.equal(h.session.status().phase, "error");
});

test("starting while a demo is already running is refused", async () => {
  const h = makeHarness();
  await h.session.start("synthetic");
  const second = await h.session.start("replay");

  assert.equal(second.ok, false);
  assert.equal(h.session.isSynthetic(), true, "the running demo must be unaffected");
});

test("stopping while the recording is still loading discards the load", async () => {
  let release: (c: ReplayClip) => void = () => undefined;
  const h = makeHarness({ loadClip: () => new Promise<ReplayClip>((resolve) => (release = resolve)) });

  const pending = h.session.start("replay");
  assert.equal(h.session.status().phase, "loading");
  h.session.stop();
  release(clip);
  const result = await pending;

  assert.equal(result.ok, false);
  assert.equal(h.session.isActive(), false);
  h.tick(1_000);
  assert.equal(h.samples.length, 0);
});

test("status updates are emitted on start, on phase change and about once per second", async () => {
  const h = makeHarness();
  await h.session.start("replay");
  const afterStart = h.statuses.length;
  assert.ok(afterStart >= 1);

  h.tick(100);
  h.tick(100);
  assert.equal(h.statuses.length, afterStart, "no spam between phase changes");

  h.tick(1_000); // crosses calibration -> running and the 1 s heartbeat
  assert.ok(h.statuses.length > afterStart);
  assert.equal(h.statuses[h.statuses.length - 1].phase, "running");
});
