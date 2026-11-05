/** The slice of Storage the flag helpers need (so tests can pass a fake). */
export interface FlagStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/**
 * Read a per-viewer boolean convenience (e.g. "show skeleton"). Browser storage
 * can be absent or throw (private window, blocked site data), so every access
 * is guarded and falls back to the default - the page must work without it.
 */
export function readStoredFlag(
  storage: FlagStorage | null | undefined,
  key: string,
  fallback: boolean,
): boolean {
  try {
    const raw = storage?.getItem(key);
    if (raw === "1") return true;
    if (raw === "0") return false;
  } catch {
    // Storage unavailable: use the default.
  }
  return fallback;
}

export function writeStoredFlag(
  storage: FlagStorage | null | undefined,
  key: string,
  value: boolean,
): void {
  try {
    storage?.setItem(key, value ? "1" : "0");
  } catch {
    // Storage unavailable: the choice just won't persist across reloads.
  }
}
