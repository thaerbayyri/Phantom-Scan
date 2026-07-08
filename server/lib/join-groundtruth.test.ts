import test from "node:test";
import assert from "node:assert/strict";
import {
  joinGroundTruthRows,
  parseRecordingCsv,
  serializeRecordingCsv,
} from "../../scripts/join-groundtruth";

test("join-groundtruth enriches live CSV rows via one sync marker and trace", () => {
  const liveCsv = [
    "# phantom_session_meta {\"session_name\":\"case-a\"}",
    "timestamp,session_ts_ms,sync_marker,x_disp_m,z_disp_m,gt_x_m,gt_y_m,gt_point_id,gt_source",
    "1000,0,0,-1.5,0,,,,none",
    "1500,500,1,0,0,,,,none",
    "2000,1000,0,1.5,0,,,,none",
  ].join("\n");

  const traceCsv = [
    "t_ms,x_m,y_m,sync_marker,point_id",
    "200,-1.4,0.1,0,N1",
    "700,0.1,0.2,1,MID",
    "1200,1.4,0.2,0,N2",
  ].join("\n");

  const parsedLive = parseRecordingCsv(liveCsv);
  const parsedTrace = parseRecordingCsv(traceCsv);
  const traceRows = parsedTrace.rows.map((row) => ({
    t_ms: Number.parseFloat(row.t_ms),
    x_m: Number.parseFloat(row.x_m),
    y_m: Number.parseFloat(row.y_m),
    sync_marker: row.sync_marker === "1" ? 1 as const : 0 as const,
    point_id: row.point_id || undefined,
  }));

  const { rows, summary } = joinGroundTruthRows(parsedLive.rows, traceRows);
  const enriched = serializeRecordingCsv(parsedLive.header, rows, parsedLive.metaLines);

  assert.equal(summary.syncOffsetMs, 200);
  assert.equal(summary.joinedRows, 3);
  assert.match(enriched, /gt_x_m,gt_y_m,gt_point_id,gt_source/);
  assert.match(enriched, /-1\.4,0\.1,N1,video/);
  assert.match(enriched, /0\.1,0\.2,MID,video/);
  assert.match(enriched, /1\.4,0\.2,N2,video/);
});
