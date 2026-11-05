/**
 * @file phase-test-logger.ts
 * @brief Opt-in CSV log of per-packet CSI phase, for live-scan phase testing.
 *
 * Disabled by default (would otherwise write a row per CSI packet, up to
 * 50 Hz per node). Enable with PHANTOM_PHASE_TEST_LOG=1; override the
 * output directory with PHANTOM_PHASE_LOG_DIR (default data/phase-tests).
 */
import fs from "fs";
import path from "path";
import { dataDir } from "./data-dir";

const ENABLED = process.env.PHANTOM_PHASE_TEST_LOG === "1";
const LOG_DIR = process.env.PHANTOM_PHASE_LOG_DIR || dataDir("phase-tests");

class PhaseTestLogger {
  private stream: fs.WriteStream | null = null;
  private filePath: string | null = null;
  private sampleCount = 0;

  constructor(private readonly enabled: boolean) {
    if (this.enabled) {
      this.open();
    }
  }

  private open() {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const iso = new Date().toISOString().replace(/[:.]/g, "-");
    this.filePath = path.join(LOG_DIR, `live-scan-phase_${iso}.csv`);
    this.stream = fs.createWriteStream(this.filePath, { flags: "a" });
    this.stream.write("timestamp_ms,node_id,seq,rssi,phase_rad\n");
    console.log(`[PhaseTestLogger] PHANTOM_PHASE_TEST_LOG=1 — recording to ${this.filePath}`);
  }

  /** Log one packet's dominant-subcarrier phase (radians, atan2(im, re)). No-op when disabled. */
  log(nodeId: number, seq: number | undefined, rssi: number, phaseRad: number) {
    if (!this.stream) return;
    this.stream.write(`${Date.now()},${nodeId},${seq ?? ""},${rssi},${phaseRad.toFixed(6)}\n`);
    this.sampleCount++;
  }

  isEnabled(): boolean {
    return this.enabled;
  }
}

export const phaseTestLogger = new PhaseTestLogger(ENABLED);
