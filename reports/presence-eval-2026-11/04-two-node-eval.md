# 04 — Two-node (N1 + N2) evaluation

**Provenance.** `python -m scripts.presence_eval.twonode` + `npx tsx scripts/presence_eval/ref_two_node.ts`, 2026-11-02T18:50:01Z, commit `744ce43` (working tree dirty: True), eval code sha256[:16] `1e96defeec9de5cb`, Python 3.13.15, numpy 2.4.4. Inputs: the 14 recordings of `data/datasets/room1/` (listed in `results/two_node_eval.json`); config `config/room.json` (N1 (−2,−3), N2 (2,−3): both on the z = −3 baseline axis, 4 m apart; router at N2's anchor). The brief says the July rig used 3 m `[UNVERIFIED: not checked in this session]`.

## 1. Pre-registered acceptance criteria (frozen before the T4 numbers)

Written by `python -m scripts.presence_eval.twonode --write-prereg` to `results/preregistered_criteria.json` (its file time precedes `two_node_eval.json`) **before** the evaluation was run. They are **proposals for Thaer to confirm or change**; they follow the brief. Honest caveat: I had already seen the T2/T3 results (drift) when freezing them; I had not seen any T4 number.

* **C1** lower 95 % block-bootstrap CI bound of walking-vs-empty AUC ≥ 0.80 in protocol (b) **and** in every applicable train session of protocol (c);
* **C2** fan false-positive rate not above the empty false-positive rate (pooled, at α = 1 % and 5 %) in (b) and (c);
* **C3** no held-out empty recording flagged occupied in more than 5 % of its windows at the α = 1 % threshold, in (b) and (c);
* a candidate meets the criteria only if C1, C2 and C3 all hold; **if none does, this report says "no candidate met the criteria" and stops.**

## 2. Method (what the numbers mean)

* Windows: 1.5 s tumbling, ≥ 20 frames, N1 and N2 both present (inner join; no zero-filling). 15 candidates = {perturb, perturb_agc, decor} × {N1 only, N2 only, max (≡ OR), mean, AND (≡ min)}. Per-node score = robust z against that node's own *training-empty* windows (median / 1.4826·MAD). `decor` is a temporal signal feature, **not** a spatial angle.
* **Threshold** for a target false-positive rate α ∈ {1 %, 5 %} = the (1 − α) quantile of the fused *training-empty* scores. `fit_model(train, feature, rule)` takes only training recordings (non-empty recordings raise `LeakageError`); the test recording is not an argument. `tests/test_presence_eval_twonode.py` proves this (signature, corrupted-test-recording invariance, split disjointness).
* Protocols: **(a) adjacent-empty** — baseline = nearest-in-time *other* empty of the same evening (reported two ways: in-sample vs the baseline itself, and vs the other same-evening empties); **(b) leave-one-recording-out** — baseline/threshold from all *other* empty recordings; **(c) cross-session** — baseline from all empties of one day, tested on recordings of the other days (train 18 Oct → test 25/27 Oct, and train 27 Oct → test 18/25 Oct).
* Positive classes: walking (s7 only — the 17 Oct walking file has ≈ 11 fps and yields no windows), still (s2 25 Oct, s1 27 Oct, s10), fan (s5, s1 18 Oct) as a negative control for ghost targets. two_people recordings are not used for the verdicts.
* CIs: moving-block bootstrap (7-window = 10.5 s blocks, 500 resamples, fixed seed) for every AUC and rate. They cover within-recording sampling variability only. Every cell with < 60 windows in a class reports "insufficient data".
* Time-to-first-detect is in `results/two_node_eval.json` (`ttfd_s`; single-window and 2-consecutive-window variants; seconds from the recording's window-grid origin; operator onset is unknown). It is one event per recording, so it has no CI.

## 3. Result: no candidate met the criteria

### 3.1 Candidates (block-bootstrap 95 % CIs in brackets)

| candidate | (a) walking AUC in-sample vs s6 | (b) LORO walking AUC | (b) still AUC | (b) walking TPR@1% / @5% | (c) train-18-Oct walking AUC | (c) walking TPR@1% | (b) empty FPR@1% | (c) empty FPR@1% (18→27 Oct) | (b) fan FPR@1% | worst held-out empty flag share (b) / (c) | C1 | C2 | C3 |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| perturb/n1 | 0.74 [0.62, 0.84] | 0.58 [0.45, 0.68] | 0.66 [0.60, 0.72] | 16% [7, 25] / 23% [12, 32] | 0.62 [0.51, 0.71] | 11% [4, 17] | 4% [2, 5] | 0% [0, 0] | 0% [0, 0] | 50% / 100% | FAIL | pass | FAIL |
| perturb/n2 | 0.75 [0.65, 0.84] | 0.57 [0.45, 0.67] | 0.81 [0.75, 0.86] | 2% [0, 6] / 4% [1, 10] | 0.58 [0.45, 0.69] | 1% [0, 2] | 2% [2, 3] | 0% [0, 0] | 0% [0, 1] | 25% / 99% | FAIL | pass | FAIL |
| perturb/max | 0.76 [0.65, 0.86] | 0.59 [0.46, 0.71] | 0.84 [0.79, 0.89] | 11% [4, 17] / 17% [8, 25] | 0.60 [0.46, 0.71] | 11% [4, 17] | 2% [2, 3] | 0% [0, 0] | 0% [0, 1] | 24% / 100% | FAIL | pass | FAIL |
| perturb/mean | 0.76 [0.65, 0.85] | 0.58 [0.44, 0.69] | 0.82 [0.76, 0.87] | 7% [2, 14] / 14% [6, 22] | 0.60 [0.46, 0.71] | 5% [0, 12] | 3% [2, 4] | 0% [0, 0] | 0% [0, 0] | 34% / 100% | FAIL | pass | FAIL |
| perturb/and | 0.74 [0.63, 0.84] | 0.56 [0.44, 0.66] | 0.73 [0.67, 0.78] | 2% [0, 6] / 8% [3, 13] | 0.61 [0.49, 0.70] | 1% [0, 3] | 4% [2, 5] | 0% [0, 0] | 0% [0, 0] | 54% / 100% | FAIL | pass | FAIL |
| perturb_agc/n1 | 0.77 [0.66, 0.86] | 0.51 [0.36, 0.62] | 0.55 [0.48, 0.62] | 14% [6, 21] / 21% [10, 29] | 0.55 [0.42, 0.64] | 7% [2, 14] | 4% [2, 5] | 0% [0, 0] | 0% [0, 0] | 51% / 100% | FAIL | pass | FAIL |
| perturb_agc/n2 | 0.75 [0.64, 0.83] | 0.65 [0.54, 0.74] | 0.85 [0.80, 0.90] | 12% [4, 19] / 26% [14, 36] | 0.60 [0.46, 0.70] | 5% [2, 10] | 3% [2, 4] | 0% [0, 0] | 10% [6, 15] | 40% / 63% | FAIL | FAIL | FAIL |
| perturb_agc/max | 0.77 [0.66, 0.86] | 0.58 [0.44, 0.70] | 0.83 [0.78, 0.88] | 19% [10, 28] / 28% [16, 37] | 0.60 [0.46, 0.71] | 10% [3, 16] | 3% [2, 4] | 0% [0, 0] | 4% [2, 7] | 39% / 100% | FAIL | FAIL | FAIL |
| perturb_agc/mean | 0.77 [0.65, 0.86] | 0.59 [0.45, 0.71] | 0.83 [0.77, 0.88] | 15% [7, 22] / 23% [12, 31] | 0.57 [0.43, 0.68] | 11% [4, 17] | 3% [2, 4] | 0% [0, 0] | 1% [0, 3] | 46% / 100% | FAIL | pass | FAIL |
| perturb_agc/and | 0.76 [0.65, 0.84] | 0.60 [0.48, 0.69] | 0.72 [0.66, 0.77] | 7% [2, 12] / 16% [8, 23] | 0.55 [0.42, 0.64] | 3% [0, 6] | 3% [2, 5] | 0% [0, 0] | 0% [0, 1] | 48% / 92% | FAIL | pass | FAIL |
| decor/n1 | 1.00 [0.99, 1.00] | 0.15 [0.09, 0.20] | 0.37 [0.30, 0.45] | 0% [0, 0] / 0% [0, 0] | 0.17 [0.10, 0.23] | 0% [0, 0] | 3% [1, 4] | 0% [0, 0] | 0% [0, 0] | 80% / 100% | FAIL | pass | FAIL |
| decor/n2 | 0.95 [0.91, 0.98] | 0.68 [0.59, 0.75] | 0.84 [0.78, 0.89] | 24% [14, 33] / 35% [22, 46] | 0.70 [0.61, 0.77] | 16% [8, 22] | 1% [0, 1] | 0% [0, 0] | 42% [30, 55] | 7% / 8% | FAIL | FAIL | FAIL |
| decor/max | 1.00 [1.00, 1.00] | 0.51 [0.39, 0.60] | 0.77 [0.70, 0.84] | 2% [0, 5] / 3% [0, 6] | 0.70 [0.61, 0.77] | 16% [8, 22] | 3% [1, 4] | 0% [0, 0] | 0% [0, 1] | 80% / 100% | FAIL | pass | FAIL |
| decor/mean | 1.00 [0.99, 1.00] | 0.42 [0.31, 0.51] | 0.73 [0.66, 0.81] | 2% [0, 5] / 4% [1, 7] | 0.43 [0.32, 0.52] | 1% [0, 3] | 2% [1, 3] | 0% [0, 0] | 0% [0, 0] | 56% / 100% | FAIL | pass | FAIL |
| decor/and | 0.97 [0.93, 0.99] | 0.22 [0.14, 0.29] | 0.50 [0.42, 0.57] | 0% [0, 1] / 3% [0, 6] | 0.17 [0.10, 0.23] | 0% [0, 0] | 1% [1, 2] | 0% [0, 0] | 0% [0, 0] | 16% / 30% | FAIL | pass | FAIL |

### 3.2 Repo reference (TypeScript, nodes 1+2)

| protocol | calibrated on | tested on (label) | s | occupied ticks (tier ≥ still) | still / moving / active | first occupied tick (s) | legacy `fuseTwoNodeTarget` target ticks (gate 0.6) |
|--|--|--|--|--|--|--|--|
| adjacent_same_evening | s6__empty | s7__walking (walking) | 212 | 37.0% | 13.6 / 21.6 / 1.8% | 1.2 | 12.6% |
| adjacent_same_evening | s6__empty | s1__still__20261027 (still) | 94 | 56.1% | 13.7 / 34.0 / 8.4% | 1.5 | 10.1% |
| adjacent_same_evening | s6__empty | s5__empty_fan (empty_fan) | 202 | 9.0% | 7.3 / 1.7 / 0.0% | 87.05 | 0.6% |
| adjacent_same_evening | s6__empty | s8__empty (empty) | 3209 | 6.3% | 2.1 / 2.9 / 1.4% | 1.2 | 1.1% |
| adjacent_same_evening | s6__empty | s9__empty (empty) | 723 | 53.8% | 12.1 / 41.7 / 0.0% | 1.2 | 1.2% |
| adjacent_same_evening | s9__empty | s10__still (still) | 363 | 79.9% | 1.6 / 42.5 / 35.9% | 1.2 | 78.7% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s7__walking (walking) | 212 | 1.1% | 1.1 / 0.0 / 0.0% | 127.95 | 12.6% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s2__still (still) | 228 | 21.8% | 16.0 / 5.9 / 0.0% | 3.75 | 46.7% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s1__still__20261027 (still) | 94 | 0.0% | 0.0 / 0.0 / 0.0% | never | 10.1% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s10__still (still) | 363 | 19.1% | 5.1 / 12.8 / 1.3% | 1.35 | 78.7% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s5__empty_fan (empty_fan) | 202 | 0.0% | 0.0 / 0.0 / 0.0% | never | 0.6% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s6__empty (empty) | 153 | 0.0% | 0.0 / 0.0 / 0.0% | never | 0.0% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s8__empty (empty) | 3209 | 0.7% | 0.7 / 0.0 / 0.0% | 560.2 | 1.1% |
| cross_session_from_18Oct_empty | s1__empty__20261018T180250Z | s9__empty (empty) | 723 | 0.3% | 0.3 / 0.0 / 0.0% | 257.95 | 1.2% |


Reading the candidate table: **C1 fails for all 15** (best lower CI bound in (b): 0.59 for decor/N2 [AUC 0.68]; in (c) train-18-Oct: 0.61 for decor/N2 and decor/max [AUC 0.70]); **C3 fails for all 15**; **C2 fails for 3** (decor/N2: fan FPR 42 % vs empty 1 %; perturb_agc/N2: 10 %; perturb_agc/max: 4 %). "(a) in-sample" is the exploratory-style number (walking vs the adjacent empty s6 it was calibrated on) and is high; every held-out number is far lower. In the last-but-three column, the (c) worst-case share is the maximum over both train sessions.

## 4. Both failure directions

**Under-detection (walking, still).** Best held-out walking TPR at the α = 1 % / 5 % thresholds in (b) is 24 % / 35 % (decor/N2) and 19 % / 28 % (perturb_agc/max); for several candidates it is 0–2 %. In (c) (train 18 Oct) walking TPR at 1 % is ≤ 16 %. The repo's own tier logic detects walking in 37 % of ticks when calibrated on the adjacent s6, but only 1.1 % when calibrated on the 18 Oct empty (first occupied tick after 128 s).

**Ghost targets (empty, fan, drifted empties).** Pooled empty FPR is near its design value in (b) (1–4 %), but *individual held-out empties* are far from it: up to 80 % flagged (decor/N1, decor/max) and 50–54 % (perturb/N1, perturb/AND) in (b). In (c), a baseline trained on the 27 Oct empties flags both 18 Oct empties in 100 % of windows (shown for decor/max; ≥ 99 % worst-case for 11 of 15 candidates), while the 18 Oct-trained baseline flags none of the 27 Oct empties (0 %). The repo's tier logic calibrated on the adjacent s6 marks the empty **s9 recording occupied in 53.8 % of ticks** (s8: 6.3 %, fan s5: 9.0 %). Adjacent in-sample decor/max AUC for walking is 1.00, yet against the other same-evening empty (s8) it is 0.20 and s8 is flagged in 100 % of windows: adjacency makes drift invisible.

**Trade-off.** The two directions pull against each other in this data: calibrating on a *near* empty (a) raises detection (walking 37 %, still 56 %) and creates ghosts (s9 54 %); calibrating on a *distant* empty (c) suppresses ghosts (≤ 0.7 % on the 27 Oct empties) and loses detection (walking 1.1 %). No tested candidate or reference configuration achieves both.

## 5. Reference baseline: the repo's own two-node logic

`scripts/eval-presence-on-datasets.ts` hard-codes four trackers and cannot be restricted to nodes 1 and 2 without editing it (forbidden here), so `scripts/presence_eval/ref_two_node.ts` (new, read-only) re-uses the same pure classes — `NodeBaselineTracker` ×2 → `RoomPresence` — and, for the legacy gate, `computeNodeMotionFromMatrix` + `fuseTwoNodeTarget` with `DEFAULT_MOTION_THRESHOLD` imported (not written), value 0.6. Windows are 800 ms, ticks 50 ms, trackers fresh per row, calibrated on the named recording, then run on the test recording (table above, "Repo reference"). The legacy energy gate at its documented default flags walking in 12.6 % of ticks and a still person in 10–79 % depending on the recording (s10 is strong on both N1 and N2: p50 of max-node motion 0.75), and empties in ≤ 1.2 %. These are single deterministic runs with no CI; they are reference numbers, not a validation. Defect noted: the config default `motionThreshold ?? 0.05` at `server/lib/websocket.ts:152` and `DEFAULT_MOTION_THRESHOLD = 0.6` at `server/lib/node-fusion.ts:43` differ by 12× (PS-EVAL-010) — not changed here.

## 6. Conclusion and limitations

**No candidate met the pre-registered criteria, so no accuracy figure is claimed.** Walking evidence rests on **one** 212 s recording by one subject; "still" on three short recordings from three sessions; the pooled training pool is dominated by the 53-minute s8 (2140 of 3026 empty windows, 71 %), so pooled baselines largely describe s8; emptiness labels are unverified; 15 candidates were compared (a multiplicity that would only matter if one had passed). Threshold values are *not* reported as recommendations and nothing was written to any setting or constant.

Tests: `tests/test_presence_eval_twonode.py` — leakage (signature; corrupted test recording cannot change the model; non-empty training refused; every split disjoint and train-on-empties-only; self-containing split rejected; threshold = training quantile), each fusion rule on known values and on a world where only N1 sees the person, determinism, "insufficient data" instead of a number, missing node → no windows.
