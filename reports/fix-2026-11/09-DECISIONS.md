# Decisions batch (Thaer's review): walking-AUC closure, PS-FIX-32, PS-FIX-27, PS-FIX-28

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv Python 3.13.15 / torch 2.12.1. Backups `.tmp/fix-backups/09-DECISIONS/` and `.tmp/fix-backups/10-PS-FIX-27/`. Footprint `results/footprint-10-PS-FIX-27.txt` (covers this whole batch). Tests: `90-test-report.md`.

## 1. Walking-AUC gap — closed
Recorded in `08-WAVE2-addendum.md` §D and ledger PS-FIX-35. The external script used a full-L warm-up; the repo's 80 % partial-lookback rule scores about 12 more early windows that sit near the empties. With the repo's rule the external script gives 0.76 / 0.74 (whole s7) and 0.72 / 0.69 (head only), identical to the repo numbers. **The external walking table is retired.** (The explanation is Thaer's rerun, not something I ran.)

## 2. PS-FIX-32 — confirmed; labelled POST HOC; sensitivity and ambiguous steps
Labelled post hoc in `epochs.py`, `epoch_eval.json` (`boundary_rule_status`) and the reports. `epoch_sensitivity.py` re-runs the pipeline for 4/6/8 dB × 10/30/60 s (`results/epoch_sensitivity.{md,json}`). Findings, all in `08-WAVE2-addendum.md` §E:
* **Robust:** at all nine settings no epoch has ≥ 2 empties **and** a walking or still recording.
* **Not robust:** the s7 step is found only with the 10 s hold (the recording ends ~19 s after it); 4 dB fragments the data (22 events). Epoch names change with the setting.
* All 10 ambiguous steps at the default are listed with their reason. 3 tests added. (I also fixed two mistakes found while checking: my lookup of the s7 recording id, and my earlier wording "positive recording", which wrongly counted two_people.)

## 3. PS-FIX-27 — `PHANTOM_DATA_DIR` (default unchanged), tested, F1/F2 re-run
* New `server/lib/data-dir.ts`: `dataDir(...parts)` = `path.resolve(process.env.PHANTOM_DATA_DIR || "data", ...parts)`. Used by the session store, runtime settings, audit logger, operator seed, dataset recorder, phase-test logger and two spots in `websocket.ts` (minimal hunks in an already-modified file). Narrower overrides (`PHANTOM_AUDIT_DIR`, `PHANTOM_OPERATOR_SEED_PATH`, `PHANTOM_PHASE_LOG_DIR`, `PHANTOM_DEMO_DATASET_DIR`) still take precedence.
* **Default unchanged:** with the variable unset (or empty) every path equals the old `path.resolve("data", …)` (test). The demo dataset default keeps its original *relative* form.
* **Tested for real:** a child process started with `PHANTOM_DATA_DIR=<tmp>` saves a session through the real session store; files appear only under `<tmp>/sessions` and the repo's `data/sessions` stays at 730 files. 4 tests. `tests/e2e_guard.py` now tells you to start the throw-away server with `PHANTOM_DATA_DIR=<scratch> PORT=5099 npm run dev` (PS-FIX-27 closed).
* **Defect found and fixed:** `npx tsc --noEmit` flagged my earlier sidecar code (`[...stats.entries()]` is not allowed by the project's target; `tsx` ran it fine, so tests passed). Now `Array.from(...)`. **`tsc` reports 0 errors for the whole project.**
* **After the batch:** TS **427/427**, Python **310 passed + 5 opt-in skips** (scratch venv), **F1/F2 3/3**, **AI-firewall 11/11 (re-run)**, audit log unchanged (2250 lines), `data/sessions` 730.

## 4. PS-FIX-28 — presence-head input norms measured on our recordings
`scripts/presence_eval/presence_head_norms.py` reproduces the sidecar's path (100-frame window every 0.2 s → 8 standardised features → csi-embed-v2 → un-normalised bn2 activation → head) on all 14 recordings and 4 nodes (≈ 100 k windows). The sidecar functions (`estimate_vitals`, `extract_features_8d`, `Enc`, `DEFAULT_FS`) are **extracted from `scripts/ai_inference.py` with `ast` and executed**, not copied, so the measurement cannot drift from the live code. No LoRA applied (opt-in, other rooms). 6 tests.

| fact | measured |
|--|--|
| head | ‖w‖ = 3.668, bias = 8.188 |
| un-normalised activation ‖pre‖, all windows | q05 / q50 / q95 = **10.4 / 24.6 / 32.7** (so the sidecar docstring's "‖pre‖ ≈ 15" is the right order of magnitude) |
| logit on the **L2-normalised** embedding | **7.3 … 8.8** in every cell (p ≥ 0.9993): saturated, as the guard says |
| logit / probability on the **un-normalised** activation | the logit does span both signs (q05 ≈ −9…−14, q95 ≈ +12…+19): **the docstring's "full 0–1 spread" is true** |
| **p(present) > 0.5 in empty recordings** | **23 % (N2) … 58 % (N1)** of windows; > 0.99 in 23–44 % |
| p > 0.5 while someone walks / stands / two people | 41–59 % / 41–52 % / 41–49 % |
| **AUC of p(present) vs empty** (window-level, pooled) | walking **0.52**, still **0.48**, two_people **0.56**, fan **0.48** — chance |

**Conclusion.** The saturation argument is *not* the real problem on un-normalised input (the guard would accept the head with a measured q05 norm of 10.4), but the head **has no presence information on our data** (AUC ≈ 0.5) and it would raise "present" in up to 58 % of empty windows. **The guard is left unchanged and the head stays refused.** Passing a measured `input_norm` to the guard would make it accept an unusable head, so I did **not** do that; saturation is a necessary check, not a sufficient one. PS-FIX-28 closed. Caveats: window-block CIs only; one room/rig; no LoRA; the extracted pipeline assumes the sidecar's 56-column input is replaced by our 51 amplitudes (statistics are column-count independent; the pose path is not touched).

## Wave 2 order from here (Thaer): 08 → 07 → 11 → 09; skip 10; PS-FIX-15 deferred
Not started at the time of writing this report; progress is in the sections that follow it and in the final message.
