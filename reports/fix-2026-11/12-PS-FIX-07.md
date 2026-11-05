# PS-FIX-07 — frame-rate truth (offline analysis; no firmware, setting or threshold changed)

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv Python 3.13.15. Command: `PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.frame_rate` (11 s). Inputs: the 14 recordings in `data/datasets/room1/` (read-only), `firmware/esp32-csi-node/main/csi_ping_pure.h` (static). Outputs: `results/frame_rate_truth.{md,json}` (every recording × node). Code: `scripts/presence_eval/frame_rate.py`; 9 synthetic-truth tests in `tests/test_presence_eval_frame_rate.py`. New files only; nothing existing was edited in this item.

## What the firmware source says
`csi_ping_pure.h`: ping interval 30 ms, timeout 20 ms, send gate 10 ms (all read by the code, not typed in). Its comment expects "~33 pps per node plus ~10 Hz of AP beacons gives roughly 40 fps". (Dated ADRs/older docs say 41–43 pps or a 50 Hz cap; item 05 corrected the living docs.)

## What the recordings say (52 node-recordings, excluding the 4 of the 2026-10-17 walking recording)
| fact | measured |
|--|--|
| median frame rate per node-recording | **65.0 fps** (min 39.5, max 68.0) — about **1.95 frames per 30 ms ping interval**, not ~1.2 (40 fps) |
| median inter-arrival gap per node-recording | 13–20 ms; q05 0–11 ms, q95 22–38 ms (so arrivals are irregular, not a 15 ms comb) |
| bit-identical consecutive frames | **0.000 in every recording and node** (all 56) |
| relative amplitude change between consecutive frames | median ≈ 0.14 of the vector norm, **the same for gaps of 5–15 ms (0.142) and 15–30 ms (0.140)**; 0.152 for gaps < 5 ms (medians of per-node-recording medians) |
| seconds below half the median rate | 0.000 in most node-recordings; up to 0.12 where a link degraded (s1 walking 2026-10-17, s1 still N3, s2 N1, s5 N3, s6 N3, s7 N1/N3) |
| node-recordings far below 65 fps | s8 N1 39.5 and s9 N1 44.0 (the node-1 link collapse already characterised in PS-EVAL-006); s2/s3/s5/s6 node 4 48–54 fps |
| 2026-10-17 walking recording | **12 fps on all four nodes**, 13 % of gaps > 100 ms. It predates commit `428d3a5` "fix: node ping stall (4-node fps)" (2026-10-18); consistent with the stall that commit describes, but no firmware version is recorded in the file `[UNVERIFIED]` |

## Conclusions (each labelled)
1. **The measured rate is about twice the firmware comment's expectation.** Two accepted frames per ping interval is what the numbers show; **why** (e.g. a second AP frame per echo, or the reply plus another frame from the filtered MAC) is **not observable**: the header carries no frame type, rate or transmitter. `[UNVERIFIED]` — a serial-log read of the firmware's existing counters (`s_cb_count`, `s_mac_skip`, `s_rate_skip`, `s_send_ok`) would answer it without flashing; I did not touch hardware.
2. **The 10 ms send gate is not what limits the rate.** If callbacks outran the gate, gaps would pile up near 10 ms; the observed median gap is 15 ms. This is an inference from the gap distribution, not a counter reading.
3. **Frames are not duplicates.** No bit-identical consecutive pairs, and close pairs differ as much as distant ones. So the frame rate is not inflated by repeated copies; this does **not** say the frames are statistically independent samples of the *person* (frame-to-frame noise is ~14 % of the norm).
4. **Sampling is irregular.** Gap q05–q95 spans roughly 8–25 ms, so features that assume a fixed rate rely on the sidecar's own estimate: `scripts/ai_inference.py` estimates `fs` from timestamps (default 20 Hz only as fallback) — I did not verify the TS server's features do the same `[UNVERIFIED]`.
5. **Zero-millisecond gaps exist in specific recordings** (host-side bursts or genuine back-to-back frames; the recorder clock has 1 ms resolution): s2 all nodes 5.5–6.2 %, s6 N3 16 %, s7 N3 14 %, s1 still N3 8 %. s2 hits all four nodes at once, which points at the host/recorder rather than a node `[UNVERIFIED]`.
6. **Arrivals lock to the 30 ms ping period only weakly** (Rayleigh R at 30 ms: median 0.13 for empty, 0.09 walking vs 0.06 at control periods). The fan recordings read higher (0.26), but that comes from the 2026-10-18 fan recording (0.27–0.31 on every node) while the 2026-10-27 fan recording is 0.07–0.11 on nodes 1–3: it is **recording-specific, not a fan signature**. Not usable as a feature, and not evidence about periodicity of the *signal* (PS-FIX-09).
7. **Detector implications.** With 100-frame sidecar windows, a window is ~1.5 s at 65 fps (and ~2.5 s at 40 fps, ~8 s at 12 fps), so the window length in seconds depends on link health. Anything calibrated in seconds (movement-score lookback, drift) should use time, not frame counts; the epoch work (PS-FIX-32) already uses a 1 s grid.

## Not done / next
* No code in the server or firmware reads or enforces any of this. A live per-node rate/gap monitor in the dashboard is **not** built (display change, Wave 3 territory).
* `[TO BE MEASURED]` on the next recordings: the sidecar summaries (PS-FIX-29) record per-node fps, so the frame-rate truth can be tracked per recording going forward; plus the firmware-counter read in conclusion 1.
