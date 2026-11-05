# 02 — Independent reproduction of the exploratory numbers

**Provenance.** `python -m scripts.presence_eval.repro` — date 2026-11-02T18:49:16Z, commit `744ce43` (working tree dirty: True), eval code sha256[:16] `1e96defeec9de5cb`, Python 3.13.15, numpy 2.4.4. Inputs: the 14 recordings of `data/datasets/room1/` (file list in `results/reproduction.json`).
**Method.** 1.5 s tumbling windows per node, windows with < 20 frames dropped; features as defined in `scripts/presence_eval/features.py`; rank-based AUC with average ranks for ties; 95 % CI from a moving-block bootstrap (block = 7 windows = 10.5 s, 1000 resamples, fixed seed, resampled separately inside each class). The CI describes within-recording sampling variability only; it does not include between-session drift. In-sample, one subject, one evening (27 Oct). Positive = first recording named, negative = second.
**Tolerance.** `reproduces` = |measured − claimed| ≤ 0.05; `approx` ≤ 0.1; otherwise `does NOT reproduce`. Claimed values are the exploratory ones from the task brief; they were not used in any computation.

## Table A — section-2 claims

| row | feature / scope | claimed | measured AUC [95 % CI] | verdict | claim inside CI |
|--|--|--|--|--|--|
| C1 fused perturb, walking s7 vs empty s6 | perturb / fused4 | 0.53 | 0.52 [0.30, 0.70] | reproduces | yes |
| ↳ C1 fused perturb, walking s7 vs empty s6 — N1+N2 fused only | perturb / fused N1+N2 | – | 0.76 [0.64, 0.85] | extra | – |
| C1b fused decor, walking s7 vs empty s6 | decor / fused4 | 0.64 | 0.63 [0.45, 0.77] | reproduces | yes |
| ↳ C1b fused decor, walking s7 vs empty s6 — N1+N2 fused only | decor / fused N1+N2 | – | 1.00 [0.99, 1.00] | extra | – |
| C2 fused perturb, empty s8 vs empty s6 | perturb / fused4 | 1.00 | 1.00 [1.00, 1.00] | reproduces | yes |
| ↳ C2 fused perturb, empty s8 vs empty s6 — N1+N2 fused only | perturb / fused N1+N2 | – | 0.94 [0.91, 0.96] | extra | – |
| C2 fused decor, empty s8 vs empty s6 | decor / fused4 | 1.00 | 1.00 [0.99, 1.00] | reproduces | no |
| ↳ C2 fused decor, empty s8 vs empty s6 — N1+N2 fused only | decor / fused N1+N2 | – | 1.00 [1.00, 1.00] | extra | – |
| C2 fused perturb, empty s9 vs empty s6 | perturb / fused4 | 1.00 | 1.00 [1.00, 1.00] | reproduces | yes |
| ↳ C2 fused perturb, empty s9 vs empty s6 — N1+N2 fused only | perturb / fused N1+N2 | – | 0.97 [0.96, 0.98] | extra | – |
| C2 fused decor, empty s9 vs empty s6 | decor / fused4 | 1.00 | 1.00 [1.00, 1.00] | reproduces | yes |
| ↳ C2 fused decor, empty s9 vs empty s6 — N1+N2 fused only | decor / fused N1+N2 | – | 1.00 [1.00, 1.00] | extra | – |
| C2 fused perturb, empty s9 vs empty s8 | perturb / fused4 | 0.84 | 0.61 [0.55, 0.66] | does NOT reproduce | no |
| ↳ C2 fused perturb, empty s9 vs empty s8 — N1+N2 fused only | perturb / fused N1+N2 | – | 0.74 [0.69, 0.80] | extra | – |
| C2 fused decor, empty s9 vs empty s8 | decor / fused4 | 0.49 | 0.36 [0.31, 0.41] | does NOT reproduce | no |
| ↳ C2 fused decor, empty s9 vs empty s8 — N1+N2 fused only | decor / fused N1+N2 | – | 0.28 [0.23, 0.33] | extra | – |
| C3 N1 decor, walking s7 vs empty s6 | decor / 1 | 1.00 | 1.00 [0.99, 1.00] | reproduces | no |
| C3 N2 decor, walking s7 vs empty s6 | decor / 2 | 0.95 | 0.95 [0.91, 0.98] | reproduces | yes |
| C3 N3 decor, walking s7 vs empty s6 | decor / 3 | 0.45 | 0.45 [0.29, 0.61] | reproduces | yes |
| C3 N4 decor, walking s7 vs empty s6 | decor / 4 | 0.91 | 0.91 [0.87, 0.97] | reproduces | yes |
| C3 N1 decor, still s1 (27 Oct) vs empty s6 | decor / 1 | 0.92 | 0.92 [0.86, 0.97] | reproduces | yes |
| C3 N2 decor, still s1 (27 Oct) vs empty s6 | decor / 2 | 0.88 | 0.88 [0.79, 0.95] | reproduces | yes |
| C3 N3 decor, still s1 (27 Oct) vs empty s6 | decor / 3 | 0.35 | 0.35 [0.16, 0.52] | reproduces | yes |
| C3 N4 decor, still s1 (27 Oct) vs empty s6 | decor / 4 | 0.70 | 0.70 [0.58, 0.87] | reproduces | yes |
| C3 N1 decor, fan s5 vs empty s6 | decor / 1 | 0.42 | 0.42 [0.29, 0.53] | reproduces | yes |
| C3 N2 decor, fan s5 vs empty s6 | decor / 2 | 0.28 | 0.28 [0.17, 0.41] | reproduces | yes |
| C3 N3 decor, fan s5 vs empty s6 | decor / 3 | 0.02 | 0.02 [0.00, 0.03] | reproduces | yes |
| C3 N4 decor, fan s5 vs empty s6 | decor / 4 | 0.13 | 0.13 [0.05, 0.20] | reproduces | yes |

## Table B — every feature, every node, against empty s6 (positive = named recording)

| contrast | feature | N1 | N2 | N3 | N4 |
|--|--|--|--|--|--|
| walking s7 vs empty s6 | perturb | 0.74 [0.61, 0.84] | 0.75 [0.64, 0.83] | 0.66 [0.49, 0.80] | 0.49 [0.30, 0.68] |
| walking s7 vs empty s6 | perturb_agc | 0.77 [0.65, 0.86] | 0.75 [0.63, 0.82] | 0.67 [0.51, 0.81] | 0.52 [0.33, 0.71] |
| walking s7 vs empty s6 | decor | 1.00 [0.99, 1.00] | 0.95 [0.91, 0.98] | 0.45 [0.29, 0.61] | 0.91 [0.87, 0.97] |
| walking s7 vs empty s6 | gainstd | 0.70 [0.63, 0.76] | 0.67 [0.58, 0.75] | 0.51 [0.44, 0.60] | 0.47 [0.35, 0.58] |
| walking s7 vs empty s6 | rssistd | 0.63 [0.52, 0.74] | 0.40 [0.21, 0.53] | 0.36 [0.18, 0.51] | 0.09 [0.04, 0.14] |
| still s1 27Oct vs empty s6 | perturb | 0.84 [0.75, 0.93] | 0.78 [0.65, 0.89] | 0.82 [0.72, 0.91] | 0.74 [0.62, 0.92] |
| still s1 27Oct vs empty s6 | perturb_agc | 0.85 [0.77, 0.93] | 0.77 [0.63, 0.87] | 0.81 [0.71, 0.90] | 0.76 [0.65, 0.93] |
| still s1 27Oct vs empty s6 | decor | 0.92 [0.86, 0.97] | 0.88 [0.79, 0.95] | 0.35 [0.16, 0.52] | 0.70 [0.58, 0.87] |
| still s1 27Oct vs empty s6 | gainstd | 0.76 [0.64, 0.86] | 0.72 [0.59, 0.83] | 0.62 [0.46, 0.78] | 0.40 [0.29, 0.53] |
| still s1 27Oct vs empty s6 | rssistd | 0.82 [0.71, 0.93] | 0.70 [0.53, 0.86] | 0.44 [0.25, 0.61] | 0.18 [0.11, 0.30] |
| fan s5 vs empty s6 | perturb | 0.49 [0.38, 0.58] | 0.45 [0.35, 0.54] | 0.36 [0.25, 0.47] | 0.83 [0.76, 0.88] |
| fan s5 vs empty s6 | perturb_agc | 0.45 [0.34, 0.55] | 0.43 [0.32, 0.52] | 0.40 [0.29, 0.50] | 0.82 [0.75, 0.88] |
| fan s5 vs empty s6 | decor | 0.42 [0.29, 0.53] | 0.28 [0.17, 0.41] | 0.02 [0.00, 0.03] | 0.13 [0.05, 0.20] |
| fan s5 vs empty s6 | gainstd | 0.52 [0.44, 0.59] | 0.53 [0.44, 0.63] | 0.52 [0.43, 0.61] | 0.74 [0.67, 0.82] |
| fan s5 vs empty s6 | rssistd | 0.44 [0.31, 0.55] | 0.22 [0.10, 0.34] | 0.27 [0.14, 0.40] | 0.51 [0.42, 0.61] |
| empty s8 vs empty s6 | perturb | 0.81 [0.78, 0.84] | 0.91 [0.88, 0.94] | 0.97 [0.96, 0.98] | 1.00 [1.00, 1.00] |
| empty s8 vs empty s6 | perturb_agc | 0.92 [0.90, 0.94] | 0.88 [0.85, 0.92] | 0.98 [0.97, 0.98] | 1.00 [1.00, 1.00] |
| empty s8 vs empty s6 | decor | 1.00 [1.00, 1.00] | 0.88 [0.85, 0.91] | 0.71 [0.65, 0.76] | 1.00 [1.00, 1.00] |
| empty s8 vs empty s6 | gainstd | 0.18 [0.14, 0.20] | 0.49 [0.41, 0.55] | 0.58 [0.52, 0.64] | 0.97 [0.96, 0.98] |
| empty s8 vs empty s6 | rssistd | 0.00 [0.00, 0.00] | 0.57 [0.47, 0.65] | 0.77 [0.72, 0.81] | 0.25 [0.19, 0.29] |
| empty s9 vs empty s6 | perturb | 0.69 [0.62, 0.74] | 0.96 [0.94, 0.98] | 0.99 [0.98, 1.00] | 1.00 [1.00, 1.00] |
| empty s9 vs empty s6 | perturb_agc | 0.84 [0.80, 0.88] | 0.95 [0.93, 0.97] | 0.99 [0.98, 1.00] | 1.00 [1.00, 1.00] |
| empty s9 vs empty s6 | decor | 1.00 [1.00, 1.00] | 0.98 [0.96, 0.99] | 0.65 [0.55, 0.74] | 1.00 [1.00, 1.00] |
| empty s9 vs empty s6 | gainstd | 0.15 [0.11, 0.17] | 0.61 [0.52, 0.69] | 0.68 [0.62, 0.75] | 1.00 [1.00, 1.00] |
| empty s9 vs empty s6 | rssistd | 0.00 [0.00, 0.00] | 0.67 [0.54, 0.77] | 0.88 [0.83, 0.93] | 0.03 [0.01, 0.05] |

## Result summary

* 20 section-2 rows were compared: **18 reproduce** (|Δ| ≤ 0.05; most to the second decimal), **2 do NOT reproduce**. The two failures are both *empty s9 vs empty s8* (perturb: claimed 0.84, measured 0.61 [0.55, 0.66]; decor: claimed 0.49, measured 0.36 [0.31, 0.41]). Two further rows have a claimed value of 1.00 just outside a CI of [0.99, 1.00] (rounding of 0.997); these count as reproduced.
* **Possible reason for the two failures (ad-hoc check, not part of the reproducible tooling).** I split s8 at its eight part-file boundaries and computed AUC(s9 vs each s8 part), fused over four nodes. For perturb the eight values were 0.89, 0.69, 0.01, 0.00, 0.51, 0.98, 0.98, 0.99; for decor 0.30, 0.39, 0.04, 0.04, 0.83, 0.70, 0.22, 0.36. So "s9 vs s8" is not one number: it depends on which ~7 minutes of s8 are used, and the exploratory 0.84 may have used a subset. I cannot verify which subset `[UNVERIFIED]`. The systematic version of this analysis is in `03-drift.md`.

## What the reproduced numbers do and do not mean

1. **The score separated walking from empty on individual nodes, but the same score separated two empty recordings equally well.** Node 1 `decor`: walking s7 vs empty s6 = 1.00 [0.99, 1.00]; *empty* s8 vs empty s6 = 1.00 [1.00, 1.00]; *empty* s9 vs empty s6 = 1.00 [1.00, 1.00]. Fused-over-four-nodes `decor` is 1.00 for both empties versus s6 as well. An AUC against one adjacent empty reference therefore cannot tell "a person" from "the empty room changed" — that is exactly the failure mode T3/T4 test.
2. **Fused-over-four-nodes `perturb` is at chance for walking** (0.52 [0.30, 0.70]) because N3 and N4 dilute the max (`perturb` N4: 0.49, N3: 0.66). Restricting to N1+N2 gives 0.76 [0.64, 0.85] for perturb and 1.00 [0.99, 1.00] for decor on the same pair of recordings — but see point 1. "Fused" in the brief is not defined for the node set; both are reported.
3. **Node dependence is large.** `decor`: N3 shows no walking signal (0.45 [0.29, 0.61], still 0.35) while N1/N2/N4 do (≥ 0.88 for walking; still 0.92/0.88/0.70).
4. **The fan moves the scores in a node-dependent direction.** Fan s5 vs empty s6: `decor` AUC 0.28/0.02/0.13 on N2/N3/N4 (fan windows have *lower* decor than the empty reference), while `perturb` N4 = 0.83 [0.76, 0.88] and `gainstd` N4 = 0.74 [0.67, 0.82] (fan windows *higher*). Whether the fan is a ghost-target risk therefore depends on the feature and the node — not a general statement about "the fan".
5. `perturb` (raw) and `perturb_agc` (the repo's definition, per-frame mean normalisation, `server/lib/node-fusion.ts:331`) agree within 0.04 AUC in every walking/still/fan cell of Table B, but differ by 0.11 (s8 vs s6, N1: 0.81 vs 0.92) and 0.15 (s9 vs s6, N1: 0.69 vs 0.84) on node 1, whose gain shifted by about 11 dB. So the two definitions are not interchangeable once a node's gain changes; the brief's `perturb` is *not* the production metric (PS-EVAL-008).
6. `rssistd` and `gainstd` are not reliable presence cues here: `rssistd` is 0.00 on N1 for both s8 and s9 vs s6 (a pure effect of the −11 dB N1 shift) and ≤ 0.40 for walking on N2–N4.

## Limitations of this reproduction

In-sample; one subject; one evening; the negative class is a single 153 s recording (≈ 100 windows) recorded minutes before the positive; the block bootstrap resamples within each class independently and ignores between-recording variability; all emptiness labels are unverified (see 01-data-inventory.md §4). Tolerances (0.05 / 0.10) are my choice, stated before looking at the verdicts.

Tests: `tests/test_presence_eval_features.py` — gain invariance (window gain: perturb, perturb_agc, decor, gainstd; per-frame gain: decor and perturb_agc only — raw `perturb`/`gainstd` are asserted *not* invariant), constant signal → 0, monotone response to injected noise, AUC against hand-computed and brute-force values incl. ties, deterministic bootstrap, block-vs-iid width, windows < 20 frames dropped, fusion inner-join.
