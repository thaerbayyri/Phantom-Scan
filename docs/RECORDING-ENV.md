# Recording environment variables (header link-state fields)

Written 2026-11-11. Describes what the recorder already does; it adds no variable and changes no code.

## What they are

The dashboard's dataset recorder cannot see the Wi-Fi channel, bandwidth, router BSSID or node firmware. The operator supplies them through five environment variables, and the recorder copies them into the `capture` object of every recording header (line 1 of each `.jsonl` part).

| Variable | Header field | Accepted value | Otherwise |
|---|---|---|---|
| `PHANTOM_CAPTURE_CHANNEL` | `capture.channel` | integer 1 to 196 | `null` |
| `PHANTOM_CAPTURE_BANDWIDTH_MHZ` | `capture.bandwidthMHz` | `20`, `40`, `80` or `160` | `null` |
| `PHANTOM_ROUTER_BSSID` | `capture.bssid` | `aa:bb:cc:dd:ee:ff` (six hex pairs; stored lowercase) | `null` |
| `PHANTOM_FIRMWARE_VERSION` | `capture.firmwareVersion` | 1 to 64 characters from `A-Z a-z 0-9 . _ + -` | `null` |
| `PHANTOM_FIRMWARE_HASH` | `capture.firmwareHash` | 7 to 64 hex characters (stored lowercase) | `null` |

`capture.source` is `"operator_env"` when at least one value was accepted, else `"not_recorded"`. An invalid value becomes `null`; it is never guessed and never stops a recording.

Source: `server/lib/dataset-recorder.ts:110-129` (`captureFromEnv`), field types at `:70-76`, read when a header is written at `:447` (`this.context.capture ?? captureFromEnv(process.env)`).

## Current state

Every recording made so far has all five fields `null` and `"source":"not_recorded"`, for example `data/datasets/campaign-raw-2026-11/campaign-raw-2026-11__c1__still__20261111T112158Z.jsonl`. The link state of those recordings is known only from the operator's session log.

## Example for the current link state

Values: channel 2, 20 MHz (owner's statement of the router setting since 2026-11-09).

Git Bash:

```bash
export PHANTOM_CAPTURE_CHANNEL=2
export PHANTOM_CAPTURE_BANDWIDTH_MHZ=20
export PHANTOM_ROUTER_BSSID=xx:xx:xx:xx:xx:xx     # [OWNER TO FILL]
export PHANTOM_FIRMWARE_HASH=xxxxxxx              # [OWNER TO CONFIRM]
npm run dev:dashboard
```

PowerShell:

```powershell
$env:PHANTOM_CAPTURE_CHANNEL = "2"
$env:PHANTOM_CAPTURE_BANDWIDTH_MHZ = "20"
$env:PHANTOM_ROUTER_BSSID = "xx:xx:xx:xx:xx:xx"   # [OWNER TO FILL]
$env:PHANTOM_FIRMWARE_HASH = "xxxxxxx"            # [OWNER TO CONFIRM]
npm run dev:dashboard
```

**Firmware hash [OWNER TO CONFIRM].** `git -C firmware/esp32-csi-node rev-parse HEAD` prints the commit of the whole repository (the firmware folder is not a repository of its own), which is the source on disk and not necessarily the build flashed on the nodes. Use it only if the nodes were flashed from that commit; otherwise use the flashed build's hash, or leave the variable unset so the field stays `null`. `PHANTOM_FIRMWARE_VERSION` is optional and has no value on file.

Whether the dashboard also reads these from a `.env` file is `[UNVERIFIED]`; set them in the shell that starts it.

## Rules

1. **Set before starting the dashboard.** The values are read from the dashboard process's environment; changing a variable in another shell afterwards has no effect on a running dashboard.
2. **Never restart the dashboard during a soak or campaign window** to set them. If the dashboard is already running for a soak or campaign, leave the fields `null` and write channel, width, BSSID and firmware in the session log instead.
3. **Check the first header** after the first Start: `capture.source` must be `"operator_env"` and the values must be the ones intended.
4. **When the link state changes** (router channel, width, router, firmware), stop the dashboard outside any recording window, set the new values, start it again, and use a new room folder. The training-folder guard (`phantom/training_guard.py`) refuses a folder whose headers carry different `capture.channel` values.
