# PS-FIX-09 — fan / periodicity candidate (offline): **negative result; no advisory label is supported**

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv Python 3.13.15. Command: `PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.periodicity` (40 s). Inputs: 10 of the 14 recordings in `data/datasets/room1/` (read-only). Outputs: `results/periodicity.{md,json}` (every grid × window setting). Code: `scripts/presence_eval/periodicity.py` (+6 synthetic-truth tests in `tests/test_presence_eval_periodicity.py`). New files only; nothing runtime was touched. Backup of the first version: `.tmp/fix-backups/14-PS-FIX-09/periodicity.py.v1`. I regenerated (overwrote) my own earlier `results/periodicity.json` once after adding the 64 Hz grid; no other file was deleted or overwritten.

## What was done
Per node, per tumbling window (10, 15, 20 s; main 15 s) on a grid shared by the nodes: resample the amplitudes to a uniform grid from the recorder timestamps (windows with a > 500 ms gap or < 20 frames/s are dropped), detrend, take the 8 highest-variance subcarriers, Hann + FFT, normalise each subcarrier's 1–20 Hz power to 1, average. Feature `peak_ratio` = max/median of that spectrum (also `narrow_share`, `peak_hz`), fused as the max over nodes 1 and 2. Evaluated on the two sessions that contain a fan (2026-10-18: 2 empties, fan, two_people; 2026-10-27: still, fan, empty, walking head before node 1's step), with the block-bootstrap AUC, the empty-vs-empty control (C4), and the task's criteria applied to a would-be veto on a reference detector (repo AGC-normalised perturbation, max over nodes 1+2, flagged above the 95th percentile of the session's calibration empty; label threshold fitted on the *other* session).

## Findings
1. **An artefact dominated the first version.** On a 50 Hz grid the strongest spectral line is **16.67 Hz in 67 of 71 two_people windows (node 1; 59 of 71 on node 2) and 199 of 212 windows (node 2) of the long empty s8**. 16.67 = 50 − 33.33 Hz: the 30 ms ping cadence, aliased by my own grid. A synthetic test reproduces it: two frame types at fixed phases of a 30 ms cycle with different amplitudes give a 16.7 Hz line at 50 Hz and no in-band peak at 64 Hz. It is also consistent with PS-FIX-07 (≈ 2 frames per ping interval). That the *real* frames differ by type is `[UNVERIFIED]` (the header has no frame type). Practical consequence: **a spectral feature computed from a 50 Hz-resampled stream of this link is dominated by the ping cadence, not by the room**.
2. **At 64 Hz (alias out of band) the feature is flat across classes.** Median `peak_ratio` 6.7–10.2 in every recording at 15 s, narrow_share ≈ 0.10–0.12. Fan vs empty AUC: 2026-10-18 **0.39 [0.29, 0.64]**, 2026-10-27 **0.60 [0.37, 0.77]**; the intervals include 0.5 and the two sessions disagree. Person vs empty: 0.46 [0.37, 0.61] and 0.70 [0.41, 0.84]. **The feature does not identify a fan.**
3. **Empty-vs-empty control fails in every setting** (worst symmetric upper bound 0.98–1.00, limit 0.65): empties separate from each other, so the feature drifts between recordings (median 6.7 in s6, 9.5–10.2 in the 2026-10-18 empties, 8.9 in s8 at 64 Hz / 15 s).
4. **The label threshold does not transfer across sessions.** Threshold fitted on 2026-10-18 vs on 2026-10-27: 8.69 vs 7.01 (64 Hz / 15 s), 7.48 vs 19.50 (10 s), 14.78 vs 4.90 (20 s).
5. **Criteria, 64 Hz / 15 s** (reference detector; empty FPR on the calibration empty is 5–6 % *by construction*):

   | criterion | result | verdict |
   |--|--|--|
   | walking AUC lower bound reduced by ≤ 0.05 | 2026-10-27 walking head 0.74 [0.56, 0.83] → **0.37 [0.21, 0.58]** (lower bound −0.35); still 0.88 [0.84, 0.95] → 0.59; 2026-10-18 two_people 0.77 [0.66, 0.87] → 0.49 [0.48, 0.60] | **FAIL** |
   | fan FPR ≤ empty FPR | 2026-10-27 fan 0.15 → 0.07 with veto vs empty 0.06 (calibration, in-sample); 2026-10-18 fan 0.02 even *without* a veto vs held-out empty 0.15 | **FAIL / not demonstrable**: the label also fired on 40–42 % of walking/still windows and 85 % of two_people windows, i.e. it vetoes people |

   At 10 s windows the results are similar (2026-10-27 walking 0.74 → 0.43, still 0.88 → 0.47). At 20 s the veto does nothing on 2026-10-27 (no window labelled mechanical, fan FPR stays 0.15 vs 0.06) and collapses the 2026-10-18 two_people AUC (0.77 → 0.41). **No setting meets both criteria.**
6. **A veto would be an under-detection hazard, not a fix:** the label separates people from empties about as well as it separates a fan, so vetoing on it removes real detections (AUC → ~0.4–0.6).

## What this cannot show
* Only **two fan recordings** (one per session), 5–19 windows each at 15 s; the intervals are wide (n is windows, not independent events).
* **No recording has a person and a fan together**, so the key failure (a person standing near a running fan being explained away) cannot be measured at all; it is the reason any use must stay advisory.
* Fan type, speed, distance and orientation are not recorded; one fan model at unknown settings.
* The reference detector is my proxy (AGC-normalised perturbation), **not** the production two-node gate (which still uses the legacy energy gate, PS-EVAL-013); results do not transfer to the live verdict.
* Only nodes 1 and 2; band content above ~20 Hz is not observable on these grids, so a fan whose blade-pass frequency is high is invisible by construction.

## Design (advisory only) — recorded, **not recommended for implementation**
If future recordings change the picture, the only acceptable form is a **display-only, advisory "possible mechanical periodicity" note** next to (never instead of) the authoritative state: it must not write or flip `is_human`, must not gate, and must be computed on a grid whose aliases of the 33.3 Hz ping cadence are outside the analysis band. A veto of the authoritative gate would need a separate code-reviewed rule and Thaer's written approval (task rule); on current evidence it would fail both criteria. Evidence needed first: ≥ 3 fan placements/speeds, **fan + person** recordings, a held-out day, and an empty-vs-empty control that passes.

## Verdict
**Candidate rejected on the data we have.** Neither failure direction is improved: under-detection (a veto removes people) and ghost targets (a fan is not isolated by this feature). No runtime behaviour changed.
