import test from "node:test";
import assert from "node:assert/strict";
import { WebSocket } from "ws";
import { SignalProcessingServer } from "./websocket";

/**
 * PS-AUDIT-014 (F1): poseFrame/targetIdentity/vitalSigns must be gated on
 * client.isAI, and targetIdentity/vitalSigns must NEVER be writable by any
 * client message (even an AI one) — only the deterministic pipeline may
 * write currentTargetIdentity/currentVitalSigns. These tests drive the
 * private handleMessage/clients/status surface directly since there is no
 * public API for injecting a WS message in-process.
 */

type Captured = { type: string; data: unknown };

function makeClient(id: string, opts: { isAI?: boolean } = {}) {
  const sent: Captured[] = [];
  const ws = {
    readyState: WebSocket.OPEN,
    send(raw: string) {
      sent.push(JSON.parse(raw));
    },
  };
  return { id, ws, sent, isAI: opts.isAI };
}

function wireClient(server: any, client: ReturnType<typeof makeClient>) {
  server.clients.set(client.id, { ws: client.ws, id: client.id, isAI: client.isAI });
}

function newProcessingServer(): any {
  const server: any = new SignalProcessingServer();
  server.status.isProcessing = true;
  return server;
}

function ingestSampleFor(server: any, nodeId: number) {
  server.ingestSample({
    timestamp: Date.now(),
    h1: { re: 1, im: 1 },
    h2: { re: 1, im: 1 },
    rssi: -40,
    nodeId,
    amplitudes: [1, 1, 1, 1],
  });
}

test("non-AI client's targetIdentity produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  const bystander = makeClient("bystander");
  wireClient(server, attacker);
  wireClient(server, bystander);

  server.currentTargetIdentity = null;
  server.handleMessage("attacker", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 0.99, mechanicalProb: 0.01 },
  });

  assert.equal(server.currentTargetIdentity, null, "authoritative field must be untouched");
  assert.equal(attacker.sent.length, 0, "attacker must not receive any broadcast from its own message");
  assert.equal(bystander.sent.length, 0, "no other client should see the injected identity");
});

test("non-AI client's vitalSigns produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  wireClient(server, attacker);

  server.currentVitalSigns = null;
  server.handleMessage("attacker", {
    type: "vitalSigns",
    data: { heartRateBpm: 999, respirationRateRpm: 999, vitalsReliable: true },
  });

  assert.equal(server.currentVitalSigns, null);
  assert.equal(attacker.sent.length, 0);
});

test("non-AI client's poseFrame produces no state change and no broadcast", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  wireClient(server, attacker);

  server.currentPoseFrame = null;
  server.handleMessage("attacker", { type: "poseFrame", data: { timestamp: 1, keypoints: [] } });

  assert.equal(server.currentPoseFrame, null);
  assert.equal(attacker.sent.length, 0);
});

test("AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  server.currentTargetIdentity = null;
  const payload = { label: "human", humanProb: 0.99, mechanicalProb: 0.01 };
  server.handleMessage("ai", { type: "targetIdentity", data: payload });

  assert.equal(server.currentTargetIdentity, null, "F1: no client message may write the authoritative channel");
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryIdentity");
  assert.deepEqual(dashboard.sent[0].data, payload);
  // The old, authoritative-looking type name must never be broadcast from a client message.
  assert.ok(!dashboard.sent.some((m) => m.type === "targetIdentity"));
});

test("AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  server.currentVitalSigns = null;
  const payload = { heartRateBpm: 72, respirationRateRpm: 15, vitalsReliable: true };
  server.handleMessage("ai", { type: "vitalSigns", data: payload });

  assert.equal(server.currentVitalSigns, null);
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryVitalSigns");
  assert.deepEqual(dashboard.sent[0].data, payload);
});

test("AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists)", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  const payload = { timestamp: 123, keypoints: [{ x: 0, y: 0, z: 0 }] };
  server.handleMessage("ai", { type: "poseFrame", data: payload });

  assert.deepEqual(server.currentPoseFrame, payload);
  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "poseFrame");
});

test("registerAIClient sets isAI, unblocking the gated message types", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai");
  wireClient(server, ai);

  server.handleMessage("ai", { type: "registerAIClient", data: null });
  assert.equal(server.clients.get("ai").isAI, true);

  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  server.handleMessage("ai", { type: "vitalSigns", data: { heartRateBpm: 60, respirationRateRpm: 12, vitalsReliable: true } });

  assert.equal(dashboard.sent.length, 1);
  assert.equal(dashboard.sent[0].type, "advisoryVitalSigns");
});

test("new-client snapshot (sendLiveSnapshotToClient) always serves the deterministic value, never an injected one", () => {
  const server = newProcessingServer();
  const attacker = makeClient("attacker");
  const ai = makeClient("ai", { isAI: true });
  wireClient(server, attacker);
  wireClient(server, ai);

  // Both an injection attempt and a legitimate AI advisory message arrive first.
  server.handleMessage("attacker", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 1, mechanicalProb: 0 },
  });
  server.handleMessage("ai", {
    type: "targetIdentity",
    data: { label: "human", humanProb: 1, mechanicalProb: 0 },
  });

  // Only the deterministic pipeline writes this — simulate its tick directly.
  const deterministic = { label: "mechanical", humanProb: 0.1, mechanicalProb: 0.9 };
  server.currentTargetIdentity = deterministic;

  const newClient = makeClient("newcomer");
  wireClient(server, newClient);
  server.sendLiveSnapshotToClient("newcomer");

  const identityMsg = newClient.sent.find((m) => m.type === "targetIdentity");
  assert.ok(identityMsg, "snapshot must include a targetIdentity message");
  assert.deepEqual(identityMsg!.data, deterministic, "snapshot must reflect only the deterministic write, never the injected/advisory data");
});

// ── resolveLiveNodeMode() staleness handling ────────────────────────────────
// Investigated after a live-UDP-replay session showed fused-two-node display
// while only node 2's packets were being replayed. Confirmed (in-process,
// deliberately no network involved, to sidestep an unrelated ambient-UDP-
// traffic confound discovered in that environment) that this function itself
// has no staleness bug — the earlier observation was traced to that ambient
// traffic supplying real node-1 samples in the background, not a code defect.
// These tests lock in the verified-correct behavior.

test("resolveLiveNodeMode: cold start with only node 2 reporting resolves single_node, not fused", () => {
  const server = newProcessingServer();
  ingestSampleFor(server, 2);
  assert.equal(server.resolveLiveNodeMode(), "single_node");
});

test("resolveLiveNodeMode: both nodes freshly reporting resolves fused_two_node", () => {
  const server = newProcessingServer();
  ingestSampleFor(server, 2);
  ingestSampleFor(server, 1);
  assert.equal(server.resolveLiveNodeMode(), "fused_two_node");
});

test("resolveLiveNodeMode: node 1 going stale mid-session (dropout) falls back to single_node while node 2 keeps reporting", () => {
  const server = newProcessingServer();
  ingestSampleFor(server, 2);
  ingestSampleFor(server, 1);
  assert.equal(server.resolveLiveNodeMode(), "fused_two_node", "sanity: starts fused");

  // Simulate node 1 going silent >1.5s ago (network drop / powered off /
  // moved out of range) without a real wait — same staleness window
  // activeHardwareNodeIds() checks (server/lib/websocket.ts).
  server.hardwareNodeLastSeenMs.set(1, Date.now() - 2000);
  assert.equal(server.resolveLiveNodeMode(), "single_node", "must fall back once node 1 is stale");
});

test("resolveLiveNodeMode: both nodes stale resolves single_node (no separate 'no nodes' state)", () => {
  const server = newProcessingServer();
  ingestSampleFor(server, 2);
  ingestSampleFor(server, 1);
  server.hardwareNodeLastSeenMs.set(1, Date.now() - 2000);
  server.hardwareNodeLastSeenMs.set(2, Date.now() - 2000);
  assert.equal(server.resolveLiveNodeMode(), "single_node");
});

test("two-node fusion uses the active pair when nodes 3 and 4 are the live sensors", () => {
  const server = newProcessingServer();
  const movingJitter = [5, 25, 2, 28, 4, 26, 3, 27, 6, 24, 2, 29];
  ingestNoisyAmplitudes(server, 3, movingJitter, 40);
  ingestNoisyAmplitudes(server, 4, movingJitter, 40);

  assert.deepEqual(server.activeHardwareNodeIds(), [3, 4]);
  assert.equal(server.resolveLiveNodeMode(), "fused_two_node");

  const fused = server.computeFusedTarget();
  assert.ok(fused, "the live N3/N4 pair must produce a fused target");
  assert.ok(Math.abs(fused!.x) < 0.01, `x=${fused!.x} should stay on the N3-N4 line`);
  assert.ok(Math.abs(fused!.z - 3) < 0.01, `z=${fused!.z} should use the N3/N4 anchors`);
});

// ── PS-GHOST-001: single-node presence gate must use the validated motion
// metric, not the separately auto-calibrated MotionGate ────────────────────
// Real single-node empty-room recordings showed the presence gate lit up on
// ~98-99% of ticks with nobody in the room (data/sessions/
// emty_2026-07-20T18-21-17-566Z.csv: motion_n2 avg 0.375/max 0.507 against
// fused_motion_threshold 0.6 — a continuous ghost target under the OLD
// motionResult.motionDetected wiring, which free-ran its own ~2.4s
// auto-calibrated scalar threshold instead of this validated metric). Fixed
// by routing single-node presence through nodeMotionFor() + the same
// threshold the two-node fused gate already uses. These lock in both
// directions: real-scale noise must NOT trip the gate, real-scale motion
// still must.
function ingestNoisyAmplitudes(
  server: any,
  nodeId: number,
  jitter: number[],
  count: number,
) {
  const baseTs = Date.now();
  for (let i = 0; i < count; i++) {
    server.ingestSample({
      timestamp: baseTs + i * 35,
      h1: { re: 1, im: 1 },
      h2: { re: 1, im: 1 },
      rssi: -45,
      nodeId,
      amplitudes: [
        jitter[i % jitter.length],
        jitter[(i + 4) % jitter.length],
        jitter[(i + 8) % jitter.length],
      ],
    });
  }
}

test("singleNodeMotionDetected: realistic empty-room node2 noise (node1 silent) does not trip the gate", () => {
  const server = newProcessingServer();
  // Small fluctuation around a baseline amplitude -- the same order of
  // magnitude of temporal variance real empty-room CSI noise shows (motion
  // ~0.4-0.5 on the 0-1 scale, still under the 0.6 threshold).
  const emptyRoomJitter = [15, 17, 13, 16.5, 13.5, 17.5, 12.5, 16, 14, 15.5, 16.8, 13.2];
  ingestNoisyAmplitudes(server, 2, emptyRoomJitter, 40);

  assert.equal(server.resolveLiveNodeMode(), "single_node", "sanity: node 1 never reported");
  assert.equal(
    server.singleNodeMotionDetected(),
    false,
    "realistic empty-room node noise must not trip the single-node presence gate",
  );
});

test("singleNodeMotionDetected: real moving-target-scale node motion still trips the gate (no over-correction)", () => {
  const server = newProcessingServer();
  // Wide swings around the same baseline -- the same order of magnitude of
  // temporal variance a real moving person produces (motion comfortably
  // above the 0.6 threshold).
  const movingJitter = [5, 25, 2, 28, 4, 26, 3, 27, 6, 24, 2, 29];
  ingestNoisyAmplitudes(server, 2, movingJitter, 40);

  assert.equal(server.resolveLiveNodeMode(), "single_node", "sanity: node 1 never reported");
  assert.equal(
    server.singleNodeMotionDetected(),
    true,
    "real moving-scale motion must still trip the single-node presence gate after the fix",
  );
});

// ── PS-GHOST-001 (Part 2): the motionStatus broadcast must also use the
// validated per-node metric, not MotionGate's own known-unreliable
// auto-calibrated result. MotionGate was left wired to this broadcast when
// the presence-gate consumer above was fixed (see
// PhantomScan_GhostTarget_Fix.md), so the dashboard's live motion indicator
// could still contradict an actual empty-room test until this fix.
test("motionStatus broadcast: known-unreliable MotionGate false positive does not reach the dashboard in an empty room", () => {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);

  // Stub MotionGate to reproduce the exact real-hardware failure: its own
  // free-running auto-calibration claims motion even though the room is
  // empty (98-99% false-positive rate measured on real recordings).
  server.motionGate.update = () => ({ motionDetected: true, variance: 1, threshold: 0.05 });

  const emptyRoomJitter = [15, 17, 13, 16.5, 13.5, 17.5, 12.5, 16, 14, 15.5, 16.8, 13.2];
  ingestNoisyAmplitudes(server, 2, emptyRoomJitter, 40);

  server.processFrame();

  const motionStatusMsgs = dashboard.sent.filter((m: Captured) => m.type === "motionStatus");
  assert.ok(motionStatusMsgs.length > 0, "sanity: motionStatus must have broadcast");
  const last = motionStatusMsgs[motionStatusMsgs.length - 1];
  assert.equal(
    (last.data as { motionDetected: boolean }).motionDetected,
    false,
    "the broadcast must follow the validated per-node metric, not the stubbed known-unreliable MotionGate result",
  );
});

test("motionStatus broadcast: manual motionGateEnabled threshold is not overridden", () => {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  server.config.motionGateEnabled = true;
  server.config.motionThreshold = 0.01;

  server.motionGate.update = () => ({ motionDetected: true, variance: 1, threshold: 0.01 });

  const emptyRoomJitter = [15, 17, 13, 16.5, 13.5, 17.5, 12.5, 16, 14, 15.5, 16.8, 13.2];
  ingestNoisyAmplitudes(server, 2, emptyRoomJitter, 40);

  server.processFrame();

  const motionStatusMsgs = dashboard.sent.filter((m: Captured) => m.type === "motionStatus");
  const last = motionStatusMsgs[motionStatusMsgs.length - 1];
  assert.equal(
    (last.data as { motionDetected: boolean }).motionDetected,
    true,
    "an operator-enabled manual threshold must keep using MotionGate's own result, unchanged",
  );
});

// ── Kalman-filtered fused position wiring (fused_room / 4-node) ────────────
// radX/radZ (the radialTarget broadcast, i.e. the on-screen dot) and
// roomFusedSnapshot (buildSensorNodes' distance labels) must both read the
// Kalman-filtered position from fusedKalman, not the raw fuseNodeTargets
// output — previously they read fused.x/z directly, which would have left
// the marker exactly as jittery as the raw signal despite the filter
// running. See fused-position-kalman.ts for the filter itself (validated
// separately against real recorded session data).

test("fused_room: radialTarget broadcast and roomFusedSnapshot both reflect the Kalman-filtered position, not raw", () => {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);

  // 4 active nodes so resolveLiveNodeMode() reports fused_room; the exact
  // amplitude values don't matter here since computeFusedTarget is stubbed
  // below -- getting a synthetic h1/h2 stream past the REAL micro-Doppler
  // classifier gate is a separate concern already out of scope for every
  // other fusion test in this file (they all call computeFusedTarget()
  // directly for the same reason -- constant h1/h2 reads as "no
  // micro-Doppler signature" and gets vetoed by classifier corroboration).
  for (const nodeId of [1, 2, 3, 4]) {
    ingestNoisyAmplitudes(server, nodeId, [10, 10, 10, 10], 20);
  }
  assert.equal(server.resolveLiveNodeMode(), "fused_room", "sanity: 4 active nodes must resolve to fused_room");

  // Stub the raw fused position computeFusedTarget would have returned this
  // tick (no `balance` field -> processFrame's fused_room branch) so this
  // test isolates the wiring under test: does radX/radZ/roomFusedSnapshot
  // actually read the Kalman-filtered output, or the raw value below?
  // Alternating raw positions: the filter initializes at the first raw
  // value, so a constant input would make filtered == raw and prove nothing.
  let tick = 0;
  let rawFused = { x: 1.23, z: -0.45, distToNearestNodeM: 1, classifierCorroboration: "inconclusive", maxMotion: 1 };
  server.computeFusedTarget = () => {
    const jitter = tick++ % 2 === 0 ? 0 : 0.1;
    rawFused = { ...rawFused, x: 1.23 + jitter, z: -0.45 - jitter };
    return rawFused;
  };

  // The MUSIC/point-cloud/DBSCAN/classification/fusion block only runs once
  // this.sampleBuffer reaches config.arrayLength (16) -- one sample is
  // pushed per processFrame() call, so the fusion path (and this stub)
  // isn't reached at all until then.
  for (let i = 0; i < server.config.arrayLength; i++) {
    server.processFrame();
  }

  const filteredState = server.fusedKalman.getState();
  assert.notEqual(filteredState.x, rawFused.x, "sanity: the filter must have actually moved away from a cold start");
  assert.equal(
    server.roomFusedSnapshot?.x,
    filteredState.x,
    "roomFusedSnapshot.x must be the filtered position, not raw fused.x",
  );
  assert.equal(
    server.roomFusedSnapshot?.z,
    filteredState.z,
    "roomFusedSnapshot.z must be the filtered position, not raw fused.z",
  );

  const radialMsgs = dashboard.sent.filter((m: Captured) => m.type === "radialTarget");
  assert.ok(radialMsgs.length > 0, "sanity: radialTarget must have broadcast once computeFusedTarget is stubbed truthy");
  const lastRadial = radialMsgs[radialMsgs.length - 1].data as { x: number; z: number };
  assert.equal(lastRadial.x, filteredState.x, "radialTarget.x must be the filtered position, not raw fused.x");
  assert.equal(lastRadial.z, filteredState.z, "radialTarget.z must be the filtered position, not raw fused.z");
});

// ── Phase 1 framework fixes (RuView port plan) ─────────────────────────────

const STUB_ROOM_FUSED = { x: 0.8, z: -1.1, distToNearestNodeM: 1, classifierCorroboration: "inconclusive", maxMotion: 1 };

function newFourNodeRoomServer(): { server: any; dashboard: ReturnType<typeof makeClient> } {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  for (const nodeId of [1, 2, 3, 4]) {
    ingestNoisyAmplitudes(server, nodeId, [10, 10, 10, 10], 20);
  }
  server.computeFusedTarget = () => ({ ...STUB_ROOM_FUSED });
  return { server, dashboard };
}

function lastRadialTarget(dashboard: ReturnType<typeof makeClient>) {
  const msgs = dashboard.sent.filter((m: Captured) => m.type === "radialTarget" && m.data);
  return msgs.length ? (msgs[msgs.length - 1].data as Record<string, unknown>) : undefined;
}

test("fused_room radialTarget is labeled fused_room_centroid, not the 1-D two-node basis", () => {
  const { server, dashboard } = newFourNodeRoomServer();
  for (let i = 0; i < server.config.arrayLength; i++) server.processFrame();

  const radial = lastRadialTarget(dashboard);
  assert.ok(radial, "sanity: a fused_room radialTarget must broadcast");
  assert.equal(radial!.positionBasis, "fused_room_centroid");
});

test("fused_room localization still runs when ISAR/MUSIC is disabled", () => {
  const { server, dashboard } = newFourNodeRoomServer();
  server.config.isarEnabled = false;
  server.processFrame();
  server.processFrame();

  const radial = lastRadialTarget(dashboard);
  assert.ok(radial, "fused localization must not depend on the ISAR/MUSIC toggle");
  assert.equal(radial!.positionBasis, "fused_room_centroid");
  // ...and must not be wiped straight after broadcast by the single-node
  // "insufficient_window" clear.
  assert.equal(server.currentTargetState.target_visible, true, "fused target must stay visible");
  assert.ok(server.currentRadialTarget, "fused radialTarget must not be cleared");
});

test("micro-Doppler classifier is fed the per-node background-subtracted residual", () => {
  const server = newProcessingServer();
  server.config.clutterRemovalEnabled = true;
  server.config.isarEnabled = false;
  const fed: number[] = [];
  const realPush = server.microDopplerClassifier.push.bind(server.microDopplerClassifier);
  server.microDopplerClassifier.push = (v: number) => {
    fed.push(v);
    return realPush(v);
  };
  server.computeFusedTarget = () => null;

  // Two nodes with very different but CONSTANT complex channels. A shared
  // subtractor would see node-to-node differences as "motion"; the old
  // |h1Proc − h1| input was the background mean (~|h1|), never ~0.
  const baseTs = Date.now();
  for (let i = 0; i < 12; i++) {
    for (const [nodeId, h] of [[1, { re: 20, im: 5 }], [2, { re: 2, im: 1 }]] as const) {
      server.ingestSample({
        timestamp: baseTs + i * 20,
        h1: h,
        h2: h,
        rssi: -45,
        nodeId,
        amplitudes: [10, 10, 10],
      });
    }
  }
  for (let i = 0; i < 16; i++) server.processFrame();

  assert.ok(fed.length > 0, "sanity: classifier must have been fed");
  for (const v of fed) {
    assert.ok(Math.abs(v) < 1e-9, `constant per-node channel must yield ~0 residual, got ${v}`);
  }
});

test("hardware queue is bounded per node so a 4-node burst cannot pin it at the global cap", () => {
  const server = newProcessingServer();
  for (const nodeId of [1, 2, 3, 4]) {
    ingestNoisyAmplitudes(server, nodeId, [10, 11, 12], 200);
  }
  const queued: number[] = server.hardwareSampleQueue.map((s: { nodeId?: number }) => s.nodeId ?? 1);
  for (const nodeId of [1, 2, 3, 4]) {
    const count = queued.filter((id) => id === nodeId).length;
    assert.ok(count > 0, `node ${nodeId} must still be queued`);
    assert.ok(count <= 8, `node ${nodeId} has ${count} queued samples; per-node cap is 8`);
  }
  // The newest sample of each node must be the one retained.
  const node1 = server.hardwareSampleQueue.filter((s: { nodeId?: number }) => s.nodeId === 1);
  const newestTs = Math.max(...node1.map((s: { timestamp: number }) => s.timestamp));
  assert.equal(node1[node1.length - 1].timestamp, newestTs);
});

test("targetDebug reports fps and motion for every anchored node, not just 1 and 2", () => {
  const server = newProcessingServer();
  for (const nodeId of [1, 2, 3, 4]) {
    ingestNoisyAmplitudes(server, nodeId, [10, 11, 12], 20);
  }
  server.updateTargetDebug();
  const debug = server.currentTargetDebug;
  for (const key of ["1", "2", "3", "4"]) {
    assert.ok(key in debug.node_fps, `node_fps must include node ${key}`);
    assert.ok(key in debug.node_motion, `node_motion must include node ${key}`);
  }
});

// ── F1 (real check): AI advisories never change the deterministic output ───

function deterministicTrace(withAiInjection: boolean) {
  const { server, dashboard } = newFourNodeRoomServer();
  const ai = makeClient("ai", { isAI: true });
  wireClient(server, ai);
  for (let i = 0; i < 12; i++) {
    if (withAiInjection) {
      server.handleMessage("ai", {
        type: "targetIdentity",
        data: {
          label: "unknown",
          humanProb: 1,
          mechanicalProb: 0,
          advisoryLabel: "human",
          presenceProb: 1,
          advisoryActivity: "active",
          advisoryActivityConfidence: 1,
          advisoryCount: 8,
          advisoryCountConfidence: 1,
          embeddingDrift: 2,
          embeddingRefAgeS: 0,
          embeddingModelId: "csi-embed-v2",
        },
      });
      server.handleMessage("ai", {
        type: "vitalSigns",
        data: { heartRateBpm: 200, respirationRateRpm: 60, vitalsReliable: true },
      });
    }
    server.processFrame();
  }
  const radial = dashboard.sent
    .filter((m: Captured) => m.type === "radialTarget" && m.data)
    .map((m: Captured) => {
      const d = m.data as Record<string, unknown>;
      return [d.x, d.z, d.label, d.isMoving, d.positionBasis];
    });
  const states = dashboard.sent
    .filter((m: Captured) => m.type === "targetState")
    .map((m: Captured) => {
      const d = m.data as Record<string, unknown>;
      return [d.state, d.target_visible, d.node_mode, JSON.stringify(d.position)];
    });
  return { radial, states, identity: server.currentTargetIdentity, vitals: server.currentVitalSigns };
}

test("F1: extreme AI advisories leave every deterministic broadcast byte-identical", () => {
  const baseline = deterministicTrace(false);
  const injected = deterministicTrace(true);
  assert.ok(baseline.radial.length > 0, "sanity: deterministic path must have produced targets");
  assert.deepEqual(injected.radial, baseline.radial);
  assert.deepEqual(injected.states, baseline.states);
  assert.deepEqual(injected.identity, baseline.identity);
  assert.deepEqual(injected.vitals, baseline.vitals);
});

test("malformed AI advisory payloads are dropped at the WS boundary, not relayed", () => {
  const server = newProcessingServer();
  const ai = makeClient("ai", { isAI: true });
  const dashboard = makeClient("dashboard");
  wireClient(server, ai);
  wireClient(server, dashboard);

  server.handleMessage("ai", { type: "targetIdentity", data: { label: "alien", humanProb: "1" } });
  // Out-of-range embedding drift (valid range is 0-2) must be rejected too.
  server.handleMessage("ai", {
    type: "targetIdentity",
    data: { label: "unknown", humanProb: 0.5, mechanicalProb: 0.5, embeddingDrift: 9 },
  });
  server.handleMessage("ai", { type: "vitalSigns", data: { heartRateBpm: "fast" } });
  server.handleMessage("ai", {
    type: "vitalSigns",
    data: { heartRateBpm: null, respirationRateRpm: null, vitalsReliable: false },
  });

  assert.deepEqual(
    dashboard.sent.map((m: Captured) => m.type),
    ["advisoryVitalSigns"],
    "only the well-formed (null = unreliable) vitals message may be relayed",
  );
});

test("trackActiveNodeSet reports join/leave transitions exactly once", () => {
  const server = newProcessingServer();
  ingestSampleFor(server, 1);
  ingestSampleFor(server, 2);
  ingestSampleFor(server, 3);
  assert.deepEqual(server.trackActiveNodeSet(), { changed: true, joined: [1, 2, 3], left: [] });
  assert.deepEqual(server.trackActiveNodeSet(), { changed: false, joined: [], left: [] });

  server.hardwareNodeLastSeenMs.set(2, Date.now() - 2000);
  assert.deepEqual(server.trackActiveNodeSet(), { changed: true, joined: [], left: [2] });
  assert.deepEqual(server.trackActiveNodeSet(), { changed: false, joined: [], left: [] });
});

// ── Phase 5: fused_room adaptive-baseline presence ─────────────────────────

function newRoomServerWithPresence(tier: string, rises: Record<number, number>, withRouter = false) {
  const server = newProcessingServer();
  // The centroid tests must not depend on whether config/room.json names a router.
  server.room = { ...server.room, router: withRouter ? { x: 2, z: -3 } : undefined };
  for (const nodeId of [1, 2, 3, 4]) ingestNoisyAmplitudes(server, nodeId, [10, 10, 10, 10], 20);
  server.updateRoomPresence = () => {
    server.lastRoomTier = tier;
    return { tier, rises, excesses: rises };
  };
  return server;
}

test("fused_room: position is weighted by each node's rise above its own baseline (no centre pull)", () => {
  const server = newRoomServerWithPresence("present_moving", { 1: 2.0, 2: 0, 3: 0, 4: 0 });
  const fused = server.computeFusedTarget();
  assert.ok(fused, "moving tier must produce a target");
  assert.deepEqual([fused.x, fused.z], [-2, -3], "only node 1 rose above its baseline -> its corner");
  assert.ok(!fused.stationaryHold);
});

test("fused_room with a router: evidence on node 1 only is placed on node 1's link, not at a far corner", () => {
  const server = newRoomServerWithPresence("present_moving", { 1: 2.0, 2: 0, 3: 0, 4: 0 }, true);
  const fused = server.computeFusedTarget();
  assert.ok(fused, "moving tier must produce a target");
  // Node 1's link runs along the z = -3 wall to the router at (2, -3).
  assert.ok(fused.z < -1.5, `expected the node 1/2 wall, got z=${fused.z}`);
  assert.ok(fused.x <= 0.5, `expected the node 1 end of that wall, got x=${fused.x}`);
});

test("fused_room: no target while the room tier is absent", () => {
  const server = newRoomServerWithPresence("absent", { 1: 0.05, 2: 0.02, 3: 0, 4: 0 });
  assert.equal(server.computeFusedTarget(), null);
});

test("fused_room: a person who stops moving is held at the last position (stationary hold)", () => {
  const server = newRoomServerWithPresence("present_still", { 1: 0.2, 2: 0.18, 3: 0.17, 4: 0.16 });
  server.roomFusedSnapshot = { x: 0.7, z: -1.2, vx: 0, vz: 0, atMs: Date.now() };
  const fused = server.computeFusedTarget();
  assert.ok(fused, "present_still with a prior target must hold it");
  assert.equal(fused.stationaryHold, true);
  assert.deepEqual([fused.x, fused.z], [0.7, -1.2]);
});

test("fused_room: present_still without a prior target never creates one", () => {
  const server = newRoomServerWithPresence("present_still", { 1: 0.2, 2: 0.18, 3: 0.17, 4: 0.16 });
  assert.equal(server.computeFusedTarget(), null);
});

test("fused_room: a stationary hold broadcasts isMoving=false and the idle target state", () => {
  const { server, dashboard } = newFourNodeRoomServer();
  server.lastRoomTier = "present_still";
  server.computeFusedTarget = () => ({ ...STUB_ROOM_FUSED, stationaryHold: true });
  server.processFrame();
  server.processFrame();
  const radial = lastRadialTarget(dashboard);
  assert.equal(radial?.isMoving, false);
  const states = dashboard.sent.filter((m: Captured) => m.type === "targetState");
  assert.equal((states[states.length - 1].data as { state: string }).state, "idle");
});

test("fused_room: node trend arrows follow the filtered 2-D velocity", () => {
  const server = newProcessingServer();
  for (const nodeId of [1, 2, 3, 4]) ingestNoisyAmplitudes(server, nodeId, [10, 10, 10, 10], 20);
  server.roomFusedSnapshot = { x: 0, z: 0, vx: 0.4, vz: 0.6, atMs: Date.now() };
  const nodes = server.buildSensorNodes();
  const trendOf = (id: number) => nodes.find((n: { node_id: number }) => n.node_id === id).trend;
  assert.equal(trendOf(3), "approaching");
  assert.equal(trendOf(1), "receding");
});

// ── Phase 8: labelled dataset recording over the WS message path ───────────

test("dataset recording: start/stop messages validate input and record live amplitude vectors", async () => {
  const fs = await import("fs");
  const os = await import("os");
  const path = await import("path");
  const { DatasetRecorder } = await import("./dataset-recorder");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-ds-ws-"));
  const server = newProcessingServer();
  server.datasetRecorder = new DatasetRecorder({ rootDir: root });
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);

  server.handleMessage("dashboard", { type: "startDatasetRecording", data: { roomId: "../bad", label: "empty" } });
  assert.equal(server.datasetRecorder.isRecording, false, "unsafe roomId must be refused");
  assert.ok(dashboard.sent.some((m) => m.type === "error"));

  server.handleMessage("dashboard", { type: "startDatasetRecording", data: { roomId: "lab", subjectId: "s1", label: "walking" } });
  assert.equal(server.datasetRecorder.isRecording, true);
  ingestNoisyAmplitudes(server, 2, [10, 11, 12], 5);
  server.handleMessage("dashboard", { type: "stopDatasetRecording" });

  const stops = dashboard.sent.filter((m) => m.type === "datasetStatus");
  const final = stops[stops.length - 1].data as { recording: boolean; frames: number; perNode: Record<string, number> };
  assert.equal(final.recording, false);
  assert.equal(final.frames, 5);
  assert.deepEqual(final.perNode, { "2": 5 });
});

// ── Review fixes: recorder faults must not crash ingest; stale baselines reset ──

test("a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample", () => {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  let stopped = 0;
  server.datasetRecorder = {
    isRecording: true,
    record() {
      throw new Error("ENOSPC: no space left on device");
    },
    stop() {
      stopped++;
      server.datasetRecorder.isRecording = false;
      return { recording: false, frames: 0, skipped: 0, perNode: {}, files: [] };
    },
  };
  assert.doesNotThrow(() => ingestNoisyAmplitudes(server, 1, [10, 11, 12], 3));
  assert.equal(stopped, 1, "must stop exactly once, not on every packet");
  assert.ok(dashboard.sent.some((m: Captured) => m.type === "error" && String(m.data).includes("Dataset recording stopped")));
});

test("a node that went silent and returns re-warms its baseline instead of reusing stale state", () => {
  const server = newProcessingServer();
  for (const id of [1, 2, 3, 4]) ingestNoisyAmplitudes(server, id, [10, 10, 10, 10], 20);
  server.updateRoomPresence([1, 2, 3, 4], Date.now());
  assert.ok(server.nodeBaselines.has(4));
  server.updateRoomPresence([1, 2, 3], Date.now() + 100); // node 4 silent
  assert.equal(server.nodeBaselines.has(4), false, "silent node's tracker must be dropped");
  assert.equal(server.nodeBaselines.has(1), true);
});

// ── test_3 fixes: position must not snap to an anchor corner ───────────────

test("fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position", () => {
  // Node 2 has a tiny baseline so a small disturbance is a huge relative rise,
  // but its ABSOLUTE excess is the same as the others'.
  const server = newRoomServerWithPresence("present_moving", { 1: 0.4, 2: 6.0, 3: 0.4, 4: 0.4 });
  server.updateRoomPresence = () => ({
    tier: "present_moving",
    rises: { 1: 0.4, 2: 6.0, 3: 0.4, 4: 0.4 },
    excesses: { 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1 },
  });
  const fused = server.computeFusedTarget();
  assert.ok(fused);
  assert.ok(Math.abs(fused.x) < 0.01 && Math.abs(fused.z) < 0.01, `equal excess must give the room centre, got ${fused.x},${fused.z}`);
});

test("fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner)", () => {
  const server = newRoomServerWithPresence("present_moving", {});
  server.updateRoomPresence = () => ({
    tier: "present_moving",
    rises: { 1: 1, 2: 1, 3: 1, 4: 1 },
    excesses: { 1: 0.30, 2: 0.10, 3: 0.10, 4: 0.10 },
  });
  const fused = server.computeFusedTarget();
  assert.ok(fused);
  const cornerDist = Math.hypot(fused.x - -2, fused.z - -3);
  assert.ok(cornerDist > 1.5, `node 1 is 3x stronger but the estimate must stay inside the room, got ${fused.x},${fused.z}`);
});

test("filtered fused position is clamped to the room and reported speed is physically capped", () => {
  const { server, dashboard } = newFourNodeRoomServer();
  // Raw fixes that would drive the Kalman filter outside the anchor hull.
  let k = 0;
  server.computeFusedTarget = () => {
    k++;
    return { x: 2 + k * 0.4, z: -3 - k * 0.6, distToNearestNodeM: 1, classifierCorroboration: "inconclusive", maxMotion: 1 };
  };
  for (let i = 0; i < 40; i++) server.processFrame();
  const radials = dashboard.sent.filter((m: Captured) => m.type === "radialTarget" && m.data).map((m: Captured) => m.data as Record<string, number>);
  assert.ok(radials.length > 0);
  for (const r of radials) {
    assert.ok(Math.abs(r.x) <= 2 + 1e-9 && Math.abs(r.z) <= 3 + 1e-9, `outside room: ${r.x},${r.z}`);
    assert.ok(r.speed <= 4 + 1e-9, `speed ${r.speed} exceeds the human cap`);
  }
});

test("Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar", () => {
  const server = newProcessingServer();
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  for (const id of [1, 2, 3, 4]) ingestNoisyAmplitudes(server, id, [10, 10, 10, 10], 20);
  server.updateRoomPresence([1, 2, 3, 4], Date.now());
  assert.equal(server.nodeBaselines.size, 4);
  server.roomFusedSnapshot = { x: 1, z: 1, vx: 0, vz: 0, atMs: Date.now() };
  server.handleMessage("dashboard", { type: "calibrateBaseline", data: null });
  assert.equal(server.nodeBaselines.size, 0, "baselines must restart");
  assert.equal(server.roomFusedSnapshot, null, "a held target must not survive recalibration");
  assert.equal(server.roomPresence.tier, "absent");
});

test("fused_room radialTarget carries a bounded position uncertainty radius", () => {
  const { server, dashboard } = newFourNodeRoomServer();
  server.computeFusedTarget = () => ({
    x: 0.5, z: -0.5, distToNearestNodeM: 1, classifierCorroboration: "inconclusive", maxMotion: 0.8, positionUncertaintyM: 1.2,
  });
  server.processFrame();
  server.processFrame();
  const radial = lastRadialTarget(dashboard);
  assert.equal(radial?.positionUncertaintyM, 1.2);
});

test("recording rows get the room tier, excess and four-node trends while fused_room is live", () => {
  const server = newProcessingServer();
  for (const id of [1, 2, 3, 4]) ingestNoisyAmplitudes(server, id, [10, 10, 10, 10], 20);
  server.lastRoomTier = "present_moving";
  server.lastNodeExcess = { "1": 0.01, "2": 0.02, "3": 0.03, "4": 0.04 };
  server.lastRoomUncertaintyM = 1.4;
  server.roomFusedSnapshot = { x: 0, z: 0, vx: 0.4, vz: 0.6, atMs: Date.now() };
  const extras = server.buildRoomRecordingExtras();
  assert.equal(extras.tier, "present_moving");
  assert.equal(extras.excess[3], 0.03);
  assert.equal(extras.trends[3], "approaching");
  assert.equal(extras.trends[1], "receding");
  assert.equal(extras.positionUncertaintyM, 1.4);
});

// ── Dashboard capture panel: live progress + late-joining clients ──────────

async function newRecordingServer(label = "walking") {
  const fs = await import("fs");
  const os = await import("os");
  const path = await import("path");
  const { DatasetRecorder } = await import("./dataset-recorder");
  const server = newProcessingServer();
  server.datasetRecorder = new DatasetRecorder({ rootDir: fs.mkdtempSync(path.join(os.tmpdir(), "phantom-ds-progress-")) });
  const dashboard = makeClient("dashboard");
  wireClient(server, dashboard);
  server.handleMessage("dashboard", { type: "startDatasetRecording", data: { roomId: "lab", subjectId: "s1", label } });
  return { server, dashboard };
}

const datasetStatuses = (c: ReturnType<typeof makeClient>) =>
  c.sent.filter((m: Captured) => m.type === "datasetStatus").map((m: Captured) => m.data as { recording: boolean; frames: number });

test("dataset recording: the panel gets live frame counts while recording (not only at start/stop)", async () => {
  const { server, dashboard } = await newRecordingServer();
  const atStart = datasetStatuses(dashboard).length;

  // A burst inside one second must not flood the socket (~65 packets/s per node).
  ingestNoisyAmplitudes(server, 1, [10, 11, 12], 40);
  assert.ok(datasetStatuses(dashboard).length - atStart <= 1, "progress must be throttled to about 1/s");

  // After the interval has elapsed the next sample reports the real running count.
  server.lastDatasetStatusMs = Date.now() - 1500;
  ingestNoisyAmplitudes(server, 1, [10, 11, 12], 1);
  const live = datasetStatuses(dashboard);
  const latest = live[live.length - 1];
  assert.equal(latest.recording, true);
  assert.equal(latest.frames, 41, "progress must carry the running frame count");
});

test("dataset recording: a client that connects mid-recording is told it is recording", async () => {
  const { server } = await newRecordingServer("empty");
  ingestNoisyAmplitudes(server, 3, [10, 11, 12], 7);
  const late = makeClient("late");
  wireClient(server, late);

  server.sendDatasetStatusTo("late");

  const statuses = datasetStatuses(late);
  assert.equal(statuses.length, 1);
  assert.equal(statuses[0].recording, true);
  assert.equal(statuses[0].frames, 7);
});

test("dataset recording: nothing is sent to a new client when no recording is running", () => {
  const server = newProcessingServer();
  const late = makeClient("late");
  wireClient(server, late);
  server.sendDatasetStatusTo("late");
  assert.equal(datasetStatuses(late).length, 0);
});
