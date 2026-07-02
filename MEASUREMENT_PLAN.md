# Measurement Plan

All metrics in this file are `[TO BE MEASURED]` until a real two-node run records them.

## Required Artifacts

- Python authority JSONL session file from `data/sessions`.
- `GET /api/status` and `GET /api/sensing/frame` snapshots before, during, and after the run.
- CSV or notes with node timestamps for CSI rate.
- Photos or notes describing node placement and wall/target setup.
- Reference respiration and heart-rate readings when vital metrics are measured.

## CSI Rate Over 60 Seconds

1. Start the canonical authority-owned run from `RUN.md`.
2. Confirm both node IDs appear in `source_pinning`.
3. Record packet counts per node over 60 seconds from JSONL `csi_frame` records.
4. Compute per-node Hz as `frame_count / 60`.
5. Record actual values; do not assume 100 Hz.

Result: `[TO BE MEASURED]`

## Midpoint Localization on 3 m Centered Axis

Coordinate convention (single source of truth: `NODE_ANCHORS` in `shared/schema.ts`):
node 1 at `[-1.5, 0]`, node 2 at `[+1.5, 0]` — 3 m separation, origin at the center
(midpoint), matching the radar render and the dashboard fusion path.

1. Place node 1 at `[-1.5, 0]` and node 2 at `[+1.5, 0]` (3 m apart, centered).
2. Place the target at the midpoint.
3. Run the dashboard fusion path (`fused_two_node`) with both nodes fresh.
4. Record fused `balance`, `x`, and node mode.
5. Pass criterion for the synthetic unit test is `balance ~= 0.5 -> x ~= 0 m` (midpoint is
   ~1.5 m from each node); live hardware tolerance is `[TO BE MEASURED]`.
   Negative control: an empty room / on-axis fan must yield **no target** (motion below the
   calibrated `PHANTOM_MOTION_THRESHOLD`), not a centered ghost.

Result: `[TO BE MEASURED]`

## Drywall Detection

1. Place one person behind the selected drywall test surface.
2. Record a no-person baseline first.
3. Record a target-present interval.
4. Compare deterministic motion/respiration gate output and target visibility.
5. Detection rate remains `[TO BE MEASURED]` until repeated trials are run.

Result: `[TO BE MEASURED]`

## Respiration Accuracy

1. Use a reference respiration belt or manual counted breathing interval.
2. Record at least 60 seconds per trial.
3. Compare deterministic respiration BPM to the reference.
4. Report mean absolute error and trial count.

Result: `[TO BE MEASURED]`

## Heart-Rate Accuracy

1. Use a pulse oximeter or equivalent reference.
2. Record synchronized reference BPM and Phantom output.
3. Report mean absolute error and trial count.

Result: `[TO BE MEASURED]`

## Honesty Rule

Synthetic, replay-only, single-node, or no-packet dry runs do not graduate any headline metric. They can only validate software behavior and measurement procedure.
