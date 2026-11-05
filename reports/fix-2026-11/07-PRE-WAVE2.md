# Pre-Wave-2 fixes (from the Gate 1 review)

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree). Footprint `results/footprint-07-PRE-WAVE2.txt` (3 changed, 4 added). Backups `.tmp/fix-backups/07-PRE-WAVE2/`. Footprint reconciliation `results/footprint-reconciliation.txt`. Tests: `90-test-report.md`.

## 1. Session history cleanup (PS-FIX-23) — tool ready, **NOT applied, waiting for you**

Applying it means editing a protected path while the dashboard owns it, so I did not. What exists:

* `scripts/restore_session_pollution.py` — **dry-run by default.** With `--apply` it (a) refuses if anything listens on :5000, (b) refuses unless removing the two entries reproduces the baseline sha256 of `_index.json` **byte-for-byte**, (c) backs up `_index.json` to `.tmp/fix-backups/23-sessions/`, (d) rewrites the index, (e) **moves (never deletes)** the 5 files to `.tmp/quarantine-sessions-<date>/`, checking every destination first so a collision aborts before anything changes. 8 tests run it in sandboxes only (dry-run changes nothing; exact 5 files + 2 entries; byte-for-byte restore + backup + idempotence; refuses on wrong hash, open port, missing baseline; all-or-nothing on a quarantine collision; unrelated same-day sessions kept).
* **Dry run on the real `data/sessions` (nothing changed):** entries `000000206 - 2026-11-02`, `000000205 - 2026-11-02`; files `000000205/206 - 2026-11-02.json`, `test20_2026-11-02T19-13-03-672Z.{json,csv,pdf}`; restored index sha256 `0261130f…683fc8` = **MATCH** with the baseline manifest.
* **Current state:** nothing is listening on :5000 right now (checked with `netstat`), so the dashboard appears to be stopped. **Say "apply" and I will run `python scripts/restore_session_pollution.py --apply`** (and tell you to restart the dashboard afterwards). If you restart the dashboard first, stop it again before telling me.

## 2. Opt-in made safer (`tests/e2e_guard.py`)

`PHANTOM_E2E_LIVE_SERVER=1` is no longer enough. The live-server e2e tests now require **a separate local port** (default `http://127.0.0.1:5099`, override `PHANTOM_E2E_SERVER_URL`) and **refuse :5000**, non-local hosts, non-http URLs and URLs without an explicit port (16 tests). Only the exact value `1` opts in. Start the throw-away server with `PORT=5099 npm run dev` (`server/index.ts` honours `PORT`). **Residual risk, stated plainly:** the session store writes to `data/sessions` relative to the server's working directory, so a throw-away server started from the repo root would still write there — start it from a scratch working directory. A `PHANTOM_DATA_DIR` setting in `server/lib/session-store.ts` would remove that risk but is a server code change; I did not make it (say if you want it).

## 3. Default test run

`tests/test_count_model.py` and `tests/test_train_activity.py` now `pytest.importorskip("sklearn", reason="scikit-learn not installed: pip install -e '.[train]' …")` **before** their first sklearn-dependent import. **Plain `pytest tests/ -q` in the repo's own `.venv` (no scikit-learn): 251 passed, 7 skipped, exit 0** (before: 2 collection errors, run aborted). The skips name their reason. With the extra installed (the scratch venv) both modules run as before: 274 passed + 5 opt-in skips. CI should install the `train` extra, otherwise two modules silently skip.

## 4. What "12" meant — corrected

My Gate 1 message said "the 12 tracked files edited in Wave 1". **That number was wrong**; I cannot reconstruct what I counted, and I should have computed it. Computed from the footprints and `git cat-file HEAD:`:

| | count |
|--|--|
| distinct files listed as changed (M) in items 01–06 | 33 |
| … tracked in git HEAD (real edits to repository files) | **25** (15 docs/report-generator files, 3 recorder/loader/eval scripts, `scripts/ai_inference.py`, `package.json`, `pyproject.toml`, 3 test files, 2 recorder sources) |
| … my own files created earlier in this task (`tests/test_dataset_loader.py`, extended in item 03) | 1 |
| … untracked files from the previous evaluation task that I modified again | 6 (`scripts/presence_eval/{drift,inventory,provenance,repro,stats,twonode}.py`) |
| … the nested-repo README (not visible to the guard; recorded by hand) | 1 |
| distinct new files (A) | 8 |

(Items 05's footprint lists 16 because it includes the nested-repo README note.) Item 07 adds 3 tracked/changed test files and 4 new files.

The two mismatches you spotted, both from the earlier evaluation task's files: **`scripts/presence_eval/provenance.py` has no backup** because its only edit in this task (the `default_out_dir()` hunk, item 04) came after I backed up the other `presence_eval` files; it is untracked, so the pre-edit text is not in git either, but the change is a 7-line addition and trivially reversible. **`tests/test_presence_eval_twonode.py` is backed up but not in the footprint** because I backed it up as a precaution and never edited it in item 04 (correct and harmless). One more: the item-02 backup folder contains a stray `__pycache__/dataset.cpython-313.pyc` created when I imported the backed-up module for the memory comparison.

## Judgement calls

* **Presence-head guard:** unchanged. Measuring the real un-normalised activation norms on our recordings (run the encoder over features from `room1`) is the right way to decide; I propose it as a Wave 2 analysis item rather than changing the check now.
* **Licences:** recorded as a standing rule: `pose_v1.safetensors` and anything MM-Fi-derived stay out of any JODDB deliverable until provenance is known (ledger PS-FIX-26). Nothing was verified at its source (no web access).
* **Recorder metadata:** agreed that operator-entered `capture` fields will mostly stay empty. The header is written when a part *opens*, so automatic per-node RSSI/fps summaries need a **sidecar written when the part closes** (`<part>.summary.json`) rather than a header field; I can add that (small, no behaviour change) — say if you want it before Wave 2.
* **Test output not pasted in full in chat:** acknowledged as a deviation; `90-test-report.md` holds the verbatim runs.

Both failure directions: not applicable (test and tooling changes only).
