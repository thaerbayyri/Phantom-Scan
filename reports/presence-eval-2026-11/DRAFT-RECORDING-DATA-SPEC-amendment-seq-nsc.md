# Amendment to RECORDING-DATA-SPEC, optional per-frame fields `seq` and `nsc`

**Status: finalized by the owner's instruction and committed.** Drafted 2026-11-09 (night, Asia/Amman).

**Sign line:** Owner instruction 2026-11-10 00:00 Amman to finalize; final text not re-read by the owner at signing; owner to read before the soak; may be amended before any c2 recording.

Amends `RECORDING-DATA-SPEC.md`, which says "Nothing here changes the recorder". The recorder change below is committed (`c51ffdc`) and host-tested; this text describes what a recording made by a dashboard build carrying it contains.

## 8. Optional per-frame fields (new section)

A frame line is `{"type":"frame","t":<host ms>,"n":<node>,"rssi":<dBm>,"a":[51 amplitudes]}`, optionally followed by two more keys:

| field | type | meaning |
|---|---|---|
| `seq` | integer, 0 to 4294967295 | The node's frame counter from the ADR-018 v1 header (offset 13). It counts frames the firmware **produced**: it is incremented once per CSI callback that passed the source-MAC filter and was serialized, **before** the 10 ms send gate (`csi_collector.c` `csi_serialize_frame`, read). It does **not** count frames sent. A step larger than 1 between consecutive recorded frames of one node is a frame that was produced but did not arrive: skipped by the 10 ms gate, failed to send, or lost on the way. The counter starts at 0 at boot (no persistence in the source), so a drop in `seq` means the node rebooted; it wraps at 2^32. |
| `nsc` | integer, 1 to 65535 | The header's `n_subcarriers`, which the firmware computes as I/Q length / 2 because it sends one antenna: 64 (LLTF only), 128 (LLTF + HT-LTF) or 192 (+ STBC-HT-LTF) per `csi-subcarriers.ts`. A proxy for the frame class. The stored `a` vector is always the 51 LLTF data values whatever `nsc` is. |

Rules:
* **Optional and additive.** A frame line without them is valid and unchanged. They are written only when the node supplied a valid value; invalid values are omitted, never guessed. The header is unchanged (schema 2).
* **Which recordings have them.** Only recordings made by a dashboard build carrying the change. The c1 blocks 1 to 4, every aborted attempt and the epoch-2 reference recording lack them. A dashboard process started before the change keeps writing the old lines until it is restarted.
* **Readers and the validator ignore them.** Tested: `scripts/presence_eval/recordings.py`, the strict `phantom/dataset.py` loader and the campaign validator give identical arrays, statistics and verdicts with and without the fields (`tests/test_recording_extra_frame_fields.py`).
* **Not a gate.** Nothing in the validator, the thresholds, the criteria or the analysis windows uses these fields. Any use in analysis is report-only unless a later pre-registered amendment says otherwise.
* `scripts/record_dataset.py` (the headless recorder) does not write them yet.
* **No sidecar change (decided).** The `*.summary.json` sidecar is unchanged; a per-part `seq`-gap report is produced offline by `scripts/presence_eval/seq_report.py`.

## Declarations

1. **No campaign gate, threshold, tier or criterion changes.** The presence threshold 0.6 and the room tiers 4/7/14 are untouched.
2. **Not used to alter c1.** c1 is judged under the frozen pre-registration exactly as written; this amendment adds information to future recordings only.
3. **What it is for.** With `seq` and `nsc`, a future frame-rate slide can be examined frame by frame (which frames vanish, and whether the frame class changes) instead of from rates alone (ledger `PS-FIX-46`, `PS-FIX-37`).

## Open points

None recorded at signing. The text may be amended before any c2 recording (see the sign line).
