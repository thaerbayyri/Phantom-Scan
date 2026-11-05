/**
 * Runtime Settings Store — small JSON file for operator-adjusted detector
 * calibration that must survive a server restart (unlike `this.config` in
 * websocket.ts, which is in-memory only). Modeled on session-store.ts's
 * fs-under-data/ convention.
 */
import * as fs from "fs";
import * as path from "path";
import { dataDir } from "./data-dir";

export interface RuntimeSettings {
  fusedTargetMotionThreshold?: number;
  motionThreshold?: number;
}

const DATA_DIR = dataDir();
const SETTINGS_FILE = path.join(DATA_DIR, "runtime-settings.json");

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

/** Read persisted settings; returns {} if the file is missing or invalid. */
export function loadRuntimeSettings(): RuntimeSettings {
  if (!fs.existsSync(SETTINGS_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

/** Merge and persist new settings values (only defined fields are written). */
export function saveRuntimeSettings(updates: RuntimeSettings): void {
  ensureDir();
  const current = loadRuntimeSettings();
  const merged: RuntimeSettings = { ...current };
  if (updates.fusedTargetMotionThreshold !== undefined) {
    merged.fusedTargetMotionThreshold = updates.fusedTargetMotionThreshold;
  }
  if (updates.motionThreshold !== undefined) {
    merged.motionThreshold = updates.motionThreshold;
  }
  fs.writeFileSync(SETTINGS_FILE, JSON.stringify(merged, null, 2), "utf-8");
}
