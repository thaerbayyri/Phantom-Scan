# 03 — Drift characterisation (empty vs empty)

**Provenance.** `python -m scripts.presence_eval.drift`, 2026-11-02T18:49:19Z, commit `744ce43` (tree dirty: True), eval code `1e96defeec9de5cb`. Inputs: every recording labelled `empty` (and `empty_fan`, `walking` s7 for contrast) in `data/datasets/room1/`; listed in `results/drift.json`.
**Method.** Recordings cut into 300 s segments (all parts of s8/s9 included; segments with < 60 windows per node are absent for that node). For each pair of *empty* segments, rank AUC of one against the other. "Separable" means AUC ≤ 0.3 or ≥ 0.7; a node/feature is flagged DRIFT when ≥ 25 % of empty-vs-empty pairs are separable. These are reporting conventions chosen before the run, not detector thresholds. Segment-level AUCs have no CI here (the within-segment bootstrap does not cover the question being asked).
**Empty segments used:** 17.

## Table A — share of separable pairs (empty vs empty) against the walking and fan contrasts

| node / feature | empty-vs-empty pairs | separable | same-day | cross-day | flag | walking s7 vs empties: separable / detect-direction (AUC ≥ 0.7) | fan s5 vs empties: separable |
|--|--|--|--|--|--|--|--|
| N1/perturb | 136 | 51% | 37% | 100% | **DRIFT** | 24% / 12% | 71% |
| N1/perturb_agc | 136 | 54% | 41% | 100% | **DRIFT** | 29% / 6% | 88% |
| N1/decor | 136 | 57% | 45% | 100% | **DRIFT** | 94% / 6% | 94% |
| N1/gainstd | 136 | 32% | 13% | 97% | **DRIFT** | 88% / 88% | 82% |
| N1/rssistd | 136 | 76% | 71% | 97% | **DRIFT** | 88% / 82% | 88% |
| N2/perturb | 136 | 75% | 68% | 100% | **DRIFT** | 35% / 6% | 94% |
| N2/perturb_agc | 136 | 68% | 59% | 97% | **DRIFT** | 24% / 6% | 88% |
| N2/decor | 136 | 74% | 79% | 57% | **DRIFT** | 41% / 35% | 100% |
| N2/gainstd | 136 | 51% | 38% | 100% | **DRIFT** | 65% / 53% | 18% |
| N2/rssistd | 136 | 80% | 78% | 87% | **DRIFT** | 41% / 29% | 100% |
| N3/perturb | 136 | 81% | 78% | 90% | **DRIFT** | 65% / 0% | 94% |
| N3/perturb_agc | 136 | 81% | 80% | 83% | **DRIFT** | 65% / 0% | 94% |
| N3/decor | 136 | 76% | 76% | 73% | **DRIFT** | 53% / 18% | 94% |
| N3/gainstd | 136 | 59% | 52% | 83% | **DRIFT** | 35% / 12% | 35% |
| N3/rssistd | 136 | 83% | 78% | 100% | **DRIFT** | 65% / 12% | 94% |
| N4/perturb | 136 | 82% | 78% | 97% | **DRIFT** | 82% / 0% | 88% |
| N4/perturb_agc | 136 | 88% | 85% | 100% | **DRIFT** | 82% / 0% | 94% |
| N4/decor | 136 | 89% | 86% | 100% | **DRIFT** | 88% / 6% | 100% |
| N4/gainstd | 136 | 64% | 54% | 100% | **DRIFT** | 94% / 12% | 94% |
| N4/rssistd | 136 | 84% | 79% | 100% | **DRIFT** | 59% / 18% | 88% |

## Table B — 27 Oct: spread of empty-segment medians versus the walking effect (s7 minus s6)

| node / feature | range of empty-segment medians | walking shift (s7 − s6 median) | ratio range / |shift| |
|--|--|--|--|
| N1/perturb | 0.02904 | 0.007941 | 3.7 |
| N1/perturb_agc | 0.03902 | 0.008067 | 4.8 |
| N1/decor | 0.3508 | 0.05979 | 5.9 |
| N1/gainstd | 0.004874 | 0.002745 | 1.8 |
| N1/rssistd | 4.44 | 0.2693 | 16.5 |
| N2/perturb | 0.05556 | 0.009082 | 6.1 |
| N2/perturb_agc | 0.05321 | 0.00834 | 6.4 |
| N2/decor | 0.1487 | 0.05213 | 2.9 |
| N2/gainstd | 0.006456 | 0.00336 | 1.9 |
| N2/rssistd | 1.001 | -0.2885 | 3.5 |
| N3/perturb | 0.1459 | 0.01856 | 7.9 |
| N3/perturb_agc | 0.1391 | 0.02406 | 5.8 |
| N3/decor | 0.6422 | -0.02667 | 24.1 |
| N3/gainstd | 0.01126 | -9.991e-05 | 112.7 |
| N3/rssistd | 3.23 | -0.502 | 6.4 |
| N4/perturb | 0.2164 | -0.001198 | 180.6 |
| N4/perturb_agc | 0.2067 | 0.00325 | 63.6 |
| N4/decor | 0.86 | 0.1071 | 8.0 |
| N4/gainstd | 0.02096 | -0.001074 | 19.5 |
| N4/rssistd | 2.27 | -1.185 | 1.9 |

## Table C — Spearman correlation across empty segments: segment-median feature vs segment-median covariate

| node / feature | vs RSSI (rho, p, n) | vs mean amplitude (rho, p, n) |
|--|--|--|
| N1/perturb | +0.35, p=0.163, n=17 | -0.38, p=0.135, n=17 |
| N1/perturb_agc | +0.30, p=0.234, n=17 | -0.32, p=0.216, n=17 |
| N1/decor | +0.24, p=0.362, n=17 | -0.42, p=0.092, n=17 |
| N1/gainstd | +0.70, p=0.002, n=17 | -0.66, p=0.004, n=17 |
| N1/rssistd | +0.67, p=0.003, n=17 | -0.88, p=0.000, n=17 |
| N2/perturb | -0.10, p=0.698, n=17 | -0.72, p=0.001, n=17 |
| N2/perturb_agc | -0.12, p=0.635, n=17 | -0.72, p=0.001, n=17 |
| N2/decor | -0.69, p=0.002, n=17 | +0.29, p=0.256, n=17 |
| N2/gainstd | +0.30, p=0.237, n=17 | -0.81, p=0.000, n=17 |
| N2/rssistd | +0.53, p=0.028, n=17 | -0.03, p=0.903, n=17 |
| N3/perturb | -0.21, p=0.408, n=17 | -0.62, p=0.008, n=17 |
| N3/perturb_agc | -0.21, p=0.408, n=17 | -0.61, p=0.010, n=17 |
| N3/decor | -0.01, p=0.967, n=17 | -0.23, p=0.379, n=17 |
| N3/gainstd | +0.02, p=0.941, n=17 | -0.44, p=0.080, n=17 |
| N3/rssistd | +0.18, p=0.478, n=17 | -0.09, p=0.736, n=17 |
| N4/perturb | -0.51, p=0.036, n=17 | -0.72, p=0.001, n=17 |
| N4/perturb_agc | -0.54, p=0.025, n=17 | -0.63, p=0.006, n=17 |
| N4/decor | -0.41, p=0.102, n=17 | -0.65, p=0.004, n=17 |
| N4/gainstd | -0.36, p=0.159, n=17 | -0.28, p=0.273, n=17 |
| N4/rssistd | -0.31, p=0.225, n=17 | -0.25, p=0.333, n=17 |

## Table D — 27 Oct empty segments: segment medians over time (`decor`, `perturb_agc`; RSSI dBm; windows of 5 min)

| segment | N1 decor / agc / rssi | N2 decor / agc / rssi | N3 decor / agc / rssi | N4 decor / agc / rssi |
|--|--|--|--|--|
| s6_empty_1027_1942#0 | 0.081 / 0.0641 / -36 | 0.09 / 0.0641 / -27 | 0.282 / 0.0825 / -49 | 0.162 / 0.107 / -44 |
| s8_empty_1027_1953#0 | 0.361 / 0.0954 / -47 | 0.173 / 0.084 / -29 | 0.731 / 0.196 / -50 | 0.669 / 0.238 / -46 |
| s8_empty_1027_1953#1 | 0.361 / 0.0923 / -47 | 0.239 / 0.0819 / -29 | 0.71 / 0.19 / -50 | 0.695 / 0.236 / -46 |
| s8_empty_1027_1953#2 | 0.409 / 0.093 / -47 | 0.133 / 0.0822 / -29 | 0.371 / 0.161 / -50 | 0.701 / 0.262 / -47 |
| s8_empty_1027_1953#3 | 0.373 / 0.0933 / -47 | 0.098 / 0.0919 / -29 | 0.299 / 0.175 / -50 | 1.02 / 0.313 / -46 |
| s8_empty_1027_1953#4 | 0.332 / 0.0938 / -46 | 0.102 / 0.0905 / -28 | 0.295 / 0.178 / -50 | 0.975 / 0.314 / -46 |
| s8_empty_1027_1953#5 | 0.37 / 0.1 / -47 | 0.106 / 0.0912 / -28 | 0.254 / 0.17 / -50 | 0.817 / 0.301 / -46 |
| s8_empty_1027_1953#6 | 0.432 / 0.103 / -47 | 0.0919 / 0.0697 / -28 | 0.142 / 0.105 / -49 | 0.458 / 0.247 / -47 |
| s8_empty_1027_1953#7 | 0.353 / 0.0869 / -47 | 0.14 / 0.0719 / -29 | 0.502 / 0.168 / -49 | 0.41 / 0.215 / -47 |
| s8_empty_1027_1953#8 | 0.325 / 0.083 / -47 | 0.173 / 0.0738 / -29 | 0.76 / 0.183 / -49.5 | 0.405 / 0.211 / -46 |
| s8_empty_1027_1953#9 | 0.283 / 0.0754 / -47 | 0.168 / 0.0763 / -29 | 0.784 / 0.186 / -50 | 0.408 / 0.22 / -46 |
| s8_empty_1027_1953#10 | 0.272 / 0.0784 / -47 | 0.166 / 0.0874 / -29 | 0.714 / 0.191 / -50 | 0.407 / 0.22 / -45 |
| s9_empty_1027_2047#0 | 0.183 / 0.0727 / -47 | 0.158 / 0.117 / -28 | 0.522 / 0.222 / -51 | 0.754 / 0.234 / -45 |
| s9_empty_1027_2047#1 | 0.325 / 0.0918 / -47 | 0.124 / 0.0943 / -28 | 0.287 / 0.173 / -50 | 0.666 / 0.264 / -46 |
| s9_empty_1027_2047#2 | 0.317 / 0.0941 / -47 | 0.111 / 0.0792 / -28 | 0.211 / 0.138 / -50 | 0.573 / 0.265 / -47 |

## Table E — cross-node correlation of window scores inside the long empties (60 s running median removed)

| recording / feature | N1-N2 | N1-N3 | N1-N4 | N2-N3 | N2-N4 | N3-N4 |
|--|--|--|--|--|--|--|
| s8/decor | +0.07 | -0.15 | +0.00 | +0.12 | -0.01 | -0.04 |
| s8/perturb_agc | +0.18 | +0.02 | +0.01 | +0.24 | +0.15 | +0.04 |
| s9/decor | +0.08 | -0.09 | -0.06 | +0.20 | +0.02 | +0.07 |
| s9/perturb_agc | +0.08 | -0.02 | -0.00 | +0.25 | +0.08 | -0.02 |

## Findings (measured)

1. **Every one of the 20 node × feature cells is flagged DRIFT.** Of the 136 pairs of the 17 empty segments (two 18 Oct recordings, s6, s8 incl. all 8 parts, s9 incl. both parts), 32 %–89 % are separable (AUC ≤ 0.3 or ≥ 0.7). Restricting to pairs from the *same evening* (27 Oct) still gives 13 %–86 %. The best case is N1 `gainstd` (13 % same-day) and the worst N4 `decor` (86 %).
2. **The spread among empty segments exceeds the walking effect in all 20 cells.** Table B: range of the 27 Oct empty-segment medians divided by the walking shift (s7 − s6 median) is between 1.8× (N1 `gainstd`) and 181× (N4 `perturb`); for `decor` it is 5.9× (N1), 2.9× (N2), 24× (N3), 8.0× (N4). For N3 `decor` and N4 `perturb` the walking median is even *below* the s6 reference.
3. **The reference s6 is the quietest empty on every node** (Table D: e.g. N4 decor 0.16 in s6 versus 0.41–1.02 in s8/s9). Against typical empty segments, walking s7 is in the detect direction (AUC ≥ 0.7) in only 0–12 % of comparisons for `perturb`/`perturb_agc` on all nodes, 6 %/35 %/18 %/6 % for `decor` on N1–N4. (N1 `gainstd`/`rssistd` show 88 %/82 %, but N1's RSSI differs by 11 dB between s7 and most empties, so those are not interpretable as detection.)
4. **The fan recording is as separable from the empties as the empties are from each other** (separable in 18 %–100 % of comparisons per cell), so no cell shows a fan-vs-empty effect distinguishable from drift either.
5. **Drift is not confined to node 1.** N1 has the RSSI step between s7 and s8 (−36 → −47 dBm), but N3 (−49 → −50 dBm) and N4 (−44 → −46/−47 dBm) show the largest `decor` and `perturb_agc` changes (N3 decor 0.28 → 0.73; N4 decor 0.16 → 0.67) with RSSI essentially constant.
6. **Drift is slow and node-specific.** Within s8 (53 min) N4 `decor` rises 0.67 → 1.02 over the first 15 min and falls to 0.41 by the last 20 min; N3 `decor` goes 0.73 → 0.14 → 0.78. Window-level scores are essentially uncorrelated across nodes after removing a 60 s running median (Table E: |ρ| ≤ 0.25 for every node pair in s8 and s9).
7. **Amplitude and relative perturbation move inversely.** Across the 17 empty segments, segment-median `perturb` correlates with segment-median mean amplitude at ρ = −0.72 (N2, p = 0.001), −0.62 (N3, p = 0.008) and −0.72 (N4, p = 0.001), n = 17. Inside s8, N4's mean amplitude dips from 13.1 to 12.4 in segments #3–#4 exactly where N4 `decor` peaks (1.02/0.975) with RSSI flat (−46). (Segments inside one recording are autocorrelated, so these p-values are optimistic; treat them as direction only.)

## Candidate causes, ranked by evidence (no cause is established)

| rank | candidate | supporting observation | refuting / limiting observation | measurement that would settle it |
|--|--|--|--|--|
| 1 | **Per-link gain / fading state changing over minutes** (receiver gain control, multipath, link margin) | Finding 7 (perturb ↔ mean amplitude, ρ ≈ −0.7 on N2/N3/N4); N4 amplitude dip coincides with N4 decor peak at constant RSSI; node-independent fluctuations (Finding 6) | `perturb_agc`, which removes per-frame gain, drifts too (N4 segment medians 0.238 at #0, 0.314 at #4, 0.211 at #8 in s8), so it is not only a gain scale; AGC state is not recorded | Log the receive gain / AGC register (or fix gain) and noise floor per frame; repeat a 60 min empty with the gain recorded |
| 2 | **Node 1 moved, rotated or obstructed** between s7 and s8, restored before s10 | N1 only: RSSI −36 → −47 → −38 dBm and frame rate 65 → 38 → 66 fps, all within ≤ 5 min of s7/s8 and s9/s10 boundaries | Explains N1 only; N3/N4 drifted without any RSSI change; N1's frame rate partly recovered inside s8 while RSSI did not | Tape-marked node positions, photographs before/after each recording, continuous per-node RSSI log; deliberately displace N1 by 20 cm as a positive control |
| 3 | **Room not actually empty** (person in adjacent room/corridor, door movement, pets, other devices) | None directly; only a note on #4 asserts emptiness; no operator log for s8/s9 | Detrended cross-node correlations ≈ 0 (a person moving in the room would normally co-elevate several links — not proven for a person near one node only); no episodic bursts visible at segment level | A timestamped operator/door-sensor log, or a camera/PIR as independent ground truth during an unattended empty soak |
| 4 | **Thermal / warm-up of the radio** | s8 segments #0–#1 (first 10 min) have high N3/N4 decor (0.73/0.71/0.67/0.70) that falls later | Not monotonic: N3 decor rises again to 0.78 at #9; N4 peaks at #3–#4, not at the start | Cold-start recordings (power-cycle, record 60 min) versus pre-warmed nodes |
| 5 | **Channel / firmware / configuration change** | Cross-day pairs are the most separable (57 %–100 %); the 17 Oct recording is clearly pre-fix firmware (11 fps) | Headers carry no channel, firmware hash or sdkconfig; all 27 Oct recordings were made within 2 h on presumably identical firmware `[UNVERIFIED]`; same-day drift is already large | Store firmware git hash, channel and AP BSSID in every dataset header |
| 6 | **Different recorder path** (headless Python vs dashboard TS) | Only recording #4 (18 Oct) was written by the Python recorder | Cannot explain 27 Oct drift (all TS recorder) | n/a for same-day drift |

## What this means for the rest of the evaluation

A presence score calibrated on one empty reference cannot be expected to remain calibrated: in these data, two recordings labelled *empty* differ by more than an occupied recording differs from an empty one, on every node and feature tried. Protocols that use an *adjacent* empty (T4 (a)) will look good because adjacency hides drift; protocols that do not (T4 (b), (c)) are the ones that matter. Drift is reported as a result, not corrected for.

## Limitations

17 segments from 5 recordings; the segment grid (300 s) and the "separable" band (0.3/0.7) are reporting choices; segments within a recording are not independent; no CI on segment AUCs; labels of emptiness are unverified, so "drift" and "occupant I do not know about" are not distinguishable from this data alone; Spearman p-values are optimistic.

Tests: `tests/test_presence_eval_drift.py` — a synthetic baseline shift between two "empty" recordings is flagged DRIFT with the shifted pair at AUC ≈ 0/1 and a ratio > 1 against the walking effect; no shift → no flag; a segment/node with too few windows is absent (never zero-filled); cross-node correlation separates common events from independent drift.
