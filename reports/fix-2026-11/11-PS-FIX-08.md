# PS-FIX-08 — header-offset audit and PHY-consistency guard (SHADOW mode)

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree), scratch venv Python 3.13.15. Backup of the only pre-existing file touched: `.tmp/fix-backups/11-PS-FIX-08/udp-server.ts.HEAD` (the file was clean in git before this item). Patch: `patches/11-PS-FIX-08-udp-server.patch` (+17 lines, no deletions). Footprint: `results/footprint-11-PS-FIX-08.txt` (the "added" list also shows the two PS-FIX-28 files because the previous footprint snapshot pre-dates them). Tests: `90-test-report.md`.

## A. Header-offset audit (is RSSI read from the right byte?)
Firmware serializer `firmware/esp32-csi-node/main/csi_collector.c:226-293` (`csi_serialize_frame`): magic@0 (u32), schema@4, node@5, antennas@6, n_subcarriers@7 (u16), freq_mhz@9 (u32), seq@13 (u32), **rssi@17 (int8)**, noise_floor@18 (int8), channel@19, device_ts_us@20 (u64), device_ts_ms@28 (u32), I/Q from 32.

Both parsers agree with it:
* TypeScript `parseCsiPacket` (`readInt8(17)` etc.), checked by `server/lib/phy-guard.test.ts` (5 tests).
* Python `phantom.protocol.parse_csi_frame` (`struct "<IBBBHIIbbBQI"`), checked by `tests/test_csi_header_offsets.py` (11 tests).

Both test files feed **the same 40-byte frame, built by hand from the offsets above** (not by either parser): `010011c501020104008509000004030201d1a4060200000001000000443322110102030405060708`. They also test RSSI at the signed-byte extremes (−128 … 127) and that neighbouring bytes (seq high byte, channel) do not leak into RSSI/noise.
**Result: no offset error found.** Limit: this proves the *parsers* match the *firmware source*; it does not prove the ESP32 radio reports RSSI in the unit the SDK documents `[UNVERIFIED]`.

## B. What the header does NOT carry
No bandwidth (HT20/HT40), no `sig_mode`, no transmitter address, no per-frame rate. So the guard can lock only (subcarrier count, channel, centre frequency). A bandwidth or sig_mode change that keeps the subcarrier count would be invisible. Adding those fields is a **firmware change; proposed only, not made, nothing flashed**: e.g. bump `CSI_SCHEMA_VERSION` to 2 with `bw`, `sig_mode`, `rate` and the first 3 bytes of the transmitter MAC. It would need Thaer's approval, a firmware build and both parsers updated in lock-step.

## C. The guard (`server/lib/phy-guard.ts`, wired in `server/lib/udp-server.ts`)
* Locks the first (subcarrier count, channel, freq) tuple per node and counts later frames that differ, per field.
* **Shadow mode:** it never drops, alters or delays a frame. A test reads `udp-server.ts` and fails if the observe block ever contains a `return`. Enforcement would be a separate approved change (PS-FIX-13).
* Log policy: first mismatch of a node, then every 1000th mismatched frame (never per frame at ~65 fps/node); the message says "frames are NOT dropped".
* `reset(nodeId?)` forgets the lock (e.g. after an operator deliberately changes the channel). Nothing calls it yet.
* No effect on detection, gating, AI or display, so F1/F2 are not weakened (re-run: green).
* Cost: one Map lookup and three comparisons per accepted frame; `snapshot()` (copies ≤ 4 small objects) runs only on mismatched frames.

## D. What I could NOT do (and why)
The task asked how much a guard would change the empty-vs-empty AUC. **That cannot be recomputed from our recordings:** they store amplitudes per frame but no per-frame channel/frequency/bandwidth, so there is no PHY tuple to guard on offline. I did not re-check per-recording subcarrier widths in this item and I did not invent a number. `[TO BE MEASURED]` on a live run: read `phyGuard.snapshot()` after a session. (Nothing exposes the snapshot over HTTP; adding that would be a server change I did not make.)

## E. Verification (after this item)
TS 432/432, `tsc --noEmit` 0 errors, Python (scratch venv) 327 passed + 5 opt-in skips, F1/F2 3/3, AI-firewall (`websocket.test.ts`) 46/46 incl. the F1 byte-identical-broadcast test; `data/sessions` 730 entries, audit log 2250 lines (both unchanged).
