/**
 * Empty-room / negative-control calibration for PHANTOM_MOTION_THRESHOLD,
 * and (Item 4) for the spatial energy threshold PHANTOM_SPATIAL_ENERGY_THRESHOLD.
 *
 * Listens directly on UDP :5005 (STOP the dashboard first — single owner!) and
 * runs the exact production motion pipeline (parseCsiPacket -> per-node 3 s
 * window -> computeNodeMotionFromMatrix), sampling max(motion1, motion2).
 * With --spatial it ALSO samples per-packet total amplitude energy (the same
 * magnitude quantity TrackingProcessor's cluster-energy gate sums) and
 * reports a mean+k*sigma suggestion for PHANTOM_SPATIAL_ENERGY_THRESHOLD via
 * calibrateEnergyThreshold (server/lib/tracking.ts).
 *
 * Usage:
 *   npx tsx scripts/calibrate-threshold.ts --seconds 120
 *   npx tsx scripts/calibrate-threshold.ts --seconds 120 --spatial
 *   PHANTOM_ALLOW_LEGACY_CSI=1 npx tsx scripts/calibrate-threshold.ts --seconds 120
 *
 * Run twice per MEASUREMENT_PLAN / REAL_TEST_REPORT:
 *   1. Empty room  -> threshold = mean + k*sigma (start k=4)
 *   2. Fan on-axis -> fan's max motion must stay BELOW the chosen threshold;
 *      if it doesn't, raise k and re-run the empty-room soak.
 */
import dgram from "dgram";
import { parseCsiPacket } from "../server/lib/udp-server";
import { computeNodeMotionFromMatrix } from "../server/lib/node-fusion";
import { calibrateEnergyThreshold } from "../server/lib/tracking";

const secondsArg = process.argv.indexOf("--seconds");
const SECONDS = secondsArg >= 0 ? parseInt(process.argv[secondsArg + 1], 10) : 120;
const PORT = parseInt(process.env.UDP_PORT || "5005", 10);
const WINDOW_MS = 3000;
const ALLOW_LEGACY_CSI =
  process.env.PHANTOM_ALLOW_LEGACY_CSI === "1" ||
  process.env.PHANTOM_ALLOW_LEGACY_CSI === "true";

const SPATIAL = process.argv.includes("--spatial");

const windows = new Map<number, { t: number; amps: number[] }[]>();
const samples: number[] = [];
const packetCounts = new Map<number, number>();
/** --spatial: per-packet total amplitude energy (sum of per-subcarrier
 * amplitudes) — the magnitude quantity the TrackingProcessor cluster gate
 * sums. Collected raw here; mean+k*sigma computed by calibrateEnergyThreshold. */
const energySamples: number[] = [];

const sock = dgram.createSocket("udp4");
sock.on("error", (err: NodeJS.ErrnoException) => {
  if (err.code === "EADDRINUSE") {
    console.error(`Cannot bind :${PORT} — stop the dashboard first (it owns the port).`);
  } else {
    console.error(err.message);
  }
  process.exit(1);
});

sock.on("message", (msg) => {
  const parsed = parseCsiPacket(msg, { allowLegacy: ALLOW_LEGACY_CSI });
  if (!parsed) return;
  const nodeId = parsed.nodeId;
  if (nodeId !== 1 && nodeId !== 2) return;

  const k = Math.min(parsed.numSubcarriers, 64);
  const amps = new Array<number>(k);
  for (let i = 0; i < k; i++) {
    const re = parsed.iqData.readInt8(i * 2);
    const im = parsed.iqData.readInt8(i * 2 + 1);
    amps[i] = Math.hypot(re, im);
  }

  const t = Date.now();
  let win = windows.get(nodeId);
  if (!win) {
    win = [];
    windows.set(nodeId, win);
  }
  win.push({ t, amps });
  while (win.length && win[0].t < t - WINDOW_MS) win.shift();
  packetCounts.set(nodeId, (packetCounts.get(nodeId) ?? 0) + 1);

  if (SPATIAL) {
    energySamples.push(amps.reduce((s, a) => s + a, 0));
  }
});

function motionFor(nodeId: number): number {
  const win = windows.get(nodeId) ?? [];
  return computeNodeMotionFromMatrix(win.map((w) => w.amps)).motion;
}

sock.bind(PORT, "0.0.0.0", () => {
  console.log(`Listening on :${PORT} for ${SECONDS}s ... keep the room in the test condition.`);
});

const startedAt = Date.now();
const tick = setInterval(() => {
  // Sample at ~5 Hz once both windows have content.
  const m1 = motionFor(1);
  const m2 = motionFor(2);
  if ((windows.get(1)?.length ?? 0) > 5 && (windows.get(2)?.length ?? 0) > 5) {
    samples.push(Math.max(m1, m2));
  }
  const elapsed = (Date.now() - startedAt) / 1000;
  if (elapsed >= SECONDS) {
    clearInterval(tick);
    sock.close();
    report(elapsed);
  }
}, 200);

function report(elapsedS: number) {
  if (samples.length === 0) {
    console.error("No samples collected — are both nodes streaming to this host?");
    process.exit(1);
  }
  const mean = samples.reduce((s, v) => s + v, 0) / samples.length;
  const sigma = Math.sqrt(
    samples.reduce((s, v) => s + (v - mean) * (v - mean), 0) / samples.length,
  );
  const max = Math.max(...samples);

  console.log(`\n=== Calibration result (${samples.length} samples over ${elapsedS.toFixed(0)}s) ===`);
  for (const id of [1, 2]) {
    const fps = (packetCounts.get(id) ?? 0) / elapsedS;
    const warn = fps < 20 ? "  << below 20 fps — fix firmware/network before trusting results" : "";
    console.log(`node ${id}: ${fps.toFixed(1)} packets/s${warn}`);
  }
  console.log(`max(motion1,motion2): mean=${mean.toFixed(4)} sigma=${sigma.toFixed(4)} max=${max.toFixed(4)}`);
  console.log(`suggested PHANTOM_MOTION_THRESHOLD: mean+3s=${(mean + 3 * sigma).toFixed(4)}  mean+4s=${(mean + 4 * sigma).toFixed(4)}  mean+5s=${(mean + 5 * sigma).toFixed(4)}`);
  console.log("(empty room: pick mean+k*sigma; fan run: observed max must stay BELOW your chosen threshold)");

  if (SPATIAL) {
    // Item 4: spatial energy noise floor. NOTE — this samples per-PACKET
    // total amplitude energy as the closest live proxy for the cluster
    // energies the TrackingProcessor gate sums; it is not identical to the
    // in-pipeline cluster energy (which depends on MUSIC point-cloud
    // geometry and DBSCAN membership). Treat the suggestion as a starting
    // point and validate against the ADR-057 procedure (empty room >5s in
    // single-node mode must clear; a real person must persist).
    const cal3 = calibrateEnergyThreshold(energySamples, 3);
    const cal4 = calibrateEnergyThreshold(energySamples, 4);
    console.log(`\n=== Spatial energy calibration (${cal3.sampleCount} per-packet samples) ===`);
    console.log(`per-packet energy: mean=${cal3.mean.toFixed(2)} sigma=${cal3.sigma.toFixed(2)} max=${cal3.max.toFixed(2)}`);
    console.log(`suggested PHANTOM_SPATIAL_ENERGY_THRESHOLD: mean+3s=${cal3.suggestedThreshold.toFixed(2)}  mean+4s=${cal4.suggestedThreshold.toFixed(2)}`);
    console.log("(apply via env PHANTOM_SPATIAL_ENERGY_THRESHOLD — see docs/SPATIAL_CALIBRATION.md)");
  }
  process.exit(0);
}
