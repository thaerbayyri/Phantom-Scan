/**
 * Resolves the mapping from a system stream's own clock to ground-truth
 * time, from one or more explicit sync events (build prompt §4.2). Never
 * guesses an alignment — callers MUST supply at least one SyncEvent, or this
 * throws NoSyncMarkerError so the CLI can refuse to score (see A4).
 *
 * One sync event yields a constant offset. Two or more yield a least-squares
 * linear fit (offset + drift), covering the "offset + drift fix" step in the
 * architecture diagram without inventing cross-correlation on signals this
 * harness doesn't have (no shared audio/video track between streams).
 */

export interface SyncEvent {
  groundTruthMs: number;
  systemMs: number;
}

export interface TimeAlignment {
  offsetMs: number;
  driftPpm: number;
}

export class NoSyncMarkerError extends Error {
  constructor(message = "TO_BE_MEASURED — no sync marker") {
    super(message);
    this.name = "NoSyncMarkerError";
  }
}

export function resolveAlignment(events: SyncEvent[]): TimeAlignment {
  if (events.length === 0) {
    throw new NoSyncMarkerError();
  }
  if (events.length === 1) {
    return { offsetMs: events[0].groundTruthMs - events[0].systemMs, driftPpm: 0 };
  }

  // groundTruthMs = systemMs * (1 + drift) + offset, least-squares fit.
  const n = events.length;
  const meanX = events.reduce((s, e) => s + e.systemMs, 0) / n;
  const meanY = events.reduce((s, e) => s + e.groundTruthMs, 0) / n;

  let numerator = 0;
  let denominator = 0;
  for (const e of events) {
    numerator += (e.systemMs - meanX) * (e.groundTruthMs - meanY);
    denominator += (e.systemMs - meanX) * (e.systemMs - meanX);
  }
  const slope = denominator === 0 ? 1 : numerator / denominator;
  const offsetMs = meanY - slope * meanX;
  const driftPpm = (slope - 1) * 1_000_000;

  return { offsetMs, driftPpm };
}

export function systemToGroundTruthMs(systemMs: number, alignment: TimeAlignment): number {
  return systemMs * (1 + alignment.driftPpm / 1_000_000) + alignment.offsetMs;
}
