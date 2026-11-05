# 99 — Final report: Waves 0–2 (state at Gate 2)

**Provenance.** 2026-11-04. Branch `feat/two-node-radar-live-detection`, HEAD `744ce43`, dirty tree (Thaer's original edits + this task). Python tests run in the scratch venv `D:\WIFI csi\phanotm\_scratch_venv_fulltest` (Python 3.13.15, scikit-learn 1.9.1, torch 2.12.1+cpu); the repo `.venv` is untouched. Full verbatim outputs for every item: `90-test-report.md` (9,300 lines). Item reports: `01…14-*.md`. Ledger: `80-issues-ledger.md`. Merge gate: `89-merge-gate.md`. RuView traceability: `85-ruview-traceability.md`.

**Standing rules kept.** Nothing was committed, pushed, stashed, reset or reformatted. No file was deleted or moved (one overwrite of my own result file, disclosed in section 5). No firmware flashed, no hardware touched. Nothing installed into the repo `.venv`. No secret printed. No safety constant changed (`DEFAULT_MOTION_THRESHOLD`, `PHANTOM_MOTION_THRESHOLD`, tier thresholds 4/7/14, `data/runtime-settings.json`). F1 (AI is advisory only) and F2 (dashboard is passive) were not weakened; both were re-run after every item.

---

## 1. Bottom line

* **Wave 2 improved tooling, tests and evidence, not the detector. No improved detection is claimed.** Nothing was replayed on drift-controlled data that shows better detection in either failure direction (under-detection or ghost targets), and no runtime detection decision changed.
* Every candidate tried failed its pre-registered criteria: the movement score, the shipped presence head (AUC 0.48–0.56 vs empty), and the fan/periodicity feature (AUC 0.39 and 0.60, intervals include 0.5).
* The new calibration tool **refuses to give a threshold on every combination of our existing recordings** (link-state change between runs; empty-vs-empty drift bounds 0.68–0.91 against a 0.65 limit).
* The data cannot support a calibrated presence score: empty recordings drift more than a person changes the signal, the emptiness of those recordings is unverified, and no link-state epoch holds ≥ 2 empties plus a walking or still recording. **What is needed is new recordings (protocol in section 8), not more analysis.**

---

## 2. Test results — before and after

| suite | before (baseline, Wave 0) | after Wave 1 | after Wave 2 (final) |
|--|--|--|--|
| TS `npm test` | **407 / 407** | 418 / 418 | **444 / 444** |
| `npx tsc --noEmit` | not recorded at baseline | — | **0 errors** |
| Python, scratch venv | **210 passed**, 0 skipped (this included 5 live-server tests run against the live dashboard, which is what caused PS-FIX-23) | 250 passed + 5 opt-in skips | **342 passed + 5 opt-in skips** |
| F1 / F2 (`test_f1_*` ×2, `test_f2_*` ×1) | 3 / 3 | 3 / 3 | **3 / 3** |
| AI-firewall (`websocket.test.ts`) | not recorded separately at baseline | 11 / 11 (filtered run: name pattern `F1\|AI\|advisory\|firewall`) | **46 / 46** (the whole file, unfiltered; the 11 is a strict subset of it. No test was added by Waves 0–2: see 09-WAVE3-addendum.md) |
| `data/sessions` entries / audit log lines | 735 / 2250 | 735 / 2250 | **730 / 2250** (the 5 fewer are the PS-FIX-23 cleanup, done with Thaer's "apply"; files are in `.tmp/quarantine-sessions-2026-11-03/`) |

Progression of the TS count per item: 407 → 407 (01) → 407 (02) → 412 (03) → 418 (04) → 418 (05, 06) → 418 (pre-Wave 2) → 423 (addendum) → 427 (decisions batch) → 432 (PS-FIX-08) → 444 (PS-FIX-11). Python: 210 → 205+5 (01) → 216+5 (02) → 222+5 (03) → 233+5 (04, 05) → 250+5 (06) → 274+5 (pre-Wave 2) → 305+5 (addendum) → 310+5 (decisions) → 327+5 (08) → 336+5 (07) → 342+5 (09). The "205 + 5" at item 01 is the same 210 tests with the 5 live-server tests made opt-in.

The repo's own `.venv` (no scikit-learn, so the training-dependent tests cannot run there): 290 passed + 7 skipped at the addendum; the three newest Python test files pass there (26 / 26).

### Verbatim — before (baseline, `90-test-report.md` lines 673–713)

```text
ℹ tests 407
ℹ suites 0
ℹ pass 407
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9376.2694
EXIT=0
...
210 passed, 7551 warnings in 275.46s (0:04:35)
EXIT=0 secs=279
```

### Verbatim — after Wave 2 (`90-test-report.md` lines 8966–9300)

```text
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9384.7242
EXIT=0
```
```text
342 passed, 5 skipped, 7551 warnings in 199.26s (0:03:19)
EXIT=0
```
```text
tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.17s =======================
EXIT=0
```
```text
ℹ tests 46        (server/lib/websocket.test.ts — AI-firewall)
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1070.192
EXIT=0
```

`npx tsc --noEmit` printed nothing (0 errors); see `90-test-report.md` under "After PS-FIX-11". The 5 Python skips are the live-server tests, which are opt-in because they write into `data/sessions` of whatever dashboard is running.

---

## 3. Per-item status

### Wave 0 / Wave 1

| item | result | report |
|--|--|--|
| PS-FIX-00 baseline | TS 407/407; full Python suite made runnable in a scratch venv (210 passed); closes PS-EVAL-001. Side effect: my full run executed the live-server tests against the running dashboard (PS-FIX-23, since cleaned up). | `90-test-report.md` |
| PS-FIX-01 test hygiene | TS suite no longer writes to the real audit log; live-server Python tests opt-in; `scikit-learn` declared as an optional `train` extra. | `01-PS-FIX-01.md` |
| PS-FIX-02 loader hardening | `phantom/dataset.py` counts bad lines/frames, never truncates mixed widths, streams in chunks (peak 388 → 172 MB, bit-identical output), strict mode kept. | `02-PS-FIX-02.md` |
| PS-FIX-03 recorders | Both recorders write the same compact JSON and header schema 2 (per-part start, geometry hash, operator-stated capture conditions, "node moved / room not empty" annotation). Readers accept schema 1 and 2. | `03-PS-FIX-03.md` |
| PS-FIX-04 evaluation tooling | Rank AUC with block-bootstrap CIs; session-blocked AUC; empty-vs-empty control C4; always-absent control; abstentions counted as misses; `null` not `NaN`. **Result: still no candidate meets the pre-registered criteria; all 15 fail C4.** | `04-PS-FIX-04.md` |
| PS-FIX-05 documentation truth | Frame rate/cap and geometry corrected; capability figures labelled `[TO BE MEASURED]`; claims swept (`results/doc-claims-audit.txt`); dated records untouched. | `05-PS-FIX-05.md` |
| PS-FIX-06 guard + licences | AI sidecar refuses the shipped presence head (‖w‖ 3.668 < bias 8.188 ⇒ p ≥ 0.989 for any unit-norm input). Licence inventory flags MM-Fi (CC BY-NC 4.0) and `pose_v1.safetensors` (unverified provenance). | `06-PS-FIX-06.md`, `06-licences.md` |

### Pre-Wave 2, Wave 2 addendum, decisions batch

| item | result | report |
|--|--|--|
| Pre-Wave 2 fixes (1–4) | E2E guard, session-pollution restore tool; 24 new tests. | `07-PRE-WAVE2.md` |
| PS-FIX-23 session cleanup | Done and verified (index hash = baseline; 5 files moved to quarantine, nothing deleted). | `08-WAVE2-addendum.md` |
| A. Link-state epochs (PS-FIX-32, labelled POST HOC with sensitivity) | s7 evidence reproduced independently (node 1 −35 → −48 dBm, 63 → 44 fps). Cause of the step: **unconfirmed**. No epoch holds both ≥ 2 empties and a walking/still recording; drift persists *inside* epoch E07. | `08-WAVE2-addendum.md`, `09-DECISIONS.md` |
| B. Movement score (labelled "not presence") | Within an epoch the empty-vs-empty gate drops from 1.00 to 0.54–0.73; walking vs a single empty 0.61–0.78; fails across epochs; fades for a still person. Below criteria. | `08-WAVE2-addendum.md` |
| C. Recorder sidecar (PS-FIX-29) | `<part>.summary.json` (first/last 10 s RSSI median and fps, step flag), both recorders, shared parity test. | `08-WAVE2-addendum.md` |
| PS-FIX-27 `PHANTOM_DATA_DIR` | Approved and done; default path identical to before (tested); 8 call sites. | `09-DECISIONS.md` |
| PS-FIX-28 head norms | Approved and done; shipped head stays refused. | `09-DECISIONS.md` |

### Wave 2 (Thaer's order: 08 → 07 → 11 → 09; 10 skipped; 15 deferred)

| item | result | report |
|--|--|--|
| **PS-FIX-08** header-offset audit + PHY guard | TS and Python parsers match the firmware serializer; RSSI is int8 @ offset 17, pinned with one hand-built frame in both test suites (`server/lib/phy-guard.test.ts`, `tests/test_csi_header_offsets.py`; no offset error). The guard (`server/lib/phy-guard.ts` + 17 lines in `server/lib/udp-server.ts`) locks (subcarrier count, channel, freq) per node and **only counts/logs, never drops, alters or delays a frame** (a source-level test enforces this). The ADR-018 header has no bandwidth, sig_mode, rate or transmitter field (PS-FIX-36). "Guarded vs unguarded AUC" cannot be recomputed from our recordings. | `11-PS-FIX-08.md` |
| **PS-FIX-07** frame-rate truth | **≈ 65 fps/node ≈ 2 frames per 30 ms ping interval** (the firmware comment says ≈ 40 fps), irregular arrivals, 0 duplicate frames. Why there are two per ping cannot be seen from the header (PS-FIX-37). | `12-PS-FIX-07.md` |
| **PS-FIX-11** calibration tooling | A live empty run < 60 min or fan run < 5 min refuses to start (exit 2). The old "suggested mean+k·sigma" and "pick at least ceil(max+1)" lines are removed. `--evaluate` refuses with a code: `soak-too-short`, `no-negative-control`, `pooled-epochs`, `drift`, `too-few-blocks`. It never writes settings (tested by code grep). **Replayed on our recordings it refuses in every combination.** The live capture path itself was not run (the dashboard owns UDP :5005); only the CLI `--evaluate` and refusal paths are tested. | `13-PS-FIX-11.md` |
| **PS-FIX-09** fan/periodicity | **Negative.** At 64 Hz the feature is flat: fan vs empty AUC 0.39 [0.29, 0.64] and 0.60 [0.37, 0.77]. The empty-vs-empty control fails in every setting. A veto would cut the walking AUC 0.74 → 0.37 and fails both criteria in every setting, so no advisory label is supported. Side finding: a 50 Hz resample aliases the 33.3 Hz ping cadence to a false 16.7 Hz line (PS-FIX-40). | `14-PS-FIX-09.md` |
| PS-FIX-10 background-match prior | **Skipped** (Thaer's decision). Not built. | — |
| PS-FIX-15 | **Deferred** until new recordings exist (Thaer's decision). | — |

### Not started — need written approval after a design note and replay evidence (Gate 2)

| item | what it is |
|--|--|
| PS-FIX-12 | Rate-scaled timing and room-level hysteresis |
| PS-FIX-13 | PHY enforcement (moving the shadow guard to enforcing) |
| PS-FIX-14 | Firmware robustness (bounded calibration, CSI-stall watchdog); host-tested only, not flashed |
| PS-FIX-16 | Fail-closed outputs (`presence=false ⇒ people=0`, vitals abstain with a reason, no frozen re-broadcast) |

---

## 4. Footprint

Each edited tracked file has a backup in `.tmp/fix-backups/<item>/` and a patch in `reports/fix-2026-11/patches/`. Footprints are in `results/footprint-*.txt`; the Wave 0–1 totals are reconciled in `results/footprint-reconciliation.txt` (**25 tracked files edited, 6 earlier untracked evaluation files modified again, 8 new files** for items 01–06; the "12" in my first Gate 1 message was wrong).

| item | edited | new |
|--|--|--|
| 00 baseline | `data/sessions/_index.json` (test pollution, since restored) | — |
| 01 | `package.json`, `pyproject.toml`, `tests/test_esp_capture_e2e.py` | `server/test-setup.ts` |
| 02 | `phantom/dataset.py` | `tests/test_dataset_loader.py` |
| 03 | `phantom/dataset.py`, `scripts/record_dataset.py`, `server/lib/dataset-recorder{,.test}.ts`, 2 test files | — |
| 04 | `scripts/eval-presence-on-datasets.ts`, 6 `scripts/presence_eval/*.py` | `auc-bootstrap.ts` (+test), `jsonutil.py`, `tests/test_presence_eval_controls.py` |
| 05 | 16 documentation files (incl. `README.md`, `.agents/AGENTS.md`, `firmware/esp32-csi-node/README.md`; no firmware source) | — |
| 06 | `scripts/ai_inference.py` | `phantom/presence_guard.py`, `tests/test_presence_guard.py` |
| Pre-Wave 2 | 3 test files | `scripts/restore_session_pollution.py`, `tests/e2e_guard.py`, 2 test files |
| Wave 2 addendum | `scripts/record_dataset.py`, `server/lib/dataset-recorder{,.test}.ts`, `tests/test_record_dataset.py` | `epoch_eval.py`, `epochs.py`, `movement.py`, 2 tests |
| PS-FIX-27 | 8 server files (`audit/logger.ts`, `auth/service.ts`, `dataset-recorder.ts`, `phase-test-logger.ts`, `runtime-settings.ts`, `session-store.ts`, `websocket.ts`, …) plus eval scripts/tests | `server/lib/data-dir.ts` (+test), `epoch_sensitivity.py` |
| **08** | `server/lib/udp-server.ts` (+17 lines) | `phy-guard.ts` (+test), `tests/test_csi_header_offsets.py`, `presence_head_norms.py` (+test) |
| **07** | — | `scripts/presence_eval/frame_rate.py`, `tests/test_presence_eval_frame_rate.py` |
| **11** | `scripts/calibrate-threshold.ts` | `scripts/accuracy/calibration-soak.ts` (+test), `replay-calibration-runs.ts` |
| **09** | — | `scripts/presence_eval/periodicity.py`, `tests/test_presence_eval_periodicity.py` |

Wave 2 **runtime** code changes (none alters a detection decision): (1) `PHANTOM_DATA_DIR` with an identical default; (2) the recorders' per-part summary sidecar and schema-2 header fields; (3) the PHY shadow guard. No `client/` file was touched in Wave 2 (F2); no `firmware/**/*.c|h` file was touched by me.

Pre-existing state that is **not** mine: the firmware files, `package.json`, `pyproject.toml`, and `runtime-settings.ts` showed as modified in Thaer's original dirty tree; my only `runtime-settings.ts` change is the documented `PHANTOM_DATA_DIR` edit (my `package.json`/`pyproject.toml` edits in item 01 are the opt-in test marker and the `train` extra). `firmware/esp32-csi-node/version.txt` is untracked but predates this task (in the baseline manifest, dated Oct 20).

---

## 5. Honesty points

* **No detection improvement is claimed** (see section 1).
* **One file of mine was overwritten:** `results/periodicity.json`, regenerated once after adding the 64 Hz grid (disclosed in `14-PS-FIX-09.md`). No other file was deleted or overwritten. The earlier PS-FIX-23 cleanup moved 5 test-pollution files to a quarantine folder with Thaer's approval.
* **Errors I corrected along the way:** the Gate 1 footprint figure; a swapped "which session each tau was fitted on" statement in `14-PS-FIX-09.md`; an unverified claim about "14 recordings with constant widths" removed from `11-PS-FIX-08.md`; a duplicate link-step report in `detectLinkSteps`; my own 50 Hz grid artefact in the first periodicity run.
* **RuView:** every RuView reference comes from the task's digest and was **not read at source** (`[UNVERIFIED]`). Only methods and invariants were ported; no RuView numbers were reused. The only RuView artefact I read is the presence head in our repo, whose numbers I measured.
* **PS-FIX-32 (link-state epochs)** is labelled POST HOC with a sensitivity analysis, as Thaer decided. The cause of the link-state step is unconfirmed.
* **Hardware truth:** two ESP32-S3 nodes, one antenna each, 1-D on-axis only; no angle-of-arrival or pose. "No motion" does not mean "empty".

---

## 6. Decisions and approvals needed from Thaer (Gate 2)

1. **Wave 3 items.** Approve or decline each of PS-FIX-12 (rate-scaled timing), -13 (PHY enforcement), -14 (firmware robustness), -16 (fail-closed outputs). Each needs written approval after a design note and replay evidence. PS-FIX-15 stays deferred; -10 stays skipped.
2. **PS-FIX-36 — header schema v2.** Add bandwidth, sig_mode, rate and transmitter to the ADR-018 header. This is a firmware change; nothing is flashed without explicit approval.
3. **PS-FIX-24 / -26 — licences.** The model directory is a nested git repo with an untracked `pose_v1.safetensors` of unverified provenance; MM-Fi weights are CC BY-NC 4.0. Decide what may ship.
4. **PS-EVAL-010 / -013.** Motion threshold 0.6 vs 0.05, and the two-node legacy energy gate. Not changed; a safety constant is never changed from a single session of data.
5. **PS-FIX-38 — docs.** Several docs still say "pick mean + k·sigma" from a short run, which now contradicts the tool. Approve the edit.
6. **PS-FIX-37.** Read the firmware serial counters once, to learn why a node delivers two frames per ping.
7. **PS-FIX-40.** Check whether the sidecar's `estimate_vitals` resamples on a grid that aliases the 33.3 Hz ping cadence.
8. **Stray files** (listed for Thaer, not touched): the `bash.exe.stackdump` and the other files named under PS-EVAL-018 in `80-issues-ledger.md`.

---

## 7. `[UNVERIFIED]` list

* Whether the real frames differ by type within a ping interval (the header has no frame type).
* Whether RSSI is in the SDK's documented unit (the byte offset and sign are verified; the unit is not).
* Whether the TS server's features use the measured sample rate rather than an assumed one.
* Whether node 4's motion metric is saturated (block maxima sit at 1.000; PS-FIX-39).
* Whether the zero-millisecond gaps in some recordings come from the recorder or from a node.
* Whether the "empty" recordings were actually empty (no entry log exists).
* The cause of the s7 link-state step (node 1 −35 → −48 dBm); the cause is unconfirmed.
* Every RuView claim in `85-ruview-traceability.md` (from the digest, not read at source).
* The live capture path of the new calibration tool (not run; only CLI `--evaluate` and refusal paths are tested).
* Anything about fan + person together, because no recording has both.

---

## 8. What would unblock detection work — new-recording protocol

One link state, nothing moved, recorded through the dashboard recorder so the part sidecars and `capture` fields fill in:

1. ≥ 60 min empty, with an entry log kept.
2. Fan alone, 5 min.
3. Walking, 5 min.
4. Still, 5 min.
5. A second empty, ≥ 60 min, at the end.
6. A fan **with** a person present.

Also read the firmware serial counters once (PS-FIX-37). With these, `calibrate-threshold.ts --evaluate` and the drift-controlled evaluation can finally be run; until then every Wave 3 detection item lacks the evidence the task requires.

---

## ملخص بالعربية

* **اكتملت الموجة 2** بالترتيب الذي حدّدته (08 ← 07 ← 11 ← 09؛ تخطّي 10؛ تأجيل 15). **لا نزعم أي تحسّن في الكشف.** حسّنّا الأدوات والاختبارات والأدلة فقط، ولم يتغيّر أي قرار كشف وقت التشغيل.
* **الاختبارات:** TS من 407 إلى **444/444**، و`tsc` بلا أخطاء، وPython من 210 إلى **342 نجاح + 5 اختيارية**، وF1/F2 = 3/3، وAI-firewall = 46/46. لم يُغيَّر أي ثابت سلامة ولم يُرسَل أي شيء إلى العتاد.
* **PS-FIX-08:** محلّلا الترويسة يقرآن RSSI من البايت الصحيح (int8 عند 17). حارس PHY بوضع shadow فقط (يسجّل ولا يُسقط أي إطار). الترويسة لا تحمل bandwidth ولا sig_mode ولا المرسِل.
* **PS-FIX-07:** المعدل ≈ 65 إطار/ث لكل عقدة ≈ إطاران لكل ping، لا إطارات مكررة؛ سبب الإطارين غير معروف.
* **PS-FIX-11:** أداة المعايرة ترفض أي تشغيل قصير أو بلا مروحة أو يخلط حالات الربط أو يعاني drift، ولا تكتب أي إعداد. على تسجيلاتنا الحالية ترفض في كل الحالات.
* **PS-FIX-09:** نتيجة سلبية؛ ميزة الدورية لا تميّز المروحة، والـ veto يخفض AUC للمشي من 0.74 إلى 0.37.
* **المطلوب منك:** قرارات PS-FIX-12/13/14/16 (كل واحد بموافقة كتابية)، وPS-FIX-36 (تغيير firmware)، والتراخيص، وPS-EVAL-010/013، وتعديل الوثائق (PS-FIX-38)، وتسجيلات جديدة وفق البروتوكول أعلاه.
* **إفصاح:** أعدت كتابة ملف نتائج واحد من إنتاجي (`results/periodicity.json`)؛ ولم أحذف أي ملف آخر.
