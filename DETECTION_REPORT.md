# Detection Report

Generated: 2026-07-01T04:01:07+03:00

## Summary

No defensible target-detection number was produced in this pass. The software and authority contract are verified, but live hardware detection characterization did not start because no CSI or heartbeat packets arrived during the canonical authority dry run and `idf.py` is unavailable in this shell.

AI is currently available in advisory mode, but F1 still applies: `phantom.dsp` owns the deterministic `is_human` verdict. AI output cannot originate or flip the human/non-human decision.

## Trial Definition

A valid detection trial requires all of the following:

- Canonical Python authority owns UDP `5005`.
- Run uses `--no-synthetic`.
- `/api/sensing/frame` reports `authority:true`, `source:"live"`, and `synthetic_enabled:false`.
- Both expected nodes are fresh and source-pinned for dual-node metrics.
- Trial session JSONL under `data/sessions` is referenced.
- Deterministic gate reports `is_human=true` during a target-present window.
- Negative controls include empty room and fan/curtain motion without respiration periodicity.

## Current Measurement Status

| Metric | Status | Evidence |
|---|---:|---|
| Live CSI Hz, node 1 | [TO BE MEASURED] | No packet arrived on UDP `5005`; no source pinning for node 1. |
| Live CSI Hz, node 2 | [TO BE MEASURED] | No packet arrived on UDP `5005`; no source pinning for node 2. |
| Fused two-node mode | [TO BE MEASURED] | Requires both nodes fresh and temporally aligned. |
| Midpoint localization | [TO BE MEASURED] | Requires two live nodes on `[0,0]` to `[5,0]` baseline. |
| Drywall detection rate | [TO BE MEASURED] | Requires repeated live target-present and target-absent trials. |
| Empty-room false positive rate | [TO BE MEASURED] | Requires matched negative-control trials. |
| Fan/curtain rejection | [TO BE MEASURED] | Required stop-condition control was not run. |
| Respiration MAE | [TO BE MEASURED] | Requires reference respiration and at least 60 seconds per trial. |
| Heart-rate MAE | [TO BE MEASURED] | Gated on measured CSI Hz >= 4 Hz and synchronized pulse-ox reference. |

## Confusion Matrix

No live trials were executed, so the confusion matrix is not populated.

| Condition | TP | FP | TN | FN | Detection rate | Specificity | 95% Wilson CI |
|---|---:|---:|---:|---:|---:|---:|---|
| Drywall 10 cm | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] |
| Drywall 15 cm | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] |
| Hollow block 15 cm | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] |
| Solid concrete 20 cm | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] |

## Range / Geometry Sweep

| Range | Midpoint result | Off-axis result | Notes |
|---:|---|---|---|
| 1 m | [TO BE MEASURED] | [TO BE MEASURED] | Requires live two-node run. |
| 2 m | [TO BE MEASURED] | [TO BE MEASURED] | Requires live two-node run. |
| 3 m | [TO BE MEASURED] | [TO BE MEASURED] | Requires live two-node run. |

## Vitals

| Metric | Status | Notes |
|---|---:|---|
| Respiration BPM MAE | [TO BE MEASURED] | Primary vital; requires reference belt or counted breathing, >= 60 seconds per trial. |
| Heart-rate BPM MAE | [TO BE MEASURED] | Do not report unless per-node CSI Hz is >= 4 Hz; otherwise mark `rate-limited`. |

## Required Next Hardware Protocol

1. Restore ESP-IDF availability so `idf.py --version`, firmware build, flash, and provision steps work.
2. Start Python authority with `--no-synthetic` on UDP `5005` and API `8789`.
3. Confirm node 1 on COM5 source-pins and emits CSI for 60 seconds.
4. Confirm node 2 on COM6 source-pins independently and fused mode activates only when both nodes are fresh.
5. Record per-node CSI Hz from JSONL `csi_frame` counts.
6. Run midpoint sanity on the 5 m baseline.
7. Only then run target-present, empty-room, and fan/curtain trials with session JSONL references.

## Honesty Statement

Measured: no-synthetic dry-run behavior, authority API contract, software replay/tests, AI advisory readiness, COM port names, and missing ESP-IDF command.

Not measured: any live target-detection performance. All detection, specificity, wall-material, range, respiration, and heart-rate claims remain `[TO BE MEASURED]`.

Single-antenna caveat: live spatial output is limited to 1-D on-axis balance. AoA/MUSIC/ESPRIT remains synthetic-only unless future hardware provides a physically valid coherent array.
