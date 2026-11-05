# 89 — Merge gate (state at Gate 1, after Wave 1)

**Provenance.** 2026-11-03, HEAD `744ce43`, branch `feat/two-node-radar-live-detection`, dirty tree (Thaer's 38 original edits + the previous evaluation task's files + this task's Wave 1). Nothing committed, pushed, stashed, reset, deleted or moved. Evidence: `90-test-report.md`, `results/baseline-manifest.txt`, `results/footprint-*.txt`, `patches/`.

| check | result | evidence |
|--|--|--|
| Full TS suite green | **PASS** 418/418 (407 baseline + 11 new: 5 recorder, 6 AUC) | `90-test-report.md` |
| Full Python suite green | **PASS** 250 passed + 5 skipped in the scratch venv (baseline 210 passed incl. the 5 live-server tests = 205 + 5 opt-in skips, plus 45 new tests: 11 loader, 6 recorder, 11 harness controls, 17 presence guard); the 5 skips are the live-server tests, now opt-in | `90-test-report.md` |
| F1 / F2 tests | **PASS** `test_f1_*` ×2 and `test_f2_*` ×1 (3/3); AI-firewall in `websocket.test.ts` 11/11 (filtered run, name pattern `F1\|AI\|advisory\|firewall`; the whole file is 46 tests: see 09-WAVE3-addendum.md); re-run after every item | `90-test-report.md` |
| Footprint of each item = files named by the item | **PASS** for items 00–07 (the one nested-repo file is recorded by hand because the guard cannot see inside a gitlink). **Correct totals (computed, `results/footprint-reconciliation.txt`): 25 tracked files edited, 6 earlier untracked evaluation files modified again, 8 new files (+ item 07: 3 changed test files, 4 new files), 1 nested-repo file.** The "12" in my first Gate 1 message was wrong. | `results/footprint-*.txt` |
| No threshold, tier constant or runtime setting changed | **PASS** — `DEFAULT_MOTION_THRESHOLD`, `PHANTOM_MOTION_THRESHOLD`, tier thresholds untouched; `data/runtime-settings.json` absent and untouched | `git diff` of the item patches; protected-path scan |
| Protected paths untouched (`.git`, `keys/`, `data/operator.json`, `data/runtime-settings.json`, `data/datasets`, `recordings/`) | **PASS** (0 files newer than the baseline). **EXCEPTION — `data/sessions`: 6 files written by my Wave 0 full-suite run against the live dashboard (PS-FIX-23).** Not deleted; restore recipe in the ledger | `find … -newer baseline-manifest.txt` |
| AI path: F1 not weakened | **PASS** — `scripts/ai_inference.py` change only withholds an advisory input; adds no message type/field | `06-PS-FIX-06.md`; F1 tests |
| Dashboard passive, F2 not weakened | **PASS** — no `client/` file touched | footprints |
| Firmware untouched, nothing flashed | **PASS** — no `firmware/**/*.c|h` edit (only `firmware/esp32-csi-node/README.md`) | footprint 05 |
| Backups for every edited tracked file in `.tmp/fix-backups/<item>/` | **PASS** | `.tmp/fix-backups/` |
| Line endings preserved | **PASS** for all edited tracked files (one stray CRLF in `dataset-recorder.test.ts` normalised; HEAD has none); two of my own untracked files became CRLF | byte check |
| Every number has provenance | **PASS** — each report states command/commit/date/inputs; results JSON carry a provenance block | item reports |
| Caveats present; limitations stated | **PASS** — each item report has "not done"/limits | item reports |
| **No claim of improved detection** | **PASS** — Wave 1 changed no detection behaviour; the stricter harness (C4) still shows **no candidate meeting the pre-registered criteria** | `04-PS-FIX-04.md` |
| Secrets not printed | **PASS** — a default test login exists in source (PS-FIX-21); its value was not reproduced | ledger |

**Verdict for Wave 1:** mergeable as new/changed files, with two items needing Thaer's action before anything is committed: **PS-FIX-23** (test artifacts in `data/sessions` + the tracked `_index.json`) and **PS-FIX-24** (nested model repo). Wave 1 changed **no runtime detection behaviour**, so it improves tooling, tests, docs and metadata honesty only.

---

# Merge gate — Wave 2 (state after PS-FIX-08, -07, -11, -09; PS-FIX-10 skipped, -15 deferred)

**Provenance.** 2026-11-03, HEAD `744ce43`, dirty tree. Evidence: `90-test-report.md` (verbatim outputs after each item), `results/footprint-{08-WAVE2,10-PS-FIX-27,11-PS-FIX-08,12-PS-FIX-07,13-PS-FIX-11,14-PS-FIX-09}.txt`, `patches/`, item reports `08-WAVE2-addendum.md`, `09-DECISIONS.md`, `11…14-PS-FIX-*.md`.

| check | result | evidence |
|--|--|--|
| Full TS suite | **PASS** 444/444 (after PS-FIX-11; 432 after PS-FIX-08) | `90-test-report.md` |
| `npx tsc --noEmit` | **PASS** 0 errors | `90-test-report.md` |
| Full Python suite (scratch venv) | **PASS** 342 passed + 5 opt-in skips (after PS-FIX-09); repo `.venv`: the new test files pass (26/26 for the three newest) | `90-test-report.md` |
| F1 / F2 and AI-firewall | **PASS** 3/3 and 46/46 (`websocket.test.ts`), re-run after each item | `90-test-report.md` |
| Safety constants / settings | **PASS** — no threshold, tier constant or runtime setting changed; `data/runtime-settings.json` untouched; the calibration tool cannot write settings (tested) | patches |
| **Runtime code changed in Wave 2 (none of it changes a detection decision)** | (1) `server/lib/data-dir.ts` + 8 call sites: `PHANTOM_DATA_DIR`, default identical to before (tested); (2) dataset recorders write a per-part summary sidecar and header schema-2 fields; (3) `server/lib/phy-guard.ts` + 17 lines in `server/lib/udp-server.ts`: counts/logs PHY-tuple changes, **never drops, alters or delays a frame** (source-level test). Reviewable as small hunks. | `09-DECISIONS.md`, `11-PS-FIX-08.md`, `patches/11-PS-FIX-08-udp-server.patch` |
| Dashboard passive (F2) | **PASS** — no `client/` file touched in Wave 2 | footprints |
| Firmware untouched, nothing flashed, no hardware touched | **PASS** | footprints |
| Protected paths | **PASS** — `data/sessions` 730 entries and audit log 2250 lines after every item; PS-FIX-23 cleanup done earlier with your "apply" | `90-test-report.md` |
| Backups of every edited tracked file | **PASS** — `.tmp/fix-backups/{08..14}-*/` | backups |
| **No claim of improved detection** | **PASS** — Wave 2 produced analysis and guards, not a better detector. Every candidate tried failed its criteria (movement score, presence head, periodicity), and the new calibration tool refuses to give a number on our existing recordings | `08-WAVE2-addendum.md`, `09-DECISIONS.md`, `13-PS-FIX-11.md`, `14-PS-FIX-09.md` |
| Honesty: unmeasured/unverifiable labelled | **PASS** — `[TO BE MEASURED]` / `[UNVERIFIED]` in each report | item reports |

**Verdict for Wave 2:** mergeable as new/changed files **after you decide** the items in the final message (PS-FIX-23 is closed; PS-FIX-24/-26 licences and PS-EVAL-010/-013 are still yours). Both failure directions are unchanged at runtime: under-detection and ghost targets are neither improved nor worsened by Wave 2.


---

# Merge gate — Wave 3 (running; state after Item A)

**Provenance.** 2026-11-04, HEAD `744ce43`, dirty tree. Drift check is the owner's provisional value `b3c571e291c55326` / 734 (Wave-2 rule `0261130fef4cfed9` / 730 not edited). Evidence: `90-test-report.md`, `09-WAVE3-addendum.md`.

| check | result | evidence |
|--|--|--|
| Full TS suite | **PASS** 444/444 before and after Item A | `90-test-report.md` |
| `npx tsc --noEmit` | **PASS** 0 errors | `90-test-report.md` |
| Full Python suite (scratch venv) | **PASS** 362 passed + 5 opt-in skips (342 + 20 new doc-lint tests) | `90-test-report.md` |
| F1 / F2 | **PASS** 3/3 | `90-test-report.md` |
| AI-firewall | **PASS** whole file 46/46 and filtered 11/11, both executed | `90-test-report.md`, `09-WAVE3-addendum.md` §1 |
| Drift check before/after | **PASS** `b3c571e291c55326` / 734, unchanged | `90-test-report.md` |
| Safety constants | **PASS** no threshold, tier constant or setting changed; code diffs are comment-only (proof in addendum §3.5) | diff vs `.tmp/fix-backups/A-PS-FIX-38/` |
| Firmware / hardware | **PASS** untouched, nothing flashed, no serial port opened | footprint |
| Dashboard passive (F2) | **PASS** no `client/` file touched | footprint |
| Commits | **none yet** (Item A's files overlap the owner's uncommitted edits; question in chat) | addendum §3.6 |


## Wave 3 — after Item B (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 444/444, 0 errors | `90-test-report.md` ("after Item B") |
| Full Python suite (scratch venv) | **PASS** 396 passed + 5 opt-in skips (362 + 24 + 10) | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46 and filtered 11/11, both executed | same |
| Sessions guard (owner's diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new files | same |
| Safety constants | **PASS** nothing changed (Item B touches no runtime file) | footprint |
| Firmware / hardware / serial | **PASS** untouched; no serial-port code exists in any new file (tested) | tests |
| Dashboard passive (F2) | **PASS** no `client/` file touched | footprint |
| Commits | Item A `6b5e330`; Item B as its own commit (all-new files) | git log |
## Wave 3 — after Item A2 (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 444/444, 0 errors | `90-test-report.md` ("after Item A2") |
| Full Python suite (scratch venv) | **PASS** 412 passed + 5 opt-in skips (396 + 16 lint tests) | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46 and filtered 11/11, both executed | same |
| Sessions guard (diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new | same |
| Safety constants / values | **PASS** none changed; `websocket.ts` diff is comment lines only; `"0.6"` and `?? 0.05` literals untouched | diff vs `.tmp/fix-backups/A2-PS-FIX-41/` |
| Firmware / hardware / serial | **PASS** untouched | footprint |
| Commits | `6b5e330` (A), `955b028` (B), `3ae66c7` (A2); nothing pushed | git log |
## Wave 3 — after Item C (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 444/444, 0 errors | `90-test-report.md` ("after Item C") |
| Full Python suite (scratch venv) | **PASS** 453 passed + 5 opt-in skips (412 + 41) | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46, filtered 11/11, both executed | same |
| Sessions guard (diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new | same |
| Safety constants / production code | **PASS** no production file changed; thresholds, tier constants, `PHANTOM_MECHANICAL_REJECT_MAX` untouched | footprint |
| Firmware / hardware / serial | **PASS** untouched | footprint |
| Commits | Item C new files as their own commit; `periodicity.py` edit stays with the Wave 2 files; nothing pushed | git log |
## Wave 3 — after Item D (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 450/450 (444 + 6), 0 errors | `90-test-report.md` ("after Item D") |
| Full Python suite (scratch venv) | **PASS** 453 passed + 5 opt-in skips (unchanged) | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46, filtered 11/11, both executed | same |
| Sessions guard (diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new | same |
| Ports | **PASS** the new test bound 5099 only (asserted); 5000 / 5005 never touched | test source |
| Safety constants / detection | **PASS** none changed; shadow mode unchanged | patch |
| Firmware / hardware / serial | **PASS** untouched | footprint |
| Commits | Item D is not committed alone (see §7.5); nothing pushed | git log |
## Wave 3 — after Items H and I (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 450/450, 0 errors (H and I) | `90-test-report.md` ("after Item H", "after Item I") |
| Full Python suite (scratch venv) | **PASS** 453 (after H) and 496 (after I: +43 licence-check tests), + 5 opt-in skips | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46, filtered 11/11, both executed | same |
| Sessions guard (diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new, after H and after I | same |
| Licence hygiene | **PASS** `check_licence_hygiene.py`: 0 failures, 1 warning (nested untracked weights) | `09-WAVE3-addendum.md` §9 |
| Safety constants / detection | **PASS** none changed | footprint |
| Firmware / hardware / serial | **PASS** untouched | footprint |
| Commits | Item H: no code (design note, untracked report). Item I: new files, committed on their own; nothing pushed | git log |
## Wave 3 — after section 4 (running)

| check | result | evidence |
|--|--|--|
| Full TS suite / `tsc` | **PASS** 450/450, 0 errors | `90-test-report.md` ("after section 4") |
| Full Python suite (scratch venv) | **PASS** 534 passed + 5 opt-in skips (496 + 25 + 13) | same |
| F1 / F2; AI-firewall | **PASS** 3/3; whole file 46/46, filtered 11/11, both executed | same |
| Sessions guard (diff rule) | **PASS** 738 files / 166 entries unchanged, 0 new | same |
| Validator and analysis are read-only | **PASS** tests hash the campaign folder before and after; any output under `data/` is refused | tests |
| No threshold or setting changed | **PASS** the analysis cannot write settings; the report claims no accuracy figure unless the pre-registered criteria are met | source |
| Pre-registration | **drafted, not frozen**: the owner must commit it before any recording is analysed (enforced by `run_campaign.py`) | `PREREG-2026-11-recording-campaign.md` |
| Commits | section 4 code and tests as their own commit; documents are in untracked `reports/` | git log |
