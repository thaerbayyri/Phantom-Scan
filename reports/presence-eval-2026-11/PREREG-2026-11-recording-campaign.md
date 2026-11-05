# PRE-REGISTRATION — 2026-11 recording campaign (presence / movement evaluation)

**Status: all owner items resolved 2026-11-04 (section 7). It becomes FROZEN when this file is committed to git.** It must be committed **before any campaign recording is analysed.** `scripts/presence_eval/run_campaign.py` enforces this: it refuses to analyse unless this file is tracked by git and unmodified, and it writes this file's SHA-256 into every report. Every number below is either inherited from existing tooling or earlier frozen criteria, or was set by the owner on 2026-11-04 (section 7 keeps the history); **no number was picked by the analyst to fill a gap.**

Written 2026-11-04 (Wave 3, section 4). Authority for every threshold below: the existing tooling or the earlier frozen criteria (sources in section 3). Nothing in this file changes a threshold, a tier constant or a setting; **no output of this campaign changes the presence threshold (0.6), the tier thresholds (4/7/14) or the 0.05 fallback.** PS-EVAL-010 and PS-EVAL-013 stay with the owner.

## 1. What this campaign can and cannot conclude

One room, one rig (four ESP32-S3 nodes, one antenna each), one link state per campaign epoch. It can say whether a **movement/presence score** separates a person from an empty room **inside one link state**, with an empty-versus-empty control. It cannot say anything about other rooms, other subjects, other link states, through-wall operation, localisation accuracy, pose, or detection rates "in general". Hardware truth applies: 1-D on-axis energy balance only; no angle of arrival; no pose; no body shape.

## 2. Validity gates (checked by `validate_campaign.py` before any number is computed)

A campaign (or a block) that fails any gate is **invalid and is not analysed**; a failed gate is a valid outcome and is reported, not worked around.

| gate | rule | source |
|--|--|--|
| recording sidecars | every block has `block.json`; every recording part has its recorder `*.summary.json`; empty blocks have a non-empty entry log | owner's rule (PS-FIX-29 sidecar; the 2026-11-03/04 dashboard sessions have none and are **not evaluation data**) |
| block durations | empty (first) ≥ 60 min with entry log; fan alone ≥ 5 min; walking ≥ 5 min; still ≥ 5 min; second empty ≥ 60 min; fan with a person present ≥ **10** min | PS-FIX-11 rules `DEFAULT_MIN_SOAK_MIN = 60`, `DEFAULT_MIN_FAN_MIN = 5`; the owner's block list. The fan-with-person duration (10 min) has no existing rule: **set by the owner 2026-11-04** |
| frame rate | per node, median frames/s inside `[20, 100]` | `MIN_BASELINE_FPS = 20` (`calibration-soak.ts`, `epochs.py`); the upper bound 100 is the firmware send gate (10 ms) |
| rate collapse | no held collapse below 0.7 × the node's own reference rate inside a block | `RATE_COLLAPSE = 0.7` (`calibration-soak.ts`, `epochs.py`) |
| RSSI step | no held RSSI step ≥ 6 dB inside a block, and no ≥ 6 dB shift of a node's median between blocks of the same link state | `LINK_STEP_DB = 6` (`calibration-soak.ts`, `epochs.STEP_DB`) |
| nodes | every node in `nodes_expected` delivers frames in ≥ 90 % of the seconds of every block | `HELD_FRACTION = 0.9` (`epochs.py`) |
| epochs segmented | every block names a `link_state_id`; a LINK CHANGE ends the block (stop, log, wait 2 min, new block); at least one link state contains all six block types | owner's LINK CHANGE rule |
| empty-versus-empty (C4) | the first and the second empty block of one link state must not separate: symmetric AUC upper bound ≤ **0.65** for every candidate score; if not, the link state changed and the **whole block set is invalid** | `DRIFT_SYMMETRIC_UPPER_BOUND = 0.65` (`calibration-soak.ts`), `EMPTY_PAIR_UPPER_BOUND` (`stats.py`), PS-EVAL C4 |

## 3. Candidate scores (each is registered with its definition; numbers are only those with a source)

Window unit: 1.5 s tumbling windows, ≥ 20 frames (`features.py`, `stats.py WINDOW_S = 1.5`). Fusion over nodes: per-window maximum over the four nodes (nodes 1 and 2 only, as a second reading). Inference unit: moving-block bootstrap, 10 s blocks, 1,000 resamples, fixed seed (`stats.py DEFAULT_BLOCK`, `DEFAULT_BOOT`, `DEFAULT_SEED`); 95 % percentile interval. A class with fewer than 60 windows reports "insufficient data" (`min_windows = 60`). **The 1.5 s window is confirmed by the owner (2026-11-04); the 800 ms window of `eval-presence-on-datasets.ts` (PS-EVAL-016) is exploratory only.**

| id | candidate | definition / source | status |
|--|--|--|--|
| K1 | `perturb_agc` | AGC-normalised perturbation (`features.py`) | evaluated in 2026-10 data: not met |
| K2 | `decor` | 1 − mean cosine of consecutive frames (`features.py`) | evaluated: not met |
| K3 | `perturb` | per-subcarrier std/mean (`features.py`) | evaluated: not met |
| K4 | causal self-baseline movement score | `x_t − q25 of the previous L s` of K1/K2 (L = 45 s and 90 s), defined only when ≥ **80 %** of the lookback windows exist (`movement.py`: `QUANTILE = 25`, `MIN_PREVIOUS_FRACTION = 0.8`) | labelled "movement, not presence"; below criteria in 2026-10 |
| K5 | periodicity peak ratio | `periodicity.py` (PS-FIX-09), on the alias-free 100 Hz grid (PS-FIX-40) | negative result in 2026-10; registered as a control, not as a hope |
| K6 | shipped presence head (control) | refused by the sidecar guard (‖w‖ 3.668 < bias 8.188) | control only; AUC 0.48–0.56 earlier |
| **K7** | **parity-aware decor** | `decor` computed on the two same-parity sub-streams (every other frame) and averaged (PS-FIX-37: the frame alternation is real in 13 of 14 recordings; same-parity decor is 0.65–0.72 of all-frames decor; it explained part of the empty-vs-empty gap on N2 decor only) | **candidate; no threshold, window or criterion number picked here; evaluated only against the criteria in section 4** |
| **K8** | **anti-aliased decimation of the 20 Hz classifier input** | the replica of the MicroDopplerClassifier scoring fed by an anti-aliased instead of a nearest-sample 20 Hz decimation (PS-FIX-40 / PS-FIX-43; in the 2026-10 replay the share of windows that would suppress moved by under 3 points and not in one direction) | **candidate; no number picked; offline measurement only, no production change** |

Scores K1–K3 and K7 are evaluated per node and fused. No candidate is added after the data are seen; any further analysis is labelled **exploratory** and cannot meet or fail a criterion.

## 4. Success and failure criteria (stated in advance)

A candidate **meets the criteria** only if **all** of C1–C3 hold in a link state that passes every gate in section 2. "Inherited" means the number was frozen on 2026-11-02 for the earlier dataset (`reports/presence-eval-2026-11/04-two-node-eval.md` §1, `results/preregistered_criteria.json`) and is carried over unchanged (C1 ≥ 0.80 and C3 5 % confirmed by the owner 2026-11-04).

| id | criterion | number | source |
|--|--|--|--|
| **C1** | walking versus the **second** empty block: lower 95 % block-bootstrap bound of the AUC | **≥ 0.80** | inherited from the 2026-11-02 criteria |
| C1b | still versus the second empty block: lower 95 % bound of the AUC. A separate claim: "a still person is detected". Failing it is a valid reported outcome; it does not change the "meets the criteria" rule (C1–C3) | **≥ 0.80** | **set by the owner 2026-11-04**, same standard as C1 (earlier data showed the movement score fading for a still person, 0.31 → 0.08, so a failure is a live possibility and is reported as such) |
| **C2** | fan alone versus the second empty block, at α = 1 % and 5 %: the difference d = (fan flagged share) − (empty_2 flagged share) with its 95 % moving-block bootstrap interval (10 s blocks, 1,000 resamples, fixed seed). C2 **fails only if the lower bound of d is above 0** (the fan is flagged significantly more than the empty); otherwise it holds | lower bound of d ≤ 0 | the inherited criterion ("not above") made robust with an interval; **approved by the owner 2026-11-04** (a point comparison is noisy for equal distributions) |
| C2b | fan with a person present versus fan alone: lower 95 % bound of the AUC. A separate claim: "a person with the fan running is separated from the fan alone". Failing it is a valid reported outcome; it does not change the "meets the criteria" rule (C1–C3) | **≥ 0.80** | **set by the owner 2026-11-04**, same standard as C1 |
| **C3** | no held-out empty block flagged occupied in more than **5 %** of its windows at α = 1 % | 5 % | inherited |
| **C4** | empty-versus-empty control (section 2) | symmetric upper bound ≤ **0.65** | existing tooling |
| C5 | minimum evidence per comparison | ≥ **100** held-out empty 10 s blocks; ≥ 60 windows per class | `MIN_HELD_OUT_BLOCKS = 100` (`calibration-soak.ts`); `min_windows = 60` |
| C6 | target false alarms for any threshold candidate | **1 per hour** | `DEFAULT_TARGET_FALSE_ALARMS_PER_HOUR` (`calibration-soak.ts`); confirmed by the owner 2026-11-04 |
| C7 | **report-only for this campaign.** Both failure directions are measured and reported in seconds per block: under-detection (walking/still seconds with no marker) and ghost (empty/fan/no-data seconds with a marker or an EMPTY verdict). **No limit is pre-registered; C7 cannot make a candidate meet or fail the criteria.** The measured values will be the basis for limits pre-registered in the next campaign | none (report-only) | **decided by the owner 2026-11-04** |

**Failure** is: a gate in section 2 failing (the block set is invalid), or C1–C3 not all holding for a candidate. If no candidate meets the criteria the report says **"no candidate met the criteria"** and stops; **no accuracy, detection rate, false-alarm rate, "probability human" or "confidence" figure is claimed**, and the display rules of `05-display-spec.md` stay in force. A negative result is a valid outcome. Thresholds are never tuned on the evaluation blocks.

## 5. Analysis plan (fixed order)

1. `python -m scripts.presence_eval.validate_campaign <folder>`: refuses (non-zero exit, clear message) on any gate failure; never writes into `data/`.
2. `python -m scripts.presence_eval.run_campaign <folder>`: re-runs the validator; checks this file is committed and unmodified; segments epochs; computes K1–K4 and K7 per node and fused; block-bootstrap AUCs with intervals; the C4 control; writes a report in which **every number is labelled `measured`** and every quantity that could not be computed is `[TO BE MEASURED]`.
3. Evidence order: the C4 gate first (if it fails, nothing else is reported as a result), then C1–C3, then the exploratory tables.
4. The output of this analysis is **not used to change any threshold in this wave.**

## 6. Exclusions and deviations

* **Not evaluation data:** dashboard session output without a recorder sidecar (for example `000000205 - 2026-11-03`, `000000206 - 2026-11-04`, `test_*`), any recording not made through the dashboard recorder or `record_dataset.py`, any block containing an undeclared link change.
* Any deviation from this plan is entered in the table below at the time it happens (date, what, why). An unlisted deviation invalidates the affected result.

| date (UTC) | deviation | reason | approved by |
|--|--|--|--|
| 2026-11-05, entered before block 1 (no campaign recording existed) | **Analysis-window rule.** Blocks 3 (`walking`), 4 (`still`) and 6 (`fan_with_person`), person present: the operator must walk out to press Stop, so the **last 20 s before the recording end** (the last frame time) are excluded from the **primary** analysis. The rule uses only this fixed number and the recorded end time; it never uses the data. If the operator reports a longer exit before any analysis, that reported value replaces 20 s and is written in that block's `block.json` as `trim_tail_s`. Blocks 1, 2 and 5 (`empty_1`, `fan_alone`, `empty_2`) are started and stopped from outside the room and are **not trimmed**. **Primary result:** windows trimmed by this rule. **Sensitivity result:** the frozen `run_campaign` as written, untrimmed. A candidate **meets the criteria only if it does so under the primary result.** Both are reported side by side; if they disagree on any criterion, that criterion is called **"sensitive to the exit seconds"**. The trim option is implemented after the last block and before any analysis (flag, default off, so the frozen behaviour is unchanged; with tests), and no result is looked at before it is done. | The exit seconds are the operator moving, not the block's condition; in the still block they would bias the result in favour of detection. | Thaer Bayyari (owner), 2026-11-05 |
| 2026-11-05, entered before block 1 (no campaign recording existed) | **C7 wording.** C7 as reported is the offline candidate-threshold version (threshold = 1 − α quantile of the first empty block's scores; under-detection = walking/still windows at or below it × 1.5 s; ghost = empty_2/fan-alone windows above it, × 1.5 s). Live markers are not in the campaign files, so a marker-based C7 is `[TO BE MEASURED]` / not available. C7 remains report-only. | The campaign recorder stores only `t, n, rssi, a` per frame (`server/lib/dataset-recorder.ts:353-355`); markers exist only in the dashboard's own session output, which is not evaluation data. The scan stays off for the whole campaign (owner decision). | Thaer Bayyari (owner), 2026-11-05 |

## 7. Items for the owner before freezing: all items resolved 2026-11-04

History of what was open, what was set, and why:

1. **Fan-with-person minimum duration: 10 min** (set by the owner; no existing rule to inherit).
2. **C1b: lower 95 % bound ≥ 0.80; C2b: lower 95 % bound ≥ 0.80** (set by the owner, same standard as C1). Each is a separate claim: "a still person is detected" and "a person with the fan running is separated from the fan alone". Failing either is a valid reported outcome. Neither changes the "meets the criteria" rule, which stays C1–C3.
3. **C7 is report-only for this campaign** (decided by the owner): both failure directions are measured and reported in seconds per block; no limit is pre-registered; C7 cannot make a candidate meet or fail the criteria; the measured values will be the basis for limits pre-registered in the next campaign.
4. **C6 (1 false alarm per hour), C1 (≥ 0.80) and C3 (5 %) confirmed** by the owner 2026-11-04. C2 uses a bootstrap interval (**approved 2026-11-04**); `run_campaign.py` is aligned to it after the commits, with a test.
5. **Evaluation unit confirmed: 1.5 s windows.** 800 ms (PS-EVAL-016) is exploratory only.
6. Commit this file, and record the commit hash in the campaign's `campaign.json` (`prereg_commit`) before the first block is recorded.
