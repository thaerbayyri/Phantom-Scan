# Wave 2 addendum — link-state epochs (A), movement score (B), recorder sidecar (C)

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv (Python 3.13.15, numpy 2.4.4). Footprint `results/footprint-08-WAVE2.txt` (the `data/sessions/_index.json` line is the **approved cleanup**, see §0). Backups `.tmp/fix-backups/08-WAVE2/`. Results: `results/epoch_eval.json`, `results/epoch_eval_tables.md`, `results/movement_score.json`, `results/movement_score_tables.md`. Tests: `90-test-report.md`.

**Scope honestly stated.** This covers the addendum only. PS-FIX-08's *own* items (RSSI byte-offset audit, PHY/identity guard in shadow mode), PS-FIX-07, -09 (fan/periodicity), -10, -11 are **not started**; the addendum extended 08 and 09 and I did the extensions first.

## 0. Session cleanup (approved) — done

`restore_session_pollution.py --apply` (dashboard confirmed stopped, hash matched): `_index.json` restored to the baseline sha256 `0261130f…683fc8` byte-for-byte, 5 files **moved** (not deleted) to `.tmp/quarantine-sessions-2026-11-03/`, pre-apply index backed up to `.tmp/fix-backups/23-sessions/`. `data/sessions` 735 → 730 files. Restart the dashboard when you want it. PS-FIX-23 is closed.

## A. Link-state epochs (extends PS-FIX-08; PS-EVAL-006)

### A1. Your evidence, verified independently (cached recordings, per-second medians)

| claim | measured |
|--|--|
| s7 node 1 steady ≈ −36 dBm for ~195 s | median **−35.0 dBm, 66.6 frames/s over +0…190 s** |
| step to ≈ −47 at +195 s (19:48:52 UTC) | first held second at **+195 s** (early dips −38/−42 at +192/+193); **−47/−48 from +195 s**; the detector's onset is **+193 s (19:48:50)** because the 10 s hold window may start two seconds early |
| frame rate 66/s → 14–42/s | per-second frames at +196…+205: 42, 36, 42, 25, 89, 47, 25, 17, **14, 14** (median ≈ 40); back to 45–65 from +206 while RSSI stays −47; median **43.7 /s** over +200…end |
| stays −47 through s8, s9 (~1.5 h), ≈ −39 by s10 | inventory medians −47 (s8, s9) and −38 (s10); the gap s9→s10 is a **+8 dB** step (−47 → −39) |
| node 4: one-second dip to −71 dBm at +203 s | **−71 dBm at +203 s** (min −78 in the following seconds), 39 frames that second; not held ≥ 10 s, so **not** an event |
| audit log has only record start/stop | `data/audit` holds 2,250 records; on 2026-10-27 19:30–21:30 UTC: 7 × `dataset_recording_started`, 7 × `dataset_recording_stopped`, 1 × `processing_started/stopped`; **nothing at 19:48:52** (s7 stopped 19:49:09.639, 17 s after the step) |

### A2. What was built (`scripts/presence_eval/epochs.py`, `epoch_eval.py`)

* **Per-node detector** on a 1 s grid: **RSSI step** = held ≥ 6 dB (≥ 90 % of the next 10 s beyond 6 dB on the same side of the previous 30 s median) **or frame-rate collapse** (median of next 10 s ≤ 0.7 × previous 30 s, baseline ≥ 20 fps). Each step also records `held_s` (time until RSSI returns within 3 dB for 5 s) and whether it is a **reversal** of the previous step.
* **Between recordings of the same day** the last/first 30 s are compared the same way (a change in an unrecorded gap); a **new calendar day always starts a new epoch**.
* **Epochs** for a node set = intervals between the union of that set's boundaries. **Transitional** = 5 s before to 30 s after a boundary event; those windows are removed from every evaluation.
* **Design decision I added (not in your spec), please confirm:** the detector also fires on N1 in *occupied* recordings (s1-still at +34 s, s2, the two_people runs) and on short flickers (s5, s1-still: ~7 dB for 16–19 s, then back). In an occupied recording an RSSI step may be the person's own body, and splitting there would throw away the occupant signal. So **a step is a boundary only if it is persistent** (new level also holds to the end of the recording *and* at the start of the next one), **or** the recording is `empty`/`empty_fan` and the new level held ≥ 60 s. Everything else is reported as `ambiguous`/excursion, never silently dropped. Reversals are never boundaries.

### A3. Result on our data (N1+N2; `results/epoch_eval_tables.md`)

* **Boundaries (7):** 3 new calendar days; the 25 Oct gap step (−12 dB); **s7 at 19:48:50 (N1 −12 dB, fps 63 → 44, persistent)**; 19:53:56 (N1 frame-rate collapse across the s7→s8 gap, 61 → 41 fps); 21:21:08 (+8 dB across the s9→s10 gap).
* **s7 handled as you asked:** the walking segment keeps **125 windows (+0…+188 s)**; **17 windows around and after the step are transitional and excluded** from every walking-vs-empty evaluation (4 before the boundary, 13 after it).
* **The 17 Oct walking recording (11 frames/s, pre-fix firmware) is excluded** for low coverage (28 % of its time grid has a usable window): its 74 windows are chance bursts, not a walking recording at normal rate.
* **Segments evaluated (13), by epoch:** E02 (18 Oct): 2 empties + fan + two_people; E03/E04 (25 Oct, split by the gap step): still / two_people; E05 (27 Oct until the s7 step): s1-still, s5 fan, **s6 (the only empty)**, s7 head; E07: **s8, s9 (empties, N1 at −47)**; E08: s10 still (N1 back at −39).
* **Structural finding:** **no epoch contains both ≥ 2 empty recordings and a walking or still recording** (E02 has two empties plus a two_people recording and a fan recording, which is not what walking/still-vs-empty needs; confirmed at all nine sensitivity settings, see §E). So *walking-vs-empty with a held-out empty cannot be evaluated inside any epoch*; those cells say `insufficient data` and nothing falls back to pooling. Within E05 the only comparison is walking (and fan, still) against the single empty s6 that also sets the baseline (adjacent-empty: optimistic).
* **Drift persists inside an epoch.** Within **E07** (s8 vs s9, N1 at a steady −47 dBm) `decor/max` fails the empty-vs-empty gate (worst symmetric upper bound **0.91**) and flags **12 %** of held-out empty windows at the α = 1 % threshold; `perturb_agc/max`: gate FAIL (0.82), FPR 5 %; `decor/n2` passes the gate (0.60) with FPR 17 %. Within **E02** (two 18 Oct empties) `decor/max` also fails (0.96). A stable RSSI/frame-rate link state does **not** remove the drift seen in 03-drift.md.
* **Across epochs (train on the empties of epoch A, test epoch B; reported separately):** most pairs fail the gate or flag 70–100 % of the other epoch's empty windows (e.g. train E05 → test E07 `decor/max`: FPR 100 %, gate FAIL 0.77). The one favourable-looking cell, E02 → E05 `decor/max` walking AUC **0.95 [0.90, 0.98]**, has **one** empty (s6) as its negative class and one walking recording: it is not evidence of generalisation.
* **Cause: UNCONFIRMED.** A physical change at node 1 (node/cable/object moved) is the leading hypothesis; nothing in the data or the audit log confirms it. Two observations to carry forward, not diagnoses: (i) the s7 change is **persistent** (1.5 h) while the s1-still/s5 excursions are **transient ~7 dB flickers** (−36 ↔ −43 dBm); (ii) the new level in s7 (−48) is deeper than a single 7 dB jump. A gain-state explanation for the flickers is `[UNVERIFIED]`.

### A4. Limits
Epochs are defined from RSSI and frame rate only; other changes (N3/N4, multipath) are not epochs. The persistence rule and the 60 s hold are my choices (stated above). 4-node epochs exist (`epoch_eval.run(nodes=(1,2,3,4))`) but N3's frequent frame-rate collapses split recordings into many small segments; I report N1+N2 as the main set. No threshold was written anywhere.

## B. Movement score (extends PS-FIX-09 as a *separate* item; not a detection candidate)

`scripts/presence_eval/movement.py`: score = current 1.5 s window − P25 of the same node's previous L ∈ {45, 90} s (**causal**, windows strictly before; no score until ≥ 80 % of the previous windows exist, so the baseline restarts at every segment/epoch start), fused by **max** over N1+N2 and over all four nodes, for `perturb`, `perturb_agc`, `decor` (12 variants). Every output carries the caveat: *relative to this node's own recent past; fades under sustained motion; zero for a motionless person; NOT presence and never evidence that a room is empty.*

**Results (window-block CIs are optimistic; session-blocked CIs need ≥ 2 recordings per class and are `[no CI]` otherwise, which is the case for walking everywhere):**

| variant (within epoch E05, vs the single empty s6) | walking AUC | fan (negative control) |
|--|--|--|
| N1+N2 `decor` L45 | 0.78 [0.70, 0.86] | 0.50 [0.34, 0.60] |
| N1+N2 `perturb_agc` L45 | 0.61 [0.50, 0.73] | 0.53 [0.40, 0.64] |
| all four `decor` L45 | 0.76 [0.63, 0.87] | 0.35 [0.23, 0.47] |

* **Empty-vs-empty gate (C4):** passes within E07 for the variants shown (0.54–0.65); fails within E02 (0.66–0.73) and **across epochs** (up to 1.00 for `decor` L45) — i.e. it reduces the control from the 1.00 of the trained scores to 0.54–0.73 *within* an epoch, as you saw, but does not remove cross-epoch drift.
* **Against your exploratory figures:** my within-epoch gate values (0.54–0.73) overlap your 0.60–0.84 range but start lower (0.54 and 0.57 are below it); my walking-vs-empty AUCs (0.61–0.78) do **not** reach the top of your 0.61–0.85 range, and there is **one** walking recording and **one** empty in its epoch. **All remain below the pre-registered criteria**: no session-blocked lower bound exists for walking, so C1 cannot be met.
* **Does it fade? (median score by third of each segment, N1+N2 `decor` L45):** the still recording **s10 falls 0.314 → 0.230 → 0.075**, the s7 walker is ≈ 0.020 / 0.023 in the first two thirds (empty s6: 0.014 / 0.012) and only 0.156 in the last third. So: it does fade for a still person, and for most of s7 the walker is barely above the empty — consistent with "never present it as presence".

## C. Recorder sidecar (PS-FIX-29) — done

Both recorders write `<part file minus .jsonl>.summary.json` **when a part closes** (rotation or stop): per node, RSSI median and frame rate over the **first and last 10 s** of the part, the part's RSSI median, `rssiDeltaDb`, `fpsRatio`, and a **step flag** (|Δ| ≥ 6 dB, or last-10 s rate ≤ 0.7 × first-10 s when the first ≥ 20 fps). A part shorter than 20 s reports `shortPart: true` and `stepFlag: null` (windows would overlap). The file is written exclusively (never overwrites), a write failure is swallowed and **never** stops or corrupts the recording, no file is written for a part with no frames, and the `*.jsonl` dataset glob never matches it. TS and Python share a **pinned parity vector** (node 1 step, node 2 collapse, steady node, short part) in both test suites. Smoke-tested end to end with the repo's synthetic sender. Observation only: it states nothing about cause.

## Evidence

TS **423/423**; Python **305 passed + 5 opt-in skips** (scratch venv), **290 passed + 7 skips** in the repo `.venv`; F1/F2 3/3; AI-firewall 11/11. New tests: 16 epoch (detector incl. one-second dip, short excursion, step + reversal, held excursion, rate collapse, gaps, persistence, boundary rules, transitional interval, no pooling across epochs, "insufficient data", low-coverage exclusion), 11 movement (causal, percentile definition, warm-up, motionless = 0, fade, burst visible, fusion/inner join, baseline never spans an epoch, labelling), 5 TS + 4 Python sidecar.

## E. PS-FIX-32: the epoch boundary rule is POST HOC — sensitivity and every ambiguous step

Thaer confirmed the rule. It is **labelled post hoc** (chosen after inspecting these recordings; not pre-registered) in `epochs.py`, in `epoch_eval.json` (`boundary_rule_status`) and here. Method: the whole pipeline is re-run for step threshold ∈ {4, 6, 8} dB × hold ∈ {10, 30, 60} s (`epoch_sensitivity.py`, `results/epoch_sensitivity.{json,md}`; N1+N2; the 60 s limit for empty recordings stays fixed).

| step / hold | in-recording events | boundaries from them | ambiguous | s7 N1 step is a boundary | epochs with ≥ 2 empties | … and walking/still |
|--|--|--|--|--|--|--|
| 4 dB / 10 s | 22 | 4 | 18 | yes (+193 s) | E06, E11 | none |
| 4 dB / 30 s | 5 | 1 | 4 | **no** | E04, E08 | none |
| 4 dB / 60 s | 3 | 2 | 1 | **no** | E05, E09 | none |
| 6 dB / 10 s (default) | 11 | 1 | 10 | yes (+193 s) | E02, E07 | none |
| 6 dB / 30 s | 3 | 0 | 3 | **no** | E02, E06 | none |
| 6 dB / 60 s | 2 | 1 | 1 | **no** | E03, E07 | none |
| 8 dB / 10 s | 6 | 1 | 5 | yes (+194 s) | E02, E07 | none |
| 8 dB / 30 s | 2 | 0 | 2 | **no** | E02, E06 | none |
| 8 dB / 60 s | 1 | 0 | 1 | **no** | E02, E06 | none |

* **Robust:** at every setting no epoch has ≥ 2 empty segments **and** a walking or still recording. (E02 / E03 carry the two_people recording.) PS-FIX-33 does not depend on the rule's parameters.
* **Not robust (be aware):** the s7 step is found **only with the 10 s hold** (at 4/6/8 dB). The recording ends ~19 s after the step, so a 30 s or 60 s hold cannot "hold" it; with those holds the whole s7 tail would remain in the evaluation. The 4 dB threshold fragments the data (22 events, up to 11 epochs). The epoch *numbering* changes with the setting, so epoch names are comparable only within one setting.
* **Every ambiguous step at the default (6 dB, 10 s)** — 10, none used as a boundary: s1 two_people N1 +9 dB (held 316 s), +6 dB (53 s), −6 dB (225 s); s2 still N1 rate collapse 54 → 16 fps (+47 s) and +8 dB (136 s); s3 two_people N1 rate collapse 57 → 38 fps (persistence unconfirmable: last recording of its day); **s1 still (27 Oct) N1 −7 dB (19 s)**; **s5 fan N1 −7 dB (16 s: excursion)**; **s7 N1 rate collapse at +194 s (the companion of the step, not itself a boundary)**; s10 still N1 −9 dB (12 s, persistence unconfirmable). The reason for each is in `results/epoch_sensitivity.md`.

## D. The external RuView-vs-Phantom Scan note (section 3 reproduced with repo code)

Input: the pasted note dated 2026-11-02, whose section 3 reports a pooled self-baseline test "not yet reproduced by repo tooling". Added `pooled_reproduction()` to `scripts/presence_eval/movement.py` (same protocol: pooled empties = s6 + s8 part 1 + s9 part 1, with part 1 ending at window 281 for s8 and 264 for s9 taken from the part files' own time ranges; positives s7 / s10 / s1(27 Oct) / s5; first L s dropped; no epochs). Output: `results/movement_pooled_reproduction.{json,md}`; 2 tests.

| config (note → repo reproduction) | walking s7 | still s10 | fan s5 | drift control s8 vs s6 |
|--|--|--|--|--|
| `decor`, 4 nodes, raw | 0.18 → **0.17** | 0.74 → 0.79 | 0.01 → **0.01** | 1.00 → **1.00** |
| `decor`, 4 nodes, self L90 | **0.85 [0.73, 0.96] → 0.76 [0.61, 0.91]** | 0.68 → 0.70 | 0.26 → 0.23 | 0.74 → 0.76 |
| `perturb`, N1+N2, raw | **0.57 → 0.41** | 0.95 → 0.95 | 0.17 → 0.15 | 0.90 → 0.92 |
| `perturb`, N1+N2, self L90 | **0.80 [0.71, 0.92] → 0.74 [0.62, 0.87]** | 0.68 → 0.70 | 0.53 → 0.52 | 0.60 → 0.62 |

* **Reproduced (within about 0.03):** the drift control, the still recordings and the fan, in all four configurations. The self-baseline does lower the drift control from 1.00/0.92 to 0.76/0.62 and the fan does not rise above the empties.
* **RESOLVED (Thaer's review):** the external script used a **full-L warm-up**; the repo's rule scores a window once ≥ 80 % of its previous L seconds exist, so the repo scores about **12 more early windows that sit near the empties**. With the repo's rule the external script reproduces **0.76 / 0.74 (whole s7) and 0.72 / 0.69 (head only)**, i.e. exactly my numbers. **The external walking table (0.85 / 0.80) is retired**; the repo numbers are the reference. (The explanation comes from Thaer's rerun of the external script, not from anything I ran.) The paragraph below is kept as the record of what was found before that.
* **Not reproduced (before the resolution above):** the **walking** AUCs are 0.05–0.16 lower than reported (0.76 vs 0.85; 0.74 vs 0.80; raw `perturb` 0.41 vs 0.57). Direction and conclusion are unchanged (raw is at or below chance, self-baseline lifts walking), but the reported 0.85 and the "lower bound 0.73" are **not** supported by repo code: mine are 0.61 and 0.62. With the transitional tail of s7 removed the walking AUC is lower still (0.72 / 0.69). The cause of the gap is unresolved `[UNVERIFIED]` (candidates: a different negative-class composition or part boundary, window alignment, which still recording was used).
* So the lead survives in kind but not in size, and it still does not meet the pre-registered criteria.

**Other statements in the note, checked where I can:** router at N2's corner in `config/room.json` ✓; tier thresholds 4/7/14 are provisional in `node-baseline.ts` ✓; the 4-node dashboard's centroid/floor-glow/axis-band visuals exist as described ✓ (read, not re-run). **"Tiers read moving/active for 91–100 % of ticks in empty phases"** is `[UNVERIFIED]` here: my own tier runs (2 nodes, s6-calibrated) gave 6.3 % occupied ticks for s8 and 53.8 % for s9. **Everything about RuView's code, ADRs and measured link ratios** is `[UNVERIFIED]`: I did not read the RuView clone.

**Section 4 (the recommended live view) is Wave 3 work (PS-FIX-15, "Honest dashboard") and needs your written approval after a design note and replay evidence for both failure directions.** I implemented none of it. It is consistent with the addendum-B finding: show change against a short self-baseline per node with freshness and an RSSI/frame-rate fault guard (this task's epoch detector is the data for that guard), never a position or "empty".

Both failure directions: A and B change no runtime behaviour (offline analysis). Neither shows a usable detector: the movement score is **not** a candidate, and under-detection (walking ≈ empty for two thirds of s7) and ghost behaviour across epochs both remain.
