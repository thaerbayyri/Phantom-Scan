# c2 empty capture: plan (2026-11-19)

Written 2026-11-19 ~12:15Z (15:15 Amman) by Claude Code (controller). Governs nothing new: it applies
`reports/presence-eval-2026-11/C2-SESSION-CHECKLIST.md` and the signed amendments
(`DRAFT-c2-prereg-amendment-link-state-reference.md`, `PREREG-2026-11-recording-campaign.md`).
Where this plan and the checklist differ, the checklist wins.

## Owner decisions taken in chat (2026-11-19)

| Decision | Value |
|---|---|
| Scope | soak + the empty blocks of c2 |
| Room ID for the c2 blocks | `c2-raw-2026-11` (new folder; `campaign-raw-2026-11` is not appended to) |
| Room ID for the soak | `soak-2026-11` (checklist §2) |
| Who presses Start/Stop | Claude Code, in the dashboard via Claude in Chrome, after the owner confirms the physical facts in chat |

## Change of scope, 2026-11-19 ~15:20Z (owner)

The owner chose to **continue c1** for the empty room instead of starting c2. The c2 sections below are kept for the
record but are not being run.

* c1 (`data/datasets/campaign-2026-11/c1-20261105/`) has blocks 01-04 accepted; `05_empty_2` attempt 1 was aborted
  (all-node rate slide, 2026-11-09). The next recording is **block 5 `empty_2`, attempt 2** = its one allowed re-record.
  After it, block 6 `fan_with_person` would remain.
* c1 `nodes_expected` = **1, 2, 4** (node 3 excluded by amendment 5f797e7).
* Host IP: the nodes send to **192.168.1.155** (owner, 2026-11-19), not 192.168.1.20 as the Ubuntu setup doc says.
* Preflight 15:13:39Z (64 s, `data/datasets/preflight-c2-20261119/`, not campaign data): N1 64.6-65.3 fps, RSSI -26;
  N3 62.2-62.6 fps, -53; N4 64.7-65.0 fps, -45; `seq`/`nsc` present. **N2 sent no frames.**
* Blocker: node 2 is required by c1 and is silent. Block 5 cannot start until N2 streams; warm start (60 min) counts
  from when N2 is back.
* Note for the analysis: c1 block 1 recorded N1 at about -31 to -37 dBm; N1 is -26 dBm now. Whether the 10-day gap
  changes the link state is decided by `validate_campaign`, not by eye.

## Pre-flight state found at 12:06Z (superseded: the nodes send to .155)

* Dashboard: running (node pid 25128, started 2026-11-19 15:00 Amman), `/api/health` ok, UDP :5005 owned by it.
* **No CSI is arriving**: dashboard shows "no live CSI signal (nodes silent)", 0 samples / 0 frames.
* Cause found on the host: the nodes are provisioned with `--target-ip 192.168.1.20` (CSI router network
  192.168.1.x), but the PC's **Wi-Fi adapter is disconnected** (APIPA 169.254.62.158) and no interface holds
  192.168.1.20. The PC is online only via `Ethernet 2` (172.16.0.56, "WifiRepeater-B3F2").
* Fix (owner, not Claude: network settings are the owner's): reconnect the PC's Wi-Fi to the CSI router
  (channel 2, 20 MHz) so that it holds 192.168.1.20. Then the controller re-checks that all four nodes are live at ~67 fps.

## Open item [OWNER TO CONFIRM]

* `nodes_expected` for c2: c1 used 1, 2, 4. Proposed now: **1, 2, 3, 4** if all four stream at ~67 fps in pre-flight
  (node 3 had rate collapses in c1; if it does so again in pre-flight, fall back to 1, 2, 4).
* Block order is **fixed** by the checklist: `empty_1` → `fan_alone` → `walking` → `still` → `empty_2` → `fan_with_person`.
  "Empty blocks only" therefore means: soak, block 1, block 2, then the owner comes back for
  blocks 3-4 (6 + 6 min), then block 5 (`empty_2`). Block 6 can follow or be skipped (owner's choice).
  `empty_2` cannot be recorded before blocks 3-4 without breaking the fixed order.

## Steps and timing (Amman, UTC+3; times shift with the real start)

| # | Step | Length | Who |
|---|---|---|---|
| P1 | Reconnect Wi-Fi; controller confirms 4 nodes ~67 fps, `seq`/`nsc` present | - | owner, controller |
| P2 | Warm start: nodes and router on ≥ 60 min before the soak (owner states since when) | ≤ 60 min | owner |
| P3 | Room empty, door closed, fan OFF, laptop on mains, phone timer; Windows Update/OneDrive paused | - | owner confirms |
| S | **Soak**: Room `soak-2026-11`, Subject `soak`, Label `empty`; Start, owner leaves; stop at +3 h 05 min | 3 h 05 | controller via Chrome |
| S-chk | `soak_check` (read-only) after Stop; PASS on every line, else no c2 block starts | ~5-10 min | controller |
| B1 | `empty_1`: Room `c2-raw-2026-11`, Subject `c2`, Label `empty`; stop at +62 min; within 1 h of soak end | 62 min | controller |
| B2 | `fan_alone`: Label `empty_fan`, fan ON at its mark; stop at +6 min | 6 min | owner sets fan, controller |
| B3 | `walking`: owner walks the taped path; "NOW walk out and press Stop" at +6 min | 6 min | owner, controller |
| B4 | `still`: owner on mark A | 6 min | owner, controller |
| B5 | `empty_2`: Label `empty`; stop at +62 min | 62 min | controller |
| B6 | `fan_with_person` (optional) | 11 min | owner, controller |

Total once the nodes stream: about 6 h of wall-clock time (warm start + soak + checks + blocks + transitions).

## Rules the controller follows

* While a recording runs: Claude Code runs nothing except the read-only wait/monitor; no edits, tests, builds, git
  or file saves. The owner saves no file in VS Code.
* No dashboard restart, no Scan, never Calibrate Empty Room, no serial, no router/channel/node change from the
  soak Start to the last Stop.
* Physical facts (room empty, door, fan, who is in the room) are ticked only on the owner's word in chat, logged with UTC.
* In-block link change (held RSSI step ≥ 6 dB or rate < 0.7 × reference): stop, log, wait 2 min, new block;
  at most one re-record per block type.
* After each block: files closed, copied with sha256 into `data/datasets/c2-2026-11/blocks/<NN_type>/`,
  `block.json` + entry log written, `validate_campaign --link-state-mode c2` run. Nothing deleted.

## After capture

* Analysis: `validate_campaign` (default and c2 mode), soak report, per-node rate/RSSI per block.
* Training: only Phase-1 training data (`train-ep2-2026-11`) is training data; campaign and soak folders are
  refused by `phantom/training_guard.py`. The empty capture alone cannot train a model (the activity trainer
  needs ≥ 2 classes from the training folder); the report will show the guard and trainer outputs as they are.
* Report: `reports/campaign-2026-11/c2-20261119/REPORT.md`, written from the logs and tool outputs only.
* Nothing is committed or pushed without the owner's instruction.
