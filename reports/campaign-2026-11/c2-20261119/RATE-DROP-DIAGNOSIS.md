# All-node frame-rate drop (~66 → ~40 fps): diagnosis and fix plan, 2026-11-19

Read-only analysis by Claude Code from today's recordings, the firmware source and the host network state. No code,
firmware, router or Windows setting was changed.

## Symptom

* All four nodes drop together from about 66 fps to 37-43 fps, stay there for tens of minutes, and recover by themselves
  (today about 18:05-18:38Z and again during the 19:17Z clip; on 2026-11-09 twice during block 5 attempt 1).
* RSSI does not change during a drop, so the boards and the room are not the cause.
* It hits every node at the same moment, so it is a shared cause, not one board.

## Evidence

1. **How a node decides to send** (`firmware/esp32-csi-node/main/csi_collector.c:301-352`, `csi_ping_pure.h`):
   * Each node pings the router every **30 ms**; the router's frames back to the node (echo replies, beacons, ACKs)
     produce CSI callbacks. Only frames from the router's MAC are kept.
   * Every kept callback gets a sequence number (`seq`). A frame is sent over UDP only if **≥ 10 ms** have passed since the
     last send (`CSI_MIN_SEND_INTERVAL_MS`); otherwise it is skipped (`rate_skip`).
2. **What the boards received did not change.** Node `seq` rose by about 136 per second in both normal and slow clips:

   | Clip | Received fps (N1) | Node seq rate | Most common seq step between sent frames | Median gap between frames |
   |---|---|---|---|---|
   | empty 184901Z (normal) | 66.0 | 138.9 /s | **2** (18,013 times) | 15 ms |
   | empty 182022Z (slow) | 42.4 | 136.4 /s | **4** (6,166 times) | 26 ms, 10th percentile **0 ms** |
   | still 191745Z (slow) | 50.2 | 137.2 /s | - | - |

   So the router's frames still reach the boards at the same rate, but in the slow periods they arrive **bunched within
   10 ms of each other**, and the 10 ms send gate throws most of each bunch away. The PC also receives the UDP packets in
   bursts (gaps of 0 ms).
3. **One router, one channel, shared by everything.** Only one access point is visible (channel 2). Since today the PC
   itself is on that Wi-Fi (192.168.1.155), so every node packet crosses the air twice: node → router (uplink) and
   router → PC (downlink), about 260 packets/s each way, on the same channel as the pings. Windows Wi-Fi has
   "Roaming Aggressiveness: Medium" (periodic off-channel scans) and "MIMO Power Save: Auto SMPS".
4. **The model's features depend on the frame rate** (`phantom/features.py:67-180`): the per-window rate is estimated,
   but `total_power` is summed up to 0.45 × fs, `change_points` counts frame-to-frame jumps, and the spectrum length
   changes with the number of frames. A 40 fps window and a 66 fps window of the same room give different features.

## Most likely cause [not proven]

Air-time contention and buffering at the single router: when the router is busy (the PC's downlink, other clients
such as the three devices at .133/.213/.237, or the PC going off-channel to scan), it delivers its frames to the nodes in
bunches. The nodes' 10 ms gate then forwards fewer of them. This fits every observation above; it is not yet proven,
because the node's own counters (`send_fail`, `rate_skip`) are not recorded in the dataset files.

## Fix plan, in order of cost

| # | Fix | Where | Effect | Cost |
|---|---|---|---|---|
| 1 | **Connect the PC to the CSI router with a LAN cable** (built-in `Ethernet` port, now unplugged) and turn the PC's Wi-Fi off or onto another network; reserve 192.168.1.155 for the cable's MAC in the router (the nodes send to .155) | owner, hardware | removes the whole downlink copy (half the air time) and the PC's scans from channel 2 | a cable; 5 min |
| 2 | Keep other devices off this router during recordings (phones, TV at .133/.213/.237) | owner | less contention | none |
| 3 | Record the node's health counters: parse the node's periodic stats packet (`send_failures`, `callback_drops`, `rate_skip`) in the server and write it into the `.jsonl` | code (server) | proves or disproves the cause next time | small code change + tests |
| 4 | Make the features rate-independent: resample each 1 s window to a fixed rate (e.g. 30 Hz) before `extract_window_features` | code (`phantom/features.py`) | a 40 fps clip and a 66 fps clip of the same scene give the same features; protects training from future drops | code change + tests; existing reports must be regenerated |
| 5 | Training guard: refuse or flag clips whose median fps is below 0.7 × 67 | code (`phantom/training_guard.py`) | no silent mixing of slow and normal clips | small code change + tests |
| 6 | Firmware: lower the send gate (10 → 5 ms) or ping faster (30 → 15 ms) | firmware, reflash 4 boards | more frames per bunch | reflash; more air time (may worsen contention); last resort |

**Recommended now:** 1 and 2 (no code), then one 30-minute empty test recording to see whether the rate stays at
about 66 fps. Then 3, 4 and 5 as one code change with tests, before Phase-1 sessions 2 and 3.

## Status 2026-11-19 ~20:10Z (uncommitted)

* **Fix 4 done**: `phantom/features.py` adds `resampled_window_features` (30 Hz fixed grid, duplicate timestamps
  averaged); `sliding_windows` (training) and `phantom/sidecar.py` (live) both use it. Correction to evidence item 4:
  on a clean, evenly sampled signal the old features were already rate-independent within 5 %; the dependence comes
  from measurement noise. On a noisy empty room, 40 vs 66 fps changed `motion_band_power` ×1.83 and `change_points`
  ×0.55 with the old path, ×1.09 and ×1.13 with resampling (`dominant_freq_hz` ×1.45 → ×1.25). Tests in
  `tests/test_features.py`.
* **Fix 5 done**: `phantom/training_guard.py` refuses a part whose summary shows any node below 46.9 fps (parts
  ≥ 60 s with a summary). Tests in `tests/test_training_guard.py`. Full Python suite: 632 passed, 5 skipped.
* The guard then refused `still 191745Z` (N3 46.7 fps); it was moved to `lowrate-train-ep2-2026-11/`. The trainer now
  refuses for too few `still` recordings (1). A diagnostic run with `--allow-unsafe` was blocked and not run.
* **Fix 3 not done** (server recording of node counters). Fixes 1-2 are the owner's (cable, other devices).

## How to verify fix 1

1. Plug the cable in; check the PC holds 192.168.1.155 on `Ethernet` and the dashboard shows all four nodes.
2. Record 30 min empty in a scratch folder (not a training or campaign folder).
3. Pass: every part's `last10s.fps` ≥ 60 on all nodes and no `rate_collapse` flag; median seq step 2.
