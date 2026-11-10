# AI models and datasets — inventory (2026-11-10)

**Status of this file:** committed (491cefb); the only training run is the people-count CNN of 2026-11-11 (refused, see 1.2); nothing was downloaded, flashed or pushed. No credential or environment secret was read or printed.
**Convention:** `[UNVERIFIED]` = not read from a file in this session. `[TO BE MEASURED]` = no measurement exists on disk. No accuracy, detection or false-positive figure is claimed by this report; the only numbers quoted are those in a report file on disk (path given) and upstream claims that are labelled as upstream's.

**Pre-check (done first).** No file under `data/` or `reports/` had been written in the previous 5 minutes (and none in the previous 60 minutes anywhere in the repo, excluding `node_modules`, `.git`, `.next`, `__pycache__`). The only `python` processes were the VS Code isort language server. No recording or soak was running.

**How the dataset facts were obtained.** A read-only streaming scanner (scratch script outside the repo) read line 1 (header) and counted frame lines per node, first/last timestamp, and whether any frame line carries a `seq` / `nsc` key. No file was loaded whole. Frame rate = frames per node ÷ (last − first timestamp) of that node, over the whole recording (so a mid-recording rate drop lowers it).

---

## Section 1 — Model inventory

### 1.0 Table

| # | Model | Status | Weights / output on disk | Runtime consumer | Default state |
|---|---|---|---|---|---|
| 1 | Activity classifier (multinomial logistic regression on window features) | **REFUSED BY GATE** | report only: `models/rooms/room1/activity.report.json`; **no `activity.json`** | `scripts/ai_inference.py` (needs `PHANTOM_ROOM_ID` + `activity.json`) | nothing to load |
| 2 | People-count CNN (`CountNet`, classes 0 / 1 / 2+) | **REFUSED BY GATE** (trained 2026-11-11, `--epochs 4 --permutations 3`) | report only: `models/rooms/room1/count.report.json` (gitignored); **no `count.json` / `count.safetensors`** | `scripts/ai_inference.py` (needs `count.json` + `count.safetensors`) | nothing to load |
| 3 | csi-embed-v2 encoder (8→64→128) | **PRETRAINED (external)** | `ai model and densepose/model/csi-embed-v2.safetensors` 39,672 B (2026-06-08 18:37); `csi-embed-v2-int4.bin` 4,672 B (standardizer only is read) | `scripts/ai_inference.py` | **loaded if both files exist** |
| 4 | Presence head (logistic, 128 weights) | **PRETRAINED (external) + REFUSED BY GATE** | `…/model/presence-head.json` 2,619 B (2026-06-08 18:37) | `scripts/ai_inference.py`, guard `phantom/presence_guard.py` | opt-in (`PHANTOM_AI_PRESENCE_HEAD`), and refused when enabled |
| 5 | Sidecar human/mechanical + activity-state tag | **NEVER TRAINED** (rule-based, not a learned model) | none (code) | `scripts/ai_inference.py`, `phantom/sidecar.py` | active |
| 6 | `pose_v1.safetensors` (PoseNet 56→34) | **PRETRAINED (external), provenance unverified** | `…/model/pose_v1.safetensors` 507,032 B (2026-06-23 21:42) | `scripts/ai_inference.py` | opt-in (`PHANTOM_AI_POSE`), off |
| 7 | LoRA room adapters `node-1.json`, `node-2.json` | **PRETRAINED (external), other rooms** | `…/model/node-1.json` 21,697 B, `node-2.json` 21,660 B (2026-06-08 18:37) | `scripts/ai_inference.py` | opt-in (`PHANTOM_AI_LORA`), off; none exist for nodes 3/4 |
| 8 | RuView v1 container: `model.safetensors` 48,840 B, `model-q2.bin` 4,096 B, `model-q4.bin` 8,192 B, `model-q8.bin` 16,384 B, `model.rvf.jsonl`, `config.json`, `training-metrics.json` | **PRETRAINED (external) — NOT USED** | all dated 2026-06-08 18:37 | no code reference found (grep of `scripts/`, `phantom/`, `server/`, `shared/`, `client/src`) | not loaded |
| 9 | Presence-eval candidates (15 statistical scores: 3 features × 5 fusion rules, thresholds fitted on empty recordings) | not an ML model; **no candidate met the pre-registered criteria** | `reports/presence-eval-2026-11/results/` | offline evaluation only | n/a |
| 10 | Firmware (`firmware/esp32-csi-node`: `edge_processing.c`, wasm3 runtime, `rvf_parser.c`) | no trained weights found | no `.wasm` file on disk; `edge_processing.h` has no model/weights/classifier mention | firmware | n/a |
| 11 | Server deterministic classifier (micro-Doppler, `processFrame()` in `server/lib/`) | not ML; not inventoried further | n/a | server | authoritative owner of presence/identity |

Other weight-like files found by repo-wide search: only `.tmp/presence_eval_cache/**/*.npz` (derived feature/window caches from `room1`, dated 2026-11-02, not models) and firmware build artifacts (`firmware/esp32-csi-node/build_filter/*.bin`: bootloader/app images, not AI). `ai model and densepose/wifi_densepose/__init__.py` is a package stub with no weights. The `models/` directory contains exactly two files: the activity report (item 1) and the count report (item 2).

### 1.F1 — Can any of these write an authoritative field? (F1)

Verified from code, not by running anything:

* The sidecar sets `identity["label"] = "unknown"` and sends only advisory fields (`advisoryLabel`, `humanProb`, `presenceProb`, `advisoryActivity`, `advisoryCount`, `embeddingDrift`, …) under message type `targetIdentity` (`scripts/ai_inference.py:656-701`).
* `server/lib/websocket.ts:512-530`: a `targetIdentity` message is accepted only from a registered AI client while processing, is validated with `advisoryIdentitySchema` (`shared/schema.ts:260`), and is **re-broadcast as type `advisoryIdentity`**. It never writes `currentTargetIdentity`; a non-AI client's message is ignored. `vitalSigns` follows the same rule (`advisoryVitalSigns`, lines 531-546). Tests: `server/lib/websocket.test.ts:94-110`.
* `poseFrame` from an AI client sets `currentPoseFrame` and broadcasts `poseFrame` (`websocket.ts:505-511`); it is a pose channel, not presence/identity, and is only sent when `PHANTOM_AI_POSE=1`. The code comment says the dashboard never renders it (`canPresentVolumetricTarget`) — [UNVERIFIED here: client rendering code was not re-read].
* No model output reaches the deterministic gate. F1 holds for items 1–7 on the code paths read.

### 1.1 Activity classifier — REFUSED BY GATE

* **Purpose / consumer.** Per-room label for an already-detected situation (`empty / still / walking / active`). Loaded by `scripts/ai_inference.py` from `models/rooms/<PHANTOM_ROOM_ID>/activity.json` only when `PHANTOM_ROOM_ID` is set; outputs `advisoryActivity`, `advisoryActivityConfidence`, `modelId` on the advisory channel. Cannot write presence (F1, above).
* **Code.** `phantom/activity_train.py` (training + gate), `phantom/activity_model.py` (numpy inference; model is plain arrays in JSON, no sklearn at runtime), `scripts/train/train_activity.py` (CLI), features from `phantom/features.py` (`FEATURE_NAMES`, 1.0 s windows, 0.5 s hop).
* **Training command.** `py -3.13 scripts/train/train_activity.py --room room1 [--group-by day]` (default `--data-root data/datasets`, `--models-root models/rooms`, 50 permutations). Exit 2 = refused.
* **Outputs on disk.** `models/rooms/room1/activity.report.json`, 1,568 B, modified 2026-10-28 00:38. **No `activity.json`** (`"exported": false`). `models/rooms/` is gitignored (`.gitignore:32`).
* **Training data.** `data/datasets/room1/` only. The report lists 12 recording groups (the 14 `room1` recordings minus the 2 `two_people` ones, which are skipped by `LABEL_TO_ACTIVITY`); `empty_fan` is merged into `empty`. Windows: empty 40,039 · still 5,444 · walking 2,206 · active 0.
* **Provenance / licence.** Ours (own code, own recordings). Contains human-subject recordings; consent record not in repo [UNVERIFIED] (`reports/fix-2026-11/06-licences.md` §E.4).
* **Refusal-gate result** (quoted from `models/rooms/room1/activity.report.json`, leave-one-recording-out): model balanced accuracy 0.3786 · majority baseline 0.3333 · motion-energy depth-3 tree 0.2819 · required margin 0.02 · shuffled-label null 95th percentile 0.5059 (50 runs). The gate requires the model to beat both baselines by the margin **and** the null; it did not exceed the null, so nothing was exported. These are the gate's own numbers on twelve recordings from one room and one rig; they are not a performance claim.
* **Training metrics for a deployable model:** none exists — `[TO BE MEASURED]`.

### 1.2 People-count CNN — REFUSED BY GATE

* **Purpose / consumer.** Advisory head-count class {0, 1, 2+} (`2` = "two or more", `countIsLowerBound`). Loaded by `scripts/ai_inference.py` from `models/rooms/<room>/count.json` + `count.safetensors`; emits `advisoryCount`, `advisoryCountConfidence`, `countLowConfidence`, `countModelId`. Advisory only (F1).
* **Code.** `phantom/count_model.py` (architecture: Conv1d 51→64→128→128 dilated, mean over time, Linear; input 40 frames × 51 subcarriers; temperature-scaled softmax), `phantom/count_train.py` (grouped-by-recording CV, majority + 2-feature motion tree + permutation null, exports only if it beats all three), `scripts/train/train_count.py`.
* **Training command.** Documented: `py -3.13 scripts/train/train_count.py --room room1` (defaults: 25 epochs, 10 permutations). **Actually run 2026-11-11:** `python scripts/train/train_count.py --room room1 --epochs 4 --permutations 3` (reduced because the defaults were estimated at ≈ 53 h on this CPU). Exit code 2 (refused).
* **Interpreter used.** The system Python **3.11.9** (`python` on PATH; torch 2.10.0+cpu, scikit-learn 1.8.0). The `py -3.13` launcher named in the script docstring was not found in the Git Bash shell, and the project `.venv` lacks scikit-learn (`ModuleNotFoundError`), so neither was used.
* **Outputs on disk.** `models/rooms/room1/count.report.json`, 1,027 B, written 2026-11-11 01:01 (gitignored, `.gitignore:32`). **No `count.json` and no `count.safetensors`** (`"exported": false`).
* **Training data.** `data/datasets/room1/`, all 14 recordings: 0-person (7 recordings, 61,220 windows), 1-person (5, 11,181), 2-person (2: `s1`, `s3`; 16,915). The two `two_people` recordings are exactly the minimum the script requires.
* **Refusal-gate result** (quoted from `models/rooms/room1/count.report.json`, grouped CV by whole recording): CNN balanced accuracy **0.3460** · majority baseline **0.3333** · motion-energy tree **0.3546** · shuffled-label null 95th percentile **0.1939** (3 runs, margin required 0.02). Refusal reason (training log): "model balanced accuracy 0.346 does not beat both baselines by 0.02 (majority 0.333, motion heuristic 0.355) or the shuffled-label null (95th pct 0.194); not exporting". Gate numbers on one room and one rig, not a performance claim.
* **Null-computation note.** The null (`phantom/count_train.py:158`) and the CNN score (line 196) both use `sklearn.metrics.balanced_accuracy_score` on the pooled out-of-fold windows of all 14 recordings (not per fold); the shuffle permutes recording labels, so all three classes stay present, a never-predicted class counts as recall 0, and scores below 3-class chance (1/3) are possible when predictions anti-correlate with the shuffled labels. Why this run's 95th percentile is 0.194 is **[UNVERIFIED]**: only the percentile of the 3 runs is stored, not the per-permutation scores.
* **Provenance / licence.** Own architecture and code; the code docstring says it fixes two defects found in RuView's `cog-person-count` (normalisation, layout). Not weights from RuView.
* **Metrics for a deployable model:** none exists — `[TO BE MEASURED]`.

### 1.3 csi-embed-v2 encoder — PRETRAINED (external)

* **Purpose / consumer.** Maps 8 features to a 128-d L2-normalised embedding; there is no classification head. The sidecar uses only the cosine distance between a node's live embedding and that node's own "Calibrate Empty Room" reference, reported as `embeddingDrift` (0–2) on the advisory channel. "The environment changed", not "someone is there" (`phantom/embedding.py` docstring; `shared/schema.ts:275-277`). Advisory only.
* **Code path.** Architecture `Enc` in `scripts/ai_inference.py:79-96` (and `csi-embed-v2.py`); input mapping `phantom/embedding.py` (dims 4, 5, 6 masked to 0 because they were constant in upstream's training capture).
* **Training command.** Not run here. Upstream states `python aether-arena/staging/train_csi_embed.py` in `github.com/ruvnet/RuView` [UNVERIFIED: not fetched].
* **Output paths.** `ai model and densepose/model/csi-embed-v2.safetensors` (39,672 B), `csi-embed-v2-int4.bin` (4,672 B; first 32 bytes = fp16 standardizer), `csi-embed-v2.py`, `csi-embed-v2-metrics.json` (763 B). The folder is a nested git repository (pinned `39a01a1`, 2026-05-31; origin `huggingface.co/ruvnet/wifi-densepose-pretrained` per `06-licences.md`).
* **Provenance.** Upstream RuView. README: trained on RuView's own capture `data/recordings/overnight-1775217646.csi.jsonl`, 6,063 feature frames, one room, two nodes. That capture is **not on disk** here (`find -iname "overnight*"` returned nothing).
* **Licence.** README front matter `license: mit`. Training-data licence not stated beyond "own local capture" `[UNVERIFIED at source]`.
* **Metrics.** None measured on Phantom hardware or data → `[TO BE MEASURED]`. Upstream's own file `csi-embed-v2-metrics.json` reports a held-out temporal-triplet accuracy for the encoder (one room, time-disjoint 80/20); that is an embedding-quality statistic from upstream, not a presence/activity accuracy, and is not reproduced here.
* **Contradiction (not resolved).** README and `csi-embed-v2-metrics.json` give encoder weights SHA-256 `3b37bca66e60…`; the file on disk hashes to `183c988b918abad3…` (computed this session; `06-licences.md` also lists `183c988b918abad3`). Either the file differs from the one described or the recorded hash is stale.

### 1.4 Presence head — PRETRAINED (external), REFUSED BY GATE

* **Purpose / consumer.** Logistic head over the un-normalised 128-d bn2 activation → `presenceProb`. Off by default; when `PHANTOM_AI_PRESENCE_HEAD` is set, `presence_head_check` runs and the head is refused if saturated.
* **Guard result (computed this session from the file).** ‖w‖ = 3.668, bias = 8.188 → ‖w‖ < |bias| → the logit cannot reach both signs for unit-norm input; `phantom/presence_guard.py` refuses it, so `presenceProb` stays `None` (`06-licences.md` quotes p(present) ≥ 0.989 for any unit-norm input; upstream RuView issue #1521 per the guard's docstring). The sidecar always reports `presenceCalibrated: false`.
* **Code / tests.** `scripts/ai_inference.py:131-145, 321-339`; `tests/test_presence_guard.py`, `tests/test_presence_head_norms.py`.
* **Provenance / licence.** Upstream RuView, MIT per README. README itself calls it an "unvalidated placeholder; [TO BE MEASURED]". Training data: upstream's capture [UNVERIFIED]; `training-metrics.json` records "taskHeads samples 60,630".
* **Metrics:** `[TO BE MEASURED]`.

### 1.5 Sidecar "human / mechanical" classifier — NEVER TRAINED (rule-based)

* This is **not a learned model.** `phantom/sidecar.py` `activity_from_motion` / `advisory_human_prob` compute a motion ratio against a per-node empty-room baseline (`WALK_RATIO = 2.0`, `RAPID_CHANGE_RATIO = 3.0`, "provisional until validated on labelled recordings"); `scripts/ai_inference.py:556-567` labels "human" if present and walking/rapid_change, otherwise "mechanical". `humanProb` is a bounded score in 0.5–0.95; "presence" requires the (refused) presence head, so `advisoryLabel` is `unknown` unless that head is enabled and accepted.
* No training data, no weights, no metrics (`[TO BE MEASURED]`). Advisory only; the server owns the human/non-human verdict.

### 1.6 `pose_v1.safetensors` — PRETRAINED (external), provenance unverified

* **Purpose / consumer.** PoseNet (Conv1d 56→64→128→128, fc 128→256→34 = 17 keypoints × (x, z)); `scripts/ai_inference.py:113-128`; shape check script `scripts/inspect_pose_weights.py`. Only loaded and run when `PHANTOM_AI_POSE=1`; output is sent as `poseFrame`, never rendered (see F1 section). Tests: `tests/test_ai_pose_lazy_load.py`.
* **File.** 507,032 B, modified 2026-06-23 21:42, SHA-256 prefix `eb249b9a6b2e1013` (computed). **Untracked inside the nested model repo** (`git status` there shows `?? pose_v1.safetensors`), so it is not part of pinned commit `39a01a1`.
* **Provenance / licence.** Not stated in the README. Whether it derives from MM-Fi (CC BY-NC 4.0) is unverified (`06-licences.md`). Standing rule recorded in `reports/fix-2026-11/80-issues-ledger.md` (PS-FIX-26): keep it out of every deliverable until provenance is proven.
* **Metrics.** Upstream README: "Camera-free pose: 2.5% PCK@20" (upstream's claim, not measured here) → ours `[TO BE MEASURED]`.
* **Contradiction (not resolved).** README front matter says MIT for the whole folder, while `06-licences.md` says `pose_v1` has **no stated licence**, and the Phantom banner in the README points to "CC BY-NC material".

### 1.7 LoRA adapters `node-1.json`, `node-2.json` — PRETRAINED (external)

Rank-4 room adapters (`loraA[128,4]`, `loraB[4,128]`, scaling 2), "trained for someone else's rooms" (code comment; `06-licences.md`). Only applied when `PHANTOM_AI_LORA=1` and only for nodes 1 and 2. No data on disk; no metrics → `[TO BE MEASURED]`.

### 1.8 RuView v1 container files — PRETRAINED (external), NOT USED

`model.safetensors`, `model-q2/q4/q8.bin`, `model.rvf.jsonl`, `config.json` (model_type `sona-lora`, 60,630 frames, nodes 2 and 1) and `training-metrics.json` describe RuView's v1 encoder. No Phantom code loads them. The README acknowledges v1's loss was flat; consistently, `training-metrics.json` lists a `lossHistory` of 20 epochs all at ≈ 0.13517 while also reporting "improvement 51.59" and `finalLoss` 0.0654 — an internal inconsistency in the upstream file, noted, not resolved.

### 1.9 Other contradictions found

* `reports/fix-2026-11/06-licences.md` (2026-11-03) says `models/rooms/` is "absent here"; on disk now it exists with the single report from 2026-10-28 00:38 (still consistent with "no trained model exists").
* `docs/DATASET_PROTOCOL.md` says boards deliver "~30–50 fps"; every 2026-10-27 onward recording measures 45–68 fps per node and every c1/epoch recording ≈ 65–67 fps (also noted in `reports/presence-eval-2026-11/00-summary.md`).

---

## Section 2 — Dataset inventory

All files are JSON Lines: line 1 header, then `{"type":"frame","t":<epoch ms>,"n":<node>,"rssi":<dBm>,"a":[51 amplitudes]}`. All frames in every dataset have 51 subcarriers (first-frame check on one file per folder; loader `phantom/dataset.py` also keeps only each node's modal width). `data/datasets/` is gitignored (`.gitignore:31`). **Channel, bandwidth, BSSID and firmware are not recorded in any header** (schema 2 has `capture.source = "not_recorded"`; schema 1 has no capture block).

**seq/nsc.** Only `smoke-test` carries `seq` and `nsc` on frames (33,993 of 33,993 frame lines). Every other dataset: 0 frames with either key.

### 2.1 `data/datasets/room1/` — the only folder the training scripts read

14 recordings, 25 files, nodes 1–4 in every recording, schema 1, no seq/nsc. "Subject" is the header `subjectId` value; those values (`s1, s2, s3, s5…s10`) match session numbers, and `reports/presence-eval-2026-11/00-summary.md` states "one subject" → whether they are different people is `[UNVERIFIED]`. Dates are UTC from `startedAtMs`.

| recording (after `room1__`) | label | count | subject field | start UTC | parts | frames (all nodes) | min | fps n1/n2/n3/n4 |
|---|---|---|---|---|---|---|---|---|
| s1 walking 20261017T204650Z | walking | 1 | s1 | 2026-10-17 20:46 | 1 | 19,400 | 6.9 | **11/12/12/12** |
| s1 two_people 20261018T173055Z | two_people | 2 | s1 | 2026-10-18 17:30 | 3 | 280,800 | 18.1 | 65/65/64/64 |
| s1 empty 20261018T175601Z | empty | 0 | s1 | 2026-10-18 17:56 | 1 | 38,654 | 2.5 | 65/64/64/64 |
| s1 empty 20261018T180250Z | empty | 0 | s1 | 2026-10-18 18:02 | 1 | 78,906 (re-scanned: spaced-JSON writer) | 5.0 | 66/66/65/66 |
| s1 empty_fan 20261018T203921Z | empty_fan | 0 | s1 | 2026-10-18 20:39 | 1 | 66,444 | 4.6 | 62/62/57/61 |
| s2 still 20261025T195835Z | still | 1 | s2 | 2026-10-25 19:58 | 1 | 52,579 | 3.8 | 57/62/63/50 |
| s3 two_people 20261025T201209Z | two_people | 2 | s3 | 2026-10-25 20:12 | 1 | 57,766 | 4.1 | 50/66/66/53 |
| s1 still 20261027T193610Z | still | 1 | s1 | 2026-10-27 19:36 | 1 | 23,053 | 1.6 | 65/66/59/55 |
| s5 empty_fan 20261027T193823Z | empty_fan | 0 | s5 | 2026-10-27 19:38 | 1 | 47,678 | 3.4 | 63/64/60/49 |
| s6 empty 20261027T194207Z | empty | 0 | s6 | 2026-10-27 19:42 | 1 | 37,449 | 2.6 | 65/66/60/53 |
| s7 walking 20261027T194537Z | walking | 1 | s7 | 2026-10-27 19:45 | 1 | 53,490 | 3.5 | 65/68/59/61 |
| s8 empty 20261027T195356Z | empty | 0 | s8 | 2026-10-27 19:53 | 8 | 777,480 | 53.5 | **45**/67/66/65 |
| s9 empty 20261027T204759Z | empty | 0 | s9 | 2026-10-27 20:47 | 2 | 178,715 | 12.0 | **48**/68/66/66 |
| s10 still 20261027T212107Z | still | 1 | s10 | 2026-10-27 21:21 | 1 | 89,790 | 6.0 | 66/64/60/58 |

Notes: the 2026-10-17 walking recording runs at ≈ 11–12 fps per node (a different firmware rate than all others). Node 1 runs at 45–48 fps in `s8`/`s9`; `00-summary.md` of the presence evaluation records an unexplained 11 dB node-1 link change between `s7` and `s8`. Several recordings are under the protocol's 5 minutes. A stray `bash.exe.stackdump` also sits in this folder (not data). `.tmp/presence_eval_cache/` holds derived `.npz` caches of these recordings (not training data in themselves).

### 2.2 `data/datasets/campaign-raw-2026-11/` — campaign c1 raw output (NOT training data)

Schema 2, nodes 1–4 present in all, no seq/nsc, recorder `dashboard`, roomId `campaign-raw-2026-11`, subject `c1`, date range 2026-11-08 to 2026-11-09. 9 recordings, 140 files (parts + summaries).

| recording (after `campaign-raw-2026-11__c1__`) | label | start UTC | parts | frames | min | fps n1/n2/n3/n4 | disposition per `campaign.json` |
|---|---|---|---|---|---|---|---|
| empty 20261108T151149Z | empty | 11-08 15:11 | 1 | 19,943 | 1.3 | 65/65/62/64 | aborted attempt (restart requested) |
| empty 20261108T151336Z | empty | 11-08 15:13 | 20 | 1,942,985 | 128.3 | 65/64/60/63 | aborted: node-3 rate collapse |
| empty 20261109T032643Z | empty | 11-09 03:26 | 4 | 310,505 | 19.7 | 66/66/64/67 | aborted: node-3 rate collapse |
| empty 20261109T035035Z | empty | 11-09 03:50 | 8 | 715,910 | 50.0 | 61/61/58/59 | invalid (< 60 min) |
| empty 20261109T044649Z | empty | 11-09 04:46 | 13 | 1,271,627 | 80.2 | 66/66/66/66 | block `01_empty_1` |
| empty_fan 20261109T092905Z | empty_fan | 11-09 09:29 | 2 | 138,416 | 8.9 | 67/67/61/65 | block `02_fan_alone` |
| walking 20261109T094733Z | walking | 11-09 09:47 | 1 | 83,291 | 5.3 | 66/66/64/66 | block `03_walking` |
| still 20261109T095902Z | still | 11-09 09:59 | 2 | 101,149 | 6.4 | 67/67/66/66 | block `04_still` |
| empty 20261109T152153Z | empty | 11-09 15:21 | 19 | 1,849,284 | 142.2 | 55/55/53/54 | aborted by the rate rule (block 5 attempt 1) |

Whether blocks 1–4 pass the pre-registered validator is not assessed here (see `reports/presence-eval-2026-11/` and `campaign.json`).

### 2.3 `data/datasets/campaign-2026-11/c1-20261105/` — organised copy of the same campaign (NOT training data)

`blocks/01_empty_1`, `02_fan_alone`, `03_walking`, `04_still` hold the recordings above for blocks 1–4 (18 file names appear in both folders with identical size and modification time; byte-identity is stated by `campaign.json` `copy_rule` (sha256) and was not re-hashed here). `blocks_aborted/` holds entry logs only; `campaign.json` (10,137 B) holds placement, confirmations and aborted attempts. Its `nodes_expected` is `[1, 2, 4]`, with `nodes_expected_before` `[1, 2, 3, 4]`, although every recording has node-3 frames.

### 2.4 `data/datasets/smoke-2026-11/` — pre-campaign smoke test, 2026-11-05 (NOT training data)

Schema 2, 4 nodes, no seq/nsc, roomId `smoke-2026-11`, subject `c1`.

| recording | label | start UTC | frames | min | fps n1/n2/n3/n4 |
|---|---|---|---|---|---|
| `c1__empty__20261105T093215Z` | empty | 11-05 09:32 | 72,893 | 4.6 | 66/65/66/66 |
| `c1__empty_fan__20261105T093720Z` | empty_fan | 11-05 09:37 | 87,008 | 5.5 | 66/65/66/66 |
| `c1__still__20261105T094324Z` | still | 11-05 09:43 | 81,795 | 5.1 | 67/66/66/66 |
| `c1__walking__20261105T094901Z` | walking | 11-05 09:49 | 84,846 | 5.4 | 66/66/66/62 |

### 2.5 `data/datasets/epoch2-ref-2026-11/` — 10-minute empty reference in the new link state (NOT training data)

| recording | label | start UTC | parts | frames | min | fps n1/n2/n3/n4 |
|---|---|---|---|---|---|---|
| `e2__empty__20261109T191642Z` | empty | 2026-11-09 19:16 | 2 | 158,489 | 9.9 | 67/67/66/67 |

### 2.6 `data/datasets/smoke-test/` — post-router-change smoke test (NOT training data)

| recording | label | start UTC | frames | min | fps n1/n2/n3/n4 | seq / nsc |
|---|---|---|---|---|---|---|
| `s1__empty__20261109T200248Z` | empty | 2026-11-09 20:02 | 33,993 | 2.1 | 68/68/67/68 | **33,993 / 33,993** |

### 2.7 Not present

`soak-2026-11`: **no such folder under `data/datasets/`** (and no soak data anywhere in the repo; only the checker code `scripts/presence_eval/soak_check.py` exists).

### 2.8 Other data in the project (NOT training data)

| item | contents (from names/listing only) | note |
|---|---|---|
| `data/sessions/` | 754 entries (dashboard session `.json`/`.jsonl`, dated 2026-03 → 2026-09; `_index.json` is modified in the working tree) | live-session logs, unlabelled per `DATASET_PROTOCOL.md`; gitignored; not opened |
| `recordings/`, root `csi_recording_*.csv`, `test_capture.csv` | 24 session CSVs (2026-02/03) + 3 root CSVs | older captures, no protocol labels `[UNVERIFIED]`; gitignored (`*.csv`) |
| `data/audit/`, `data/operator.json` | audit logs, operator settings | not data; may hold names/IPs; not opened |

### 2.9 Which dataset trained / evaluated which model

| model | dataset(s) actually used | evidence |
|---|---|---|
| Activity classifier | `data/datasets/room1/` (12 of its 14 recordings) — evaluation only, refused | `activity.report.json` `groups` |
| Activity classifier — exploratory, epoch 1, c1 blocks 1-4 only | `data/datasets/train-c1-ep1-2026-11/` (18 byte-identical copies of c1 blocks 1-4; header roomId `campaign-raw-2026-11`; README local, gitignored). Run 2026-11-11 (`--room train-c1-ep1-2026-11`, system Python 3.11.9, default permutations): refused with exit 2 by the minimum-recordings check (empty 2, still 1, walking 1 recordings; windows empty 42,768 · still 3,044 · walking 2,536 · active 0) **before any evaluation**; no report written, no model exported | training log only; no `models/rooms/train-c1-ep1-2026-11/` exists |
| Count CNN | `data/datasets/room1/` (all 14 recordings) — evaluation only, refused | `count.report.json` |
| csi-embed-v2 | upstream capture `overnight-1775217646.csi.jsonl` (not on disk) | upstream README |
| Presence head | upstream capture [UNVERIFIED] | upstream `training-metrics.json` |
| `pose_v1` | unknown | README silent |
| LoRA node-1/2 | upstream rooms (not on disk) | code comment |
| Presence-eval candidates (not ML) | `room1` (14 recordings), offline | `reports/presence-eval-2026-11/00-summary.md` |
| Sidecar heuristic | none | rule-based |

**Keeping campaign data out of training.** The loader reads only `<data-root>/<room>/*.jsonl` (`phantom/dataset.py:210-218`), so `--room room1` cannot pick up campaign folders. But the campaign's `roomId` equals its folder name (`campaign-raw-2026-11`), so `train_activity.py --room campaign-raw-2026-11` **would** load it: no code in `phantom/dataset.py`, `activity_train.py`, `count_train.py` or `scripts/train/` mentions campaign, soak, smoke or epoch (grep). The separation is by convention only.

### 2.10 External datasets referenced in code or docs (none downloaded; no copy on disk)

| name | licence stated in repo | referenced in | on disk? |
|---|---|---|---|
| MM-Fi (NeurIPS 2023) | CC BY-NC 4.0 | `docs/adr/ADR-015-public-dataset-training-strategy.md:62` (primary pose set) | no |
| Wi-Pose (NjtechCVLab) | "Research use" | ADR-015:80 | no |
| RF-Pose, Person-in-WiFi (CMU/3D), DensePose From WiFi, Widar 3.0, XRF55 | not stated (ADR lists them as excluded) | ADR-015 exclusion table | no |
| WiCount (`huggingface.co/datasets/RS2002/WiCount`), WiFall (`…/RS2002/WiFall`) | not stated `[UNVERIFIED]` | `docs/esp32s3-framework-comparison-report.md` §5 | no |
| Gupta et al., IEEE DataPort DOI 10.21227/e6c6-aa21 | not stated `[UNVERIFIED]` | same | no |
| "Less is More: The Dilution Effect in Multi-Link Wireless Sensing" (Zenodo; doc gives ≈ 45.7 GB) | not stated `[UNVERIFIED]` | same | no |
| EHUNAM (figshare DOI 10.6084/m9.figshare.28541225.v1) | CC BY 4.0 (per that doc) | same | no |
| IEEE DataPort DOI 10.21227/xbhv-f125 (80 MHz human sensing) | not stated `[UNVERIFIED]` | same | no |
| RuView `overnight-1775217646.csi.jsonl`; HF `ruvnet/wifi-densepose-mmfi-pose`, `ruv/ruview` | MIT stated for RuView model README | model README | no |

---

## Section 3 — Gap analysis against `docs/DATASET_PROTOCOL.md`

The protocol asks for: all labels; **5 min per label per session**; **≥ 3 sessions on different days/times** (evaluation holds out whole sessions); **≥ 2 subjects** (distinct `subjectId`); stay inside the labelled condition; record in the deployment room.

### 3.1 Labels, sessions, days in `room1` (the only trainable folder)

| label | recordings | distinct days (UTC) | recordings ≥ 5 min | in protocol | status |
|---|---|---|---|---|---|
| empty | 5 | 2 (10-18, 10-27) | 3 (`180250Z` 5.0, `s8` 53.5, `s9` 12.0) | yes | ≥ 3 sessions, < 3 days |
| empty_fan | 2 | 2 | 0 (4.6, 3.4) | yes | **< 3 sessions**, all under 5 min |
| still | 3 | 2 (10-25, 10-27) | 1 (`s10` 6.0) | yes | 3 sessions, < 3 days, mostly short |
| walking | 2 | 2 (10-17, 10-27) | 1 (`10-17`, but at 11–12 fps) | yes | **< 3 sessions** |
| active | **0** | 0 | 0 | yes | **missing** |
| two_people | 2 | 2 (10-18, 10-25) | 1 (`s1` 18.1) | yes | **< 3 sessions** |
| three_people | **0** | 0 | 0 | optional | missing |

* **Subjects:** the `subjectId` field is `s1…s10`, matching session numbers; the presence evaluation states one subject. The ≥ 2-subject requirement is not demonstrably met `[UNVERIFIED]`.
* **Count classes:** 2+ is represented only by two recordings, the training script's minimum.
* **Quality problems on record:** node-1 link change of 11 dB between `s7` and `s8` (unannotated); node-1 rate 45–48 fps in `s8`/`s9`; one walking recording at ≈ 11 fps; `empty` labels rest on unverified emptiness (`00-summary.md`); the activity report shows the gate failing on these data.

### 3.2 Link state / epoch and frame rate versus the current epoch

Current epoch (from `DRAFT-c2-prereg-amendment-link-state-reference.md`): router change of 2026-11-09 evening, **channel 2 fixed, 20 MHz, b/g/n mixed**, ≈ 67 fps delivered, four nodes. The channel is recorded in no header, so epoch membership of any file is inferred from its timestamp `[UNVERIFIED]`.

| dataset | date (UTC) | nodes | fps | labels | seq/nsc | in current epoch? |
|---|---|---|---|---|---|---|
| room1 | 2026-10-17 → 10-27 | 1–4 | 11–68 (varies by node/recording) | empty, empty_fan, still, walking, two_people | no | **no** (pre-router-change; channel `[UNVERIFIED]`) |
| smoke-2026-11 | 2026-11-05 | 1–4 | 62–67 | empty, empty_fan, still, walking | no | no |
| campaign-raw / campaign-2026-11 (c1) | 2026-11-08/09 up to ≈ 15:21 | 1–4 (campaign expected 1,2,4) | 53–67 | empty, empty_fan, walking, still | no | no (ends before the router change; amendment says no c2 block exists yet) |
| epoch2-ref-2026-11 | 2026-11-09 19:16 | 1–4 | 66–67 | empty only (9.9 min) | no | **yes** (by timestamp) |
| smoke-test | 2026-11-09 20:02 | 1–4 | 67–68 | empty only (2.1 min) | **yes** | **yes** (by timestamp) |

Consequences:
* **No labelled non-empty data exists in the current epoch.** `still`, `walking`, `active`, `two_people`, `three_people`, `empty_fan` in the current link state: none.
* The 12.1 min of current-epoch data is empty-room only and is not training data (campaign/reference rules).
* The only trainable folder (`room1`) predates the router change by two weeks and has unknown channel and mixed rates; the protocol itself says models "do not transfer between rooms or subjects", and the presence evaluation found two empties more different from each other than walking from empty.

### 3.3 What is needed before any model could be trained and trusted

1. **Record new protocol-compliant labelled data in the current link state** (channel 2 fixed, four nodes, ≈ 67 fps): all of empty, empty_fan, still, walking, active, two_people (three_people optional), ≥ 5 min each, ≥ 3 sessions per label on different days/times, ≥ 2 distinct people with distinct `subjectId`. Record into a dedicated training room id, **not** into campaign/soak/smoke folders.
2. **Record the link state in the header** (channel, bandwidth, BSSID, firmware hash are `not_recorded` today) and use the `seq`/`nsc` capture that only `smoke-test` has, so rate drops and loss are measurable per file.
3. **Add a training-side guard** that refuses campaign/soak/smoke/epoch folders (none exists), and refuses mixed link states. Not implemented here (read-only task).
4. **Annotate and verify labels** (emptiness confirmation, entry logs) and obtain volunteer consent / retention rule (`06-licences.md` §E.4).
5. **Make one interpreter canonical for training.** scikit-learn is listed in `pyproject.toml`; it is present in the system Python 3.11.9 (1.8.0, used for the 2026-11-11 count run) and **absent from `.venv`**; the `py -3.13` launcher named in the training scripts was not found in the Git Bash shell. Pick one environment (with scikit-learn) so the gate tests and `train_*.py` run reproducibly.
6. Only after 1–5: run the existing gate (held-out whole recordings, majority baseline, motion tree, shuffled-label null; and `--group-by day` once ≥ 3 days exist). A model that does not pass stays unexported; none of the numbers in this report may be quoted as accuracy.
7. Independent of training: resolve the licence/provenance questions (`pose_v1`, MM-Fi/Wi-Pose terms, encoder hash mismatch) before any RuView weight is shipped.

---

## Section 4 — One-page summary

**Trained by us (a real output file exists):** *none.* The only training outputs are `models/rooms/room1/activity.report.json` and `models/rooms/room1/count.report.json` (refusal reports; no weights file).

**Trained by us but REFUSED BY GATE:** activity classifier and people-count CNN (reports only, `exported: false`).

**Never trained (nothing on disk):** sidecar human/mechanical tag (rule-based by design).

**Pretrained external, provenance not ours:** csi-embed-v2 encoder (the only one active by default; advisory `embeddingDrift`); presence head (refused by guard, off by default); `pose_v1` (off by default, provenance and licence unverified, keep out of deliverables); LoRA `node-1/2` (off by default, other rooms); RuView v1 container files (not loaded by any code).

**Exact training-data path per model**

| model | training-data path |
|---|---|
| Activity classifier | `data/datasets/room1/` (`train_activity.py --room room1`) |
| Activity classifier (exploratory, epoch 1) | `data/datasets/train-c1-ep1-2026-11/` (`train_activity.py --room train-c1-ep1-2026-11`): c1 blocks 1-4 only, header roomId `campaign-raw-2026-11`, README local (gitignored); refused before evaluation (one still and one walking recording), no report, no model exported |
| People-count CNN | `data/datasets/room1/` (`train_count.py --room room1`); run 2026-11-11 (reduced), refused |
| csi-embed-v2, presence head, LoRA, v1 files | upstream RuView capture, not on disk |
| `pose_v1` | unknown |
| Sidecar heuristic | none |

**Not training data:** `data/datasets/campaign-raw-2026-11/`, `campaign-2026-11/`, `smoke-2026-11/`, `epoch2-ref-2026-11/`, `smoke-test/`, `data/sessions/`, `recordings/`, root CSVs; `soak-2026-11` does not exist on disk. Separation from training is by convention only; no guard in code.

**What to do next**
1. Record the labelled sessions listed in §3.3 (current link state, ≥ 3 sessions/label, ≥ 2 subjects, ≥ 5 min) into a dedicated training room id.
2. Add the missing header fields and a training-folder guard before recording or training.
3. Use one interpreter that has scikit-learn (system Python 3.11.9 has it; `.venv` does not), then run the existing refusal gate on the new data; ship nothing that the gate refuses.
4. Settle licence/provenance of `pose_v1` and the encoder hash mismatch; keep RuView weights advisory-only and optional.
5. Until then, keep all AI output advisory (F1 verified in code) and state no accuracy, detection or false-positive figure anywhere.
