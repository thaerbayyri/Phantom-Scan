# Recording protocol as a data spec — 2026-11 campaign

Companion to `PREREG-2026-11-recording-campaign.md`. The validator (`python -m scripts.presence_eval.validate_campaign <campaign folder>`) enforces exactly this spec. It never writes into `data/`. **Nothing here changes the recorder**: recordings are made with the dashboard "Training Data Capture" or `scripts/record_dataset.py`, which already write the JSONL parts and the `*.summary.json` sidecar (PS-FIX-03 / PS-FIX-29); this spec only adds two small JSON files and a folder layout around them.

## 1. Blocks (all inside ONE link state)

| block type | folder | recorder label | min duration | person | fan | entry log |
|--|--|--|--|--|--|--|
| `empty_1` | `01_empty_1` | `empty` | **≥ 60 min** | none | off | **required** |
| `fan_alone` | `02_fan_alone` | `empty_fan` | ≥ 5 min | none | on | required |
| `walking` | `03_walking` | `walking` | ≥ 5 min | 1 | off | not required |
| `still` | `04_still` | `still` | ≥ 5 min | 1 | off | not required |
| `empty_2` | `05_empty_2` | `empty` | **≥ 60 min** | none | off | **required** |
| `fan_with_person` | `06_fan_with_person` | `still` or `walking` (state which in `block.json`) | ≥ **10** min (set by the owner 2026-11-04) | 1 | on | not required |

One recording per block (a label never spans two conditions). Order is fixed so the second empty closes the campaign; nodes are not touched between blocks.

## 2. LINK CHANGE rule

A **link change** is a held RSSI step of **≥ 6 dB** on any node, or a **frame-rate collapse** (a held rate below 0.7 × that node's reference rate). When one happens: **stop the recording, log it, wait 2 minutes, start a NEW block** (a new recorder file). A block that contains a link change is invalid. The new block gets a new `link_state_id` unless the operator can show the level returned to its earlier value. Blocks are only compared inside one `link_state_id`; at least one link state must contain all six block types.

## 3. Folder layout

```
data/datasets/campaign-2026-11/<campaign_id>/
  campaign.json
  blocks/
    01_empty_1/
      block.json
      entry-log.txt
      room1__<subject>__empty__<UTC>.jsonl            (+ .part2.jsonl ...)   recorder output
      room1__<subject>__empty__<UTC>.summary.json     (+ .part2.summary.json) recorder sidecar, one per part
      serial-node<N>.txt                              optional pasted serial log (docs/serial-counter-capture.md)
    02_fan_alone/ ...
```

Naming: the recorder's own (`<room>__<subject>__<label>__<UTCstamp>[.partN].jsonl`). `<campaign_id>` is free text without spaces. **Never** put campaign files under `data/sessions/` (the dashboard's own session summaries).

## 4. `campaign.json` (one per campaign)

| field | type | meaning |
|--|--|--|
| `schema_version` | int | 1 |
| `campaign_id` | string | folder name |
| `prereg_commit` | string | git commit hash of `PREREG-2026-11-recording-campaign.md` (committed **before** the first block) |
| `nodes_expected` | int list | node ids that must deliver frames, e.g. `[1, 2, 3, 4]` |
| `node_placement` | object | per node id: `x_m`, `z_m`, `height_m`, `orientation`; plus `n1_n2_distance_m`, `router_position` |
| `firmware` | object | `git_hash`, `sdkconfig` reference, `wifi_channel`, `ap_bssid` |
| `operator` | string | who ran it |
| `notes` | string | free text |

## 5. `block.json` (one per block)

| field | type | meaning |
|--|--|--|
| `schema_version` | int | 1 |
| `block_id` | string | unique in the campaign, e.g. `01_empty_1` |
| `block_type` | string | one of `empty_1`, `fan_alone`, `walking`, `still`, `empty_2`, `fan_with_person` |
| `recording` | string | base name of the recording (without `.jsonl` / `.partN`) |
| `start_utc`, `stop_utc` | ISO-8601 UTC | the operator's start and stop; checked against the recorded frame times |
| `link_state_id` | string | blocks sharing a value are in one link state |
| `person_count` | int | people in the room (0 for empty and fan alone) |
| `person_present` | bool | |
| `fan_on` | bool | |
| `fan_position` | string or null | marked position when the fan is on |
| `subject` | string or null | |
| `link_state_notes` | string | what the operator saw (RSSI shown on the dashboard, anything moved) |
| `link_change_events` | list | `{utc, reason, node, rssi_before, rssi_after, fps_before, fps_after, wait_until_utc}`; a block that ENDED because of a link change lists it here |
| `entry_log` | string | file name, `entry-log.txt` (empty blocks) |
| `notes` | string | |

`entry-log.txt`: one line per event, `YYYY-MM-DDTHH:MM:SSZ <who> <what>` (door opened, corridor activity, someone entered). A line is required at the start (`room checked empty`) and at the end. An empty block with **no** entry log is invalid: its emptiness cannot be verified.

## 6. Example (`block.json`)

```json
{
  "schema_version": 1, "block_id": "01_empty_1", "block_type": "empty_1",
  "recording": "room1__s11__empty__20261110T080000Z",
  "start_utc": "2026-11-10T08:00:00Z", "stop_utc": "2026-11-10T09:05:00Z",
  "link_state_id": "L1", "person_count": 0, "person_present": false,
  "fan_on": false, "fan_position": null, "subject": null,
  "link_state_notes": "RSSI N1 -41 N2 -45 N3 -44 N4 -47 at start; nothing moved",
  "link_change_events": [], "entry_log": "entry-log.txt", "notes": ""
}
```

## 7. What the validator refuses (non-zero exit, one clear line each)

sidecar missing (`campaign.json`, `block.json`, a recording's `*.summary.json`, an empty block's entry log); block shorter than its minimum; frame rate outside `[20, 100]` per node; held rate collapse or RSSI step ≥ 6 dB inside a block; a node missing (< 90 % of seconds with frames); an undeclared RSSI shift ≥ 6 dB between blocks of one link state; a block without a `link_state_id`; no link state containing all six block types; a duplicate `block_id`; an unknown `block_type`; an output path under `data/`.
