# 09 — Wave 3 addendum (running record; one section per item)

**Provenance.** 2026-11-04. Branch `feat/two-node-radar-live-detection`, HEAD `744ce43`, dirty tree. Nothing committed, pushed, flashed or deleted so far. Python tests run in the scratch venv `D:\WIFI csi\phanotm\_scratch_venv_fulltest` (3.13.15). Verbatim suite outputs: `90-test-report.md` (sections "Wave 3 — baseline before Item A" and "Wave 3 — after Item A").

## 0. Session-state hashes (rule 5, as amended by the owner)

| | `_index.json` sha256 prefix | `data/sessions` entries | quarantine |
|--|--|--|--|
| Wave-2 baseline (rule text, **not edited**) | `0261130fef4cfed9` | 730 | 5 |
| Currently observed | `b3c571e291c55326` | 734 | 5 |

The 4 extra entries are `000000205 - 2026-11-03.json` and `test_21_2026-11-03T20-26-17-824Z.{csv,json,pdf}` (written 2026-11-03 23:26 local, ~11 min after Wave 2 work ended). **Origin unknown**; it looks like a dashboard run (69–76 s, 1,257 frames) but that is not proven. The owner decided (option 3): leave it in place, do not quarantine, do not declare it his or pollution. A dry run of `scripts/restore_session_pollution.py --ids "000000205 - 2026-11-03"` (no `--apply`) shows that removing that one index entry reproduces `0261130fef4cfed9…` exactly, so the observed state differs from the Wave-2 baseline by that single session and nothing else.

For Wave 3 only, `b3c571e291c55326` / 734 is the **provisional drift check**, verified before and after every run (`drift-before` / `drift-after` blocks in `90-test-report.md`). Nothing in Wave 3 writes to `data/sessions/`; no Wave 3 test starts anything on 5000 or 5005 (nothing was listening on 5000, 5005 or 5099 before the baseline).

**Update, owner decision of 2026-11-04 (supersedes the provisional hash check above for the rest of Wave 3).** The dashboard is live (`npm run dev` since 15:57, UDP 5005), so the index hash changes whenever a session is saved: at the end of the first Item B run it read `abdcc7fcbf20bb85` / 738 (new files `000000206 - 2026-11-04.json`, `test_2026-11-04T13-00-13-492Z.{csv,json,pdf}`). The Wave 3 drift rule is now a **diff rule**: before each item a sessions guard snapshots every file in `data/sessions` (path, size, sha256) and every `_index.json` entry; after the item it PASSES if every snapshotted file still exists with the same sha256 and every pre-existing index entry is present and identical (the index file itself is covered entry by entry, because the dashboard rewrites it). New files or entries from the live dashboard are listed and never stop work; a deleted, modified or renamed pre-existing file or entry stops work. The guard was tested on a synthetic folder (9 cases: unchanged, new file, new file + new entry, reformatted index, modified / deleted / renamed file, modified / deleted entry: all behave as specified). The old Wave-2 rule text (`0261130fef4cfed9` / 730) is **left as written; it is superseded for Wave 3 by the diff rule, and the owner will re-baseline later.** The new dashboard output (`000000205 - 2026-11-03`, `000000206 - 2026-11-04`, `test_21_*`, `test_2026-11-04*`) has no recording sidecar, is not evaluation data, and was not read, classified, quarantined or analysed (the guard only hashes bytes). The dashboard owns UDP 5005; it was neither stopped nor started, and tests use only port 5099.

Safety backup of the whole working tree before any commit: `.tmp/pre-wave3-backup/` (`working-tree.patch` = `git diff HEAD --binary`, 215,074 bytes, sha256 `b8257f3add2af124…`; `untracked/` = 168 files, all byte-identical to the originals; `MANIFEST.sha256`; the patch reverse-applies cleanly to the tree). Proposal (not executed) for committing the Wave 0–2 work: `88-commit-proposal.md`.

## 1. The 11-versus-46 question (answered; executed, not only title-matched)

* **11** = `server/lib/websocket.test.ts` run with the name filter `F1|AI|advisory|firewall` (`npx tsx --import ./server/test-setup.ts --test --test-name-pattern="F1|AI|advisory|firewall" server/lib/websocket.test.ts`). Origin of the filter: `reports/presence-eval-2026-11/06-test-report.md:13`. Executed now: **11 tests, 11 pass, 0 fail, 0 skipped**.
* **46** = the same file run whole, no filter. Executed now: **46 tests, 46 pass, 0 fail, 0 skipped**.
* The 11 are a **strict subset** of the 46: matching the filter against the 46 test titles gives exactly 11 (static check), and the executed filtered run reports 11.
* No test was added, removed, renamed or skipped by Waves 0–2: `server/lib/websocket.test.ts` has the same sha256 as in the Wave 0 baseline manifest (`44f7b410f19d19e708a594ad852f33c2c97cbaddd0aacbea3fc449c0fcb06367`). **No firewall test that existed before has stopped running.** Not a blocking finding.
* **Corrections made** (backups in `.tmp/fix-backups/W3-corrections/`): `00-summary.md:13`, `89-merge-gate.md:9` (the "11/11" lines now say "filtered run"), and `99-final-report.md:26` (the wrong claim "the file gained tests in later items" is replaced). The other item reports (`01`–`06`, `09-DECISIONS.md`, `90-test-report.md`) also say "AI-firewall 11/11"; those are dated records of the filtered run and were left untouched.
* **Weakness to know about:** the filtered selection depends on test titles containing one of four words. A firewall-relevant test whose title lacks them would be excluded from the 11. The whole-file 46 is the safer number to cite.

### 1.1 Uncommitted 46th test — for the owner's decision (not touched, not committed)

HEAD has 45 tests in that file; the working tree has 46. The extra one is `Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar` (`server/lib/websocket.test.ts:839`). `server/lib/websocket.ts` is also modified in the working tree and was already modified when this task started (it appears in the initial `git status`). It was in the working tree before Wave 0 (the file's sha256 equals the Wave 0 baseline). It is **not** part of any Wave 3 item and will not be committed as one.

## 2. Status table (updated after each item)

| item | status | commit | tests added | blocking? | failure direction checked |
|--|--|--|--|--|--|
| A PS-FIX-38 | **done** | `6b5e330` (hunk-level, Item A only) | 20 Python (doc lint) | non-blocking | neither (no detection code path changed; comment-only edits to 4 code files, proven by diff) |
| B PS-FIX-37 | **done** (analysis + tooling; the serial counters themselves still have to be read by the owner by hand) | `955b028` | 24 + 10 Python | non-blocking | neither (offline analysis of recordings; no detection, gate or display path touched) |
| A2 PS-FIX-41 | **done** (docs, templates, comments; lint extended) | `3ae66c7` (hunk-level, 21 replacements) | +16 Python (lint 20 -> 36) | non-blocking | neither (no value or code path changed) |
| C PS-FIX-40 | **done** (tool fixed; production decimation measured, NOT changed) | new files committed alone (hash in the chat report) | +41 Python | non-blocking | **both**: under-detection (walking suppress 0.78 % -> 3.64 % anti-aliased) and ghost (empty 3.53 % -> 3.04 %, fan 1.01 % -> 2.70 %); proxy, no production change |
| D PHY-guard fault isolation | **done** | not committed alone (rides with the PS-FIX-08 commit) | +6 TS | non-blocking | **under-detection**: frames ingested with a throwing guard 0/5 -> 5/5; ghost: not affected |
| H PS-FIX-12 | **design only** (no code) | none (untracked report) | 0 | non-blocking | neither (nothing changed) |
| I PS-FIX-24/-26 licence hygiene | **done** (re-verified; check script; nothing deleted) | new files committed alone (hash in the chat report) | +43 Python | non-blocking (PS-FIX-26 stays blocking for a commercial deliverable) | neither |
| section 4 recording-readiness | **done** (pre-registration drafted, data spec, validator, one-command analysis, dry run identical) | code and tests committed alone (hash in the chat report); documents untracked | +38 Python | non-blocking | neither (no detection path changed) |
| PS-FIX-42, E, F (after the owner's commits), G (demoted) | pending | | | | |

## 3. Item A — PS-FIX-38: stop documenting an unsafe threshold rule

### 3.1 What the evidence says (re-verified this session)

* `DEFAULT_MOTION_THRESHOLD` is `process.env.PHANTOM_MOTION_THRESHOLD ?? "0.6"` (`server/lib/node-fusion.ts:48`, unchanged).
* The 0.6 came from **one 60 s empty-room recording** on the two-node rig: 296 samples of `max(motion1, motion2)`, mean 0.49, sigma 0.027, max 0.58 (`LIVE_HARDWARE_TEST_REPORT.md:90`, "not separately saved to a file").
* Recordings of the same empty room separate from each other: the calibration tool's empty-vs-empty control refuses with symmetric AUC upper bounds 0.68–0.90 on the default combination and 0.75–0.91 on s8 alone, against a 0.65 limit (`13-PS-FIX-11.md:26-27`). So a k·sigma rule over a 60 s window is not supported.

### 3.2 Every hit, with its disposition

Search patterns: `mean + k`, `k·σ`/`k*sigma`, `μ + Nσ`, `mean+Ns`, "N sigma", "standard deviation", "suggested/derived/calibrated … motion threshold", over `*.md`, `docs/`, `generated_reports/`, `client/src`, `scripts/build_academic_reports.py` and code comments. The client has **no** hit (no dashboard help text states the rule).

| where | what it said | disposition |
|--|--|--|
| `docs/SPATIAL_CALIBRATION.md:24-26, 33` | "mean + k·σ, the same method calibrate-threshold.ts uses for the motion gate"; "prints a suggested … (mean+3σ / mean+4σ)" | **rewritten**: provisional, descriptive, not drift/pooling-checked; no longer the motion-gate method |
| `docs/SPATIAL_CALIBRATION.md` procedure (old steps 1–3) | "Procedure (hardware session, ~15 min)", a 300 s run, "note both suggestions" | **rewritten**: ≥ 60 min empty soak with entry log, ≥ 5 min fan control in the same link state, `--evaluate`; refusal is a valid outcome; figures `[TO BE MEASURED]` |
| `Phantom-Scan-Final-Project-Report-4Node.md:352` (FR15) | "derives the motion gate from a recorded baseline (mean + k·σ)" | **rewritten** (tool refuses single runs; gate provisional; rates `[TO BE MEASURED]`) |
| same, `:490`, `:330`, `:70` | "derived/recalibrated/calibrated against the two-node rig's empty-room baseline" | **reworded**: a single 60 s recording, provisional, "not a mean + k·σ result" |
| `README.md:194` caveat, `:234` table | "was calibrated 2026-07-20 against a 2-node rig's empty-room baseline"; "calibrated on a 2-node rig" | **reworded** + one added sentence: why k·σ is unsupported (drift figures above) and what real recalibration requires |
| `MEASUREMENT_PLAN.md:37-38` | "the calibrated `PHANTOM_MOTION_THRESHOLD`" | **reworded**: provisional, 0.6, false-alarm rate `[TO BE MEASURED]` |
| `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:444` | "Presence detection: adaptive threshold μ + 3σ (60-second sliding window)" | **qualified**: firmware edge-tier design target, provisional, rates `[TO BE MEASURED]`. The "sliding window / 1,200-sample" details were **not** checked against firmware `[UNVERIFIED]` |
| `scripts/build_academic_reports.py:772` (FR14), `:1449` (recommendation) | exported-report template: "derives the motion gate … (mean + k*sigma)"; "replace the placeholder gate with a mean + k*sigma calibrated threshold" | **rewritten** (60 min soak + fan control + `--evaluate`; gate provisional; rates `[TO BE MEASURED]`). The docx was **not** rebuilt (see §3.5) |
| `server/lib/node-fusion.ts:34-36` | "Calibrated … 0.6 sits just above that noise ceiling" | **comment rewritten** (PROVISIONAL, single recording, not a k·sigma result, what recalibration needs). **Value unchanged** |
| `scripts/calibrate-threshold.ts:10, 101`, `server/lib/tracking.ts:27-29`, `server/lib/tracking.test.ts:13` | comments claiming the motion gate uses the same mean+k*sigma method / calling the figure a "suggestion" | **comments corrected** (descriptive, provisional) |
| `LIVE_HARDWARE_TEST_REPORT.md:30, 90`, `PhantomScan_FixAll_Session_Report.md:32`, `PhantomScan_FixAll_RuViewAudit_Session_Report.md:117-118`, `PhantomScan_HardwareReality_Alignment_Report.md:99` | dated session records quoting the old rule or old tool output | **left as history**; allow-listed in the lint (and the lint fails if an entry stops matching) |
| `shared/schema.ts:133, 165`, `server/lib/signal-processing.ts:799`, `server/lib/websocket.ts:2001` | "auto-calibrated 3σ" floor of the legacy `MotionGate` | **left**: accurate description of existing code; this is the PS-EVAL-013 legacy gate, which stays with the owner |
| `server/lib/tracking.ts:39, 55` (`suggestedThreshold: mean + kSigma*sigma`), `scripts/calibrate-threshold.ts:240` (prints the spatial figure) | code behaviour | **left** (not a documentation hit; behaviour change is out of scope) |
| `firmware/esp32-csi-node/main/edge_dsp_pure.h:240-247`, `edge_processing.h:43` (`EDGE_CALIB_SIGMA_MULT 3.0f`), `edge_processing.c:799` | firmware comments/constants describing its on-board baseline | **left** (accurate; firmware is Item F only) |
| `docs/adr/*`, `docs/research/*`, `README.md:187, 405` | sigma in the DSP/statistics sense, or the 8σ calibration-sample reject | **not about the threshold rule**; left |

### 3.3 The doc-lint test

`tests/test_doc_lint_threshold_rule.py` (20 tests). It fails if `mean + k`, `μ + Nσ`, `mean+Ns`, `k·σ` (any spacing; σ / sigma / std / bare s; `·`, `*`, `×`) appears in a living doc, a report builder or client source **without** `[TO BE MEASURED]` or "provisional" in the same paragraph (Markdown table rows are judged one by one; source files use a ±2-line window). Scope: root `*.md`, `docs/*.md`, `docs/presentations`, `generated_reports`, `.agents`, `scripts/build_*.py`, `client/src`. Excluded on purpose: the four dated records above, `reports/`, `docs/adr`, `docs/research`, and source comments in `server/` and `scripts/`. It also self-tests (9 flagged phrases, 5 accepted ones, cross-paragraph and table-row cases) and checks that the allow-list is not stale.

**It can fail.** Run over the pre-edit backups (`.tmp/fix-backups/A-PS-FIX-38/`) it flags 5 unqualified statements in 4 files (SPATIAL_CALIBRATION.md, the Final Report FR table, the Preliminary Technical Deliverable, and 2 in `build_academic_reports.py`). It passes on the edited tree. **Limit:** the lint catches the rule *phrase*; the wording-only edits (README "calibrated", MEASUREMENT_PLAN, Final Report lines 70/330/490) are not protected by it (README and MEASUREMENT_PLAN had 0 pre-edit lint hits).

### 3.4 Tests, before and after (verbatim in `90-test-report.md`)

| suite | before | after |
|--|--|--|
| TS `npm test` | 444 / 444 | 444 / 444 |
| `npx tsc --noEmit` | 0 errors (no output) | 0 errors (no output) |
| Python (scratch venv) | 342 passed, 5 skipped | **362 passed**, 5 skipped (+20 doc-lint tests) |
| F1/F2 (`test_f1_*` ×2, `test_f2_*` ×1) | 3 / 3 | 3 / 3 |
| AI-firewall, whole file / filtered | 46 / 46 and 11 / 11 | 46 / 46 and 11 / 11 |
| drift check | `b3c571e291c55326` / 734 | `b3c571e291c55326` / 734 |

### 3.5 Not done / limits

* **No threshold, tier constant or runtime setting changed.** Proof: `diff` of the four edited code files against their backups shows only comment lines changed (`node-fusion.ts` +9/−5, `tracking.ts` +3/−3, `tracking.test.ts` +2/−2, `calibrate-threshold.ts` +3/−2); the literal `"0.6"` is still at `server/lib/node-fusion.ts:48`.
* **Failure direction:** neither. No detection decision, gate or display path changed, so there is nothing to replay for under-detection or ghost targets.
* The exported `.docx` reports and `generated_reports/*.md` were **not** regenerated, so existing exports still carry the old text until `build_academic_reports.py` is run again.
* **Drifted claim found, not edited (out of Item A's scope):** the default gate is stated as **0.12** in `scripts/build_academic_reports.py:441, 764, 819, 1003, 1122, 1442`, `generated_reports/Appendix.md:294`, `generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md:104` and `PhantomScan_Component_Inventory_Report.md:212`. The code default is 0.6 (0.12 was the original placeholder). Listed as PS-FIX-41 in the ledger.
* The new live-recalibration wording is a **procedure**, not a result: no soak, fan control or `--evaluate` run has been done. All false-alarm and detection figures are `[TO BE MEASURED]`.

### 3.6 Commit

**Committed as `6b5e330`** (hunk-level; nothing pushed). The working tree already carried uncommitted lines in 6 of Item A's files (the owner's and my Wave 0–2 edits), so the item's hunks were re-based onto HEAD (`patches/A-PS-FIX-38.commit.patch`, applied with `git apply --cached`; the original `patches/A-PS-FIX-38.patch` does not apply to HEAD because its context includes those other lines). Verified before committing: every staged blob equals HEAD plus only the 19 Item A replacements, the changed-line counts per file equal the counts measured earlier (e.g. README 4, SPATIAL_CALIBRATION 32, node-fusion.ts 14), and the 11 staged files are the whole set. The report files (ledger, gate, test report, corrections) are not in that commit: `reports/` is entirely untracked.


## 4. Item B — PS-FIX-37: make the frame-alternation finding reproducible

### 4.1 What was built (all new files, read-only on the data)

* `scripts/presence_eval/frame_parity.py` — per node and recording: lag-1..4 correlation of subcarrier vectors under four stated preprocessings, lag-1..3 mean |ΔRSSI|, the inter-frame gap histogram, `decor` on all frames versus the two same-parity substreams, and the empty-vs-empty AUC of `perturb` / `decor` on all frames versus parity substreams for s8 vs s6, s9 vs s6, s9 vs s8. Writes only `reports/fix-2026-11/results/frame-parity.md` and `frame_parity.json`; a test asserts it writes nothing else.
* **Path correction:** the multi-node recordings are in **`data/datasets/room1`** (14 recordings, 25 files), not `data/sessions/` as the task text said. `data/sessions` holds dashboard session summaries and is never read by this script. The report states this on its first line.
* `scripts/presence_eval/parse_serial_counters.py` + `docs/serial-counter-capture.md` — a parser for a PASTED serial log and a by-hand procedure. No serial-port code anywhere (a test pins that the module contains no serial/socket import or write). The two firmware log lines were read from `csi_collector.c`, not assumed: `medium tick: yield=…pps csi_cb=… send_fail=… rate_skip=… cb_drop=…` (about 1 s apart) and `CSI cb #N: len=… rssi=… ch=… mac_skip=…` (first 3, then every 250th). The doc warns that attaching a serial monitor usually resets the board (a LINK CHANGE) and must not be done inside a recording block.
* Run: `PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.frame_parity` (about 90 s). Result sha256 prefixes: `frame-parity.md` `6e51cb029c3cce8b`, `frame_parity.json` `41543bf9ce6bf319`.

### 4.2 Preprocessing behind each lag figure (which one is whose)

| variant | what is removed | what it is for |
|--|--|--|
| `raw` | nothing | the static channel dominates: every lag is about 0.99 for ANY stream |
| `shape` | each frame's own mean over subcarriers | keeps the static spectral shape: lags 0.7–0.9 |
| `timedemean` (primary) | per-frame gain, then the per-subcarrier time mean | static channel gone: shows the alternation clearly |
| `highpass` | `timedemean` plus a ~1 s moving mean | drift cannot masquerade as structure |

**Which one is the owner's / the reviewer's figure?** Session s6, node 3: `shape` lag-1 **0.716**, lag-2 **0.821**: the reviewer's "N3 lag-1 0.72, lag-2 0.82" is reproduced to two decimals by `shape` (raw is 0.990 / 0.994; timedemean is −0.412 / +0.377). So the reviewer's preprocessing is, by numerical agreement, per-frame subcarrier-demeaned with the static shape kept; their script was not seen `[UNVERIFIED]`. The "~0 lag-1" I quoted earlier is the **all-recording median of `timedemean`** (N1 −0.019, N2 −0.189, N3 +0.020, N4 −0.022), not a per-session value and not the same quantity: on s6 N3 it is −0.41. Both lead to the same conclusion; they are simply not the same number. A raw-amplitude lag-1 that is "higher" than my ~0 is expected for any preprocessing that leaves the static channel in.

### 4.3 Findings (from `frame-parity.md`, computed, 14 recordings x 4 nodes)

| quantity | N1 | N2 | N3 | N4 |
|--|--|--|--|--|
| median lag1 / lag2 / lag3 / lag4 (`timedemean`) | −0.019 / 0.444 / 0.021 / 0.354 | −0.189 / 0.454 / −0.148 / 0.404 | 0.020 / 0.450 / 0.063 / 0.354 | −0.022 / 0.456 / 0.043 / 0.369 |
| recordings with lag2 > lag1; zigzag survives high-pass | 13/14; 13 of 13 | 13/14; 13 of 13 | 13/14; 13 of 13 | 13/14; 13 of 13 |
| median mean-abs ΔRSSI lag1 / lag2 (dB) | 5.22 / 3.16 | 2.37 / 1.03 | 3.11 / 1.68 | 3.11 / 1.96 |
| median decor ratio, same-parity / all frames | 0.72 | 0.68 | 0.65 | 0.65 |
| cross-session gap, decor: separation all frames → parity (drop) | 1.00 → 0.99 (+0.01) | 0.93 → 0.64 (**+0.29**) | 0.68 → 0.75 (−0.06) | 1.00 → 0.95 (+0.05) |

* The one recording without the zigzag on every node is `room1__s1__walking__20261017T204650Z`.
* The gap histogram and the other tables are in `frame-parity.md` (Tables 1–5).
* Reviewer's numbers versus this run: alternation **reproduced** (lag-2 above lag-1 and lag-3, RSSI smaller at lag 2, decor lower by 28–35 % on the substreams, against their 25–37 %). The claim "AUC stays 0.93–1.00 after same-parity recomputation" is **reproduced for N1 decor and N4 (about 0.95–1.00) and N3 perturb, but not for N2 decor** (0.88 → 0.55 / 0.58 and 0.98 → 0.69 / 0.76).

### 4.4 Conclusion (as the owner asked, and as the computed text in `frame-parity.md` says)

1. The interleaving is real: 13 of 14 recordings, on all four nodes, and it survives high-pass filtering.
2. It explains part of the empty-vs-empty gap on **N2 decor** (and part of N2 perturb, drop 0.14) but **not on N1 or N4** (nor N3).
3. It inflates decor levels (all-frames decor is 1.4–1.5 times the same-parity value). That affects the decor level and the choice of lag; it does **not** explain the between-session drift in general.
4. **No threshold or feature change follows.** The presence threshold (0.6), the tier thresholds and every detector are unchanged.
5. It motivates PS-FIX-36 (a transmitter / frame-type header field). **Obligation:** parity-aware decor must be listed as a candidate, with no number picked, in `reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md`. That file is written in the recording-readiness section and **does not exist yet**; it is not claimed as done.

### 4.5 Tests, before and after (full output in `90-test-report.md`, section "Wave 3 — after Item B": section sha256 `f2e1d4cb7936fa7c…`, whole-file sha256 `c0cb484d92ff9a46…`)

| suite | before (= after Item A) | after Item B |
|--|--|--|
| TS `npm test` | 444 / 444 | 444 / 444 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 362 passed, 5 skipped | **396 passed**, 5 skipped (+24 frame_parity, +10 serial parser) |
| F1/F2 | 3 / 3 | 3 / 3 |
| AI-firewall, whole file / filtered | 46 / 46 and 11 / 11 | 46 / 46 and 11 / 11 |
| sessions guard | snapshot (738 files, 166 entries) | **PASS**: 0 changed, 0 new files, 0 new entries |

### 4.6 Failure direction

Neither. Item B is an offline analysis of recordings plus tooling: no detection, gating, display or ingest path changed, so there is nothing to replay for under-detection or ghost targets.

### 4.7 Not done / limits

* The firmware serial counters have **not** been read (no serial port is opened by anything here). Why a node delivers ~2 frames per ping is still unexplained; the counters can narrow it (MAC-filter share, 10 ms gate drops) but cannot give frame types.
* `t` is the recorder host's clock, not a device timestamp; a same-parity substream is a statistical probe, not proof of two frame types. The "empty" recordings have no entry log.
* The ESP-IDF `monitor --no-reset` flag in the capture doc is `[UNVERIFIED]` (not run); the COM8/COM9 node mapping is from earlier session notes `[UNVERIFIED]`.
* No threshold, feature or runtime setting changed.

### 4.8 Preconditions that came up

The first Item B run ended with the old hash check failing; the cause was the live dashboard (see §0), not this item (the script is read-only, and a test pins that). The guard check for Item B passed with no new dashboard files.

### 4.9 Commit

All Item B files are new and wholly mine, so no hunk selection was needed: `scripts/presence_eval/frame_parity.py`, `scripts/presence_eval/parse_serial_counters.py`, `tests/test_presence_eval_frame_parity.py`, `tests/test_parse_serial_counters.py`, `docs/serial-counter-capture.md` (the commit hash is in the chat report). The result files under `reports/` are untracked with the rest of the reports folder.
## 5. Item A2 — PS-FIX-41: correct the stated default gate and the "calibrated" claims

### 5.1 What the code actually does (verified in source, this session)

| path | default | applies when | source |
|--|--|--|--|
| **Fused presence gate** (decides whether a target exists) | `fusedTargetMotionThreshold` ← `data/runtime-settings.json` (absent) ?? `DEFAULT_MOTION_THRESHOLD` = `PHANTOM_MOTION_THRESHOLD ?? "0.6"` = **0.6** | always, for `fuseTwoNodeTarget` and `fuseNodeTargets` (compared with max of the per-node `motion`) | `server/lib/node-fusion.ts:47-48, 417, 709`; `server/lib/websocket.ts:154-155, 2245` |
| **Scalar `MotionGate`** (the Motion / No Motion badge, single-node path) | starts at **0.05**, then 3 sigma of the first 100 samples (auto-calibration) | `motionGateEnabled` is `false` by default, so the manual `motionThreshold` (fallback **0.05**) is NOT used; it applies only if the gate is switched on | `server/lib/signal-processing.ts:799-850`; `server/lib/websocket.ts:153, 1131-1133` |
| **0.12** | not a default anywhere in runtime code | historical original default of `DEFAULT_MOTION_THRESHOLD` (before 2026-07-20); survives only as an explicit argument in tests and in stale documents | `server/lib/node-fusion.test.ts`, `tests/behavioral/fusion-invariants.test.ts`, docs below |

Do the code paths disagree? Not as statements: the 0.6 gate and the 0.05 → 3 sigma `MotionGate` are two different gates on two different quantities. That two-gate structure is the existing **PS-EVAL-010 / -013** question (0.6 versus 0.05, legacy gate). **Nothing was changed or fixed there; it stays with the owner.** No new disagreement needs a decision.

### 5.2 Every statement found, and what was done (docs, templates and comments only; no value changed)

| where | statement | disposition |
|--|--|--|
| `scripts/build_academic_reports.py` (exported-report builder) lines 441, 764, 819, 1003, 1122-1128, 1442 | "default 0.12", "calibrated gate", "mean + 3/4/5-sigma candidates", "Uncalibrated default gate: the 0.12" | **corrected**: 0.6, provisional, descriptive statistics only, negative control "has not yet been met", rates `[TO BE MEASURED]` (6 edits) |
| `generated_reports/Appendix.md:71, 294`, `Section-1.2-WiFi-Frequency-vs-CSI.md:70, 104` | "default 0.12"; "calibratable"; "above the calibrated empty-room threshold" | **corrected** (provisional, 0.6, `[TO BE MEASURED]`); hand-edited, because the markdown was not rebuilt |
| `JODDB_PHASE2_TECHNICAL_PROPOSAL.md` (two statements) | gate "not yet calibrated on real hardware" (wrong in the other direction: it was set from one 60 s two-node recording); "First real threshold calibrated on hardware" | **corrected** to the true state and to the protocol that would justify a real figure |
| `docs/presentations/JODDB-Sponsorship-Pitch-Script.md` (English and Arabic) | "once the two-node foundation is calibrated and proven" | **corrected** in both languages: it has not yet been calibrated or validated; the threshold is provisional. The Arabic sentence was written by me and needs a native-speaker read `[UNVERIFIED]` |
| `Phantom-Scan-Final-Project-Report-4Node.md` (3 statements) | "the same **validated** per-node motion gate/metric and threshold"; "honestly recalibrated" | **corrected**: not validated; provisional |
| `README.md` (the second place, line 401) | "a correctly-calibrated threshold cannot be computed from clamped inputs" | qualified: the current 0.6 stays provisional |
| `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md:463` | "Variance threshold tau 0.001 (auto-calibrated via noise floor)" | a **different quantity** (top-K subcarrier selection, not the presence gate): labelled design value, provisional, not checked against the implementation `[UNVERIFIED]` |
| `server/lib/websocket.ts:2005-2007` (comment) | "DEFAULT_MOTION_THRESHOLD, **empirically calibrated against a real empty-room + fan negative control**" | **FALSE, corrected.** The project's own `LIVE_HARDWARE_TEST_REPORT.md` finding 5 says a fan produced a confident false target at 0.6 and the control "has never actually passed" |
| `tests/behavioral/fusion-invariants.test.ts:114` (comment) | "clears the default 0.12 threshold" | the test passes 0.12 explicitly; comment now says so and that the code default is 0.6 |
| exported **PDF** (`scripts/reporting/session_reporter.py`) and **CSV** (`server/lib/recording-export.ts`) templates | no statement of the default gate or of calibration; the CSV carries only the numeric `motion_threshold`, `scalar_motion_threshold`, `fused_motion_threshold` values | **nothing to correct** |
| `LIVE_HARDWARE_TEST_REPORT.md`, `PhantomScan_Component_Inventory_Report.md:212`, and five other dated reports | "0.12 default" / "calibrated" as history | **left as history**; allow-listed in the lint |
| `2-node-esp32s3-run.md:175`, `scripts/ruview-dashboard-bridge.py:255` | `motion_band > 0.12` | a **different detector** (the RuView bridge heuristic); not the presence gate; left |

### 5.3 Findings worth the owner's attention

1. **A code comment asserted something the project's own evidence contradicts** (fan negative control). Fixed as a comment; the gate's behaviour is unchanged. Related: the Final Report called the gate and its metric "validated"; they are not.
2. **The exported PDF prints `Confidence: NN.N%`** (`session_reporter.py`, `classification_confidence` = share of frames carrying the dominant label, `most_common[1] / total`). A reader such as JODDB will read "100.0%" as the probability of being right. That is not what it measures. **Not changed** (outside the threshold scope; it changes a report the sponsor reads). Listed as PS-FIX-42 for the owner's decision.
3. The sponsor-facing pitch said the foundation was "calibrated and proven"; now it says it is not yet.

### 5.4 The lint extension

`tests/test_doc_lint_threshold_rule.py` has a second rule: "calibrated" (also "recalibrated", "auto-calibrated"; **not** "uncalibrated" or "calibration") in the same paragraph as "threshold", without "provisional" or `[TO BE MEASURED]`, in a living doc, a report builder or client source. Run first on the unfixed tree it was **red** in exactly 10 places (README, JODDB proposal x2, Final Report x2, SYSTEM_DESIGN, the pitch, Section-1.2, the builder x2); after the fix it is green. Five more dated reports are allow-listed as history (`PhantomScan_RealLiveFailure_Analysis.md`, `PhantomScan_GhostTarget_Fix.md`, `PhantomScan_Research_Gap_Analysis.md`, `PHANTOM_SCAN_REMEDIATION_REPORT.md`, `PhantomScan_RuView_Port_Full_Report.md`). Limits: the lint catches the words, not the meaning (it would not have caught "validated" or "proven"; those were found by reading).

### 5.5 Tests, before and after (full output in `90-test-report.md`, section "Wave 3 — after Item A2")

| suite | before (= after Item B) | after Item A2 |
|--|--|--|
| TS `npm test` | 444 / 444 | 444 / 444 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 396 passed, 5 skipped | **412 passed**, 5 skipped (+16 lint tests: 20 -> 36) |
| F1/F2 | 3 / 3 | 3 / 3 |
| AI-firewall, whole file / filtered | 46 / 46 and 11 / 11 | 46 / 46 and 11 / 11 |
| sessions guard | snapshot 738 files / 166 entries | **PASS**, 0 changed, 0 new |

### 5.6 Failure direction and limits

Neither: no value, gate or code path changed (the `websocket.ts` diff is comment lines only; the literals `"0.6"` at `node-fusion.ts:48` and `?? 0.05` at `websocket.ts:153` are untouched). The exported `.docx` was **not** rebuilt; `generated_reports/*.md` were edited by hand to match the corrected builder.

### 5.7 Commit

`3ae66c7` (hunk-level; all 21 replacements apply to HEAD; staged blobs verified equal to HEAD plus only these replacements). Item B is `955b028`.
## 6. Item C — PS-FIX-40: does the 33.3 Hz ping cadence alias, and where does it matter?

### 6.1 The premise, checked against the code

The task text says "the 50 Hz resample aliases the 33.3 Hz ping cadence". **In production nothing resamples to 50 Hz.** The 50 Hz grid was the default of **my own evaluation tool** (`scripts/presence_eval/periodicity.py`, `GRID_HZ = 50.0`), the only uniform resampler in the repo. The question left open in the final report ("does the sidecar's `estimate_vitals` resample on a grid that aliases?") has a clear answer: **no**. `estimate_vitals(mags, fs)` (`scripts/ai_inference.py:388`) takes the rows as samples at `fs = (n−1)/span` measured from the timestamps (`_estimate_fs`, `:492`, guard 1–200 Hz, fallback `DEFAULT_FS = 20.0`, `:208`); it does not resample.

**But production does decimate, with no anti-alias filter.** The legacy per-tick path runs `processFrame` from `setInterval(…, 50)` (`server/lib/websocket.ts:808-809`, comment "Process at ~20 FPS") and takes **one** queued sample per tick (`dequeueHardwareSample()`, `:1087`, `:2567`; the queue is round-robin over nodes, capped at 1000, `:1105`). A stream arriving at roughly 65 frames/s per node is thereby decimated to 20 samples/s by picking the next frame, and that 20 Hz sequence feeds the scalar `MotionGate` (`:1130`), the `MicroDopplerClassifier` (`:1208`) and the `VitalsComputer` (`:1170`).

### 6.2 Every resample or fixed-rate assumption (file:line, checked this session)

| where | what | kind |
|--|--|--|
| `server/lib/websocket.ts:806-809` | `setInterval(processFrame, 50)`: one sample per 50 ms tick | **20 Hz decimation, no anti-alias filter**, live |
| `server/lib/websocket.ts:1087, 2567-2582, 1105` | dequeue: next queued sample, round-robin across nodes; queue cap 1000 | the decimator itself |
| `server/lib/signal-processing.ts:439-441` | `MicroDopplerClassifier(bufferSize = 40, sampleRate = 20)`; `highFreqRatio` = power above **5 Hz** of a 2 s window; can suppress a presence claim | fixed rate 20, live |
| `server/lib/signal-processing.ts:804, 808-809, 828` | `MotionGate`: `bufferSize = 30`, `calibrationCount = 100`, initial threshold 0.05 | counts in samples (= 5 s at 20 Hz) |
| `server/lib/vitals.ts:86-88, 121` | `VitalsComputer(sampleRate = 20, windowSeconds = 10)`, buffer 200, `computeDFT(…, this.sampleRate)` | fixed rate 20, live |
| `server/lib/signal-processing.ts:1004-1012` | demo generator `sampleRate = 20` | demo only |
| `scripts/ai_inference.py:201, 208, 388, 492-502` | `HISTORY_LEN = 100` frames; `DEFAULT_FS = 20.0` fallback; `fs` measured as mean rate | no resampling; a window counted in frames (1.5 s at 65 fps) |
| `phantom/dsp.py:84, 181` (`sample_rate_hz = 5.0`), set at `phantom/runtime.py:72` | `RespirationBandFilter` rfftfreq at 5 Hz | reference runtime, not the live path |
| `scripts/reporting/activity_classifier.py:45`, `scripts/rf_validation/dual_target_analyzer.py:45`, `scripts/csi_filter_pipeline.py:689` | `20.0` Hz defaults | offline / auxiliary tools |
| `server/lib/dataset-recorder.ts:142` | `SUMMARY_MIN_FPS = 20` | recorder summary threshold |
| `server/lib/phase-test-logger.ts:6`, `server/lib/udp-server.ts:722` | comments "50 Hz per node", "20-50 Hz" | **stale comments** (measured: about 65 fps per node) |
| `scripts/presence_eval/periodicity.py:35-36` (`GRID_HZ`, `GRIDS_HZ`) | the only uniform linear resampler | evaluation tool, **fixed here** |

Several of these are window lengths counted in frames or samples that silently assume a rate: that is PS-FIX-12 (Item H), not changed here.

### 6.3 Alias arithmetic and the two bands (new tool `scripts/presence_eval/alias_check.py`, 41 tests)

The ping cadence is 30 ms = 33.33 Hz (`csi_ping_pure.h`), and the recordings carry an alternation of frame kinds at that period (Item B), so the amplitude stream has a real 33.33 Hz component and harmonics. Alias frequency = |k·33.33 − n·fs|:

| fs (Hz) | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | harmonics inside respiration (0.1–0.5) / cardiac (0.8–2.0) / 1–20 Hz |
|--|--|--|--|--|--|--|--|
| 20 (production tick) | 6.67 | 6.67 | 0 | 6.67 | 6.67 | 0 | 0 / 0 / 4 |
| 50 (old tool grid) | 16.67 | 16.67 | 0 | 16.67 | 16.67 | 0 | 0 / 0 / 4 |
| 64 (PS-FIX-09 workaround) | 30.67 | **2.67** | 28.0 | **5.33** | 25.33 | **8.0** | 0 / 0 / **3** |
| **100 (new default)** | 33.33 | 33.33 | 0 | 33.33 | 33.33 | 0 | 0 / 0 / **0** |

* **The alias does not land inside either vital band on any grid**, for any harmonic up to k = 12 (tested). Vital respiration and cardiac frequencies are not corrupted by an alias *line*.
* **A red flag in an earlier claim:** `14-PS-FIX-09.md` says 64 Hz "moves the alias out of the 1–20 Hz band". True for the fundamental only: the 2nd, 4th and 6th harmonics fold to 2.67, 5.33 and 8.0 Hz, inside the band.
* Synthetic stream (two frames per ping alternating in kind, 0.3 Hz respiration and 1.2 Hz cardiac tones): the strongest line above 2.5 Hz lands exactly where the arithmetic says (16.67 / 30.67 / 33.33 Hz on the 50 / 64 / 100 Hz grids; **6.67 Hz** after production-like 20 Hz decimation); respiration is recovered at 0.30 Hz on every path.
* **The cardiac tone is a different story under the production-like decimation.** Irregular nearest-sample decimation spreads the strong 33.3 Hz energy into a broadband skirt: cardiac-tone signal-to-noise (peak over band median) is **3–11** with nearest-sample decimation, against **430–1,600** anti-aliased and **110–1,400** on the linear grids (9 stream/seed combinations; the test asserts the ordering). So the vitals path can lose a small cardiac tone to decimation noise, even though no alias line sits in the band. Synthetic only `[UNVERIFIED]` on real data.

### 6.4 Real recordings

**(a) The periodicity tool, 15 s windows, three grids** (`results/periodicity.json`; the previous file is backed up in `.tmp/fix-backups/C-PS-FIX-40/results/`):

| grid | share of windows whose 1–20 Hz peak sits at the ping alias | fan vs empty AUC, 2026-10-18 | fan vs empty AUC, 2026-10-27 | empty-vs-empty control (limit 0.65) |
|--|--|--|--|--|
| 50 Hz | **0.734** (the artefact: 16.67 Hz) | 0.10 [0.00, 0.30] | 0.68 [0.56, 0.93] | fails, 1.00 |
| 64 Hz | 0.000 | 0.39 [0.29, 0.64] | 0.60 [0.37, 0.77] | fails, 1.00 |
| **100 Hz** | 0.000 | 0.36 [0.23, 0.62] | 0.53 [0.32, 0.74] | fails, 1.00 |

The 50 Hz artefact produced spurious extreme AUCs (0.10); on the alias-free grid the intervals include 0.5 in both sessions and the empty-vs-empty control still fails. **PS-FIX-09's negative result stands**: no fan/periodicity label is supported.

**(b) Production-like decimation versus anti-aliased decimation, through a replica of the classifier's scoring** (`alias_check.py`, all 4 nodes of the 14 recordings pooled by class, 2 s windows, step 0.5 s). Suppression needs **both** label `mechanical` and `humanProb ≤ 0.2` (`node-fusion.ts:125-126`, a placeholder constant):

| class | windows | median high-frequency (>5 Hz) share, raw → anti-aliased | share of windows that would suppress, raw → anti-aliased | windows whose label changes |
|--|--|--|--|--|
| walking (person present) | 1,662 | 0.537 → 0.356 | **0.78 % → 3.64 %** | 47.7 % |
| still (person present) | 5,398 | 0.556 → 0.354 | 2.02 % → 3.08 % | 51.0 % |
| two_people | 10,628 | 0.558 → 0.363 | 1.99 % → 3.36 % | 49.8 % |
| empty | 36,138 | 0.565 → 0.372 | 3.53 % → 3.04 % | 49.7 % |
| empty_fan | 3,764 | 0.548 → 0.367 | 1.01 % → 2.70 % | 49.9 % |

Reading, both failure directions: **under-detection** (person present, suppressed): the alias does **not** increase suppression; in this proxy anti-aliasing would suppress *more* walking windows (0.78 % → 3.64 %), not fewer. **Ghost target** (empty / fan, not suppressed): for empty rooms suppression moves 3.53 % → 3.04 %; for the fan, 1.01 % → 2.70 %. The alias clearly inflates the high-frequency ratio (about 0.19 for every class, class-independent) and flips about half of all labels, but the **decision** that matters moves by under 3 points and not in one direction. **Limits:** the replica's scalar is the per-frame mean amplitude of ONE node, a proxy for the production `dynamicAmplitude` (clutter-removed complex channel, nodes interleaved by the round-robin queue); decimation is emulated as the first frame at or after each 50 ms tick. This measures the mechanism, not the live label rates.

### 6.5 The fix, and what was deliberately not changed

* **Changed (tool only, no flag needed):** `GRID_HZ = 50.0 → 100.0`, `GRIDS_HZ = (50.0, 64.0, 100.0)` in `periodicity.py`; the old grids stay in the compared set, so earlier results remain reproducible. **Why exactly 100 Hz:** it is 3 × 33.33 Hz, so every harmonic of the ping cadence folds to 0 Hz (removed by detrending) or to 33.33 Hz (above the 20 Hz band); the Nyquist frequency (50 Hz) is 1.5 times the fundamental (margin 16.7 Hz); 64 Hz fails this (harmonics 2, 4, 6 land in band). The arrivals are about 65 per second, so interpolating to 100 Hz adds no information; it only keeps the alias out of the band. Fan-label conclusions are unchanged (6.4a).
* **Not changed:** the production decimation path (`websocket.ts:808`, the dequeue). It is detection-critical, a change would have to be replayed through the real scalar path in both failure directions (the proxy above is not enough), and the measured effect on the suppress decision is small and not one-directional. A design for an anti-aliased or rate-scaled per-tick path belongs with PS-FIX-12 (Item H). `DEFAULT_MOTION_THRESHOLD`, the tier thresholds and `PHANTOM_MECHANICAL_REJECT_MAX` are untouched.
* **Presence-gate output counts:** none can move: no production code changed (the only edited code files are the evaluation tool and its new module).

### 6.6 Tests, before and after (full output in `90-test-report.md`, section "Wave 3 — after Item C")

| suite | before (= after Item A2) | after Item C |
|--|--|--|
| TS `npm test` | 444 / 444 | 444 / 444 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 412 passed, 5 skipped | **453 passed**, 5 skipped (+41: alias arithmetic, synthetic alias line, band-energy / SNR, nearest versus anti-aliased decimation, FIR, classifier replica, suppress constant pinned to the TS source, periodicity grid, read-only guard) |
| existing DSP / periodicity tests | unchanged | unchanged (`test_presence_eval_periodicity.py` 6/6 pass on explicit rates) |
| F1/F2; AI-firewall whole / filtered | 3/3; 46/46; 11/11 | 3/3; 46/46; 11/11 |
| sessions guard | snapshot 738 files / 166 entries | **PASS**, 0 changed, 0 new |

### 6.7 Limits and commit

Limits: proxy scalar (6.4b); the synthetic SNR result is synthetic only; recorder timestamps are host clock; no hardware touched. **Commit:** the new files (`alias_check.py`, `tests/test_presence_eval_alias_check.py`) are committed on their own. The `periodicity.py` edit is a 4-line change to one of my untracked Wave 2 files (PS-FIX-09), so it stays with that file in the Wave 0–2 commits (`88-commit-proposal.md`); its diff is `patches/C-PS-FIX-40.patch`.
## 7. Item D — a PHY-guard fault can never drop or delay a frame

### 7.1 A real defect, found by the test going red first

The guard added in PS-FIX-08 is documented as "shadow mode, never drops". The new test injects a guard whose `observe` throws and sends five frames through the REAL UDP handler (`startUDPServer`, port **5099 only**). **Before the fix: 0 of 5 frames were ingested.** An exception inside the message handler's guard call propagated out of the handler, so a guard fault would have dropped every frame. The baseline test (healthy guard) passed in the same run. (The red run also did not exit: the handler's sidecar-forward socket was never closed, so the process hung until killed.)

### 7.2 The change (`server/lib/udp-server.ts`, `server/lib/phy-guard.ts`)

* `phyGuard.observe(...)`, the `snapshot()` read and the mismatch logging are inside one `try/catch`; a thrown fault increments `phyGuardFaults` and the frame carries on to `signalServer.ingestSample` untouched.
* Log policy: `shouldLogPhyGuardFault(n)` is true for the **first** fault and then every **1000th**, never per frame. The line names the node and the error and says the frame is still ingested.
* `server.on("close")` now also closes the sidecar-forward socket (it leaked before). The live server never closes normally, so this is behaviour-neutral at runtime; it lets a test or a clean shutdown exit.
* **No threshold, tier, setting or detection decision changed.** Shadow mode is unchanged: the guard still never drops or alters a frame.

### 7.3 Tests (6 new, `server/lib/udp-server-phy-guard-fault.test.ts`)

Healthy guard: frame ingested, no fault logged (baseline). Throwing guard: **5 of 5 frames ingested, first one in 6.9 ms**, samples unaltered (node 1, RSSI −47). Five faults produce **exactly one** log line. After the fault clears, ingestion carries on and a healthy frame logs nothing. The log policy table (1st and every 1000th: n = 1, 1000, 2000 yes; 2, 3, 10, 999, 1001, 1999, 2001, 0 no). The test asserts the bound port is 5099 and closes the server and aborts if it is anything else; `UDP_PORT` is set before `./udp-server` is evaluated (it reads it at load). It never touches 5000 or 5005. The existing PS-FIX-08 tests (including the source-level "never drops" test) pass unchanged.

### 7.4 Suites, before and after (full output in `90-test-report.md`, section "Wave 3 — after Item D")

| suite | before (= after Item C) | after Item D |
|--|--|--|
| TS `npm test` | 444 / 444 | **450 / 450** (+6) |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 453 passed, 5 skipped | 453 passed, 5 skipped (no Python file changed) |
| F1/F2; AI-firewall whole file / filtered | 3/3; 46/46; 11/11 | 3/3; 46/46; 11/11 |
| sessions guard | snapshot 738 files / 166 entries | **PASS**, 0 changed, 0 new |

### 7.5 Failure direction, limits, commit

* **Under-detection (frames dropped because of a guard fault): 0 of 5 ingested before, 5 of 5 after.** Ghost direction: not affected (nothing is added to or suppressed from the stream).
* Limits: only an injected exception was tested (the guard's own code has no known fault); the fault counter is per server instance and resets on restart; the log goes to `console.error`.
* **Not committed on its own:** the `try/catch` wraps a block that exists only in the working tree (the PS-FIX-08 lines in `udp-server.ts` were never committed), and the new test needs `phy-guard.ts`, also uncommitted. Staging Item D alone against HEAD is not possible. It goes into the **PS-FIX-08 commit** of the Wave 0–2 sequence (`88-commit-proposal.md` §8). Diff: `patches/D-PS-FIX-D.patch`; backups `.tmp/fix-backups/D-PS-FIX-D/`.
## 8. Item H — PS-FIX-12 rate-scaled timing: design note only

`10-PS-FIX-12-design.md`. No production code, no test, no value changed; the suites are identical to the Item D run (TS 450/450, `tsc` clean, Python 453 passed + 5 skipped, F1/F2 3/3, firewall 46/46 and 11/11, guard PASS; output in `90-test-report.md` "after Item H" and in `results/last25-per-item.md`). It lists **18 constants** counted in frames or samples with `file:line`, converts each to seconds at 11 / 42 / 65 fps, shows that the fused detector's own window is already time-based (`MOTION_WINDOW_MS`, `websocket.ts:41-44, 2048`), quantifies the failure case from the s7 link step (a 100-frame window grows 1.59 s → 2.27 s, +43 %; a 1200-frame firmware baseline 19.0 s → 27.3 s), and ends with **9 Gate 3 questions**. One detail worth knowing now: at 65 fps the sidecar's 100-frame history gives an FFT bin spacing of 0.65 Hz, so **no bin falls inside the 0.1–0.5 Hz respiration band**.

## 9. Item I — licence hygiene (PS-FIX-24 / -26): re-verified, check script added; nothing deleted or moved

### 9.1 Re-verified against the current files (2026-11-04)

| fact | now | was (`06-licences.md`, 2026-11-03) |
|--|--|--|
| `ai model and densepose/model/pose_v1.safetensors` | 507,032 B, sha256 `eb249b9a6b2e10130437a10976ed0230b0d085f86a0553d7226e1ae6eae4b9e5`, mtime 23 Jun | same size and hash prefix `eb249b9a6b2e1013` |
| nested repo `model/` | gitlink pinned `39a01a1`; `README.md` modified; **`pose_v1.safetensors` still untracked inside it** | same |
| tracked by the superproject? | **no**: only the gitlink; `git ls-files "ai model and densepose"` lists the gitlink and `wifi_densepose/__init__.py` | same |
| other weight-like files in the working tree (`.safetensors .onnx .pt .pth .npz .glb`, outside `node_modules`, `.venv`, `.tmp`) | only the three in the nested repo: `csi-embed-v2.safetensors`, `model.safetensors`, `pose_v1.safetensors` | same |
| packaged build `dist/` (gitignored; 7 files: `index.cjs` 1,179,749 B built 8 Sep, `public/…`) | **0 matches** for `pose_v1`, `MM-Fi`, `MMFi`, `Wi-Pose`, `safetensors` in any file | not checked before |
| packaging config (`package.json`, `script/build.ts`, `vite.config.ts`, `.gitignore`) | nothing references the model directory | not checked before |
| exported-report templates (`scripts/build_academic_reports.py`, `scripts/reporting/session_reporter.py`, `server/lib/recording-export.ts`) | no mention | not checked before |
| deliverable documents (`README.md`, `docs/*.md`, `docs/presentations/`, `generated_reports/`) | no mention | not checked before |
| mentions anywhere else | `docs/adr` (10 files) and `docs/research/03` (third-party design notes); `new-implementation_plan.md` and four dated `PhantomScan_*` reports (internal history); `scripts/ai_inference.py` and `scripts/inspect_pose_weights.py` (the sidecar, below) | |
| MM-Fi / Wi-Pose data, weights or code | **none vendored**; MM-Fi appears only in ADR text (CC BY-NC 4.0). Whether the `PoseNet` architecture in `ai_inference.py` ("matches pose_v1") is MM-Fi-derived is **`[UNVERIFIED]`** | |

### 9.2 New finding — PS-FIX-45: the sidecar loads the restricted weights whenever the file exists

`scripts/ai_inference.py:300-316` calls `load_file(POSE_WEIGHTS)` at startup `if os.path.exists(POSE_WEIGHTS)`, **regardless of the opt-in flag**. Only the inference (`:513`) and the `poseFrame` output (`:690`) are gated by `PHANTOM_AI_POSE` (default off). So the weights of unverified provenance are loaded into memory in a running product even though no pose result is emitted by default. **Not changed** (a code change, not a deletion or a check): the owner's options are (a) load only when `PHANTOM_AI_POSE` is set, (b) remove the weights from the working tree before any packaging, (c) both. A folder copy of the working tree (as opposed to a git clone, which carries only the gitlink) would still carry the file.

### 9.3 The check script (`scripts/check_licence_hygiene.py`, 43 tests, read-only)

* **Fails (exit 1)** when: a tracked file has a weight-like suffix; a tracked or packaged file has the **SHA-256** of `pose_v1` (found even if renamed); `dist/` contains `pose_v1` / `MM-Fi` / `MMFi` / `Wi-Pose` (any case) or a weight-like file; or those strings appear in a template, source file or deliverable document, unless the exact file is in `REVIEWED_MENTIONS` (two entries, with reasons, and the check fails if an entry goes stale).
* **Warns (exit 0)** for restricted weights in the working tree that are neither tracked nor packaged; `--strict-working-tree` makes that a failure. It never deletes, moves or edits anything (a test hashes the tree before and after a failing run and asserts no write/delete call exists in the source).
* **Real run:** `OK (0 failures, 1 warning)`: 7 packaged files and 229 template/source/document files scanned, the two reviewed mentions noted, the nested `pose_v1.safetensors` reported as a warning. With `--strict-working-tree` it fails on that warning, as intended.
* Limits: the content scan reads bytes, so an obfuscated or compressed mention would not be seen; the digest check covers only the one restricted file; `docs/adr` and `docs/research` are out of scope on purpose.

### 9.4 Tests, before and after (full output in `90-test-report.md`, section "Wave 3 — after Item I")

| suite | before (= after Item D) | after Item I |
|--|--|--|
| TS `npm test` | 450 / 450 | 450 / 450 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 453 passed, 5 skipped | **496 passed**, 5 skipped (+43) |
| F1/F2; AI-firewall whole file / filtered | 3/3; 46/46; 11/11 | 3/3; 46/46; 11/11 |
| sessions guard | snapshot 738 files / 166 entries | **PASS**, 0 changed, 0 new |

Failure direction: neither (no detection, display or ingest path touched). Commit: the script and its test are new files and are committed on their own.
## 10. Section 4 — recording-readiness (so analysis can start the day recordings exist)

Nothing here analyses a new recording (none exists) and nothing changes a threshold, a tier constant or a setting.

### 10.1 Pre-registration first (`reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md`)

Written **before** the validator and the analysis code; it states the validity gates, the candidate scores, the success criteria and the failure rule in advance. Every number has a source in the existing tooling or the 2026-11-02 frozen criteria (`04-two-node-eval.md` §1): C1 walking vs the second empty, lower 95 % bound ≥ **0.80**; C2 fan false-positive rate not above the empty's; C3 no held-out empty flagged in more than **5 %** of its windows at α = 1 %; C4 empty-vs-empty symmetric upper bound ≤ **0.65**; ≥ **100** held-out empty blocks and ≥ **60** windows per class; **1** false alarm per hour as the calibration target; 6 dB / 0.7 / 20 fps / 60 min / 5 min from `calibration-soak.ts` and `epochs.py`. **Left as `[OWNER TO SET]` (no number picked):** the fan-with-person duration, C1b (still vs empty), C2b (fan with a person), C7 (seconds tolerated in each failure direction); `[OWNER TO CONFIRM]` C6 and the inherited C1–C3. **Added as candidates, with no numbers:** K7 parity-aware decor (PS-FIX-37) and K8 anti-aliased decimation of the 20 Hz classifier input (PS-FIX-40 / PS-FIX-43; offline only, PS-FIX-43 stays measured-not-changed). **It is not frozen until the owner commits it:** `run_campaign.py` refuses to analyse unless the file is tracked and unmodified, and writes its SHA-256 into every report.

### 10.2 Recording protocol as a data spec (`RECORDING-DATA-SPEC.md`)

Folder layout (`data/datasets/campaign-2026-11/<campaign_id>/campaign.json` + `blocks/NN_<type>/`), naming (the recorder's own), `campaign.json` and `block.json` fields (block type, start/stop UTC, entry log, link-state notes, fan on/off, person count, node placement, link-change events), the six blocks (empty ≥ 60 min with entry log; fan alone ≥ 5; walking ≥ 5; still ≥ 5; second empty ≥ 60; fan with a person) all inside one link state, and the **LINK CHANGE rule** (≥ 6 dB held RSSI step or a held rate collapse → stop, log, wait 2 min, new block). No recorder change is needed.

### 10.3 Ingest validator (`scripts/presence_eval/campaign.py`, CLI `validate_campaign`, 25 tests)

Read-only; exit 0 valid / 1 invalid / 2 usage. **Refuses, with one clear line each:** a missing sidecar (`campaign.json`, `block.json`, a recording's `*.summary.json`, an empty block's entry log, or an entry log with fewer than a start and an end line); a block shorter than its minimum; a node rate outside [20, 100] fps; a held RSSI step or rate collapse inside a block (reusing `epochs.detect_events`); a node missing or present in under 90 % of the seconds; an undeclared ≥ 6 dB shift between blocks of one link state; a block without `link_state_id`; no link state holding all six block types; an unknown type, a duplicate id, or a label that does not match the block type; unreadable JSON or recordings. The `--json` report is refused under `data/`; a test hashes the campaign folder before and after and asserts nothing changed. The fan-with-person minimum is **not enforced** (a warning says so) until the owner sets it.

### 10.4 One-command analysis (`scripts/presence_eval/run_campaign.py`, 13 tests)

`python -m scripts.presence_eval.run_campaign <folder>`: refuses (exit 1) if the validator fails, (exit 3) if the pre-registration is not committed and unmodified (`--allow-uncommitted-prereg` is for dry runs and is flagged in the report), (exit 2) for any output under `data/`. Then: per-block windows, K1–K3, **K7 parity-aware decor**, the **causal self-baseline movement score** (windows strictly before t; defined only with ≥ 80 % of the lookback windows; L = 45 s and 90 s), AUC with 10 s moving-block bootstrap intervals (1,000 resamples, fixed seed), the **C4 gate first**, C1–C3, and both failure directions in seconds (walking/still seconds with no marker; empty/fan seconds with a marker). Thresholds are fitted on the **first empty block only** (tested). Every number is `measured`; anything not computable (for example fewer than 60 windows) is `[TO BE MEASURED]`; criteria without a number are `[OWNER TO SET]` and are not judged; if no candidate meets the criteria the report says "no candidate met the criteria" and claims no accuracy, detection-rate or false-alarm figure. Note: C2 is implemented as the pre-registered strict point comparison (fan flagged share not above the empty's, with no interval), which is noisy for equal distributions; the owner may want an interval before freezing.

### 10.5 Dry run on the existing recordings: same numbers as the current repo tooling

The existing recordings contain link steps, so the dry run feeds the **repo's own epoch segmentation** (`epochs.build_timeline` + `epoch_eval.make_segments`, wrapped as `legacy_epoch_segments`) through `run_campaign`'s scoring and evaluation layer and compares with `results/movement_score.json` (variant `N1+N2/decor/L45`):

| comparison | run_campaign | stored by the existing tooling | difference |
|--|--|--|--|
| E05 walking (s7) vs empty (s6), AUC | 0.777791703221 | 0.777791703221 | **0** (tolerance 1e-9), windows 101 / 79 vs 101 / 79 |
| E07 s8 vs s9 empty pair, AUC | 0.540075201625 | 0.540075201625 | **0** (tolerance 1e-9) |
| E07 worst symmetric upper bound | 0.574 | 0.574 | bootstrap size differs (1000 vs 300), compared within 0.05 |

A first attempt on the whole recordings gave 118 walking windows instead of 101: s7 contains node 1's persistent step (−35 → −48 dBm), the stored result uses the part before it. That is exactly what the validator is there to prevent in a real campaign (a block with a held step is refused). **Nothing in this dry run is a new result, and no threshold is touched.**

### 10.6 Suites, before and after (full output in `90-test-report.md`, section "Wave 3 — after section 4")

| suite | before (= after Item I) | after section 4 |
|--|--|--|
| TS `npm test` | 450 / 450 | 450 / 450 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 496 passed, 5 skipped | **534 passed**, 5 skipped (+25 validator, +13 run_campaign) |
| F1/F2; AI-firewall whole file / filtered | 3/3; 46/46; 11/11 | 3/3; 46/46; 11/11 |
| sessions guard | snapshot 738 files / 166 entries | **PASS**, 0 changed, 0 new |

Failure direction: neither for this section (no detection path changed); the analysis tool reports both directions in seconds once data exist. **Commit:** the code and tests are new files committed on their own; the two documents live in the (untracked) `reports/` folder: **the owner commits the pre-registration first** (step 1 of `88b-commit-steps.md`).

## 11. After the commits (2026-11-05)

### 11.1 The 88b commit run

26 commits (P, O1-O8, M-01...M-08, M-10...M-14, R; `e3b87ca` ... `4e0ea25`), run by `.tmp/commit-steps/run_steps.py`. For every step the expected `--stat` was printed, the staged `git diff --cached --stat` was printed, and the step was committed only because the two were identical (the stop-on-mismatch path was tested first in a throwaway clone with a deliberately altered expectation). Nothing was pushed; `.tmp/pre-wave3-backup` verified before step 1; sessions guard **PASS** (738 files / 166 entries, 0 new). **Final proof:** `HEAD` blob equals the working-tree file for all 1,903 files outside `data/`, `.tmp/` and `node_modules` (LF-normalised). The only line of `git diff HEAD --stat -- . :!data :!node_modules` is the nested model repository (`ai model and densepose/model`, 0 insertions, 0 deletions): it was already ` m` in the pre-commit `git status` (`.tmp/pre-wave3-backup/git-status.txt`); inside it `README.md` is modified and `pose_v1.safetensors` is untracked; the recorded gitlink commit is unchanged. **Nine commits (P and O1-O8) carry no `Co-Authored-By` trailer** (the runner's message for P left it out); history was not rewritten.

### 11.2 Pre-registration frozen with the owner's values (commit `e3b87ca`, committed before any analysis)

Fan-with-person minimum **10 min**; C1b and C2b lower 95 % bound **>= 0.80**, each a separate claim that does not change the "meets the criteria" rule (C4 gate + C1-C3); **C7 report-only** (both failure directions in seconds per block, no limit, cannot make a candidate meet or fail; the measured values become the basis for the next campaign's limits); C6 (1 per hour), C1 (>= 0.80), C3 (5 %) confirmed; 1.5 s windows confirmed (800 ms, PS-EVAL-016, exploratory only); section 7 keeps the history. `grep "OWNER TO"` on the file: no match. Consequence: `test_the_real_prereg_file_...` (which asserted the open items were still open) was **red from `e3b87ca` until `cfe9158`**; HEAD `f3aab82` therefore had 1 failing test in the Python suite (538 passed, 1 failed, 5 skipped), by design and fixed in the next commit.

### 11.3 PS-FIX-45 (commit `f3aab82`): `pose_v1` is read only when `PHANTOM_AI_POSE` is on

Before: `load_file(POSE_WEIGHTS)` ran at sidecar start whenever the file existed, although inference and `poseFrame` were already gated. After: the load sits behind the same flag; flag off logs why and reads nothing. Test: the load block is cut out of `ai_inference.py` with `ast` and executed against stubs (flag off: 0 reads; flag on: exactly 1; flag on, file missing: warning, 0 reads; flag off, file missing: no "random keypoints" warning; no other statement uses `POSE_WEIGHTS`), 5 tests, red before (3 failed) and green after. F1/F2 3/3 and the licence-hygiene tests pass. Failure direction: with the flag off nothing changes for the operator (pose was never rendered); with the flag on behaviour is identical.

### 11.4 Campaign code now matches the frozen pre-registration (commit `cfe9158`)

C2 is an interval: d = (fan flagged share) - (empty_2 flagged share), 95 % moving-block bootstrap (10 s blocks, 1,000 resamples, fixed seed) at alpha 1 % and 5 %; it fails only if the lower bound is above 0 (new `stats.block_bootstrap_rate_diff`). A test case where the fan's point share (2.0 %) exceeds the empty's (1.0 %) but 6 windows cannot show it passes C2 (the old strict comparison failed it); a loud fan (+5) fails; an identical distribution passes. C1b / C2b are computed per candidate and rendered as separate claims, never in the verdict (test: both false, verdict still MEETS). C7 is rendered as a report-only table (walking / still seconds not flagged, empty_2 / fan-alone seconds flagged, alpha 1 %). The validator enforces the 10 min fan-with-person minimum. The "strict point comparison" sentence in section 10.4 is **superseded by this section**.

### 11.5 Suites

| suite | before (section 4) | after `cfe9158` |
|--|--|--|
| TS `npm test` | 450 / 450 | 450 / 450 |
| `npx tsc --noEmit` | 0 errors | 0 errors |
| Python (scratch venv) | 534 passed, 5 skipped | **545 passed**, 5 skipped (+5 PS-FIX-45, +5 run_campaign, +1 validator) |
| F1/F2; AI-firewall whole file / filtered | 3/3; 46/46; 11/11 | 3/3; 46/46; 11/11 |
| sessions guard | 738 / 166 | **PASS**, 0 changed, 0 new |
