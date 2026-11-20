# Empty-room capture session, 2026-11-19: report

Written by Claude Code (controller) from the tool outputs of this session only. Nothing was committed or pushed.

## Outcome (updated 17:20Z)

**c1 block 5 (`empty_2`, attempt 2) was recorded: 62.60 min, all four nodes clean, with one logged deviation
(short node-2 warm-up).** It is in `data/datasets/campaign-2026-11/c1-20261105/blocks/05_empty_2/`. The c1 campaign
is still **INVALID** under the frozen validator: block 6 (`fan_with_person`) is missing, and the c1-mode link-state
rule flags N1 against block 1. No soak, no c2 block and no training run took place. The section "First attempt
window" below covers the earlier part of the day, when node 2 was silent.

## Update 17:58Z: c1 block 6 recorded; all six blocks present

* `06_fan_with_person`, activity **still** (chosen by the controller at the owner's request, before Start), fan on
  (owner: "The fan is one"). Recording `campaign-raw-2026-11__c1__still__20261119T174304Z`, 17:43:04Z → 17:54:53Z,
  **11.83 min** (minimum 10). Controller pressed Start and Stop in Chrome; "NOW: walk out" sent at about 17:54:10Z,
  so `trim_tail_s` = 50 (not the 20 s default). On mark A / no phone / door closed: requested, not separately confirmed.
* Per node (all frames): N1 -26 dBm (-40..-25), N2 -25 (-30..-24), N3 -53 (-57..-49), N4 -45 (-50..-44);
  fps 65.8-66.8 on N1, N2, N4 and 64.4 on N3; no step or collapse flag in either part.
* Copied with sha256 into `blocks/06_fan_with_person/` (4 files, all OK), `block.json` + entry log written.

**validate_campaign, 6 blocks:**

| Mode | Verdict | Failures |
|---|---|---|
| c1 (frozen first-60-s reference, registered for c1) | **INVALID** | 4 undeclared link changes, all against `01_empty_1`: N4 -6 dB at block 2 (old); N1 +6 dB at block 4 (old); N1 +7 dB at block 5 (new); N1 +7 dB at block 6 (new) |
| c2 (whole-block medians vs adjacent empty block; c2 amendment) | **VALID** | 0 failures, 0 warnings |

Not run: `run_campaign` (the analysis). Under the registered c1 rule the campaign is invalid, so the analysis would
refuse or be unregistered. Using the c2 rule for c1 would be a change of rule chosen **after** seeing which rule
passes; that is a pre-registration decision for the owner and must be written as such if taken. This report takes
no position.

## Update 19:10Z: Phase-1 training session 1 (`train-ep2-2026-11`, subject `s1`)

Training on `train-c1-ep1-2026-11` was tried first and **refused by the guard** (exit 2: every file's header roomId is
`campaign-raw-2026-11`, i.e. copies of campaign data). `--allow-unsafe` was not used.

Recordings (controller pressed Start/Stop in Chrome; room facts on the owner's word):

| Recording (UTC) | Label | Length | fps (N1/N2/N3/N4, last 10 s) | Kept in training folder |
|---|---|---|---|---|
| 181004Z | empty_fan | 5.23 min | 37.5 / 37.5 / 36.6 / 37.5 | no → `lowrate-train-ep2-2026-11/` |
| 182022Z | empty | 5.27 min | 40.3 / 40.3 / 40.2 / 40.1 | no → `lowrate-train-ep2-2026-11/` |
| 184015Z | still | 5.22 min | 65.4 / 65.2 / 64.2 / 65.1 | yes |
| 184627Z | walking | 1.96 min | - | no → `aborted-train-ep2-2026-11/` (owner left the room during the clip) |
| 184901Z | empty | 5.16 min | 66.3 / 66.4 / 66.1 / 66.1 | yes |
| 185609Z | empty_fan | 5.17 min | 65.3 / 65.0 / 61.7 / 65.2 | yes |
| 190257Z | walking | 5.13 min | 60.6 / 60.8 / 60.5 / 60.5 | yes |

* From about 18:05Z to about 18:38Z all four nodes ran at 37-41 fps (RSSI unchanged; PC Wi-Fi 96 %, mains, CPU ~52 %,
  mostly the Chrome dashboard tab). Cause unknown [UNVERIFIED]; it recovered by itself, like the 2026-11-09 slide.
  The two clips recorded then were moved out so that the label is not confounded with the frame rate. Nothing deleted.
* No clip flagged an RSSI step. RSSI medians: N1 -26..-27, N2 -25..-26, N3 -50..-53, N4 -45..-47 dBm.

**Training run** (`python -m scripts.train.train_activity --room train-ep2-2026-11`): **REFUSED, exit 2**, nothing
written: "too few recordings/windows for ['still', 'walking'] (need >= 2 recordings and >= 20 windows each; have
recordings={'empty': 2, 'still': 1, 'walking': 1})". The trainer counts empty_fan as `empty`. It also warned that
fewer than 3 recording days make any score optimistic.

**Second pair recorded, then trained again (19:23Z):**

| Recording (UTC) | Label | Length | fps (N1/N2/N3/N4, last 10 s) | Median RSSI N1/N2/N3/N4 | Flags |
|---|---|---|---|---|---|
| 191106Z | walking | 5.12 min | 57.9 / 56.8 / 55.4 / 57.6 | -28 / -27 / -48 / -47 | N1 step flag |
| 191745Z | still | 5.09 min | 43.1 / 42.8 / 42.2 / 42.7 | -32 / -33 / -47 / -48 | N1 step flag |

The rate slid again during the second still clip (about 43 fps), and its RSSI differs from the first still clip
(N1 -32 vs -26, N2 -33 vs -25). Both clips were kept as recorded (the trainer chooses nothing by hand).

`train_activity --room train-ep2-2026-11`: 6 recordings, 1 day, classes empty (incl. empty_fan) / still / walking,
about 4,900 windows each, held out by recording. **REFUSED, exit 2, `exported: false`:**

| Metric | Value |
|---|---|
| Model balanced accuracy | **0.413** |
| Motion heuristic | 0.422 |
| Majority class | 0.000 |
| Shuffled-label null, 95th percentile | 0.447 |
| Margin required | 0.02 |

Confusion matrix (rows true, columns predicted; empty / still / walking): empty 3461 / 1217 / 270; still
**3144 / 31** / 1765; walking 1084 / 1208 / 2612. The model does no better than the simple motion rule or chance on
held-out recordings: held-out still was called empty almost always. Only `models/rooms/train-ep2-2026-11/activity.report.json`
was written; no model file. **No model is usable from today's data.**

## Update ~20:10Z: rate-drop diagnosis and code fixes

See `RATE-DROP-DIAGNOSIS.md`. Code changed (uncommitted, tests green, 632 passed): rate-independent features
(30 Hz resampling, training and sidecar) and a training-guard refusal for clips below 46.9 fps. The guard moved the
second still clip out (N3 46.7 fps); training now refuses for too few `still` recordings (empty 2, still 1, walking 2).
No model trained.

Third still clip `still 195129Z` (5.11 min): N1 65.2, N2 64.6, N4 63.1 fps, but **N3 37.3 fps with a step flag**
(node 3 alone this time, as in its c1 collapses). The guard refused it; training did not run (exit 2). The
`activity.report.json` in `models/rooms/train-ep2-2026-11/` is still the 19:23Z one (0.413, not exported).

## Update ~20:20Z: first model exported (nodes 1, 2, 4; exploratory, one day)

Code added (uncommitted; 61 related tests pass): `--exclude-nodes` for `train_activity` (guard skips the excluded
node's rate check, the loader drops its streams via `phantom.dataset.without_nodes`, and the report records
`excluded_nodes` and the 30 Hz feature resampling).

`python -m scripts.train.train_activity --room train-ep2-2026-11 --exclude-nodes 3`, 6 recordings (empty 184901Z,
empty_fan 185609Z, still 184015Z + 195129Z, walking 190257Z + 191106Z), held out by recording: **exported, exit 0**
→ `models/rooms/train-ep2-2026-11/activity.json`.

| Metric | Value |
|---|---|
| Model balanced accuracy | **0.489** |
| Motion heuristic | 0.393 (model beats it by 0.096) |
| Shuffled-label null, 95th percentile | 0.479 (model above it by only **0.010**) |
| Majority class | 0.000 |

Confusion (rows true; empty / still / walking): empty 3029 / 256 / 426; **still 1421 / 34 / 2256**; walking 886 / 431 / 2361.

**What this does and does not show:** the model separates empty from walking better than the motion rule, but it
almost never recognises `still` (34 of 3,711 held-out windows), and it is barely above what shuffled labels reach.
One day, one subject, two recordings per label: the trainer itself warns the score is optimistic. The model is
advisory only (never overrides the deterministic verdict) and must not be quoted as an accuracy.

## Update 2026-11-20: owner-requested run on all clips and all four nodes

Owner's instruction: retrain with every node and every recording, including those below 46.9 fps. Done in a separate
folder so the guarded model is untouched: all 9 clips copied (`cp`) into `data/datasets/train-ep2-2026-11-all/`
(the 6 training clips + the 3 low-rate clips); the aborted 1.96 min walking clip was left out because its label is
wrong (the owner left the room during it), not because of its rate. Run:
`train_activity --room train-ep2-2026-11-all --allow-unsafe` (all nodes), output `models/rooms/train-ep2-2026-11-all/`.

The guard listed every override (4 slow clips; header roomId differs from the copy folder). **Result: REFUSED, not
exported, exit 2.**

| Metric | All clips, nodes 1-4 | Guarded set, nodes 1, 2, 4 (exported 19 Nov) |
|---|---|---|
| Model balanced accuracy | 0.488 | 0.489 |
| Motion heuristic | **0.555** | 0.393 |
| Majority class | 0.333 | 0.000 |
| Shuffled-label null, 95th pct | 0.452 | 0.479 |

Confusion (rows true; empty / still / walking): empty 7219 / 1283 / 1474; still 3560 / 850 / 2978;
walking 1047 / 797 / 3060. Windows: empty 9,976, still 7,388, walking 4,904.

Reading: adding the slow clips and node 3 did not help the model (0.488), while the simple motion rule rose to 0.555
on this mix, so the model loses to it and is not exported. `still` is recognised a little more often (850 of 7,388)
but is still mostly called empty or walking.

## c1 block 5 result

* Recording `campaign-raw-2026-11__c1__empty__20261119T160828Z`, 10 parts, first frame 16:08:28Z, last frame 17:11:04Z.
* Started at 16:08:28Z **not by the controller** (who pressed Start is [UNVERIFIED]); the controller had asked to wait
  until 16:55Z for node 2's warm-up. The owner chose to keep it and asked that node 3 also be reported.
  Stopped by the controller in Chrome at 62.6 min.
* Room empty, door closed, fan off: owner's "all done start" at 16:05:56Z, before Start. No entry event reported.
* **Deviation:** node 2 returned between about 15:35Z and 15:58Z, so about 10-33 min of warm-up instead of 60.
  The dashboard was restarted at 15:58:49Z, about 10 min before Start.

Per node, per 10-minute segment (from all frames):

| Node | Whole-block median RSSI (range) | RSSI per 10 min | fps per 10 min |
|---|---|---|---|
| 1 | -26 dBm (-42..-25) | -26 in every segment | 65.2 → 67.4 |
| 2 | -24 dBm (-32..-23) | -24 in every segment | 65.0 → 67.5 |
| 3 (excluded in c1) | -54 dBm (-57..-49) | -53..-54 | 64.2 → 66.9 |
| 4 | -46 dBm (-53..-45) | -46 in every segment | 65.0 → 67.2 |

The read-only monitor read all 10 part summaries: no step flag and no rate collapse on any node.
Files copied into the block folder with sha256 (`SHA256SUMS.txt`, all 20 OK); originals kept in `campaign-raw-2026-11`.

## validate_campaign on c1 (5 blocks)

Default (c1) mode, the frozen first-60-s reference: **INVALID, 4 failures**

* no link state contains all six block types (block 6 `fan_with_person` missing);
* `01_empty_1` → `02_fan_alone`: N4 -43 → -50 dBm (-6 dB) [existed before today];
* `01_empty_1` → `04_still`: N1 -33 → -27 dBm (+6 dB) [existed before today];
* `01_empty_1` → `05_empty_2`: **N1 -33 → -26 dBm (+7 dB)** [new today].

c2 mode (whole-block medians against the adjacent empty block; the c2 amendment, not registered for c1):
**INVALID, 1 failure**, only the missing `fan_with_person` block. No link-state failure.

Which mode governs c1 is a pre-registration question for the owner; this report does not choose.

## First attempt window (before node 2 returned)

## What was done (UTC; Amman = UTC+3)

| Time (approx.) | Action | Result |
|---|---|---|
| 12:06 | Pre-flight on the dashboard (Claude in Chrome, `localhost:5000`) | "no live CSI signal (nodes silent)", 0 frames |
| 12:06 | Host network check | PC Wi-Fi disconnected (APIPA); only `Ethernet 2` up |
| 12:15 | Wrote `PLAN-empty-capture.md` (c2 soak + empty blocks, owner decisions) | plan only |
| ~14:55 | Owner reconnected Wi-Fi | PC on `Thaer_2.4Ghz`, channel 2, signal 97 %, IP **192.168.1.155** (DHCP) |
| ~15:05 | Owner: the nodes send to 192.168.1.155 (not .20 as in `docs/UBUNTU_ESP32_SETUP.md`) | address kept |
| ~15:10 | Dashboard had reloaded to the operator sign-in; owner signed in in the controlled tab | live panel shows N1, N3, N4 |
| 15:13:39 | **Preflight recording, 64 s**, `data/datasets/preflight-c2-20261119/` (not campaign data) | see table below |
| ~15:20 | Owner changed scope: **continue c1** for the empty room instead of c2 | plan file updated |
| 15:17 | Dashboard restarted on owner request (`npm run dev`, terminal tab c1) | port 5000 + UDP :5005 up; N1, N3, N4 back within 1 s |
| ~15:25 | Owner power-cycled node 2 | still no node-2 frames (~965 packets / 5 s = 3 nodes) |
| ~15:30 | Read-only serial read of COM5, 20 s, DTR/RTS off, no write | board up ~3.5 h, 63-67 pps, ch 2: **not node 2** |
| ~15:35 | Owner: node 2 cannot be reached for USB | session stopped |

## Preflight scan result (`preflight-c2-20261119__preflight__empty__20261119T151339Z`)

From the dashboard's `.summary.json` (10 s windows; step threshold 6 dB; collapse ratio 0.7):

| Node | Frames | fps first 10 s | fps last 10 s | Median RSSI | Step / collapse flag |
|---|---|---|---|---|---|
| 1 | 4150 | 64.6 | 65.3 | -26 dBm | none |
| 2 | 0 | - | - | - | not received |
| 3 | 4017 | 62.2 | 62.6 | -53 dBm | none |
| 4 | 4155 | 64.7 | 65.0 | -45 dBm | none |

Frames carry `seq` and `nsc` (128). The room state during this recording was not confirmed by the owner; the label
`empty` is the form default, so the file is a link check only and must not be used as empty-room data.

## c1 status (unchanged today)

* Accepted blocks: `01_empty_1` (80.2 min), `02_fan_alone` (8.9 min), `03_walking` (5.3 min), `04_still` (6.4 min).
* `05_empty_2`: attempt 1 aborted on 2026-11-09 (all-node rate slide to 35-44 fps). Attempt 2 is the one allowed re-record.
* `06_fan_with_person`: not recorded.
* Note: N1 was about -31 to -37 dBm in c1 block 1 and is -26 dBm today. Whether that counts as a link-state change
  for `empty_2` against `empty_1` is for `validate_campaign` to decide; not judged by eye.

## Training

Not run. Under `phantom/training_guard.py` the campaign, soak, smoke and preflight folders are refused as training
data, and no new training-folder (`train-ep2-2026-11`) recordings exist. The activity and count models remain as in
the room1 reports: `exported: false`, advisory only.

## Open issues

1. **Node 2 was silent** until about 15:35-15:58Z; it then returned (cause not known [UNVERIFIED]) and streamed
   cleanly through block 5.
1b. **c1 still needs block 6** (`fan_with_person`, 11 min, owner in the room) and an owner decision on the
   link-state mode (c1 mode fails three block pairs, c2 mode none).
2. **Host IP documentation.** The nodes target 192.168.1.155 per the owner; the setup docs say 192.168.1.20. The PC
   holds .155 by DHCP, so a lease change would silence all nodes; a DHCP reservation would prevent that.
3. **Warm start.** When node 2 returns, block 5 needs 60 min of warm-up before its 62 min recording.
4. The dashboard now runs from terminal tab c1 of this app (the earlier instance in the VS Code terminal was stopped).
