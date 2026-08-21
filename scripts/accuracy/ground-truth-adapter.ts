/**
 * Parses an operator-keypress or video-timestamp ground-truth log into
 * present/absent intervals plus an optional sync marker.
 *
 * CSV contract (see groundtruth-logger.ts for the writer side):
 *   t_start_ms,t_end_ms,label,subject_id
 *   0,0,sync,
 *   1200,15300,present,subject-1
 *
 * label is one of "present" | "absent" | "sync". "sync" rows are zero-width
 * (t_start_ms === t_end_ms) and mark the operator-triggered sync event used
 * by time-aligner.ts. Absence is the default for any time not covered by a
 * "present" row — explicit "absent" rows are optional documentation, not
 * required for scoring (see confusion-scorer.ts isGroundTruthPositiveAt).
 */
import { parseRecordingCsv } from "../join-groundtruth";

export type GroundTruthLabel = "present" | "absent" | "sync";

export interface GroundTruthRow {
  tStartMs: number;
  tEndMs: number;
  label: GroundTruthLabel;
  subjectId?: string;
}

export interface GroundTruthLog {
  rows: GroundTruthRow[];
  /** First "sync" row's t_start_ms, or null if the log has none (see A4). */
  syncMarkerMs: number | null;
}

const VALID_LABELS = new Set<GroundTruthLabel>(["present", "absent", "sync"]);

export function parseGroundTruthCsv(csvText: string): GroundTruthLog {
  const { rows: rawRows } = parseRecordingCsv(csvText);
  if (rawRows.length === 0) {
    throw new Error("Ground-truth CSV has no data rows.");
  }

  const rows: GroundTruthRow[] = rawRows.map((row, index) => {
    const label = row.label as GroundTruthLabel;
    if (!VALID_LABELS.has(label)) {
      throw new Error(
        `Ground-truth CSV row ${index + 1}: invalid label "${row.label}" (expected present|absent|sync).`,
      );
    }
    const tStartMs = Number.parseFloat(row.t_start_ms ?? "");
    if (!Number.isFinite(tStartMs)) {
      throw new Error(`Ground-truth CSV row ${index + 1}: invalid t_start_ms.`);
    }
    const tEndMsRaw = Number.parseFloat(row.t_end_ms ?? "");
    const tEndMs = Number.isFinite(tEndMsRaw) ? tEndMsRaw : tStartMs;

    return {
      tStartMs,
      tEndMs,
      label,
      subjectId: row.subject_id || undefined,
    };
  });

  const syncRow = rows.find((row) => row.label === "sync");

  return { rows, syncMarkerMs: syncRow ? syncRow.tStartMs : null };
}

/** True if a "present" interval covers tMs (half-open [start, end)). */
export function isGroundTruthPositiveAt(log: GroundTruthLog, tMs: number): boolean {
  return log.rows.some(
    (row) => row.label === "present" && tMs >= row.tStartMs && tMs < row.tEndMs,
  );
}

/** Trial time bounds implied by the ground-truth log (present + absent rows only). */
export function groundTruthTimeBounds(log: GroundTruthLog): { startMs: number; endMs: number } | null {
  const bounded = log.rows.filter((row) => row.label !== "sync");
  if (bounded.length === 0) return null;
  const starts = bounded.map((row) => row.tStartMs);
  const ends = bounded.map((row) => row.tEndMs);
  return { startMs: Math.min(...starts), endMs: Math.max(...ends) };
}
