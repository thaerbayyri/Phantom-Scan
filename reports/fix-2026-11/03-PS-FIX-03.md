# PS-FIX-03 — recorder metadata and format (PS-EVAL-005, -009, -015)

**Provenance.** 2026-11-02, HEAD `744ce43` (dirty tree). Footprint `results/footprint-03-PS-FIX-03.txt` (6 files, all named below). Patch `patches/03-PS-FIX-03.patch`. Backups `.tmp/fix-backups/03-PS-FIX-03/`. Tests: `90-test-report.md`.

## Change

Header **schema 2** in both recorders (`server/lib/dataset-recorder.ts`, `scripts/record_dataset.py`). It only **adds** fields to schema 1:

| field | meaning | PS-EVAL |
|--|--|--|
| `partStartedAtMs` | start time of *this part file*; `startedAtMs` stays the *recording* start (it names the files and is shared by all parts, so nothing that keys on it breaks) | -009 |
| `geometryHash` | first 16 hex of sha256 of canonical JSON of `{roomWidthM, roomDepthM, anchors}` (keys sorted, no spaces). **Identical in both languages**: `5482ff6134c7d4c0` for the committed `config/room.json` (checked in TS and Python) and `5ad06de70373cbe1` for the test geometry (same literal in both test suites) | -015 |
| `capture{channel, bandwidthMHz, bssid, firmwareVersion, firmwareHash, source}` | operator-stated capture conditions from `PHANTOM_CAPTURE_CHANNEL`, `PHANTOM_CAPTURE_BANDWIDTH_MHZ`, `PHANTOM_ROUTER_BSSID`, `PHANTOM_FIRMWARE_VERSION`, `PHANTOM_FIRMWARE_HASH` (and CLI flags on the Python recorder). **Invalid or absent → `null`, `source:"not_recorded"`; never guessed, never a crash.** | -015 |
| `annotation{nodeMoved, roomNotEmpty, text}` | operator tri-state flags (`true/false/null`) and ≤ 500 chars of text; accepted by `parseDatasetStart` (`annotation` key) and by `--node-moved/--no-node-moved`, `--room-not-empty`, `--annotation` | -015 |
| `recorder` | `"dashboard"` or `"headless"` | -005 |

**One JSON layout:** the Python recorder now writes compact JSON (`separators=(",",":")`), byte-for-byte the style of the dashboard recorder. Old spaced files (e.g. the 18 Oct empty) still parse.

**Loaders (backward compatible):** `phantom/dataset.py` accepts schema **1 and 2** (`SUPPORTED_SCHEMAS`), and `Recording.header` exposes the first header verbatim, so training code can read `annotation`/`capture`. The evaluation loader (`scripts/presence_eval/recordings.py`) already ignored unknown keys. Schema ≠ 1/2 still raises.

## What it does NOT do (honest limits)

* **No firmware version/hash is obtained automatically.** `firmware/esp32-csi-node/version.txt` is an untracked file and says nothing about what is flashed; `capture.firmware*` is operator-supplied or `null`. Channel/bandwidth/BSSID are likewise operator statements, **not measured** from the frames (the ADR-018 header carries `freqMhz`, `noiseDbm`, `channel`, `seq`, but `CSISample` does not carry them to the recorder; plumbing them is an ingest-path change → PS-FIX-08, shadow mode).
* **The dashboard has no UI for the new fields** (client untouched). The server accepts `annotation` in the start request; the capture panel does not send it yet. Env variables work today.
* `websocket.ts` was **not** touched (capture is read inside the recorder).
* Old recordings are not rewritten.

## Evidence

* TS: `dataset-recorder.test.ts` 14/14 (9 existing, one assertion updated 1 → 2; 5 new): canonical JSON/hash parity, schema-2 header with null-not-guess defaults, per-part `partStartedAtMs` strictly increasing while `startedAtMs` is shared, env validation (valid/invalid/`6.5`), annotation validation and presence in every part header.
* Python: `test_record_dataset.py` + `test_dataset_loader.py` 26/26 (6 new recorder tests incl. NaN/inf/`6.5`/empty channel, compact-JSON round trip through the loader; 1 loader test for schema 2 and header exposure).
* **End-to-end smoke:** `scripts/record_dataset.py --port 5099 … --channel 6 --bandwidth-mhz 20 --bssid AA:BB:CC:00:11:22 --node-moved --annotation "smoke test"` fed by `scripts/synth-csi-udp.py`: 59 frames, compact header with the fields above, `load_recording` → `clean=True`. (Run on a private port and temp dir, because the live dashboard owns :5005.)
* Suites: TS **412/412**; Python **222 passed + 5 opt-in skips**; F1/F2 3/3; AI-firewall 11/11; `tsc` reports no error mentioning `dataset-recorder`.

Both failure directions: not applicable (recording metadata only; no detection path touched). F1/F2 untouched.
