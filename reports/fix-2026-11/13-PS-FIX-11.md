# PS-FIX-11 — calibration tooling that refuses to recommend from weak evidence

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv / Node (tsx). Backup: `.tmp/fix-backups/13-PS-FIX-11/calibrate-threshold.ts` (the file was unmodified in git). Patch: `patches/13-PS-FIX-11-calibrate-threshold.patch` (158 lines). Footprint: `results/footprint-13-PS-FIX-11.txt` (1 changed, 3 new files). Tests: `90-test-report.md` (TS 444/444, tsc 0 errors, F1/F2 3/3, AI-firewall 46/46). **No setting, threshold, constant or `data/runtime-settings.json` was touched; the tool cannot write one** (a test greps the code for that).

## What changed
* `scripts/accuracy/calibration-soak.ts` (new, pure, 12 tests): collects **10 s block maxima** per metric (`motion.fused` = max(node 1, node 2), `motion.n1…n4`, `roomZ`) plus per-node block RSSI/frame counts, and evaluates runs.
* `scripts/calibrate-threshold.ts` (edited): `--label empty|fan|occupied`, `--out <run.json>` (exclusive create, never overwrites), `--min-soak-minutes` (default 60), `--min-fan-minutes` (default 5), and an offline `--evaluate --empty a.json,b.json --fan f.json [--occupied w.json] [--target-fa-per-hour N]` (no socket, writes nothing; exit 0 = candidate allowed, 3 = refused).
  * A live **empty run shorter than 60 min, or fan shorter than 5 min, refuses to start** (exit 2) before binding any socket.
  * The old "suggested PHANTOM_MOTION_THRESHOLD mean+k·sigma" and "pick at least ceil(max+1) for PHANTOM_ROOM_TIER_STILL" lines are **removed**: a single run can no longer produce a recommendation. Descriptive statistics stay. The spatial-energy suggestion is kept but now says it is *not* drift- or pooling-checked.
* `scripts/accuracy/replay-calibration-runs.ts` (new, offline): replays a recording through the same `computeNodeMotionFromMatrix` into a run file, so the rules can be exercised on real data. Read-only on `data/datasets`.

## Rules (each refusal is named; a candidate is printed only when none fires)
| code | fires when |
|--|--|
| `soak-too-short` | empty soak < 60 min (configurable) |
| `no-negative-control` | no fan run, or < 5 min |
| `pooled-epochs` | a held RSSI step ≥ 6 dB (20 s hold) or frame-rate collapse ≤ 0.7× inside a run, a level change between consecutive runs, or runs on different calendar days |
| `drift` | empty-vs-empty control: the second half of the empty soak vs the first half, symmetric AUC upper bound > 0.65 (same definition as PS-EVAL C4) for any metric |
| `too-few-blocks` | < 100 held-out empty blocks for a metric |

When allowed: the candidate for each metric is chosen on the **first half** of the soak (the smallest value leaving ≤ target false alarms/hour, default 1/h); **percentiles, false alarms/hour (empty), false alarms/hour (fan) and misses (occupied) are reported on the held-out half / other runs, separately.** Misses are `[TO BE MEASURED]` unless an occupied run is supplied. "Candidate" is a number for you to consider, not a setting.

## Evidence
1. **Synthetic truth (12 tests):** clean 90 min + fan → allowed; 30 min, no/short fan, drift in the second half, a held RSSI step, a frame-rate collapse, a different calendar day, a level change between runs → each refused with its code; a one-block RSSI flicker is *not* a step; fan false alarms and occupied misses are reported separately; `--evaluate` writes no file; a short live run exits 2. **One real defect found by the tests and fixed:** a single persistent step was reported twice (the baseline window still straddled the step); the scan now skips one baseline window after a hit.
2. **Real data (replayed, `results/cal/`):** s8 (53 min empty) + s9 (12 min empty) as the soak, s5 fan (3.3 min), s7 walking as occupied.
   * Defaults: **refused** — `no-negative-control` (3.3 min), `pooled-epochs` (node 1 −36.0 → −47.0 dBm and 61.4 → 41.0 fps between the fan and the empty runs: the PS-EVAL-006 link change), `drift` (symmetric upper bounds 0.68–0.90 on all five metrics).
   * With the length rules relaxed, still **refused** for pooling and drift. s8 **alone** (relaxed) also **refused for drift** (0.75–0.91): the second half of the s8 empty recording scores *lower* than the first (AUC 0.17–0.36), the same empty-room drift already documented in PS-FIX-33. So on our existing recordings the tool correctly produces **no calibration number**.
   * This is a check that the rules fire on a real link change and real drift, **not** a threshold validation; nothing was applied.
3. `motion.n4` block maxima sit at 1.000 at p90–p99, i.e. node 4's motion metric looks saturated/clipped on these recordings `[UNVERIFIED]` (not investigated; it matters for any future per-node threshold).

## Limits / honesty
* The link-state rule is a **coarser, post-hoc** version of `epochs.py` (10 s blocks, 20 s hold, any step refuses). It was chosen by me, not specified.
* "Held-out" is the second half in time of one soak: it controls overfitting to the calibration half, not a different day or a different room state. The room being genuinely empty is operator-asserted and unverified (PS-EVAL-007).
* The `roomZ` metric reuses the production `NodeBaselineTracker`; during warm-up samples are skipped, as before.
* Docs that tell operators to "pick mean + k·sigma" (`docs/SPATIAL_CALIBRATION.md`, `MEASUREMENT_PLAN.md`, reports) were **not** edited in this item; they now disagree with the tool (ledger PS-FIX-38).
* Not run live: the dashboard owns UDP :5005 and I did not stop it or touch hardware; the live path (`--label … --out`) is covered only by the two CLI tests (evaluate, refusal), not by a capture `[UNVERIFIED]`.
