# Serial counter capture — a procedure the owner follows by hand (PS-FIX-37)

**Question this answers:** each node delivers about 65 frames per second, roughly **2 accepted frames per 30 ms ping interval** (`reports/fix-2026-11/12-PS-FIX-07.md`), and the recordings show a frame alternation (`reports/fix-2026-11/results/frame-parity.md`). Why two per ping? The UDP header carries no frame type, rate or transmitter, so the recordings cannot say. The firmware's own counters can narrow it down.

**This is manual and read-only.** The dashboard never opens a serial port (invariant F2) and nothing in this repo does: you read the node's existing log output with your own terminal and paste it into a text file. The parser (`scripts/presence_eval/parse_serial_counters.py`) only reads that text file.

## Read this first: attaching a serial monitor can reset the node

On most ESP32 development boards, opening the USB serial port toggles the DTR/RTS lines, which **reboots the chip**. A reboot restarts every counter and re-forms the Wi-Fi link, so it is a **LINK CHANGE** in the recording protocol (a shift of 6 dB or more, or an fps collapse, means: stop, log, wait 2 minutes, start a new block).

* **Never attach during a recording block.** Do it before the campaign or after the last block, and note it in the block log.
* If your monitor can open the port without resetting the board, use that. With ESP-IDF this is `idf.py -p <port> monitor --no-reset` `[UNVERIFIED]` (not run here; check `idf.py monitor --help` for your version).
* **Do not type in the monitor window.** Keystrokes are written to the node over serial. Select-and-copy, or use the monitor's log-to-file option.
* The ports used in earlier sessions were COM8 = node 4 and COM9 = node 2 `[UNVERIFIED]` (from session notes, not re-checked): confirm in Device Manager.

## Which lines to capture

Both are printed by `firmware/esp32-csi-node/main/csi_collector.c` (read, not run):

| log line | printed | fields |
|--|--|--|
| `medium tick: yield=<n>pps csi_cb=<n> send_fail=<n> rate_skip=<n> cb_drop=<n>` | about once per second (`vTaskDelay(1000)`) | `yield` = frames sent in that tick (`s_send_ok` delta); `csi_cb` = CSI callbacks in that tick (`s_cb_count` delta, all transmitters); `send_fail`, `rate_skip`, `cb_drop` = cumulative since boot |
| `CSI cb #<n>: len=<n> rssi=<n> ch=<n> mac_skip=<n>` | the first 3 callbacks, then every 250th | `#n` and `mac_skip` = cumulative since boot (`mac_skip`: callbacks dropped by the source-MAC filter before the send gate) |

Related constants (`csi_ping_pure.h`): ping interval 30 ms (`CSI_PING_INTERVAL_MS`), send gate 10 ms (`CSI_MIN_SEND_INTERVAL_MS`, so at most 100 frames/s per node).

## Steps

1. Pick a slot **outside** any recording block (see above). Power the node as usual; wait until the `medium tick` lines start.
2. For **one node at a time**, capture **at least 2 minutes** (10 minutes is better) of the live log. Keep the room as it is during the capture (note whether the fan is on and whether anyone is present).
3. Save the text as `reports/fix-2026-11/serial-counters/serial-node<N>-<YYYYMMDD-HHMM>.txt` (never under `data/`). Colour codes and the `I (12345) csi_collector:` prefixes are fine; the parser strips them.
4. Run, per file:
   `python -m scripts.presence_eval.parse_serial_counters reports/fix-2026-11/serial-counters/serial-node2-20261104-1630.txt --node 2`
5. Paste the parser's printed summary (and attach the text file) into the session notes.

## How to read the result (what each outcome would mean)

| observation | meaning |
|--|--|
| frames per 30 ms ping interval ≈ 2 and `rate_skip` per second is small | two frames per ping really pass the MAC filter and the 10 ms gate: they come from the link you are listening to |
| share of callbacks dropped by the MAC filter is large | most callbacks are other transmitters; the accepted ones are a minority |
| `rate_skip` per second is large (and the share of ticks at the 100 pps cap is high) | the 10 ms gate is discarding frames; the recorded rate is set by the gate, not by the radio |
| `send_fail` or `cb_drop` grows | frames are lost on the node before they reach the host |
| a warning that counters went down | the node rebooted during the capture: split the log at that point |

**What the counters cannot tell you:** which frame **types** are counted. The callback does not report a type, so two kinds of frame per ping (for example an echo reply and a second frame) cannot be separated from the log alone. That needs the header fields proposed in PS-FIX-36 (transmitter address, rate, bandwidth, `sig_mode`).

Nothing here changes a threshold, a setting or the firmware.
