import * as fs from "fs";
import * as path from "path";
import { pathToFileURL } from "url";

type GroundTruthSource = "none" | "dwell" | "video";

export interface LiveCsvRow {
  [key: string]: string;
}

export interface GroundTruthTraceRow {
  t_ms: number;
  x_m: number;
  y_m: number;
  sync_marker?: 0 | 1;
  point_id?: string;
}

export interface JoinSummary {
  syncOffsetMs: number;
  liveRows: number;
  joinedRows: number;
}

export function joinGroundTruthRows(
  liveRows: LiveCsvRow[],
  traceRows: GroundTruthTraceRow[],
  syncOffsetMs?: number,
): { rows: LiveCsvRow[]; summary: JoinSummary } {
  if (traceRows.length === 0) {
    throw new Error("Ground-truth trace is empty.");
  }

  const resolvedOffsetMs = syncOffsetMs ?? resolveSyncOffsetMs(liveRows, traceRows);
  let joinedRows = 0;

  const rows = liveRows.map((row) => {
    const existingSource = (row.gt_source || "none") as GroundTruthSource;
    if (existingSource === "dwell" && row.gt_x_m && row.gt_y_m) {
      return row;
    }

    const sessionTsMs = Number.parseFloat(row.session_ts_ms || "");
    if (!Number.isFinite(sessionTsMs)) {
      return row;
    }

    const trace = findNearestTrace(traceRows, sessionTsMs + resolvedOffsetMs);
    if (!trace) {
      return row;
    }

    joinedRows += 1;
    return {
      ...row,
      gt_x_m: trimFloat(trace.x_m),
      gt_y_m: trimFloat(trace.y_m),
      gt_point_id: trace.point_id ?? row.gt_point_id ?? "",
      gt_source: "video",
    };
  });

  return {
    rows,
    summary: {
      syncOffsetMs: resolvedOffsetMs,
      liveRows: liveRows.length,
      joinedRows,
    },
  };
}

export function parseRecordingCsv(input: string): {
  metaLines: string[];
  header: string[];
  rows: LiveCsvRow[];
} {
  const lines = input
    .split(/\r?\n/)
    .filter((line) => line.length > 0);
  const metaLines = lines.filter((line) => line.startsWith("#"));
  const dataLines = lines.filter((line) => !line.startsWith("#"));
  if (dataLines.length === 0) {
    throw new Error("CSV has no header row.");
  }

  const header = parseCsvLine(dataLines[0]);
  const rows = dataLines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row: LiveCsvRow = {};
    header.forEach((key, index) => {
      row[key] = values[index] ?? "";
    });
    return row;
  });

  return { metaLines, header, rows };
}

export function serializeRecordingCsv(header: string[], rows: LiveCsvRow[], metaLines: string[] = []): string {
  const lines = [...metaLines, header.join(",")];
  for (const row of rows) {
    lines.push(header.map((key) => csvEscape(row[key] ?? "")).join(","));
  }
  return lines.join("\n");
}

function resolveSyncOffsetMs(
  liveRows: LiveCsvRow[],
  traceRows: GroundTruthTraceRow[],
): number {
  const liveSync = liveRows.find((row) => row.sync_marker === "1");
  const traceSync = traceRows.find((row) => row.sync_marker === 1);
  if (!liveSync || !traceSync) {
    throw new Error("Missing sync marker in live CSV or ground-truth trace; pass --sync-offset-ms.");
  }

  const liveTs = Number.parseFloat(liveSync.session_ts_ms || "");
  if (!Number.isFinite(liveTs)) {
    throw new Error("Live sync row is missing session_ts_ms.");
  }
  return traceSync.t_ms - liveTs;
}

function findNearestTrace(
  traceRows: GroundTruthTraceRow[],
  targetMs: number,
): GroundTruthTraceRow | null {
  let best: GroundTruthTraceRow | null = null;
  let bestDelta = Number.POSITIVE_INFINITY;
  for (const row of traceRows) {
    const delta = Math.abs(row.t_ms - targetMs);
    if (delta < bestDelta) {
      best = row;
      bestDelta = delta;
    }
  }
  return best;
}

function parseGroundTruthTrace(csvText: string): GroundTruthTraceRow[] {
  const { header, rows } = parseRecordingCsv(csvText);
  return rows.map((row) => {
    const trace: GroundTruthTraceRow = {
      t_ms: Number.parseFloat(row.t_ms || ""),
      x_m: Number.parseFloat(row.x_m || ""),
      y_m: Number.parseFloat(row.y_m || ""),
      point_id: row.point_id || undefined,
    };
    if (row.sync_marker === "1") {
      trace.sync_marker = 1;
    }
    if (!Number.isFinite(trace.t_ms) || !Number.isFinite(trace.x_m) || !Number.isFinite(trace.y_m)) {
      throw new Error(`Invalid ground-truth trace row for header ${header.join(",")}`);
    }
    return trace;
  });
}

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\"") {
      if (inQuotes && line[i + 1] === "\"") {
        current += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      values.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  values.push(current);
  return values;
}

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, "\"\"")}"`;
  }
  return value;
}

function trimFloat(value: number): string {
  return value.toFixed(6).replace(/\.?0+$/, "");
}

function parseArgs(argv: string[]) {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    args.set(key, argv[i + 1] ?? "");
    i += 1;
  }
  return args;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = parseArgs(process.argv.slice(2));
  const liveCsvPath = args.get("--csv");
  const tracePath = args.get("--trace");
  const outputPath = args.get("--out");
  const syncOffsetArg = args.get("--sync-offset-ms");

  if (!liveCsvPath || !tracePath || !outputPath) {
    console.error("Usage: tsx scripts/join-groundtruth.ts --csv <live.csv> --trace <trace.csv> --out <enriched.csv> [--sync-offset-ms <ms>]");
    process.exit(1);
  }

  const liveCsv = fs.readFileSync(path.resolve(liveCsvPath), "utf-8");
  const traceCsv = fs.readFileSync(path.resolve(tracePath), "utf-8");
  const parsedLive = parseRecordingCsv(liveCsv);
  const traceRows = parseGroundTruthTrace(traceCsv);
  const syncOffsetMs = syncOffsetArg ? Number.parseFloat(syncOffsetArg) : undefined;
  const { rows, summary } = joinGroundTruthRows(parsedLive.rows, traceRows, syncOffsetMs);
  const enriched = serializeRecordingCsv(parsedLive.header, rows, parsedLive.metaLines);

  fs.writeFileSync(path.resolve(outputPath), enriched, "utf-8");
  console.log(
    `[join-groundtruth] wrote ${summary.joinedRows}/${summary.liveRows} joined rows to ${outputPath} (sync offset ${summary.syncOffsetMs} ms)`,
  );
}
