# 01 — Data inventory: `data/datasets/room1/`

**Provenance.** Command `python -m scripts.presence_eval.inventory` (venv Python 3.13.15, numpy 2.4.4), run 2026-11-02 on branch `feat/two-node-radar-live-detection`, HEAD `744ce43` with a dirty working tree (Thaer's uncommitted edits; the evaluation code itself is untracked, so its identity is the `eval_code_sha256_16` in the `provenance` block of `results/inventory.json`). Inputs: all 25 `*.jsonl` files in `data/datasets/room1/` (1.6 GB, read-only, streamed). Every number below is copied from `results/inventory.json`.

**Scope.** These are *recording-quality* facts. Nothing here says whether a person was or was not in the room: labels come from the file name/header and were not independently verified.

## 1. Recordings (25 files → 14 recordings)

A recording = base file + `.partN` continuations. 0 malformed lines, 0 bad-length frames, 0 unknown-node frames, 0 out-of-order frames in any file.

| # | recording (subject, label) | UTC start | parts | dur s | declared count |
|--|--|--|--|--|--|
| 1 | s1 walking | 2026-10-17 20:46 | 1 | 416 | 1 |
| 2 | s1 two_people | 2026-10-18 17:30 | 3 | 1087 | 2 |
| 3 | s1 empty | 2026-10-18 17:56 | 1 | 151 | 0 |
| 4 | s1 empty | 2026-10-18 18:02 | 1 | 300 | 0 |
| 5 | s1 empty_fan | 2026-10-18 20:39 | 1 | 275 | 0 |
| 6 | s2 still | 2026-10-25 19:58 | 1 | 228 | 1 |
| 7 | s3 two_people | 2026-10-25 20:12 | 1 | 245 | 2 |
| 8 | s1 still | 2026-10-27 19:36 | 1 | 94 | 1 |
| 9 | s5 empty_fan | 2026-10-27 19:38 | 1 | 202 | 0 |
| 10 | s6 empty | 2026-10-27 19:42 | 1 | 153 | 0 |
| 11 | s7 walking | 2026-10-27 19:45 | 1 | 212 | 1 |
| 12 | s8 empty | 2026-10-27 19:53 | 8 | 3209 | 0 |
| 13 | s9 empty | 2026-10-27 20:47 | 2 | 723 | 0 |
| 14 | s10 still | 2026-10-27 21:21 | 1 | 363 | 1 |

Header geometry is identical in every file: 4 m × 6 m, anchors N1 (−2,−3), N2 (2,−3), N3 (2,3), N4 (−2,3); `firmwareFilterMac` is `null` everywhere. Header `startedAtMs` precedes the first frame by ≤ 0.03 s in all files. Header `notes` is empty in 13 of 14 recordings.

### Per node: frames / measured frames·s⁻¹ (frames ÷ (last t − first t)) / median RSSI dBm / mean amplitude

| # | N1 | N2 | N3 | N4 |
|--|--|--|--|--|
| 1 | 4720 / 11.3 / −23 / 13.12 | 4923 / 11.8 / −54 / 12.94 | 4841 / 11.6 / −32 / 13.15 | 4916 / 11.8 / −46 / 12.91 |
| 2 | 70710 / 65.1 / −36 / 12.86 | 70136 / 64.5 / −34 / 13.14 | 70098 / 64.5 / −54 / 12.89 | 69856 / 64.3 / −41 / 13.27 |
| 3 | 9734 / 64.5 / −34 / 13.49 | 9628 / 63.8 / −29 / 12.49 | 9642 / 63.9 / −55 / 13.13 | 9650 / 64.0 / −38 / 13.19 |
| 4 | 19861 / 66.2 / −34 / 13.39 | 19657 / 65.5 / −29 / 12.66 | 19639 / 65.5 / −55 / 13.12 | 19749 / 65.8 / −38 / 13.12 |
| 5 | 17077 / 62.1 / −30 / 12.91 | 16998 / 61.8 / −29 / 13.15 | 15598 / 56.7 / −57 / 12.20 | 16771 / 61.0 / −43 / 13.25 |
| 6 | 12911 / 56.6 / −33 / 13.05 | 14060 / 61.7 / −24 / 13.32 | 14309 / 62.8 / −49 / 12.89 | 11299 / 49.6 / −45 / 13.44 |
| 7 | 12326 / 50.3 / −46 / 13.27 | 16117 / 65.8 / −25 / 13.59 | 16269 / 66.4 / −47 / 13.06 | 13054 / 53.3 / −44 / 13.50 |
| 8 | 6164 / 65.3 / −36 / 13.23 | 6194 / 65.6 / −27 / 13.58 | 5536 / 58.6 / −50 / 13.36 | 5159 / 54.6 / −46 / 13.14 |
| 9 | 12747 / 63.2 / −36 / 13.11 | 12946 / 64.2 / −27 / 13.61 | 12198 / 60.5 / −49 / 13.37 | 9787 / 48.5 / −44 / 12.97 |
| 10 | 9939 / 64.8 / −36 / 13.11 | 10161 / 66.3 / −27 / 13.65 | 9161 / 59.8 / −49 / 13.43 | 8188 / 53.4 / −44 / 13.06 |
| 11 | 13737 / 64.7 / −36 / 13.23 | 14356 / 67.6 / −27 / 13.59 | 12457 / 58.6 / −50 / 13.38 | 12940 / 60.9 / −45 / 13.34 |
| 12 | 145595 / 45.4 / −47 / 13.63 | 214319 / 66.8 / −29 / 13.38 | 210311 / 65.5 / −50 / 13.13 | 207255 / 64.6 / −47 / 12.82 |
| 13 | 34344 / 47.5 / −47 / 13.67 | 48964 / 67.7 / −28 / 13.35 | 47532 / 65.8 / −50 / 13.01 | 47875 / 66.2 / −46 / 12.91 |
| 14 | 23893 / 65.9 / −38 / 13.34 | 23373 / 64.4 / −32 / 13.40 | 21581 / 59.5 / −51 / 13.05 | 20943 / 57.7 / −42 / 12.87 |

## 2. Frame-rate discrepancy — reconciled

Claim under test: "≈ 53–68 frames/s per node in s6/s7, versus the project constant ≈ 41–43 pkt/s (50 Hz cap)".

* **Measured:** s6 (#10) 64.8 / 66.3 / 59.8 / 53.4 and s7 (#11) 64.7 / 67.6 / 58.6 / 60.9 frames/s for N1–N4. Range 53.4–67.6 → **the 53–68 claim reproduces.**
* **What `t` is:** the recorder host's wall clock at write time (`scripts/record_dataset.py:125`, `time.time()*1000`), not a device timestamp. UDP datagrams can be written back-to-back, so several frames share one millisecond: 0.2–6.2 % of frames share a ms with the previous frame on most nodes, up to 16.4 % on N3 in s6 and 13.8 % in s7. **Bursts exist; duplicated frames do not** (0 consecutive identical amplitude vectors in any node of any recording). Rates computed from unique `t` differ from rates computed from frame counts by up to 9.8 frames/s (N3, s6: 59.8 vs 49.95).
* **Is the 50 Hz cap real?** Not for these recordings. The committed firmware send gate is `CSI_MIN_SEND_INTERVAL_MS 10U` (`firmware/esp32-csi-node/main/csi_ping_pure.h:29`, introduced in commit `428d3a5`, 2026-10-18, "node ping stall (4-node fps)"; the comment at `csi_collector.c:110` says "10 ms = 100 Hz max"). The project memory note records the new firmware as flashed to all four boards on 2026-10-18 `[UNVERIFIED from this session: no serial log was read]`. The per-second maximum in recordings #2–#14 is 62–107 frames/s, i.e. well above 50.
* **Where 41–43 pps comes from:** `TEST_AND_CLEANUP_REPORT.md:58` — a serial `medium tick: yield=41-43pps` reading from an earlier two-node rig, before the 18 Oct firmware change. It is a pre-fix figure. The 17 Oct `walking` recording (#1) is also a pre-fix capture: 11.3–11.8 frames/s with 33–49 gaps > 1 s per node. Several docs still state the 50 Hz cap / 41–43 pps as current (`firmware/esp32-csi-node/README.md:15,115,153`, `generated_reports/Appendix.md:215`, `docs/system_architecture_methodology.md:102`) → **PS-EVAL-002**.
* **Consequence for evaluation:** recording #1 is a different capture regime (≈ 11 fps, gaps) and is excluded from window-based statistics that need ≥ 20 frames per 1.5 s window (it would yield ≈ 17 frames per window).

## 3. RSSI shifts > 6 dB between chronologically adjacent recordings (8 flags)

| node | from → to | Δ dB | gap h | same UTC day |
|--|--|--|--|--|
| 1 | #1 walking 17 Oct → #2 two_people 18 Oct | −13 | 20.7 | no |
| 2 | #1 → #2 | +20 | 20.7 | no |
| 3 | #1 → #2 | −22 | 20.7 | no |
| 3 | #5 empty_fan 18 Oct → #6 s2 still 25 Oct | +8 | 167.3 | no |
| 1 | #6 s2 still → #7 s3 two_people (25 Oct) | −13 | 0.23 | **yes** |
| 1 | #7 s3 two_people 25 Oct → #8 s1 still 27 Oct | +10 | 47.4 | no |
| 1 | **#11 s7 walking → #12 s8 empty (27 Oct)** | **−11** | 0.14 | **yes** |
| 1 | **#13 s9 empty → #14 s10 still (27 Oct)** | **+9** | 0.55 | **yes** |

Node 1 on 27 Oct, per 5-minute bin (from `results/inventory.json`): median RSSI is −36 in s1-still/s6/s7, **−47 in every bin of s8 and s9**, and −38/−36 in s10. Node 1's frame rate over s8's full 5-minute bins is 37.8, 37.1, 37.4, 37.5, 37.6, 38.9, 40.7, 52.4, 61.7, 61.7 frames/s (versus ≈ 65 in s6/s7/s10), while RSSI stays at −47. So the RSSI drop and the frame-rate drop both begin within the ≤ 5 min between the end of s7 (≈ 19:49 UTC) and the start of s8 (19:53:56 UTC); the frame rate partly recovers inside s8 while RSSI does not. The other three nodes do not shift by more than 6 dB in that interval. **Something changed at node 1 (or in its immediate surroundings) between s7 and s8 and changed back between s9 and s10; the headers carry no annotation of it** (PS-EVAL-006). Cause is not determined here (see 03-drift.md).

## 4. Are the empty recordings plausibly empty?

Evidence that exists: (a) the label/file name; (b) one header note — recording #4: *"empty 5 min, headless recorder, room confirmed empty by user"*; (c) declared `count: 0`. Evidence that does **not** exist: any operator log with timestamps for the 27 Oct empties, any independent sensor (camera, door counter), or a second person's confirmation. #3, #10, #12, #13 (and the empty_fan recordings #5, #9) carry no note. s8 is 53 minutes long and s9 12 minutes, recorded in the same room across the period in which an RSSI step occurred; an empty room for 53 continuous minutes is **not verifiable from this data** (PS-EVAL-007). They are treated as "labelled empty", never as "proven empty".

## 5. The October report's "7 labelled recordings, no still/active data"

Both statements are true of different dates. `Phantom-Scan-Final-Project-Report-Oct2026.md:1027` says the recorder "has produced seven labelled **files** … (two `empty`, one `empty_fan`, three parts of `two_people`, one `walking`), from one subject on 17–18 October. There are no `still` or `active` recordings." That matches recordings #1–#5 above exactly (7 files, 5 recordings). `REPORT-NOTES-Oct2026.md:36` rewrites it as "7 labelled recordings", which is a files-vs-recordings miscount. The folder now holds 25 files / 14 recordings because 25 Oct (still s2, two_people s3) and 27 Oct (still s1, still s10, walking s7, empty s6/s8/s9, fan s5) were added after that snapshot. **The report sentence is stale, not wrong at the time it was written** (PS-EVAL-003). Note also that "active" and "three_people" labels exist in the recorder but have no recordings, "still" now exists three times (#6, #8, #14), and "walking" twice (#1 pre-fix, #11).

## 6. Other findings

* **Two writers.** #4 (18 Oct headless recorder) is serialised with spaces (`{"type": "frame", …}`); every other file is compact JSON from the dashboard recorder. Both parse identically; any byte-level tool must tolerate both (PS-EVAL-005). My first independent recount of #4 returned 0 frames for exactly this reason (a test bug, fixed).
* **`phantom/dataset.py` is stricter than the data.** It raises on a single malformed line, silently truncates frames to the shortest width, and loads float64 without counters (PS-EVAL-004). The new loader (`scripts/presence_eval/recordings.py`) tolerates and counts instead.
* **N3 is bursty** in s6/s7 (13.8–16.4 % same-ms frames, up to 4 gaps > 1 s) and **N4 is slow** in several recordings (48.5–54.6 frames/s in #6, #8–#10); node health is not uniform across the day.
* **N2 is the strongest link** in recordings #2–#14 (−24 … −34 dBm); `config/room.json` puts the router at (2, −3), i.e. at N2's anchor.

## 7. Limitations

One room, one rig, one calendar week, nodes possibly moved between days (not recorded). Rates are host-side receipt rates, not radio rates. RSSI medians are integers (dBm) from the firmware. Labels are unverified. The 17 Oct recording is from different firmware.

Tests: `tests/test_presence_eval_inventory.py` (synthetic header/frames/parts/malformed/missing-node/out-of-order/cache round-trip, RSSI-step logic, and a real-folder recount against `results/inventory.json`; skipped if the folder is absent).
