# c2 session checklist: soak first, then the six blocks

**Status: uncommitted draft, written 2026-11-10 from the signed amendments (commit `3e8ec9d`).** The amendments govern; this checklist only turns them into steps. It is not part of the pre-registration. Times are Amman (UTC+3); the controller (Claude Code) gives every time as Amman first, with UTC in brackets, and the exact stop time of each recording.

## 0. Rules for the whole session, from the first Start of the soak to the Stop of block 6
- **Phone timer** set for every stop time (the Stop is the operator's; in c1 several stops were late or early).
- **No dashboard restart.** The dashboard process running since 2026-11-09 23:00:19 already writes `seq` and `nsc`; keep it running.
- **No file saves during any recording.** Nobody saves any file in VS Code or anywhere in the repo while a recording runs (a saved client-imported file can reload the open dashboard tab). Claude Code runs **nothing** (no edits, no tests, no scripts) while a recording runs.
- **No router, firmware, node placement or channel change** from the start of the soak to the end of block 6. Any such change needs a new soak.
- **No serial** on any node (opening serial resets it). **Scan stays OFF.** **Never press Calibrate Empty Room.**
- The operator confirms every physical fact (room empty, door closed, fan state and position, person on the path or on mark A) in chat; the controller logs it with a UTC time and never ticks a physical fact itself.

## 1. Before the soak
1. Read the signed amendments once (`reports/presence-eval-2026-11/DRAFT-c2-prereg-amendment-link-state-reference.md`).
2. **[OWNER TO CONFIRM]** the node set of c2 (`nodes_expected`); c1 used nodes 1, 2 and 4. The soak checker takes the list with `--nodes`.
3. Room empty, door closed, **fan OFF**. Laptop on mains. Close Chrome tabs you do not need (the machine ran short of memory on 2026-11-09).

## 2. The soak (at least 3 hours)
1. Training Data Capture: **Room ID `soak-2026-11`**, Subject `soak`, Label `empty`. Fan OFF, scan OFF.
2. Press Start, leave the room, close the door, tell the controller "started". Phone timer for **3 h 05 min** (the minimum is 3 h; the extra minutes are margin).
3. **Do not touch anything for 3 h.** No one enters the room. Entry/door events, if any, are reported to the controller and logged.
4. Press Stop at the stop time given. The recorder rotates parts about every 6.4 minutes; that is normal.
5. **Timing rule (one rule):** c2 block 1 starts at most **1 hour after the soak ends**, and no router, firmware, node placement or channel change happens in between; otherwise a new soak is needed.
6. Right after Stop, with no recording running, the controller runs the checker (read-only; a 3 h soak takes several minutes):
   `python -m scripts.presence_eval.soak_check data/datasets/soak-2026-11/<recording>.jsonl --nodes <node list> --block1-start <planned UTC start of block 1>`
   **PASS** on every line = c2 may start (the produced-rate and D/P lines are report-only). **FAIL** = no c2 block starts; the soak recording is kept, not deleted; investigate and record a new soak.
7. If block 1 actually starts later than planned, re-run the checker with the real start time; the 1 h limit is about the real start.

## 3. The six blocks (fixed order, one link state)
Recorder fields: **Room ID `c2-raw-2026-11` [OWNER TO CONFIRM; c1 used `campaign-raw-2026-11`]**, Subject `c2`, Label as in the table.

| # | block | Label | planned / minimum | who and what |
|---|---|---|---|---|
| 1 | `empty_1` | `empty` | 62 / 60 min | nobody, fan off, entry log required |
| 2 | `fan_alone` | `empty_fan` | 6 / 5 min | nobody, fan ON at its mark, entry log required |
| 3 | `walking` | `walking` | 6 / 5 min | 1 person, fan off, slow steady walk on the taped path |
| 4 | `still` | `still` | 6 / 5 min | 1 person, fan off, standing still on mark A |
| 5 | `empty_2` | `empty` | 62 / 60 min | nobody, fan off, entry log required |
| 6 | `fan_with_person` | `still` or `walking` (the operator chooses and says which BEFORE Start) | 11 / 10 min | 1 person, fan ON |

For every block, in this order:
1. The controller prints **ACTION FOR OPERATOR** (times in Amman) and waits for the operator's confirmation. It runs the sessions guard and arms the read-only monitor **before** the operator presses Start.
2. The operator presses Start, says "started", and (blocks 3, 4, 6) stays in the room as instructed. The controller reads the start time from the recording file name.
3. The controller gives "do not stop before" and "stop at" times. For blocks 3, 4 and 6 it says "NOW: walk out and press Stop" at the planned length; the last 20 s of those blocks are excluded from the primary analysis (frozen rule).
4. After Stop the controller verifies the files are closed, copies them with sha256 checks into `blocks/<NN_type>/`, writes `block.json` and the entry log, and logs every operator statement with its UTC time. Nothing is deleted.

## 4. The link-state rule (c2 amendment A1)
- **One rule for every block: whole-block medians.** Per node of `nodes_expected`, the block's whole-block median RSSI (all frames, untrimmed, compared **unrounded**) against the whole-block median of its **adjacent empty block**: `empty_1` for `fan_alone`, `walking` and `still`; `empty_2` for `fan_with_person`; and `empty_1` against `empty_2`. **Fails at 6 dB or more; passes below 6 dB.**
- The in-block gates are unchanged: a held RSSI step of 6 dB or more, or a held rate collapse below 0.7 x the node's reference, inside a block is a LINK CHANGE (stop, log, wait 2 min, new block).
- The controller runs `python -m scripts.presence_eval.validate_campaign <c2 campaign folder> --link-state-mode c2` after each block, **never while a recording runs**.
- A block that fails is **invalid and is not analysed**, and the failure is reported. A re-recording is a **new block** (new recorder file, after the 2-minute wait); it keeps the link state only if the A1 check passes for it.
- **At most one re-record per block type.** A second failure of the same block type **ends c2 as "link-state check not satisfied"**. All data is kept and reported; no rule is changed.

## 5. After block 6
1. Stop. Do nothing to the dashboard. The controller copies the campaign folder to a second location with sha256 verification and asks where.
2. `validate_campaign` in the default mode and with `--link-state-mode c2`; paste both, a refusal is a valid outcome.
3. Not started yet, to be done before any analysis: the node-set option and the trim option of `run_campaign` (promised in the amendments of 2026-11-05 and 2026-11-09), and the decision how `run_campaign` uses the c2 link-state mode (it currently validates in the default mode).
4. Nothing is committed or pushed without the owner's explicit instruction.
