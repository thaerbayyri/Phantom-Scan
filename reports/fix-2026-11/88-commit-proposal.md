# 88 — PROPOSAL (not executed): committing the Wave 0–2 work in logical commits

**Status:** proposal only; nothing in this file has been run. HEAD is `6b5e330` (Item A is already committed there as `6b5e330`; this proposal is measured against the pre-Item-A HEAD `744ce43`, so Item A's lines count as mine). Safety backup of the whole tree before any of this: `.tmp/pre-wave3-backup/` (`MANIFEST.sha256`).

## 1. How ownership was determined

* **Wave 0 baseline** = `results/baseline-manifest.txt` (sha256 of every file at the start of the task, HEAD `744ce43`). A modified file never edited by me is **owner-only**.
* For a file I edited, the **earliest backup** in `.tmp/fix-backups/<item>/` is its Wave 0 state (checked against the manifest hash: column `chain ok`). **Owner lines** = changed lines between `744ce43` and that backup. **My lines** = changed lines between that backup and the file now. Counts are changed lines (added + removed), not hunks.
* A file with both numbers non-zero is **mixed**. Proposed method for those: a per-file 3-way merge chain (base = the state before item k, ours = what is staged so far, starting from HEAD, theirs = the state after item k), staged by blob (`git update-index --cacheinfo`) and verified exactly as Item A was (staged blob == HEAD + that item only, line counts equal). The dry run in section 3 shows whether each chain merges without conflict.

## 2. Modified tracked files

52 files: owner-only 17, mine-only 33, mixed 2.

| file | class | owner lines | my lines | items that edited it (order) | chain ok (mine) / unchanged since Wave 0 (owner-only) |
|--|--|--|--|--|--|
| `.agents/AGENTS.md` | mine-only | 0 | 2 | 05-PS-FIX-05 | yes |
| `DETECTION_REPORT.md` | mine-only | 0 | 4 | 05-PS-FIX-05 | yes |
| `JODDB_PHASE2_TECHNICAL_PROPOSAL.md` | mine-only | 0 | 10 | 05-PS-FIX-05 | yes |
| `MEASUREMENT_PLAN.md` | mine-only | 0 | 4 | 05-PS-FIX-05 | yes |
| `Phantom-Scan-Final-Project-Report-4Node.md` | mine-only | 0 | 12 | 05-PS-FIX-05 | yes |
| `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md` | mine-only | 0 | 12 | 05-PS-FIX-05 | yes |
| `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md` | mine-only | 0 | 4 | 05-PS-FIX-05 | yes |
| `docs/WIFI_DENSEPOSE_INTEGRATION.md` | mine-only | 0 | 2 | 05-PS-FIX-05 | yes |
| `docs/presentations/JODDB-Sponsorship-Pitch-Script.md` | mine-only | 0 | 2 | 05-PS-FIX-05 | yes |
| `docs/system_architecture_methodology.md` | mine-only | 0 | 2 | 05-PS-FIX-05 | yes |
| `firmware/esp32-csi-node/README.md` | mine-only | 0 | 12 | 05-PS-FIX-05 | yes |
| `generated_reports/Appendix.md` | mine-only | 0 | 6 | 05-PS-FIX-05 | yes |
| `generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md` | mine-only | 0 | 2 | 05-PS-FIX-05 | yes |
| `package.json` | mine-only | 0 | 4 | 01-PS-FIX-01 | yes |
| `phantom/dataset.py` | mine-only | 0 | 158 | 02-PS-FIX-02, 03-PS-FIX-03 | yes |
| `pyproject.toml` | mine-only | 0 | 8 | 01-PS-FIX-01 | yes |
| `scripts/ai_inference.py` | mine-only | 0 | 12 | 06-PS-FIX-06 | yes |
| `scripts/build_academic_reports.py` | mine-only | 0 | 18 | 05-PS-FIX-05 | yes |
| `scripts/calibrate-threshold.ts` | mine-only | 0 | 104 | 13-PS-FIX-11 | yes |
| `scripts/eval-presence-on-datasets.ts` | mine-only | 0 | 53 | 04-PS-FIX-04 | yes |
| `scripts/record_dataset.py` | mine-only | 0 | 195 | 03-PS-FIX-03, 08-WAVE2 | yes |
| `server/audit/logger.ts` | mine-only | 0 | 3 | 10-PS-FIX-27 | yes |
| `server/auth/service.ts` | mine-only | 0 | 3 | 10-PS-FIX-27 | yes |
| `server/lib/dataset-recorder.test.ts` | mine-only | 0 | 175 | 03-PS-FIX-03, 08-WAVE2 | yes |
| `server/lib/dataset-recorder.ts` | mine-only | 0 | 203 | 03-PS-FIX-03, 08-WAVE2, 10-PS-FIX-27 | yes |
| `server/lib/phase-test-logger.ts` | mine-only | 0 | 3 | 10-PS-FIX-27 | yes |
| `server/lib/runtime-settings.ts` | mine-only | 0 | 3 | 10-PS-FIX-27 | yes |
| `server/lib/session-store.ts` | mine-only | 0 | 3 | 10-PS-FIX-27 | yes |
| `server/lib/udp-server.ts` | mine-only | 0 | 17 | 11-PS-FIX-08 (backup is the HEAD copy; own lines taken from the item patch, total diff vs HEAD 17) | yes |
| `tests/test_count_model.py` | mine-only | 0 | 6 | 07-PRE-WAVE2 | yes |
| `tests/test_esp_capture_e2e.py` | mine-only | 0 | 24 | 01-PS-FIX-01, 07-PRE-WAVE2 | yes |
| `tests/test_record_dataset.py` | mine-only | 0 | 123 | 03-PS-FIX-03, 08-WAVE2 | yes |
| `tests/test_train_activity.py` | mine-only | 0 | 6 | 07-PRE-WAVE2 | yes |
| `README.md` | mixed | 1 | 12 | 05-PS-FIX-05 | yes |
| `server/lib/websocket.ts` | mixed | 212 | 5 | 10-PS-FIX-27 | yes |
| `client/src/components/dashboard/RadialScene.tsx` | owner-only | 48 | 0 | — | yes |
| `client/src/components/dashboard/ai-advisory-panel.tsx` | owner-only | 17 | 0 | — | yes |
| `client/src/components/dashboard/point-cloud-3d.tsx` | owner-only | 3 | 0 | — | yes |
| `client/src/components/dashboard/top-bar.tsx` | owner-only | 89 | 0 | — | yes |
| `client/src/components/dashboard/vitals-monitor.tsx` | owner-only | 21 | 0 | — | yes |
| `client/src/hooks/use-websocket.ts` | owner-only | 27 | 0 | — | yes |
| `client/src/pages/dashboard.tsx` | owner-only | 32 | 0 | — | yes |
| `firmware/esp32-csi-node/CMakeLists.txt` | owner-only | 5 | 0 | — | yes |
| `firmware/esp32-csi-node/main/Kconfig.projbuild` | owner-only | 15 | 0 | — | yes |
| `firmware/esp32-csi-node/main/csi_collector.c` | owner-only | 38 | 0 | — | yes |
| `firmware/esp32-csi-node/sdkconfig.defaults` | owner-only | 15 | 0 | — | yes |
| `server/lib/target-presentation.test.ts` | owner-only | 54 | 0 | — | yes |
| `server/lib/target-state.test.ts` | owner-only | 26 | 0 | — | yes |
| `server/lib/target-state.ts` | owner-only | 6 | 0 | — | yes |
| `server/lib/websocket.test.ts` | owner-only | 11 | 0 | — | yes |
| `shared/schema.ts` | owner-only | 15 | 0 | — | yes |
| `shared/target-presentation.ts` | owner-only | 18 | 0 | — | yes |

`data/sessions/_index.json` is runtime data rewritten by the live dashboard: **do not commit it**.

## 3. 3-way merge-chain dry run for the mixed files (a conflict needs a human)

| file | per-item merge result |
|--|--|
| `README.md` | 05-PS-FIX-05: clean |
| `server/lib/websocket.ts` | 10-PS-FIX-27: 1 conflict(s) |

## 4. Untracked files (168)

* **Mine** (named as added in an item footprint): 32
* **Not named in any footprint** (the owner's, or generated): 136

Not in any footprint:

* `client/src/components/dashboard/demo-banner.tsx`
* `client/src/hooks/use-persisted-flag.ts`
* `client/src/lib/demo-banner.test.ts`
* `client/src/lib/demo-banner.ts`
* `client/src/lib/stored-flag.test.ts`
* `client/src/lib/stored-flag.ts`
* `client/src/lib/vitals-status.test.ts`
* `client/src/lib/vitals-status.ts`
* `docs/esp32s3-framework-comparison-report.md`
* `firmware/esp32-csi-node/version.txt`
* `reports/fix-2026-11/00-summary.md`
* `reports/fix-2026-11/01-PS-FIX-01.md`
* `reports/fix-2026-11/02-PS-FIX-02.md`
* `reports/fix-2026-11/03-PS-FIX-03.md`
* `reports/fix-2026-11/04-PS-FIX-04.md`
* `reports/fix-2026-11/05-PS-FIX-05.md`
* `reports/fix-2026-11/06-PS-FIX-06.md`
* `reports/fix-2026-11/06-licences.md`
* `reports/fix-2026-11/07-PRE-WAVE2.md`
* `reports/fix-2026-11/08-WAVE2-addendum.md`
* `reports/fix-2026-11/09-DECISIONS.md`
* `reports/fix-2026-11/09-WAVE3-addendum.md`
* `reports/fix-2026-11/11-PS-FIX-08.md`
* `reports/fix-2026-11/12-PS-FIX-07.md`
* `reports/fix-2026-11/13-PS-FIX-11.md`
* `reports/fix-2026-11/14-PS-FIX-09.md`
* `reports/fix-2026-11/80-issues-ledger.md`
* `reports/fix-2026-11/85-ruview-traceability.md`
* `reports/fix-2026-11/89-merge-gate.md`
* `reports/fix-2026-11/90-test-report.md`
* `reports/fix-2026-11/99-final-report.md`
* `reports/fix-2026-11/patches/00-PS-FIX-00.patch`
* `reports/fix-2026-11/patches/01-PS-FIX-01.patch`
* `reports/fix-2026-11/patches/02-PS-FIX-02.patch`
* `reports/fix-2026-11/patches/03-PS-FIX-03.patch`
* `reports/fix-2026-11/patches/04-PS-FIX-04.patch`
* `reports/fix-2026-11/patches/05-PS-FIX-05.patch`
* `reports/fix-2026-11/patches/06-PS-FIX-06.patch`
* `reports/fix-2026-11/patches/07-PRE-WAVE2.patch`
* `reports/fix-2026-11/patches/08-WAVE2.patch`
* `reports/fix-2026-11/patches/10-PS-FIX-27.patch`
* `reports/fix-2026-11/patches/11-PS-FIX-08-udp-server.patch`
* `reports/fix-2026-11/patches/11-PS-FIX-08.patch`
* `reports/fix-2026-11/patches/12-PS-FIX-07.patch`
* `reports/fix-2026-11/patches/13-PS-FIX-11-calibrate-threshold.patch`
* `reports/fix-2026-11/patches/13-PS-FIX-11.patch`
* `reports/fix-2026-11/patches/14-PS-FIX-09.patch`
* `reports/fix-2026-11/patches/A-PS-FIX-38.patch`
* `reports/fix-2026-11/results/baseline-manifest.txt`
* `reports/fix-2026-11/results/cal/eval_A_defaults.txt`
* `reports/fix-2026-11/results/cal/eval_B_relaxed_lengths.txt`
* `reports/fix-2026-11/results/cal/eval_C_s8_alone.txt`
* `reports/fix-2026-11/results/cal/s5_fan.json`
* `reports/fix-2026-11/results/cal/s6_empty.json`
* `reports/fix-2026-11/results/cal/s7_walking.json`
* `reports/fix-2026-11/results/cal/s8_empty.json`
* `reports/fix-2026-11/results/cal/s9_empty.json`
* `reports/fix-2026-11/results/doc-claims-audit.txt`
* `reports/fix-2026-11/results/epoch_eval.json`
* `reports/fix-2026-11/results/epoch_eval_tables.md`
* `reports/fix-2026-11/results/epoch_sensitivity.json`
* `reports/fix-2026-11/results/epoch_sensitivity.md`
* `reports/fix-2026-11/results/footprint-00-PS-FIX-00.txt`
* `reports/fix-2026-11/results/footprint-01-PS-FIX-01.txt`
* `reports/fix-2026-11/results/footprint-02-PS-FIX-02.txt`
* `reports/fix-2026-11/results/footprint-03-PS-FIX-03.txt`
* `reports/fix-2026-11/results/footprint-04-PS-FIX-04.txt`
* `reports/fix-2026-11/results/footprint-05-PS-FIX-05.txt`
* `reports/fix-2026-11/results/footprint-06-PS-FIX-06.txt`
* `reports/fix-2026-11/results/footprint-07-PRE-WAVE2.txt`
* `reports/fix-2026-11/results/footprint-08-WAVE2.txt`
* `reports/fix-2026-11/results/footprint-10-PS-FIX-27.txt`
* `reports/fix-2026-11/results/footprint-11-PS-FIX-08.txt`
* `reports/fix-2026-11/results/footprint-12-PS-FIX-07.txt`
* `reports/fix-2026-11/results/footprint-13-PS-FIX-11.txt`
* `reports/fix-2026-11/results/footprint-14-PS-FIX-09.txt`
* `reports/fix-2026-11/results/footprint-A-PS-FIX-38.txt`
* `reports/fix-2026-11/results/footprint-reconciliation.txt`
* `reports/fix-2026-11/results/frame-parity.md`
* `reports/fix-2026-11/results/frame_parity.json`
* `reports/fix-2026-11/results/frame_rate_truth.json`
* `reports/fix-2026-11/results/frame_rate_truth.md`
* `reports/fix-2026-11/results/movement_pooled_reproduction.json`
* `reports/fix-2026-11/results/movement_pooled_reproduction.md`
* `reports/fix-2026-11/results/movement_score.json`
* `reports/fix-2026-11/results/movement_score_tables.md`
* `reports/fix-2026-11/results/periodicity.json`
* `reports/fix-2026-11/results/periodicity.md`
* `reports/fix-2026-11/results/preregistered_criteria.json`
* `reports/fix-2026-11/results/presence_head_norms.json`
* `reports/fix-2026-11/results/presence_head_norms.md`
* `reports/fix-2026-11/results/two_node_eval.json`
* `reports/fix-2026-11/results/two_node_tables.md`
* `reports/presence-eval-2026-11/00-summary.md`
* `reports/presence-eval-2026-11/01-data-inventory.md`
* `reports/presence-eval-2026-11/02-reproduction.md`
* `reports/presence-eval-2026-11/03-drift.md`
* `reports/presence-eval-2026-11/04-two-node-eval.md`
* `reports/presence-eval-2026-11/05-display-spec.md`
* `reports/presence-eval-2026-11/06-test-report.md`
* `reports/presence-eval-2026-11/07-next-recording-protocol.md`
* `reports/presence-eval-2026-11/08-issues-and-merge-gate.md`
* `reports/presence-eval-2026-11/results/drift.json`
* `reports/presence-eval-2026-11/results/drift_tables.md`
* `reports/presence-eval-2026-11/results/inventory.json`
* `reports/presence-eval-2026-11/results/preregistered_criteria.json`
* `reports/presence-eval-2026-11/results/ref_two_node.json`
* `reports/presence-eval-2026-11/results/reproduction.json`
* `reports/presence-eval-2026-11/results/reproduction_tables.md`
* `reports/presence-eval-2026-11/results/two_node_eval.json`
* `reports/presence-eval-2026-11/results/two_node_tables.md`
* `scripts/presence_eval/__init__.py`
* `scripts/presence_eval/drift.py`
* `scripts/presence_eval/features.py`
* `scripts/presence_eval/frame_parity.py`
* `scripts/presence_eval/inventory.py`
* `scripts/presence_eval/provenance.py`
* `scripts/presence_eval/recordings.py`
* `scripts/presence_eval/ref_two_node.ts`
* `scripts/presence_eval/repro.py`
* `scripts/presence_eval/stats.py`
* `scripts/presence_eval/tables.py`
* `scripts/presence_eval/twonode.py`
* `server/lib/demo-replay.test.ts`
* `server/lib/demo-replay.ts`
* `server/lib/demo-session.test.ts`
* `server/lib/demo-session.ts`
* `server/lib/demo-walker.test.ts`
* `server/lib/demo-walker.ts`
* `server/lib/websocket-demo.test.ts`
* `tests/test_doc_lint_threshold_rule.py`
* `tests/test_presence_eval_drift.py`
* `tests/test_presence_eval_features.py`
* `tests/test_presence_eval_frame_parity.py`
* `tests/test_presence_eval_inventory.py`
* `tests/test_presence_eval_twonode.py`

## 5. Proposed commits (order)

The owner's work goes first, as his own commits, so my items sit on top of it. Grouping of his work is his call; the groups are only a suggestion by directory.

| # | commit | contents | who |
|--|--|--|--|
| 0 | done | `6b5e330` Item A / PS-FIX-38 | mine |
| 1 | owner: firmware (esp32-csi-node) | 5 files | owner |
| 2 | owner: client dashboard | 15 files | owner |
| 3 | owner: server runtime | 11 files | owner |
| 4 | owner: shared schema | 2 files | owner |
| 5 | owner: scripts and python tools | 12 files | owner |
| 6 | owner: tests | 6 files | owner |
| 7 | owner: docs (markdown) | 1 files | owner |
| 8 | owner's share of the 2 mixed files | his lines in each mixed file; they stay unstaged while my item commits are made, then go in this commit | owner |
| 9 | `01-PS-FIX-01` | 4 files (0 mixed) | mine |
| 10 | `02-PS-FIX-02` | 2 files (0 mixed) | mine |
| 11 | `03-PS-FIX-03` | 6 files (0 mixed) | mine |
| 12 | `04-PS-FIX-04` | 11 files (0 mixed) | mine |
| 13 | `05-PS-FIX-05` | 15 files (1 mixed) | mine |
| 14 | `06-PS-FIX-06` | 3 files (0 mixed) | mine |
| 15 | `07-PRE-WAVE2` | 7 files (0 mixed) | mine |
| 16 | `08-WAVE2` | 10 files (0 mixed) | mine |
| 17 | `10-PS-FIX-27` | 16 files (1 mixed) | mine |
| 18 | `11-PS-FIX-08` | 6 files (0 mixed) | mine |
| 19 | `13-PS-FIX-11` | 4 files (0 mixed) | mine |
| 20 | `14-PS-FIX-09` | 2 files (0 mixed) | mine |
| 21 | Wave 0–3 reports | `reports/fix-2026-11/**` (the whole folder is untracked, Wave 3 files included) | mine |

## 6. Not for any commit

* `data/sessions/_index.json` and the dashboard's session files (`data/sessions/**`): runtime output.
* `.tmp/**`: backups, caches, scratch.
* The nested model repo (`m` in `git status`) and `models/**/pose_v1.safetensors` (PS-FIX-24/-26 licence rule).
* `reports/fix-2026-11/09-WAVE3-addendum.md` is a running file: commit it only when Wave 3 is closed.

## 7. Before executing anything

1. Re-verify `.tmp/pre-wave3-backup/MANIFEST.sha256`.
2. Do the owner commits first. For each mixed file stage by blob, never `git add <file>` (that takes both sides).
3. After each commit: `git diff --cached` is empty, the suites pass, and the sessions guard passes.
## 8. Added after the proposal was written (Wave 3 items that touch uncommitted Wave 0–2 files)

* **Item D (PHY-guard fault isolation)**: edits `server/lib/udp-server.ts` and `server/lib/phy-guard.ts` (both belong to the PS-FIX-08 set) and adds `server/lib/udp-server-phy-guard-fault.test.ts`. Put all of it in the **PS-FIX-08 commit**; it cannot be committed before it (no baseline in HEAD).
* **Item C (alias analysis)**: `alias_check.py` and its test are already committed (`0f2db12`). The 4-line `GRID_HZ` / `GRIDS_HZ` change to `scripts/presence_eval/periodicity.py` belongs to the **PS-FIX-09 commit** (`patches/C-PS-FIX-40.patch`).
* **Items A, B, A2** are committed (`6b5e330`, `955b028`, `3ae66c7`).
