# 08 — Issue ledger and merge gate

**Scope.** Defects/mismatches found in existing code, data and documents while doing this task. **None was fixed** (the task forbids modifying tracked files). "Blocking" = blocks a detection/accuracy claim or this task's merge; "non-blocking" = should be fixed but does not. Owner `[TBD]` everywhere: for Thaer to assign.

## 1. Issue ledger

| ID | description | evidence | blocking? | owner | status |
|--|--|--|--|--|--|
| PS-EVAL-001 | `scikit-learn` is not installed in any interpreter on this machine, so `tests/test_count_model.py` and `tests/test_train_activity.py` cannot be collected; `pytest tests/` aborts with 2 collection errors, and the full Python suite (last known 163 passed / 5 skipped) cannot be reproduced. The slow count-CNN test could not be timed. `phantom/activity_train.py:24` imports `sklearn` unconditionally. | `06-test-report.md` (verbatim collection errors); import probe of `.venv`, system 3.13, WindowsApps 3.11 | **blocking** (merge gate: full Python suite) | [TBD] | open |
| PS-EVAL-002 | Docs state a 50 Hz firmware cap and ≈ 41–43 pps as current; committed send gate is `CSI_MIN_SEND_INTERVAL_MS 10U` (100 Hz) since commit `428d3a5` (2026-10-18) and recordings run 64–67 fps/node. | `firmware/esp32-csi-node/main/csi_ping_pure.h:29`; `csi_collector.c:110`; `firmware/esp32-csi-node/README.md:15,115,153`; `generated_reports/Appendix.md:215`; `docs/system_architecture_methodology.md:102`; 01 §2 | non-blocking | [TBD] | open |
| PS-EVAL-003 | Final report says the recorder "has produced seven labelled files … no still or active recordings" (true on 18 Oct); the folder now has 25 files / 14 recordings incl. still and walking. `REPORT-NOTES-Oct2026.md:36` rewrites "files" as "recordings". | `Phantom-Scan-Final-Project-Report-Oct2026.md:1027`; `REPORT-NOTES-Oct2026.md:36`; 01 §5 | non-blocking | [TBD] | open |
| PS-EVAL-004 | `phantom/dataset.py` raises on any malformed line, silently truncates frames to the shortest width, keeps no parse counters, loads float64 whole recordings. | `phantom/dataset.py:50–97` | non-blocking | [TBD] | open |
| PS-EVAL-005 | Two recorders write different JSON formatting (`{"type": "frame", …}` with spaces from the headless Python recorder vs compact JSON from the dashboard); `t` is host receipt time, so frames burst (up to 16.4 % share a millisecond with the previous one on N3). | `data/datasets/room1/room1__s1__empty__20261018T180250Z.jsonl`; `scripts/record_dataset.py:125`; 01 §2, §6 | non-blocking | [TBD] | open |
| PS-EVAL-006 | Node 1 RSSI dropped 11 dB (−36 → −47) and its frame rate fell 65 → 38 fps in the ≤ 5 min between s7 and s8 on 27 Oct and recovered by s10; no annotation anywhere. | `results/inventory.json` (`rssi_median_per_5min`, `fps_per_5min_full_bins`); 01 §3 | **blocking** for any calibration/accuracy claim from these data | [TBD] | open |
| PS-EVAL-007 | Emptiness of the `empty` recordings is unverified (one header note in 14 recordings; none for the 53-min s8). Drift and unlogged occupants cannot be told apart. | `results/inventory.json` (`notes`); 01 §4; 03 ranked causes | **blocking** for any accuracy claim | [TBD] | open |
| PS-EVAL-008 | The brief's `perturb` (raw std/mean) is not the production metric `computeAgcNormalizedPerturbation` (per-frame mean normalisation); they differ by up to 0.15 AUC on a node whose gain shifted. | `server/lib/node-fusion.ts:331`; 02 point 5 (Table B) | non-blocking | [TBD] | open |
| PS-EVAL-009 | In multi-part recordings every part header repeats the first part's `startedAtMs` (e.g. all 8 parts of s8), so part boundaries cannot be read from headers. | `results/inventory.json` `part_starts` for s8 | non-blocking | [TBD] | open |
| PS-EVAL-010 | Motion-threshold defaults disagree 12×: `DEFAULT_MOTION_THRESHOLD = 0.6` vs `motionThreshold ?? 0.05`. Not changed. | `server/lib/node-fusion.ts:43`; `server/lib/websocket.ts:152` | non-blocking (needs owner decision) | [TBD] | open |
| PS-EVAL-011 | `canRenderConfidentHuman` named in the brief/report does not exist in code; real gates are `canPresentTruthfulTarget`, `canPresentLiveTargetPosition`, `canPresentIllustrativeBody`, `canPresentVolumetricTarget`, `canPresentAxisMotionVector`. | grep over `*.ts,*.tsx,*.md,*.py`; `shared/target-presentation.ts:22–115`; `PhantomScan_HardwareReality_Alignment_Report.md:122` | non-blocking | [TBD] | open |
| PS-EVAL-012 | "k ≈ 8, τ ≈ 125 ms" is speed smoothing only; the tracker's τ = 0.6154 s gives ≈ 0.26 Hz, not 0.33 Hz. | `client/src/lib/smooth-follow.ts:57`; `server/lib/node-baseline.ts:141`; 05 §1 | non-blocking | [TBD] | open |
| PS-EVAL-013 | Two live nodes use the legacy energy gate (`fuseTwoNodeTarget`), not the adaptive tier trackers used for 3–4 nodes. Offline reference: legacy gate fires for 12.6 % of walking ticks; tier logic calibrated on an adjacent empty marks the empty s9 occupied 53.8 % of the time. | `server/lib/node-fusion.ts:435`; `websocket.ts:246–262, 1274–1314`; 04 §5 | **blocking** for claiming two-node detection performance | [TBD] | open |
| PS-EVAL-014 | Committed geometry (4 m N1–N2, router at N2) vs the brief's 3 m July rig `[UNVERIFIED]`; re-measure before using any position scale. | `config/room.json`; 05 | non-blocking | [TBD] | open |
| PS-EVAL-015 | Neither dataset headers nor the UI record node moves, firmware hash, channel or BSSID. | headers in `data/datasets/room1/*`; 01 §3; 03 cause #5 | non-blocking (addressed by 07 §1) | [TBD] | open |
| PS-EVAL-016 | Tools use different windows: `calibrate-threshold.ts` 1500 ms, `eval-presence-on-datasets.ts` 800 ms; numbers from the two do not transfer. | `scripts/calibrate-threshold.ts` (`WINDOW_MS`), `scripts/eval-presence-on-datasets.ts:18` | non-blocking | [TBD] | open |
| PS-EVAL-017 | The existing eval script `eval-presence-on-datasets.ts` hard-codes four nodes (cannot be restricted to N1+N2 without editing) and its AUC subsamples every n-th window with no CI; a new read-only script was needed for the two-node reference. | `scripts/eval-presence-on-datasets.ts:47,88–95` | non-blocking | [TBD] | open |
| PS-EVAL-018 | Stray `bash.exe.stackdump` files in `data/datasets/room1/` (and repo root). | `ls data/datasets/room1` | non-blocking | [TBD] | open |
| PS-EVAL-019 | Running the repo's own TS suite appends to the gitignored `data/audit/audit-current.jsonl` (auth tests), i.e. the mandated full-suite run has a runtime-data side effect. | file mtime/last line 18:50:27Z during the final `npm test`; `.gitignore:34` | non-blocking | [TBD] | open |

## 2. Per-change merge gate (this task: new files only)

| check | result | evidence |
|--|--|--|
| Full TS suite green | **PASS** — 407/407 before and after | 06-test-report.md |
| Full Python suite green | **FAIL / not met** — 2 files uncollectable (PS-EVAL-001); the 190 collectable tests pass (148 pre-existing + 42 new) | 06-test-report.md |
| F1/F2 tests green | **PASS** — `test_f1_*` ×2, `test_f2_*` ×1; 11 AI-firewall tests in `websocket.test.ts` | 06-test-report.md |
| No tracked file modified | **PASS** — `git diff` sha256 identical before/after; `git status` differs only by new untracked `reports/`, `scripts/presence_eval/`, 4 `tests/test_presence_eval_*.py` | 06-test-report.md |
| No threshold or runtime setting touched | **PASS** — no tracked diff; `data/runtime-settings.json` not touched; the new code only imports `DEFAULT_MOTION_THRESHOLD` read-only and has no `runtime-settings` reference; all writes go to `reports/…/results`, `.tmp/` | grep in this task; 04 §5 |
| `data/` read-only | **PASS** for `data/datasets` (no file newer than the baseline marker); note PS-EVAL-019 for `data/audit` (written by the repo's own test suite) | `find data -newer …` |
| AI path / ingest / firmware untouched; F1, F2 not weakened | **PASS** — nothing under `server/`, `client/`, `shared/`, `firmware/`, `phantom/` was edited | git diff hash |
| Every number has provenance | **PASS with exceptions** — all `results/*.json` carry command, commit, tree-dirty flag, code hash, date, inputs. Exceptions: the part-by-part s9-vs-s8 AUCs in 02 (ad-hoc check, labelled as such); `results/ref_two_node.json` has no provenance block (command in the script header; date = file time) | 02, 04 |
| Caveats present | **PASS** — temporal-feature (not angle), "no motion ≠ no person", unverified labels, 1-D on-axis, no accuracy claim | 02–05 |
| Limitations section present | **PASS** — 01 §7, 02, 03, 04 §6; 05/07 are documents (non-claims + `[TO BE MEASURED]`) | reports |
| Not committed/stashed/reset/reformatted | **PASS** — none of those git operations were run | session |

**Gate verdict:** all checks pass except the full Python suite (PS-EVAL-001), which is an environment gap rather than a failure of the new code. Merging these new files is not blocked by anything else, but **the results must not be used for any accuracy claim** (PS-EVAL-006, -007, -013).

## 3. `[UNVERIFIED]` items and what would verify them

| item | what would verify it |
|--|--|
| New firmware flashed to all four boards on 18 Oct (taken from project memory) | serial logs of that flash, or `idf.py` build/flash history |
| Exploratory "s9 vs s8" 0.84 / 0.49 (which subset of s8 was used) | the original scratch script/parameters |
| Brief's estimator bandwidth ≈ 0.33 Hz | locate the stage with τ ≈ 0.48 s or confirm it was a different estimate |
| July rig distance 3 m | measurement or the July session log |
| The 15-test gap (163 − 148) is exactly the two sklearn files | install scikit-learn in a scratch venv and run the full suite |
| Same firmware on all 27 Oct recordings | firmware hash stored in dataset headers (07 §1) |
| Whether the empty recordings were empty | independent entry log (07 §3 unattended soak) |
