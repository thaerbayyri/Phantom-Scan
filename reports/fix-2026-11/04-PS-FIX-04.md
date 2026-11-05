# PS-FIX-04 — evaluation tooling (PS-EVAL-008, -016, -017)

**Provenance.** 2026-11-02, HEAD `744ce43` (dirty tree), venv: scratch (Python 3.13.15, numpy 2.4.4). Footprint `results/footprint-04-PS-FIX-04.txt` (7 changed, 4 added; all named below). Patch `patches/04-PS-FIX-04.patch`. Backups `.tmp/fix-backups/04-PS-FIX-04/` (the `provenance.py` and `jsonutil.py` hunks postdate the backup of the other `presence_eval` files, so their patch shows as whole-file; those files are untracked files from the previous task). Real-data results: `results/two_node_eval.json`, `results/two_node_tables.md`, `results/preregistered_criteria.json`. Test output: `90-test-report.md`.

## Change

| piece | what |
|--|--|
| `scripts/accuracy/auc-bootstrap.ts` (new) + `__tests__/auc-bootstrap.test.ts` (6 tests) | rank-based AUC with average ranks (O(n log n)), seeded moving-block bootstrap CI (block ≥ 10 s), `null` for an empty class; parity with the Python AUC pinned (`0.453125` on a tie-heavy vector) |
| `scripts/eval-presence-on-datasets.ts` | `--nodes 1,2` (frames of other nodes are not read; they read as zero evidence) and `--window-ms N` (header comment notes `calibrate-threshold.ts` uses 1500 ms, this one 800 ms: **PS-EVAL-016**); the old subsampled O(n²) AUC (every n-th window, no CI) is replaced by the full-data AUC **with a 95 % block-bootstrap CI**; it already used the **production** `computeAgcNormalizedPerturbation` (so PS-EVAL-008 needed no change here; the Python harness reports `perturb` and the production-equivalent `perturb_agc` side by side). Empty recordings stay in the output on purpose: their AUC vs the reference empty is the empty-vs-empty control row. |
| `scripts/presence_eval/stats.py` | `session_block_auc` (resamples whole recordings, then blocks; needs ≥ 2 recordings per class, otherwise `lo/hi: null` with a reason) and `empty_pair_control` (symmetric AUC upper bound per empty pair, gate ≤ 0.65) |
| `scripts/presence_eval/twonode.py` | **C4** (the stricter gate: for every pair of held-out empties the symmetric AUC upper bound ≤ 0.65, in protocols (b) and (c)); **abstentions counted as misses** (`tpr_abstain_as_miss`, `abstention_share`: windows on the recording grid without a joint N1+N2 score are not detections); **occupied-sensitivity control** (an always-absent scorer must be rejected); session-blocked AUC per class; `--prereg-out`. **C1–C3 are unchanged**; nothing was relaxed. |
| `scripts/presence_eval/jsonutil.py` (new) | all result writers now emit `null` instead of `NaN`/`Infinity` (the old files contained invalid JSON for undefined metrics) |
| `scripts/presence_eval/provenance.py`, `inventory.py`, `repro.py`, `drift.py` | `PRESENCE_EVAL_OUT` output override (this item wrote to `reports/fix-2026-11/` so the previous task's results stay intact); `dump_json` |
| `tests/test_presence_eval_controls.py` (11 tests) | session-blocked AUC (null + reason with one recording; deterministic; wider than window-blocked when recordings differ in level), empty-pair control (matched pass / baseline shift fails / null with < 2 empties), C4 reported and failing on a drifting empty, constant scorer rejected, "insufficient data" for the control, abstentions as misses (half the windows missing → TPR halves), null-not-NaN, strictly valid result JSON |

## Evidence

* **Pre-registration:** the C4 addition was frozen in `results/preregistered_criteria.json` (22:49:04) before the run; C1–C3 text is identical to the previous task's. These remain **proposals for Thaer**.
* **Real data, same recordings, new controls** (`results/two_node_eval.json`): **no candidate meets the criteria; 0 of 15 pass C4** (worst empty-pair symmetric upper bound **1.00** for every candidate in the leave-one-recording-out protocol); the always-absent control is rejected (AUC 0.50, never fires); undefined cells are `null` and the file contains no `NaN`.
* **Session-blocked intervals are far wider than window-blocked ones**: e.g. `decor/N2`, still vs empty, leave-one-recording-out: AUC 0.84, session-blocked 95 % CI **[0.60, 0.96]** versus **[0.78, 0.89]** when windows are the unit. The earlier tables therefore **understated uncertainty**; the walking class has **one** recording, so its session-blocked CI is `null` ("insufficient data").
* **TS script on real data** (`--nodes 1,2`, `room1 empty walking`, 30 s): with the adaptive trackers run sequentially, walking recordings give AUC 0.50 [0.45, 0.55] and 0.49 [0.37, 0.62] against the last empty, while the empty control rows read 0.59 [0.50, 0.65], 0.48, 0.23 [0.19, 0.30], 0.50. Output file in `90-test-report.md`.
* Suites: TS **418/418**; Python **233 passed + 5 opt-in skips**; F1/F2 3/3; AI-firewall 11/11.

Both failure directions: this item adds measurement controls only (no behaviour change). It makes the ghost-target direction visible (C3, C4) and counts under-detection honestly (abstentions as misses).

## Not done

`scripts/eval-presence-on-datasets.ts` was not retired (it is still the only tool that runs the *real* tracker classes); the Python harness remains the pre-registered evaluator. The new TS CI path has no test beyond the pure `auc-bootstrap` module (the script itself is exercised only by the real-data run above).
