# Training-data recording checklist (new room folder, epoch 2)

**Status: draft, written 2026-11-11 from `AI-MODELS-AND-DATASETS.md` §3.3 and `docs/DATASET_PROTOCOL.md`.** It turns §3.3 into steps; it does not change the protocol. Items marked **[OWNER TO CONFIRM]** are decisions this document does not make. No accuracy or detection figure is promised by recording this data: whether a model passes is decided later by the existing refusal gate.

## 0. Hard gate: when these recordings may happen

**These recordings happen only AFTER the soak and the c2 campaign are finished, and NOT in the same evening as c2.** Not before the soak, not between soak and c2 blocks, not after block 6 on the same evening. Reasons: the c2 link-state rules forbid any change from the first Start of the soak to the Stop of block 6, and the recorder, the nodes and the operator are busy with c2; a training session in the same evening would also add a second reason for the link state to differ between c2 blocks. Start no earlier than the day after c2 ends **[OWNER TO CONFIRM the exact date]**.

Training is a separate, later step and is **not** part of this checklist (see §7).

## 1. What must be recorded (from inventory §3.3 item 1)

| Requirement | Value |
|---|---|
| Labels (7) | `empty`, `empty_fan`, `still`, `walking`, `active`, `two_people`, `three_people` |
| Length | **at least 5 min** of frames per recording, per label per session |
| Sessions | **at least 3 per label, on different days** (different RF conditions); a session = one recording of that label |
| Subjects | **at least 2 different people** for the single-person labels (`still`, `walking`, `active`), each with their own Subject ID |
| Link state | **channel 2 fixed, 20 MHz, b/g/n mixed (epoch 2)**, four nodes, about 67 fps per node |
| Room folder | a **new** room folder, **not `room1`** |
| Minimum total | 7 labels × 3 sessions × 5 min = 21 recordings, 105 min of labelled time (plus transitions) |

Notes that come from what is on disk now:
* `two_people` needs 2 people and `three_people` needs 3 on every session day **[OWNER TO CONFIRM that 3 people are available; `three_people` is optional in `DATASET_PROTOCOL.md` but is requested here]**.
* No label has been recorded in the current link state yet (only two empty recordings exist, 12.1 min). `room1` (October, unknown channel, 11–68 fps) is **not** reused.
* In `room1` the Subject field held session numbers (`s1…s10`). **Here Subject ID = the person**, not the session: `p1`, `p2`, `p3` (never reused for a different person). Which person is `p1`/`p2`/`p3` is written in the session log, not in the dataset.

## 2. Names (set before the first session; **[OWNER TO CONFIRM the Room ID]**)

* **Room ID: `train-ep2-2026-11`** (proposed). It must be a **new** folder `data/datasets/train-ep2-2026-11/`, following the `data/datasets/<roomId>/<roomId>__<subjectId>__<label>__<UTC stamp>.jsonl` convention. It must **not** be `room1`, and must not contain `campaign`, `soak`, `smoke` or `epoch2`, so it can never be confused with c1, c2, the soak or the reference recordings.
* The Training Data Capture panel **defaults Room ID to `room1` and Subject ID to `s1`**. Change **both** fields before every Start; check the file name afterwards (§5). A file that lands in `room1` is a mistake: stop, tell the controller, do not delete it.
* Subject IDs: `p1`, `p2`, (`p3` for `three_people`). Labels exactly as in the table above (the panel's drop-down).

## 3. Settings that must hold for every recording

* **Scan OFF.** Start Scan is not pressed (by the operator or the controller) for the whole session.
* **Never press Calibrate Empty Room** (it changes advisory baselines and is not part of recording).
* **No auto-stop.** The panel has no auto-stop control; the **operator presses Stop** at the planned time (phone timer for every stop). Nothing may stop a recording early or late by itself; if one ends unexpectedly, log it and treat that recording as incomplete.
* **100,000-frame parts.** The recorder's default is `DEFAULT_MAX_FRAMES_PER_FILE = 100_000` (`server/lib/dataset-recorder.ts:58`); it is not an operator setting. Expect `.part2`, `.part3`, … files about every 6 min with four nodes. If parts are not about that size, tell the controller before continuing.
* **Claude Code is idle during every recording.** From each Start to its Stop, Claude Code runs **nothing**: no edits, no tests, no builds, no scripts, no git. No file is saved in VS Code or anywhere in the repo (a saved file can reload the dashboard tab). Checks run only **between** recordings, never while one is running.
* **No dashboard restart, no router / firmware / channel / node-placement change, no serial on any node** (opening serial resets a node), from the first Start of the session to the last Stop.
* **Channel 2 / epoch 2 unchanged** since the router change of 2026-11-09; the recorder does **not** store channel, bandwidth, BSSID or firmware (header says `not_recorded`), so the operator writes them in the session log (§4).
* Stay inside the labelled condition for the **whole** recording. Anything that is not the label (door opened, phone call, second person, a pause in walking) means **Stop and re-record**; never keep a contaminated recording.
* Do not touch the boards or router between takes of one session.
* The dashboard process keeps writing `seq` and `nsc` (running since 2026-11-09 23:00:19, per the c2 checklist); do not restart it. Confirm the first frames carry them (§5).

## 4. Before each session day

1. Four nodes live and fresh in the dashboard, about 67 fps each; router channel 2 fixed, 20 MHz, mixed mode; nodes and router in their usual places, untouched, photographed **[OWNER TO CONFIRM that photos are taken as in c1]**.
2. Warm start: nodes and router on at least 60 min.
3. Phone in airplane mode, laptop on mains, Windows Update and OneDrive paused, Chrome tabs closed, as in c1.
4. Session log started (a text file outside `data/`, e.g. in `reports/ai-inventory-2026-11/`): date, who is `p1`/`p2`/`p3`, router channel/width/mode, node set and positions, firmware version if known, fan position, anything unusual. The log is the only place where physical facts are written; the **operator** confirms each physical fact (room empty, door closed, fan state, who is in the room) in chat, and the controller logs it with a UTC time.
5. Volunteer consent and a data-retention rule exist for every person recorded **[OWNER TO CONFIRM; not on file today, see `06-licences.md` §E.4]**.

## 5. Per-recording procedure (all 7 labels, same steps)

1. In the panel: Room ID `train-ep2-2026-11`, Subject ID (`p1`/`p2`/`p3`/`none` for empty labels, see below), Label. Say the three values in chat.
2. Press Start; the panel's 10 s countdown lets people leave the room or take position before frames are labelled.
3. Hold the condition for **at least 5 min** (plan 6 min so a trimmed start/end still leaves 5): 
   * `empty`: nobody in or near the room, door closed, fan off.
   * `empty_fan`: nobody, door closed, fan ON at its mark.
   * `still`: one person stands or sits still at a **different spot each take**.
   * `walking`: one person walks the whole room (corners, wall midpoints, centre) at a steady pace.
   * `active`: one person moves vigorously (turning, reaching, sitting/standing).
   * `two_people`: two people moving independently.
   * `three_people`: three people moving independently.
4. Press Stop at the planned time (phone timer). Say "stopped" in chat.
5. **Between recordings only** (Claude Code is not idle-restricted now): check the new file name is under `data/datasets/train-ep2-2026-11/`, files are closed, header line shows the right roomId/subjectId/label, all four nodes appear, per-node rate is about 67 fps with no collapse, and the first frames carry `seq` and `nsc`. Anything off → log it; re-record (a re-record is a new file; never delete the failed one).
6. Wait at least 2 minutes before the next recording if a link change was suspected (same rule as c1/c2).

Empty labels have no person: use Subject ID `none` **[OWNER TO CONFIRM]** (an empty file still needs a valid ID).

## 6. Suggested plan (a suggestion, not a requirement) — **[OWNER TO CONFIRM]**

Three different days (not the c2 evening). Each day, in an order that keeps similar labels apart (e.g. empty → still p1 → walking p1 → active p1 → two_people → empty_fan → three_people), all 7 labels once; add the same single-person labels for `p2` on at least one day (preferably on every day) so that every single-person label has two subjects. About 7 × 6 min of labelled time per day plus transitions, around 60–90 min.

Per-day acceptance (suggested, not pre-registered): every label present; each recording at least 5 min with all four nodes; no unexplained rate collapse; session log complete.

## 7. After recording, before any training

* Nothing is committed or pushed without the owner's explicit instruction; `data/datasets/` is gitignored and stays local.
* Add a **training-side guard** that refuses campaign/soak/smoke/epoch folders and mixed link states (inventory §3.3 item 3; not implemented).
* Use one interpreter with scikit-learn for training (inventory §3.3 item 5).
* Only then run the existing refusal gate (`scripts/train/train_activity.py` / `train_count.py` with `--room train-ep2-2026-11`; with default permutation counts, not the reduced run of 2026-11-11); once at least 3 days exist also `--group-by day`. A model the gate refuses stays unexported. No accuracy is claimed before the gate passes on held-out recordings.
* Keep campaign data out of training, and `room1` out of the new room's training unless the owner decides otherwise **[OWNER TO CONFIRM]**; `room1` was recorded before the router change.
