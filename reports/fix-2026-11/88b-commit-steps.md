# 88b — Commit steps (NOT executed; the owner approves and runs each one)

Generated 2026-11-04 from the working tree at HEAD `0e61373`. **Nothing here has been run in this repository.** Every step was dry-run in a THROWAWAY CLONE (`git clone --no-hardlinks`, deleted afterwards), which produced the `git diff --cached --stat` blocks below and proved that after the last step the committed tree equals the working tree for all 117 files covered (**yes**). Safety backup of the whole tree: `.tmp/pre-wave3-backup/` (`MANIFEST.sha256`).

## How each step works

* `bash .tmp/commit-steps/stage-<ID>.sh` stages the exact blobs of that step **by blob** (`git hash-object -w --no-filters` + `git update-index --cacheinfo`), never `git add <file>`, so a file that carries both your lines and mine contributes only the right lines. The script is plain text: read it first.
* Then `git diff --cached --stat` must equal the block shown for the step; then `git commit -F .tmp/commit-steps/message-<ID>.txt` (the message is shown below and may be edited).
* The working tree is never touched; `git status` shows the remaining uncommitted work.

## Preflight (before step P)

```
git diff --cached --name-only        # nothing may be staged
git log -1 --format=%h               # expect 0e61373
```

## Step P — commit the pre-registration FIRST (before any recording is analysed)

```
git add reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md
git diff --cached --stat
git commit -m "docs: pre-register the 2026-11 recording campaign (criteria fixed before any analysis)"
```

`run_campaign.py` refuses to analyse a campaign until this file is committed and unmodified. Edit the `[OWNER TO SET]` items before committing if you want them in the frozen version.

## Step O1 — chore(client): client dashboard

```
bash .tmp/commit-steps/stage-O1.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O1.txt
```

Message:

```
chore(client): client dashboard

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `client/src/components/dashboard/RadialScene.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/components/dashboard/ai-advisory-panel.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/components/dashboard/point-cloud-3d.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/components/dashboard/top-bar.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/components/dashboard/vitals-monitor.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/hooks/use-websocket.ts`: his whole file (identical to its Wave 0 hash)
* `client/src/pages/dashboard.tsx`: his whole file (identical to its Wave 0 hash)
* `client/src/components/dashboard/demo-banner.tsx`: new file, not named in any item footprint
* `client/src/hooks/use-persisted-flag.ts`: new file, not named in any item footprint
* `client/src/lib/demo-banner.test.ts`: new file, not named in any item footprint
* `client/src/lib/demo-banner.ts`: new file, not named in any item footprint
* `client/src/lib/stored-flag.test.ts`: new file, not named in any item footprint
* `client/src/lib/stored-flag.ts`: new file, not named in any item footprint
* `client/src/lib/vitals-status.test.ts`: new file, not named in any item footprint
* `client/src/lib/vitals-status.ts`: new file, not named in any item footprint

Expected `git diff --cached --stat` (captured from the dry run):

```
 client/src/components/dashboard/RadialScene.tsx    | 48 +++++++-----
 .../src/components/dashboard/ai-advisory-panel.tsx | 17 +++--
 client/src/components/dashboard/demo-banner.tsx    | 38 +++++++++
 client/src/components/dashboard/point-cloud-3d.tsx |  3 +
 client/src/components/dashboard/top-bar.tsx        | 89 +++++++++++++++++++++-
 client/src/components/dashboard/vitals-monitor.tsx | 21 ++---
 client/src/hooks/use-persisted-flag.ts             | 26 +++++++
 client/src/hooks/use-websocket.ts                  | 27 +++++++
 client/src/lib/demo-banner.test.ts                 | 66 ++++++++++++++++
 client/src/lib/demo-banner.ts                      | 52 +++++++++++++
 client/src/lib/stored-flag.test.ts                 | 47 ++++++++++++
 client/src/lib/stored-flag.ts                      | 37 +++++++++
 client/src/lib/vitals-status.test.ts               | 56 ++++++++++++++
 client/src/lib/vitals-status.ts                    | 27 +++++++
 client/src/pages/dashboard.tsx                     | 32 +++++++-
 15 files changed, 548 insertions(+), 38 deletions(-)
```

## Step O2 — chore(firmware): firmware (esp32-csi-node)

```
bash .tmp/commit-steps/stage-O2.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O2.txt
```

Message:

```
chore(firmware): firmware (esp32-csi-node)

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `firmware/esp32-csi-node/CMakeLists.txt`: his whole file (identical to its Wave 0 hash)
* `firmware/esp32-csi-node/main/Kconfig.projbuild`: his whole file (identical to its Wave 0 hash)
* `firmware/esp32-csi-node/main/csi_collector.c`: his whole file (identical to its Wave 0 hash)
* `firmware/esp32-csi-node/sdkconfig.defaults`: his whole file (identical to its Wave 0 hash)
* `firmware/esp32-csi-node/version.txt`: new file, not named in any item footprint

Expected `git diff --cached --stat` (captured from the dry run):

```
 firmware/esp32-csi-node/CMakeLists.txt         |  5 ++++
 firmware/esp32-csi-node/main/Kconfig.projbuild | 15 ++++++++++
 firmware/esp32-csi-node/main/csi_collector.c   | 38 ++++++++++++++++++++++++++
 firmware/esp32-csi-node/sdkconfig.defaults     | 15 ++++++++++
 firmware/esp32-csi-node/version.txt            |  1 +
 5 files changed, 74 insertions(+)
```

## Step O3 — chore(server): server runtime

```
bash .tmp/commit-steps/stage-O3.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O3.txt
```

Message:

```
chore(server): server runtime

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `server/lib/target-presentation.test.ts`: his whole file (identical to its Wave 0 hash)
* `server/lib/target-state.test.ts`: his whole file (identical to its Wave 0 hash)
* `server/lib/target-state.ts`: his whole file (identical to its Wave 0 hash)
* `server/lib/udp-server.ts`: his whole file (identical to its Wave 0 hash)
* `server/lib/websocket.test.ts`: his whole file (identical to its Wave 0 hash)
* `server/lib/demo-replay.test.ts`: new file, not named in any item footprint
* `server/lib/demo-replay.ts`: new file, not named in any item footprint
* `server/lib/demo-session.test.ts`: new file, not named in any item footprint
* `server/lib/demo-session.ts`: new file, not named in any item footprint
* `server/lib/demo-walker.test.ts`: new file, not named in any item footprint
* `server/lib/demo-walker.ts`: new file, not named in any item footprint
* `server/lib/websocket-demo.test.ts`: new file, not named in any item footprint
* `server/lib/websocket.ts`: owner's lines only (Wave 0 state merged onto HEAD; 0 conflict(s))

Expected `git diff --cached --stat` (captured from the dry run):

```
 server/lib/demo-replay.test.ts         | 149 ++++++++++++++++
 server/lib/demo-replay.ts              | 226 +++++++++++++++++++++++++
 server/lib/demo-session.test.ts        | 185 ++++++++++++++++++++
 server/lib/demo-session.ts             | 206 ++++++++++++++++++++++
 server/lib/demo-walker.test.ts         | 118 +++++++++++++
 server/lib/demo-walker.ts              | 249 +++++++++++++++++++++++++++
 server/lib/target-presentation.test.ts |  54 ++++++
 server/lib/target-state.test.ts        |  26 +++
 server/lib/target-state.ts             |   6 +-
 server/lib/udp-server.ts               |  40 +++++
 server/lib/websocket-demo.test.ts      | 301 +++++++++++++++++++++++++++++++++
 server/lib/websocket.test.ts           |  11 ++
 server/lib/websocket.ts                | 212 ++++++++++++++++++++++-
 13 files changed, 1774 insertions(+), 9 deletions(-)
```

## Step O4 — chore(shared): shared schema and presentation

```
bash .tmp/commit-steps/stage-O4.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O4.txt
```

Message:

```
chore(shared): shared schema and presentation

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `shared/schema.ts`: his whole file (identical to its Wave 0 hash)
* `shared/target-presentation.ts`: his whole file (identical to its Wave 0 hash)

Expected `git diff --cached --stat` (captured from the dry run):

```
 shared/schema.ts              | 15 +++++++++++++++
 shared/target-presentation.ts | 18 ++++++++++++++++++
 2 files changed, 33 insertions(+)
```

## Step O5 — chore(tests): tests

```
bash .tmp/commit-steps/stage-O5.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O5.txt
```

Message:

```
chore(tests): tests

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `tests/test_presence_eval_drift.py`: new file, not named in any item footprint
* `tests/test_presence_eval_features.py`: new file, not named in any item footprint
* `tests/test_presence_eval_inventory.py`: new file, not named in any item footprint
* `tests/test_presence_eval_twonode.py`: new file, not named in any item footprint

Expected `git diff --cached --stat` (captured from the dry run):

```
 tests/test_presence_eval_drift.py     |  84 ++++++++++++++++++
 tests/test_presence_eval_features.py  | 142 +++++++++++++++++++++++++++++++
 tests/test_presence_eval_inventory.py | 155 ++++++++++++++++++++++++++++++++++
 tests/test_presence_eval_twonode.py   | 154 +++++++++++++++++++++++++++++++++
 4 files changed, 535 insertions(+)
```

## Step O6 — chore(scripts): scripts

```
bash .tmp/commit-steps/stage-O6.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O6.txt
```

Message:

```
chore(scripts): scripts

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `scripts/presence_eval/__init__.py`: new file, not named in any item footprint
* `scripts/presence_eval/drift.py`: new file, not named in any item footprint
* `scripts/presence_eval/features.py`: new file, not named in any item footprint
* `scripts/presence_eval/inventory.py`: new file, not named in any item footprint
* `scripts/presence_eval/provenance.py`: new file, not named in any item footprint
* `scripts/presence_eval/recordings.py`: new file, not named in any item footprint
* `scripts/presence_eval/ref_two_node.ts`: new file, not named in any item footprint
* `scripts/presence_eval/repro.py`: new file, not named in any item footprint
* `scripts/presence_eval/stats.py`: new file, not named in any item footprint
* `scripts/presence_eval/tables.py`: new file, not named in any item footprint
* `scripts/presence_eval/twonode.py`: new file, not named in any item footprint

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/__init__.py     |   1 +
 scripts/presence_eval/drift.py        | 248 ++++++++++++++++++++++
 scripts/presence_eval/features.py     | 106 ++++++++++
 scripts/presence_eval/inventory.py    | 154 ++++++++++++++
 scripts/presence_eval/provenance.py   |  51 +++++
 scripts/presence_eval/recordings.py   | 197 ++++++++++++++++++
 scripts/presence_eval/ref_two_node.ts | 102 ++++++++++
 scripts/presence_eval/repro.py        | 139 +++++++++++++
 scripts/presence_eval/stats.py        | 128 ++++++++++++
 scripts/presence_eval/tables.py       |  85 ++++++++
 scripts/presence_eval/twonode.py      | 374 ++++++++++++++++++++++++++++++++++
 11 files changed, 1585 insertions(+)
```

## Step O7 — chore(docs): docs

```
bash .tmp/commit-steps/stage-O7.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O7.txt
```

Message:

```
chore(docs): docs

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `docs/esp32s3-framework-comparison-report.md`: new file, not named in any item footprint

Expected `git diff --cached --stat` (captured from the dry run):

```
 docs/esp32s3-framework-comparison-report.md | 105 ++++++++++++++++++++++++++++
 1 file changed, 105 insertions(+)
```

## Step O8 — chore(root): root files and other

```
bash .tmp/commit-steps/stage-O8.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-O8.txt
```

Message:

```
chore(root): root files and other

The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.
```

Files (path: how staged):

* `README.md`: owner's lines only (Wave 0 state merged onto HEAD; 0 conflict(s))

Expected `git diff --cached --stat` (captured from the dry run):

```
 README.md | 1 +
 1 file changed, 1 insertion(+)
```

## Step M-01 — test: stop the suites writing into the real audit log and live sessions (PS-FIX-01)

```
bash .tmp/commit-steps/stage-M-01.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-01.txt
```

Message:

```
test: stop the suites writing into the real audit log and live sessions (PS-FIX-01)

TS tests use a temp audit dir; the live-server Python tests are opt-in; scikit-learn declared as an optional 'train' extra.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `package.json`: my hunks only (3-way: base = state before 01-PS-FIX-01)
* `pyproject.toml`: my hunks only (3-way: base = state before 01-PS-FIX-01)
* `tests/test_esp_capture_e2e.py`: my hunks only (3-way: base = state before 01-PS-FIX-01)
* `server/test-setup.ts`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 package.json                  |  4 ++--
 pyproject.toml                |  8 ++++++++
 server/test-setup.ts          | 23 +++++++++++++++++++++++
 tests/test_esp_capture_e2e.py | 19 +++++++++++++------
 4 files changed, 46 insertions(+), 8 deletions(-)
```

## Step M-02 — fix: harden the dataset loader (PS-FIX-02)

```
bash .tmp/commit-steps/stage-M-02.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-02.txt
```

Message:

```
fix: harden the dataset loader (PS-FIX-02)

phantom/dataset.py counts bad lines/frames, never truncates mixed widths, streams in chunks; strict mode kept.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `phantom/dataset.py`: my hunks only (3-way: base = state before 02-PS-FIX-02)
* `tests/test_dataset_loader.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 phantom/dataset.py           | 150 ++++++++++++++++++++++++++++++++++++-------
 tests/test_dataset_loader.py | 139 +++++++++++++++++++++++++++++++++++++++
 2 files changed, 267 insertions(+), 22 deletions(-)
```

## Step M-03 — feat: both recorders write the same compact JSON and header schema 2 (PS-FIX-03)

```
bash .tmp/commit-steps/stage-M-03.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-03.txt
```

Message:

```
feat: both recorders write the same compact JSON and header schema 2 (PS-FIX-03)

Per-part start, geometry hash, operator-stated capture conditions, node-moved annotation; readers accept schema 1 and 2.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `phantom/dataset.py`: my hunks only (3-way: base = state before 03-PS-FIX-03)
* `scripts/record_dataset.py`: my hunks only (3-way: base = state before 03-PS-FIX-03)
* `server/lib/dataset-recorder.test.ts`: my hunks only (3-way: base = state before 03-PS-FIX-03)
* `server/lib/dataset-recorder.ts`: my hunks only (3-way: base = state before 03-PS-FIX-03)
* `tests/test_record_dataset.py`: my hunks only (3-way: base = state before 03-PS-FIX-03)

Expected `git diff --cached --stat` (captured from the dry run):

```
 phantom/dataset.py                  |  8 ++-
 scripts/record_dataset.py           | 99 ++++++++++++++++++++++++++++++++++---
 server/lib/dataset-recorder.test.ts | 77 ++++++++++++++++++++++++++++-
 server/lib/dataset-recorder.ts      | 93 ++++++++++++++++++++++++++++++++--
 tests/test_record_dataset.py        | 61 ++++++++++++++++++++++-
 5 files changed, 325 insertions(+), 13 deletions(-)
```

## Step M-04 — feat: stricter evaluation tooling (PS-FIX-04)

```
bash .tmp/commit-steps/stage-M-04.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-04.txt
```

Message:

```
feat: stricter evaluation tooling (PS-FIX-04)

Rank AUC with block-bootstrap CIs, session-blocked AUC, empty-vs-empty control C4, always-absent control, abstentions counted as misses.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/eval-presence-on-datasets.ts`: my hunks only (3-way: base = state before 04-PS-FIX-04)
* `scripts/accuracy/__tests__/auc-bootstrap.test.ts`: new file
* `scripts/accuracy/auc-bootstrap.ts`: new file
* `scripts/presence_eval/jsonutil.py`: new file
* `tests/test_presence_eval_controls.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/accuracy/__tests__/auc-bootstrap.test.ts |  55 +++++++++
 scripts/accuracy/auc-bootstrap.ts                |  84 ++++++++++++++
 scripts/eval-presence-on-datasets.ts             |  49 +++++---
 scripts/presence_eval/jsonutil.py                |  34 ++++++
 tests/test_presence_eval_controls.py             | 140 +++++++++++++++++++++++
 5 files changed, 348 insertions(+), 14 deletions(-)
```

## Step M-05 — docs: correct frame rate, geometry and capability claims (PS-FIX-05)

```
bash .tmp/commit-steps/stage-M-05.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-05.txt
```

Message:

```
docs: correct frame rate, geometry and capability claims (PS-FIX-05)

Capability figures labelled [TO BE MEASURED]; claims swept; dated records untouched.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `.agents/AGENTS.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `DETECTION_REPORT.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `JODDB_PHASE2_TECHNICAL_PROPOSAL.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `MEASUREMENT_PLAN.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `Phantom-Scan-Final-Project-Report-4Node.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `README.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `docs/WIFI_DENSEPOSE_INTEGRATION.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `docs/presentations/JODDB-Sponsorship-Pitch-Script.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `docs/system_architecture_methodology.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `firmware/esp32-csi-node/README.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `generated_reports/Appendix.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md`: my hunks only (3-way: base = state before 05-PS-FIX-05)
* `scripts/build_academic_reports.py`: my hunks only (3-way: base = state before 05-PS-FIX-05)

Expected `git diff --cached --stat` (captured from the dry run):

```
 .agents/AGENTS.md                                      |  2 +-
 DETECTION_REPORT.md                                    |  4 ++--
 JODDB_PHASE2_TECHNICAL_PROPOSAL.md                     | 10 ++++++----
 MEASUREMENT_PLAN.md                                    |  2 +-
 Phantom-Scan-Final-Project-Report-4Node.md             |  4 ++--
 README.md                                              |  8 ++++----
 docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md | 10 ++++++----
 docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md           |  4 +++-
 docs/WIFI_DENSEPOSE_INTEGRATION.md                     |  2 +-
 docs/presentations/JODDB-Sponsorship-Pitch-Script.md   |  2 +-
 docs/system_architecture_methodology.md                |  2 +-
 firmware/esp32-csi-node/README.md                      | 12 ++++++------
 generated_reports/Appendix.md                          |  6 +++---
 generated_reports/Section-1.2-WiFi-Frequency-vs-CSI.md |  2 +-
 scripts/build_academic_reports.py                      | 14 +++++++-------
 15 files changed, 45 insertions(+), 39 deletions(-)
```

## Step M-06 — feat: AI sidecar refuses the saturated shipped presence head (PS-FIX-06)

```
bash .tmp/commit-steps/stage-M-06.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-06.txt
```

Message:

```
feat: AI sidecar refuses the saturated shipped presence head (PS-FIX-06)

phantom/presence_guard.py and tests; licence inventory in the reports.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/ai_inference.py`: my hunks only (3-way: base = state before 06-PS-FIX-06)
* `phantom/presence_guard.py`: new file
* `tests/test_presence_guard.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 phantom/presence_guard.py    | 54 ++++++++++++++++++++++++++++
 scripts/ai_inference.py      | 12 +++++--
 tests/test_presence_guard.py | 86 ++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 150 insertions(+), 2 deletions(-)
```

## Step M-07 — test: E2E guard and the session-pollution restore tool (pre-Wave-2)

```
bash .tmp/commit-steps/stage-M-07.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-07.txt
```

Message:

```
test: E2E guard and the session-pollution restore tool (pre-Wave-2)

tests/e2e_guard.py, scripts/restore_session_pollution.py and their tests.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `tests/test_count_model.py`: my hunks only (3-way: base = state before 07-PRE-WAVE2)
* `tests/test_esp_capture_e2e.py`: my hunks only (3-way: base = state before 07-PRE-WAVE2)
* `tests/test_train_activity.py`: my hunks only (3-way: base = state before 07-PRE-WAVE2)
* `scripts/restore_session_pollution.py`: new file
* `tests/e2e_guard.py`: new file
* `tests/test_e2e_guard.py`: new file
* `tests/test_restore_session_pollution.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/restore_session_pollution.py    | 135 ++++++++++++++++++++++++++++++++
 tests/e2e_guard.py                      |  43 ++++++++++
 tests/test_count_model.py               |   6 +-
 tests/test_e2e_guard.py                 |  41 ++++++++++
 tests/test_esp_capture_e2e.py           |  17 ++--
 tests/test_restore_session_pollution.py | 105 +++++++++++++++++++++++++
 tests/test_train_activity.py            |   6 +-
 7 files changed, 342 insertions(+), 11 deletions(-)
```

## Step M-08 — feat: link-state epochs, movement score and recorder summary sidecar (Wave 2 addendum)

```
bash .tmp/commit-steps/stage-M-08.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-08.txt
```

Message:

```
feat: link-state epochs, movement score and recorder summary sidecar (Wave 2 addendum)

epochs.py, epoch_eval.py, movement.py; both recorders write a per-part summary sidecar.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/record_dataset.py`: my hunks only (3-way: base = state before 08-WAVE2)
* `server/lib/dataset-recorder.test.ts`: my hunks only (3-way: base = state before 08-WAVE2)
* `server/lib/dataset-recorder.ts`: my hunks only (3-way: base = state before 08-WAVE2)
* `tests/test_record_dataset.py`: my hunks only (3-way: base = state before 08-WAVE2)
* `scripts/presence_eval/epoch_eval.py`: new file
* `scripts/presence_eval/epochs.py`: new file
* `scripts/presence_eval/movement.py`: new file
* `tests/test_presence_eval_epochs.py`: new file
* `tests/test_presence_eval_movement.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/epoch_eval.py  | 207 +++++++++++++++++++++++++++
 scripts/presence_eval/epochs.py      | 264 +++++++++++++++++++++++++++++++++++
 scripts/presence_eval/movement.py    | 227 ++++++++++++++++++++++++++++++
 scripts/record_dataset.py            |  98 ++++++++++++-
 server/lib/dataset-recorder.test.ts  |  98 +++++++++++++
 server/lib/dataset-recorder.ts       | 109 ++++++++++++++-
 tests/test_presence_eval_epochs.py   | 234 +++++++++++++++++++++++++++++++
 tests/test_presence_eval_movement.py | 169 ++++++++++++++++++++++
 tests/test_record_dataset.py         |  62 ++++++++
 9 files changed, 1465 insertions(+), 3 deletions(-)
```

## Step M-10 — feat: PHANTOM_DATA_DIR for every data path, default unchanged (PS-FIX-27)

```
bash .tmp/commit-steps/stage-M-10.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-10.txt
```

Message:

```
feat: PHANTOM_DATA_DIR for every data path, default unchanged (PS-FIX-27)

server/lib/data-dir.ts and eight call sites; the default path is identical to before (tested).

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `server/audit/logger.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/auth/service.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/lib/dataset-recorder.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/lib/phase-test-logger.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/lib/runtime-settings.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/lib/session-store.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `server/lib/websocket.ts`: my hunks only (3-way: base = state before 10-PS-FIX-27)
* `scripts/presence_eval/epoch_sensitivity.py`: new file
* `server/lib/data-dir.test.ts`: new file
* `server/lib/data-dir.ts`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/epoch_sensitivity.py | 108 +++++++++++++++++++++++++++++
 server/audit/logger.ts                     |   3 +-
 server/auth/service.ts                     |   3 +-
 server/lib/data-dir.test.ts                |  60 ++++++++++++++++
 server/lib/data-dir.ts                     |  14 ++++
 server/lib/dataset-recorder.ts             |   5 +-
 server/lib/phase-test-logger.ts            |   3 +-
 server/lib/runtime-settings.ts             |   3 +-
 server/lib/session-store.ts                |   3 +-
 server/lib/websocket.ts                    |   5 +-
 10 files changed, 198 insertions(+), 9 deletions(-)
```

## Step M-11 — feat: PHY shadow guard and header-offset audit; a guard fault never drops a frame (PS-FIX-08)

```
bash .tmp/commit-steps/stage-M-11.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-11.txt
```

Message:

```
feat: PHY shadow guard and header-offset audit; a guard fault never drops a frame (PS-FIX-08)

Shadow mode only counts/logs. A thrown guard fault is isolated in try/catch and logged once per 1000 (0/5 frames ingested before, 5/5 after); the forward socket closes with the server.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/presence_eval/presence_head_norms.py`: new file
* `server/lib/phy-guard.test.ts`: new file
* `server/lib/phy-guard.ts`: new file
* `server/lib/udp-server-phy-guard-fault.test.ts`: new file
* `tests/test_csi_header_offsets.py`: new file
* `tests/test_presence_head_norms.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/presence_head_norms.py  | 166 ++++++++++++++++++++++++++
 server/lib/phy-guard.test.ts                  |  85 +++++++++++++
 server/lib/phy-guard.ts                       |  69 +++++++++++
 server/lib/udp-server-phy-guard-fault.test.ts | 158 ++++++++++++++++++++++++
 tests/test_csi_header_offsets.py              |  58 +++++++++
 tests/test_presence_head_norms.py             |  64 ++++++++++
 6 files changed, 600 insertions(+)
```

## Step M-12 — feat: frame-rate truth analysis (PS-FIX-07)

```
bash .tmp/commit-steps/stage-M-12.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-12.txt
```

Message:

```
feat: frame-rate truth analysis (PS-FIX-07)

scripts/presence_eval/frame_rate.py and its test.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/presence_eval/frame_rate.py`: new file
* `tests/test_presence_eval_frame_rate.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/frame_rate.py    | 183 +++++++++++++++++++++++++++++++++
 tests/test_presence_eval_frame_rate.py |  73 +++++++++++++
 2 files changed, 256 insertions(+)
```

## Step M-13 — feat: calibration soak rules; no threshold from a single run (PS-FIX-11)

```
bash .tmp/commit-steps/stage-M-13.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-13.txt
```

Message:

```
feat: calibration soak rules; no threshold from a single run (PS-FIX-11)

scripts/accuracy/calibration-soak.ts, replay tool; calibrate-threshold.ts refuses short runs and never writes settings.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/calibrate-threshold.ts`: my hunks only (3-way: base = state before 13-PS-FIX-11)
* `scripts/accuracy/__tests__/calibration-soak.test.ts`: new file
* `scripts/accuracy/calibration-soak.ts`: new file
* `scripts/accuracy/replay-calibration-runs.ts`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 .../accuracy/__tests__/calibration-soak.test.ts    | 172 ++++++++++++
 scripts/accuracy/calibration-soak.ts               | 297 +++++++++++++++++++++
 scripts/accuracy/replay-calibration-runs.ts        |  88 ++++++
 scripts/calibrate-threshold.ts                     |  95 +++++--
 4 files changed, 637 insertions(+), 15 deletions(-)
```

## Step M-14 — feat: fan/periodicity analysis, negative result; alias-free 100 Hz grid (PS-FIX-09, PS-FIX-40)

```
bash .tmp/commit-steps/stage-M-14.sh
git diff --cached --stat
git commit -F .tmp/commit-steps/message-M-14.txt
```

Message:

```
feat: fan/periodicity analysis, negative result; alias-free 100 Hz grid (PS-FIX-09, PS-FIX-40)

periodicity.py; default grid 100 Hz = 3 x the ping cadence, old grids kept.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Files (path: how staged):

* `scripts/presence_eval/periodicity.py`: new file
* `tests/test_presence_eval_periodicity.py`: new file

Expected `git diff --cached --stat` (captured from the dry run):

```
 scripts/presence_eval/periodicity.py    | 329 ++++++++++++++++++++++++++++++++
 tests/test_presence_eval_periodicity.py |  84 ++++++++
 2 files changed, 413 insertions(+)
```

## Step R — the reports (last)

```
git add reports
git diff --cached --shortstat
git commit -m "docs: Wave 0-3 evaluation reports, ledgers, merge gate and test output"
```

Expected `--shortstat` at generation time: `116 files changed, 143757 insertions(+)`. This number grows if more report files are added after this document was generated (re-run the generator, or compare counts approximately). `reports/fix-2026-11/09-WAVE3-addendum.md` is a running record: commit it only when Wave 3 is closed.

## Never commit

`data/sessions/_index.json` and the dashboard's session files, `.tmp/`, the nested model repository (`ai model and densepose/model`, shown as `m` in `git status`) and `pose_v1.safetensors` (PS-FIX-24/-26).

## Findings from the dry run

* every 3-way merge was clean; no conflicts. (`server/lib/websocket.ts`: with your lines committed first, my PS-FIX-27 hunk applies on top without the conflict seen in `88-commit-proposal.md`.)
