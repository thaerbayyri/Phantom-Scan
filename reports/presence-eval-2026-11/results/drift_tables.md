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
