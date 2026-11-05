# PS-FIX-00 and PS-FIX-01 — baseline and test hygiene

**Provenance.** Run 2026-11-02, branch `feat/two-node-radar-live-detection`, HEAD `744ce43`, dirty tree (baseline manifest: `results/baseline-manifest.txt`, 1,773 files; `git diff` sha256 `b9887e0d…`). Outputs: `90-test-report.md`. Footprints: `results/footprint-00-PS-FIX-00.txt`, `results/footprint-01-PS-FIX-01.txt`. Patch: `patches/01-PS-FIX-01.patch`. Backups: `.tmp/fix-backups/01-PS-FIX-01/`.

## PS-FIX-00 — baseline (closes PS-EVAL-001)

* TS 407/407; F1/F2 3/3; AI-firewall 11/11.
* Scratch venv (outside the repo, `D:\WIFI csi\phanotm\_scratch_venv_fulltest`, the repo's own `.venv` package set + scikit-learn 1.9.1): **full Python suite 210 passed, 0 failed, 0 skipped in 275 s.** The earlier 163 passed + 5 skipped = 168 = 210 − 42 (tests added by the evaluation task), so the missing tests were exactly the sklearn-dependent ones, and the earlier 5 skips were the live-server tests (see below). The slow count-CNN test `test_count_model.py::test_trains_calibrates_exports_and_reloads` takes **68.0 s**.
* **Unplanned side effect, disclosed.** That 275 s run executed `TestServerIngestion` against the operator's live dashboard on `:5000` (it was up; earlier runs skipped these tests because it was not). It logged in with the test's default credentials, ingested recorded samples and created sessions. Artifacts created at 22:13 local: `data/sessions/000000205 - 2026-11-02.json`, `000000206 - 2026-11-02.json`, `test20_2026-11-02T19-13-03-672Z.{json,csv,pdf}`, and two new entries in the **tracked** `data/sessions/_index.json`. I did not delete or edit them (rule: never touch `data/sessions`, never delete). **Proven restore recipe for Thaer:** removing exactly the two index entries whose `id` ends with `2026-11-02` reproduces the baseline sha256 of `_index.json` byte-for-byte (`json.dumps(entries, indent=2)`, no trailing newline); the server may need a restart so it does not re-write them. Whether this polluted any live display or stored data on the server side is `[UNVERIFIED]`.

## PS-FIX-01 — what changed (4 files)

| file | change | why |
|--|--|--|
| `server/test-setup.ts` (new) | sets `PHANTOM_AUDIT_DIR` to a per-process temp dir (removed on exit) unless already set | the audit logger singleton read `data/audit` and the TS suite appended auth events to the operator's real audit log (PS-EVAL-019) |
| `package.json` | `npm test` and `test:dashboard-auth` run `tsx --import ./server/test-setup.ts --test …` | loads the setup in every test process |
| `tests/test_esp_capture_e2e.py` | `TestServerIngestion._server_available()` returns False unless `PHANTOM_E2E_LIVE_SERVER=1`; skip message updated | the tests log in, ingest and create sessions on whatever answers on :5000 |
| `pyproject.toml` | `[project.optional-dependencies] train = ["scikit-learn"]` (no pin; only 1.9.1 was tested); the import stays at module top | scikit-learn is genuinely required by `phantom/activity_train.py`, `count_train.py`, `scripts/train/*` and was declared nowhere |

## Evidence (before / after)

| | before | after |
|--|--|--|
| `data/audit/audit-current.jsonl` lines across a full `npm test` | grew (2226 → 2250 during the evaluation task and Wave 0) | **2250 → 2250, mtime unchanged** |
| TS suite | 407/407 | 407/407 |
| Python (scratch venv) | 210 passed (incl. live-server tests against :5000, creating sessions) | 205 passed + 5 skipped (the opt-in tests); `data/sessions` file count 735 → 735 |
| F1/F2, AI-firewall | 3/3, 11/11 | 3/3, 11/11 |

Both failure directions: not applicable (no detection behaviour touched).

## Not done / notes

* The dependency set for running the suite (numpy, scipy, PyWavelets, pytest, torch, safetensors, …) is still declared nowhere; only the `train` extra was added. Logged as PS-FIX-20.
* `tests/test_esp_capture_e2e.py` ships default login credentials for the live-server tests (overridable by env). Not printed here; a default credential in source is logged as PS-FIX-21 for Thaer.
* The live-server tests were not exercised by this change (they were never meant to run in CI); the opt-in path itself is unrun `[UNVERIFIED]`.
