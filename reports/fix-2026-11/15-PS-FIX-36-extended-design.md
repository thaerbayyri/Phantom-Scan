# PS-FIX-36 extended: PHY trailer for the CSI datagram (design, 2026-11-09)

**Status.** Design plus two host-tested modules. **Nothing is flashed, nothing is wired into the live ingest, the recorder, `csi_collector.c` or `CMakeLists.txt`.** No decision is taken here; integration needs the owner's approval. Labels: measured / read = seen in this repo or on this machine today; `[UNVERIFIED]` = not seen.

## 1. Read this first: two things the recordings could already have told us

1. **The v1 header already carries a sequence counter** (`seq`, u32 at offset 13). **What it counts**, from `csi_collector.c` (read, not run): `s_sequence` is a file-static u32 (line 39), incremented once per call of `csi_serialize_frame` that passes its buffer-size check (line 275). That function is called from `wifi_csi_callback` (line 322) **after** the source-MAC filter (line 316) and **before** the 10 ms send gate (line 329). So `seq` counts frames **produced** (callbacks from the wanted transmitter that were serialized), **not frames sent**: a frame later skipped by the gate (`s_rate_skip`) or whose send failed (`s_send_fail`) still consumes a number; callbacks dropped by the MAC filter (`s_mac_skip`) do not, and an oversized frame (serialize returns 0 before the increment) does not. The heartbeat packet's `seq` is the current value of the same counter (line 592), not a count of its own, and the frames sent to the edge-processing queue (`edge_enqueue_csi`) are not numbered. Per second, `delta seq = delta send_ok + delta send_fail + delta rate_skip` (the serial "medium tick" line prints `yield` = send_ok per tick and cumulative `send_fail` and `rate_skip`). **`[UNVERIFIED]`, the source cannot show:** whether the Wi-Fi driver drops CSI before it calls the callback; whether the callback always runs in one task (the counter is a plain non-atomic variable that the heartbeat task also reads); the real split between gate skips and datagrams lost on the way (needs the serial counters of PS-FIX-37 or the recorded `seq` of step 0 below); whether a node reboots during a recording (a reboot restarts the counter at 0, there is no persistence in the source, and it shows as a drop in `seq`). On the host, `PacketOrderGuard` counts `gapCount` from `seq` steps but only in memory (`udp-server.ts`), and it rejects a replayed or out-of-order `seq`. **The recorder stores only `t, n, rssi, a`** in recordings made before the step 0 change, so no older recording can show the gaps.
2. **The header's `n_subcarriers` is `I/Q length / 2` for the firmware's single antenna (`n_antennas` is fixed at 1 in `csi_serialize_frame`).** `reduceCsiFrame` reads only the first 64-entry LLTF block (`csi-subcarriers.ts`, read), so every recorded vector has 51 values whatever the packet type. The raw I/Q length is 128 (LLTF only), 256 (LLTF + HT-LTF) or 384 bytes (+ STBC-HT-LTF) per the comment in that file. That length is a free proxy for the frame class, and the recordings throw it away.

**Step 0 (no firmware change): done 2026-11-09, host-tested, uncommitted.** The dashboard recorder now also writes `seq` and `nsc` (= `n_subcarriers`) per frame when the node supplies them; the frame line is byte-identical when they are absent (`dataset-recorder.ts`, tests in `dataset-recorder.test.ts`, `dataset-seq-nsc.test.ts`, `udp-server-phy-guard-fault.test.ts`, `tests/test_recording_extra_frame_fields.py`). Not live until the dashboard is restarted; draft spec amendment: `reports/presence-eval-2026-11/DRAFT-RECORDING-DATA-SPEC-amendment-seq-nsc.md`. Original proposal: It would answer "which frames vanish in a slide" and "what is the mix of frame classes" for any future campaign. This is the cheapest next step and does not need the trailer.

A measured clue that the length matters: during the epoch-2 reference run the Wi-Fi adapter received 262 unicast packets/s at 85,555 B/s, i.e. 326 B per packet on average. With about 42 B of Ethernet/IP/UDP headers (`[UNVERIFIED]` overhead) that is a mean UDP payload of about 284 B, close to 32 + 256, which would mean most frames carry 256 B of I/Q. Not proven: only a packet capture or Step 0 can say.

## 2. `wifi_csi_info_t` in the project's ESP-IDF

Project: ESP-IDF v5.5.2, target ESP32-S3 (`E:\Espressif\frameworks\esp-idf-v5.5.2`, `sdkconfig`). The S3 has no HE support, so the non-HE `wifi_pkt_rx_ctrl_t` applies. Source: `components/esp_wifi/include/local/esp_wifi_types_native.h` lines 36-130 (read). The v5.3.1 tree is also installed; it was **not** compared.

| field | exists | bits | in v1 header | in trailer |
|---|---|---|---|---|
| `rx_ctrl.rssi` | yes | 8 | yes (@17) | no |
| `rx_ctrl.rate` | yes | 5 | no | yes (non-HT only) |
| `rx_ctrl.sig_mode` | yes | 2 | no | **yes** |
| `rx_ctrl.mcs` | yes | 7 | no | yes |
| `rx_ctrl.cwb` | yes | 1 | no | **yes** |
| `rx_ctrl.smoothing`, `not_sounding` | yes | 1, 1 | no | no |
| `rx_ctrl.aggregation` | yes | 1 | no | yes |
| `rx_ctrl.stbc`, `fec_coding`, `sgi` | yes | 2, 1, 1 | no | yes |
| `rx_ctrl.noise_floor` | yes | 8 | yes (@18) | no |
| `rx_ctrl.ampdu_cnt` | yes | 8 | no | yes |
| `rx_ctrl.channel`, `secondary_channel` | yes | 4, 4 | channel (@19) | secondary |
| `rx_ctrl.timestamp` | yes | 32 (us, local rx time) | no (v1 has `esp_timer` us at serialization) | no |
| `rx_ctrl.ant`, `sig_len`, `rx_state` | yes | 1, 12, 8 | no | no |
| `mac[6]` (source) | yes | 48 | no | last 3 bytes |
| `dmac[6]` | yes | 48 | no | no |
| `first_word_invalid` | yes | 1 | no | yes |
| `buf`, `len` | yes | n/a | the payload | n/a |
| `hdr` (pointer to the 802.11 header) | yes | n/a | no | frame-control bytes 0 and 1 |
| `payload`, `payload_len` | yes | n/a | no | no |
| `rx_seq` | yes | 16 | no | **yes** (802.11 sequence number) |

Whether `hdr` is non-NULL and at least two bytes long at run time on this firmware is `[UNVERIFIED]`; the packer takes an explicit `hdr_valid` flag for that reason.

## 3. Why a trailer, not new header bytes

All 32 bytes of the v1 header are in use. The only redundant bytes are `device_ts_ms` (offset 28, 4 bytes, equal to `device_ts_us / 1000`).

| option | v1 readers | verdict |
|---|---|---|
| **A. 16-byte trailer after the I/Q** (chosen) | The live TypeScript `parseCsiPacket` rejects only datagrams *shorter* than `32 + n_ant * n_sc * 2`; `reduceCsiFrame` reads only entries inside that range. A trailer is ignored there. **Proven by tests against the real functions.** **The Python parser `phantom/protocol.py` requires an exact length and rejects a trailer frame (measured, section 3b).** | backward compatible for the TypeScript ingest only; Python readers must change first |
| B. Reuse the 4 bytes of `device_ts_ms` | Needs a presence marker; v1 still requires `schema == 1`; 4 bytes cannot hold `sig_mode`, `cwb`, frame type and transmitter plus a marker. | rejected |
| C. New magic or schema 2, packed header | An old server drops every frame (unknown magic or `schema != 1`). | needs server-first deployment; kept as a fallback only |

This departs from the literal wording "in the 32-byte header" because the header cannot hold the fields without breaking v1 readers. If a header-only layout is wanted, option C is the way, with the cost above.

### 3b. Known incompatibility: the Python readers (found in review, then measured)

`phantom/protocol.py` `parse_csi_frame` (line 201) returns `InvalidPacket("csi_payload_length_mismatch")` unless the I/Q length is **exactly** `n_ant * n_sc * 2`. Measured 2026-11-09 on the golden frame: the 160-byte plain frame parses to `CsiFrameV1`, the 176-byte trailer frame is rejected. Callers: `scripts/ai_inference.py` (the :5006 sidecar, fed with mirrored datagrams) and `scripts/record_dataset.py`. So **the trailer must not be sent until those two are changed** (tolerate `>=`, or strip the trailer), with a Python test on the golden frame. Not changed here: that is live-path code and an owner decision. `scripts/record-csi-udp.py` has no frame parsing of its own (read).

**Resolved 2026-11-09 (host-tested, uncommitted):** `parse_csi_frame` now accepts exactly two shapes, a plain frame (`32 + n_ant * n_sc * 2` bytes) or that plus one valid 16-byte trailer (magic PHX1 and checksum), parses the second as the first and ignores the trailer; any other length is still `csi_payload_length_mismatch`. The trailer is looked for only at exactly plain + 16 bytes, so I/Q bytes that look like a trailer inside a plain frame stay I/Q (collision tests). `scripts/ai_inference.py` and `scripts/record_dataset.py` needed no change of their own, because both only call `parse_csi_frame`; their paths are covered by `tests/test_csi_phy_trailer.py` (the sidecar's real `parse_csi_packet` body, extracted from the source, and the record_dataset parse, amplitude and `frame_record` path).

## 4. Wire layout (little-endian, 16 bytes, after the I/Q)

| bytes | content |
|---|---|
| 0-3 | magic `0x31584850` ("PHX1": `50 48 58 31`) |
| 4 | `sig_mode`[1:0], `cwb`<<2, `aggregation`<<3, `stbc`[1:0]<<4, `sgi`<<6, `fec_coding`<<7 |
| 5 | `mcs`[6:0], `first_word_invalid`<<7 |
| 6 | `ampdu_cnt` |
| 7 | `rate`[4:0], `secondary_channel`[1:0]<<5, `hdr_valid`<<7 |
| 8, 9 | 802.11 frame-control bytes 0 and 1 (0 when `hdr_valid` is 0) |
| 10-11 | `rx_seq` |
| 12-14 | transmitter: last three bytes of `mac` |
| 15 | XOR of bytes 4..14 |

Frame type = type (bits 2-3) and subtype (bits 4-7) of byte 8. Transmitter = three bytes of `mac` (enough to tell the AP's echo replies from other senders when the full MAC is known from provisioning). Bandwidth = `cwb` plus `secondary_channel`. The sequence counter stays the v1 `seq`; the trailer adds `rx_seq`.

## 5. Dispatch, longer signature first

`classifyCsiDatagram` (`server/lib/csi-phy-trailer.ts`) tests the longer signature first: a datagram is the trailer shape only if `length == 32 + n_ant * n_sc * 2 + 16` **and** the last 16 bytes carry the magic **and** a valid checksum. Otherwise a well-formed v1 frame stays `csi_v1`. Tests: trailer frame found first; a plain frame whose I/Q ends in a valid-looking trailer stays `csi_v1`; right length with junk stays `csi_v1`; 15 trailer bytes stays `csi_v1`; wrong schema, zero subcarriers, heartbeat magic, short input are `not_csi_v1`; nothing throws. "Longer-magic-first" is my reading of the request (specific signature before the generic one); if a different dispatch was meant, say so.

## 6. Golden frames and tests

`tests/fixtures/phy_trailer_golden.json` (three 16-byte trailers with their decoded fields) and `tests/fixtures/adr018_phy_trailer_frame.hex` (176 bytes: 32 header + 128 I/Q + 16 trailer). The same three hex strings are in the C test; a TypeScript test reads the C file and fails if they differ. Run: C `gcc -std=c99 -O2 -Wall -Wextra -I.. test_csi_phy_trailer_pure.c ../csi_phy_trailer_pure.c` (MSYS2 gcc, `C:\msys64\ucrt64\bin` on PATH); TS `npx tsx --import ./server/test-setup.ts --test server/lib/csi-phy-trailer.test.ts server/lib/udp-server.test.ts`.

## 7. Bytes per second at 4 nodes x 67 fps (UDP payload only)

| I/Q length | v1 per frame | v1 B/s | with trailer B/s | added |
|---|---|---|---|---|
| 128 (LLTF) | 160 | 42,880 | 47,168 | +4,288 (+10.0 %) |
| 256 (LLTF + HT-LTF) | 288 | 77,184 | 81,472 | +4,288 (+5.6 %) |
| 384 (+ STBC) | 416 | 111,488 | 115,776 | +4,288 (+3.8 %) |

Airtime impact of 16 more bytes per datagram on the node-to-laptop hop was not measured.

## 8. Not done (needs approval)

* Call `csi_phy_trailer_pack` from `csi_serialize_frame` after the I/Q `memcpy`, behind a Kconfig symbol that defaults to off; add the `.c` to `CMakeLists.txt`; `CSI_MAX_FRAME_SIZE` (2080) already has room. Compile for the target is `[UNVERIFIED]`.
* The Python parser blocker in 3b is resolved (host-tested, uncommitted); the remaining blockers are the owner's approval and the integration items below.
* At integration: assert an even `info->len` (the trailer is recognised only at `32 + 2 * n_subcarriers + 16`); include the trailer in the `frame_size > buf_len` check in `csi_serialize_frame`; `secondary_channel` is 4 bits in the IDF struct but 2 bits on the wire (values 0-2 fit).
* Tests to add with the integration: a golden with `rate != 0` and `ampdu_cnt > 3`, a case with `hdr_valid = 0` and non-zero `rate`, `n_antennas > 1`, and trailer frames at 256 and 384 I/Q bytes through `classifyCsiDatagram` and `reduceCsiFrame`.
* Server: classify in `udp-server.ts`, carry the fields to the recorder, bump the recorder schema.
* Step 0 above.
* Firmware reflash and the order of server-then-firmware.

## 9. Rollback

Delete the files listed in section 6 and the firmware pair; no runtime code references them.
