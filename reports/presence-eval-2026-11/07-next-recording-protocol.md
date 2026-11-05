# 07 — Next recording protocol (document only)

**Purpose.** The existing data cannot say whether the drift in 03-drift.md is hardware/link state, an unlogged occupant, a moved node, or a firmware/config change, and cannot say whether anything generalises beyond one subject, one room, one rig. This is the *minimal* controlled campaign that would settle those questions. **All outcomes of it are `[TO BE MEASURED]`.** Nothing here has been run.

## 1. Before anyone records (freeze the plan)

1. Freeze the analysis plan: the acceptance criteria in 04-two-node-eval.md §1 (or Thaer's revision of them) and the protocols (b) leave-one-recording-out and (c) cross-session. Commit the plan file *before* the first recording.
2. Fix the rig: both nodes (N1, N2) on tape-marked floor positions on the baseline axis; measure and write down the N1–N2 distance (committed `config/room.json` says 4 m; the brief says July used 3 m `[UNVERIFIED]`), heights, orientations, router position (committed: at N2's anchor). Photograph both nodes in place before and after every sitting. **Nodes are not touched between phases.**
3. Write a `session.json` next to the recordings (the dataset header does not carry these): firmware git hash and `sdkconfig` used, Wi-Fi channel, AP BSSID, node ↔ serial port map, recorder host and recorder (dashboard "Training Data Capture" or `scripts/record_dataset.py`), host NTP status, room description, door/window states, who is in the building.
4. Save each node's serial log (`medium tick: yield=…`) for the whole sitting.
5. Use the allowed labels only (`empty`, `empty_fan`, `still`, `walking`); put the phase id, subject, marker and operator in the header `notes` field (it exists and is currently empty in 13 of 14 recordings). **One recording per phase** so a label never spans two conditions.

## 2. One sitting (minimum 2 repeats in the same sitting)

The operator announces each phase aloud and writes `UTC time, phase id, what happened` to a plain-text log (wall clock, to the second) as it happens; recordings are started 10 s before the announced start (the recorder's countdown does this) and trimmed by the log, not by memory.

| phase | id | duration | who / what |
|--|--|--|--|
| empty (operator outside the room, door closed) | E1 | 10 min | nobody in the room; log any door/corridor activity |
| standing still at marker A (then B, then C) | S-A/B/C | 3 min each | subject stands on the tape mark, facing the baseline, normal breathing |
| slow walk along the marked path | W | 3 min | subject walks the tape-marked path, steady pace |
| empty again | E2 | 10 min | as E1 |
| fan on at a marked position | F-on | 5 min | fan running, nobody in the room |
| fan off, empty | E3 | 10 min | as E1 |

Repeat the whole table at least twice in the sitting (R1, R2). Between phases the operator records the per-node RSSI shown on the dashboard in the log (the per-frame RSSI is also in the dataset).

## 3. What must vary (each in a separate, logged recording)

* **Second day** (≥ 24 h later), same rig, nodes untouched, photos compared. Settles cross-session behaviour (protocol (c)).
* **Second subject** (different build/clothing), same sitting structure on a day the first subject also records. Settles subject dependence.
* **Long unattended empty**: ≥ 60 min, operator and everyone else out of the room, with an independent entry record (door contact, PIR, or a camera pointed at the door where consent allows). Settles "drift" versus "unlogged occupant" — the key unknown in 03-drift.md.
* **Cold versus warm start**: one sitting that begins immediately after powering the nodes, one after ≥ 60 min of warm-up. Settles thermal/AGC warm-up.
* **Node-displacement positive control**: two labelled empties, N1 displaced by a measured 20 cm between them and the move recorded. Gives the size of a "node moved" effect to compare with the drift seen on 27 Oct.
* **Through-wall condition, one per wall type** (e.g. drywall, brick/concrete — whichever exist on site): subject on the far side of the wall from the baseline, same phases as §2; wall thickness and material in `session.json`. Detection ranges and rates through walls are `[TO BE MEASURED]`; none is assumed.

## 4. Threshold-recalibration campaign (`scripts/calibrate-threshold.ts`)

Purpose: find out whether the empty-room calibration is *stable* before anyone trusts a threshold. **Nothing is written to settings during the study**; the script prints suggestions, which go into the report as data.

1. **Stop the dashboard** (the script listens directly on UDP :5005 and needs to be the single owner; the live server is the sole ESP32 ingest otherwise).
2. Empty-room soak, start of sitting: `npx tsx scripts/calibrate-threshold.ts --seconds 120` (add `--spatial` only if the spatial threshold is also under study). Record the printed suggestion.
3. Longer soaks to see the suggestion move: `--seconds 1800`, then repeat the 120 s run after 1 h and on day 2. Plot suggestion versus time; a suggestion that changes by more than the walking effect measured in the same sitting means one calibration cannot be trusted.
4. **Negative control:** fan on the marked position, `--seconds 120`; the fan's max motion must stay below the candidate threshold (the script's own rule; if not, raise `k` and redo step 2).
5. **Positive checks** (script run while the subject stands at marker A, then walks the path): confirm the candidate threshold is exceeded; record the fraction of 1.5 s windows above it.
6. Keep the window length identical between tools: `calibrate-threshold.ts` defaults to 1500 ms, `eval-presence-on-datasets.ts` to 800 ms (PS-EVAL-016); state which one each number came from.
7. Only if the analysis (pre-registered criteria, held-out days and subject) passes does Thaer decide whether to apply a value through the existing runtime-settings path. That decision and that change are **outside this task**.

## 5. Analysis on the new data

Run unchanged: `python -m scripts.presence_eval.inventory`, `…repro`, `…drift`, `…twonode`, plus `npx tsx scripts/presence_eval/ref_two_node.ts`. Add the sitting/day/subject to the grouping so protocol (c) uses day and subject as the held-out unit. Report all three protocols side by side, with block-bootstrap CIs, both failure directions, and "no candidate met the criteria" if that is the outcome.

## 6. Logged data checklist (per sitting)

Rig photos before/after · `session.json` · operator phase log with UTC timestamps · serial logs per node · per-node RSSI notes · door/PIR/camera entry record for unattended phases · firmware hash · recorder output files with notes filled · list of any deviation (someone entered, node touched, AP rebooted).

## 7. Results

`[TO BE MEASURED]` — no value in this document is a measurement.
