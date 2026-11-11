> Point-in-time build report for the human-movement-detection accuracy
> harness. See `CURRENT_STATE.md`'s "Accuracy Harness" section for the short
> version and `MEASUREMENT_PLAN.md`/`REAL_TEST_REPORT.md` for the campaign
> this harness scores against.

# Accuracy Harness Report

## What was found before building (§0 of the build prompt)

- `scripts/join-groundtruth.ts` and `server/lib/join-groundtruth.test.ts`
  already exist and are still current. They join **position** ground truth
  (`t_ms,x_m,y_m,sync_marker,point_id`) onto a recording's `gt_x_m`/`gt_y_m`
  columns for the S3–S8 on-axis localization campaign. This is a different
  concern from **presence/absence** confusion-matrix scoring (recall, false
  positive rate) — the two do not overlap and neither supersedes the other.
  The new harness reuses `join-groundtruth.ts`'s `parseRecordingCsv` for
  generic CSV parsing (header/meta-line/row splitting) instead of
  re-implementing it.
- `scripts/calibrate-threshold.ts` already tunes `PHANTOM_MOTION_THRESHOLD`
  and `PHANTOM_SPATIAL_ENERGY_THRESHOLD`. The harness only *consumes* the
  resulting threshold value (as provenance metadata in every report) — it
  does not choose or re-tune a threshold.
- `MEASUREMENT_PLAN.md` and `REAL_TEST_REPORT.md` define the canonical P0–S8
  campaign, the `NODE_ANCHORS` geometry, and the 20 fps/node preflight gate
  the harness's precondition check reuses.
- `shared/schema.ts` has **no literal `is_human` field**. `TargetState.state`
  is the F1-owned deterministic verdict, an enum of
  `none | stale | idle | moving | degraded`. The harness's scoreable
  "is_human" verdict is `state === "idle" || state === "moving"` —
  `"degraded"` (single-node evidence, `target_visible` still `true`) is
  deliberately excluded from the positive verdict, matching the build
  prompt's own §4.3 rule ("a degraded label is still a miss for accuracy
  purposes, even though it's an honest UI label").
- `server/lib/recording-export.ts`'s `RECORDING_COLUMNS` CSV schema
  (`session_ts_ms`, `sync_marker`, `target_state`, `target_visible`,
  `node1_fps`, `node2_fps`, `node_mode`, …) is the replay-mode input format;
  it already carries everything the harness needs per row.
- No `/api/sync-marker` endpoint and no documented RSSI acceptance envelope
  exist anywhere in the repo. The harness does not invent either: live-mode
  sync relies on both the WS tap and `groundtruth-logger.ts` stamping events
  with the same host `Date.now()` clock (see `system-state-adapter.ts` doc),
  and RSSI is not gated (no threshold to gate against).

## What was built

```
scripts/accuracy/
  types.ts                    # MetricValue {value,status,evidence} contract
  ground-truth-adapter.ts     # parses operator-keypress/video presence CSV
  system-state-adapter.ts     # replay-CSV adapter + live read-only WS tap
  time-aligner.ts             # sync-marker offset/drift resolution, refuses without one
  confusion-scorer.ts         # 1 Hz majority-vote binning, TP/FP/FN/TN, derived metrics
  report-generator.ts         # trial + campaign reports, precondition gating
  run-accuracy-trial.ts       # CLI: --mode=replay|live --groundtruth=<path> --out=<dir>
  groundtruth-logger.ts       # minimal keypress logger (s=sync, p=toggle present, q=quit)
scripts/accuracy/__tests__/
  confusion-scorer.test.ts    # A1, A2, A3, A6
  time-aligner.test.ts        # offset/drift recovery, A4
  ground-truth-adapter.test.ts
  report-generator.test.ts    # A5, A7
```

`package.json`'s `test` script now includes
`scripts/accuracy/__tests__/**/*.test.ts` alongside the existing globs.

## Tests

All 16 new tests pass, alongside the full existing 223-test suite (239 total,
0 failures) via `npm test`. `npm run check` (tsc) is unaffected.

| Test | Covers |
|---|---|
| A1 synthetic perfect match | recall=1, FPR=0, F1=1 on matched present/absent regions |
| A2 synthetic all-miss | system all-negative during ground-truth-positive → recall=0, TP=0 |
| A3 stale-demotion counted as miss | a `"stale"` bin during ground-truth-positive scores FN, not excluded |
| A4 no sync marker → refusal | `resolveAlignment([])` throws `NoSyncMarkerError` with `TO_BE_MEASURED — no sync marker` |
| A5 precondition gating | fps<20/node and degraded-only trials excluded from campaign rollup with a named reason |
| A6 empty-room/negative-control invariant | 20 randomized trials against an all-negative ground truth assert TP is structurally always 0 |
| A7 report schema | every `DerivedMetrics` field enforced to carry `{value,status,evidence}`; `buildTrialReport` itself throws on a malformed metric |

## Smoke test

None of the 24 files in `recordings/*.csv` have paired ground truth, and all
are in the pre-`RECORDING_COLUMNS` raw-sample schema (`h1_re,h1_im,h2_re,h2_im,rssi`
only — no `target_state`/`sync_marker`/`target_visible`), so none are scoreable
by this harness as-is. **Stated plainly: there is no real recording to smoke-test
against yet.**

Instead, the full pipeline was smoke-tested end-to-end against a synthetic
recording+ground-truth pair (empty room 0–3s, subject present+moving 3–8s,
stale-demotion window 8–8.5s, empty 8.5–10s), generated in the session
scratchpad, not committed to the repo:

```
$ npx tsx scripts/accuracy/run-accuracy-trial.ts --mode=replay \
    --recording=<synthetic>.csv --groundtruth=<synthetic-gt>.csv \
    --threshold-source="smoke-test — synthetic data, not a real calibration run" \
    --out=<dir>
[run-accuracy-trial] wrote report to <dir> (preconditions PASS)
```

Result: TP=5, FP=0, FN=1, TN=3 over 9 bins — recall=0.833, precision=1.0,
F1=0.909, FPR=0.0, all `MEASURED`. The single FN bin correctly lands on the
8–8.5s stale-demotion window (confirms A3's behavior against real code, not
just the unit test). Refusal was also confirmed live: pointing the same
recording at a ground-truth file with no `sync` row prints
`TO_BE_MEASURED — no sync marker` and exits 1.

This run validates the software, per `MEASUREMENT_PLAN.md`'s own Honesty
Rule ("Synthetic, replay-only... dry runs do not graduate any headline
metric. They can only validate software behavior and measurement
procedure.") — it is not a measurement of Phantom Scan's real-world
detection accuracy.

## Current measured status

**`TO_BE_MEASURED`.** The harness works and is tested, but the S1–S8 campaign
in `REAL_TEST_REPORT.md` has not been run against a live human subject on the
two-node hardware, and no existing recording has paired ground truth. No
detection rate, false-positive rate, or detection-range number for Phantom
Scan exists yet — building this harness does not change that, and
`REAL_TEST_REPORT.md`/`MEASUREMENT_PLAN.md`/Chapter 7 should keep saying
`TO BE MEASURED` until an actual trial is recorded and scored through this
tool.
