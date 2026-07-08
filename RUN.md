# Run Guide

This guide targets the current checkout. **The Node dashboard (`npm run dev`) is the
canonical live path and the sole owner of UDP `5005` ESP32 ingest.** The old Python
authority is an opt-in special mode only (see below) and must never run alongside the
dashboard.

## Canonical Ports

- Dashboard/API + browser UI: `5000` (auto-falls back to 5001-5019 if busy)
- Dashboard UDP CSI ingest (ESP32 → host): `5005`
- AI sidecar UDP input (dashboard forwards accepted raw frames): `5006`

## Canonical Start Sequence

1. Build, flash, and provision the firmware first (see Firmware below). Canonical live
   runs assume both boards are already streaming the 32-byte ADR-018 CSI frame plus
   heartbeat contract to host UDP `5005`. Boards running RuView-lineage firmware also
   emit a 1 Hz `0xC5110006` feature-state packet — the dashboard parses it too.

Serial pass signals before moving on:

- WiFi connects to the target SSID
- `self-ping started -> <gw> @50Hz (CSI OFDM source)`
- `CSI filter upgraded to MGMT+DATA`
- CSI callback logs climb
- `medium tick: yield=...` is non-zero on a quiet network

2. Start the dashboard. It binds UDP `5005` directly (`server/lib/udp-server.ts`) and
   serves the browser UI:

```powershell
npm run dev
```

Expected console lines:

```text
[dev-full] starting dashboard on port 5000 (owns UDP :5005 ESP32 ingest)
[UDP] CSI Receiver listening on 0.0.0.0:5005
```

3. Open `http://localhost:5000`, log in, and start a scan. With both boards streaming
   you get `fused_two_node` mode, per-node beacons with distance/trend labels, and the
   **Board DSP** card (firmware `0xC5110006` presence/motion/respiration/heart-rate,
   shown alongside the host-DSP estimates for cross-checking).

4. Optional: start the advisory AI sidecar. The dashboard forwards accepted raw frames
   to `127.0.0.1:5006` automatically.

```powershell
python scripts\ai_inference.py
```

## Processes that MUST NOT run alongside the dashboard

Both of these bind UDP `5005` and will steal or block the ESP32 stream:

- `python -m phantom.runtime live ...` (the superseded Python authority)
- `python scripts\ruview-dashboard-bridge.py` (bench-only diagnostic; run it standalone
  on a bench, never together with `npm run dev`)

If the dashboard logs `[UDP] Cannot bind UDP :5005 — the port is already in use`, find
and stop the other process first.

## Python Authority (opt-in special mode only)

The legacy Python-authority path still exists behind an explicit flag. It makes the
Python process own `5005` instead of the dashboard — do not use it for canonical
two-node evidence:

```powershell
$env:PHANTOM_USE_AUTHORITY = "1"
npm run dev
```

## Python Environment (for the optional scripts)

Create and activate a local virtual environment from the explicit Python 3.13
interpreter. Do not rely on the Windows Store `python.exe` alias.

```powershell
& 'C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe' -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Optional advisory AI install:

```powershell
pip install -r requirements-live-ai.txt
python -c "import json; from phantom.ai_status import probe_ai_stack; print(json.dumps(probe_ai_stack().to_dict(), indent=2))"
```

If the AI probe is not ready, the runtime remains deterministic-only.

## Firmware

From an ESP-IDF shell (or use the Docker build in `firmware/esp32-csi-node/README.md`):

```powershell
cd firmware\esp32-csi-node
idf.py build
idf.py -p COM5 flash monitor
idf.py -p COM6 flash monitor
```

Provision credentials/node identity without reflashing via
`firmware/esp32-csi-node/esp-flash.py` (SSID, password, target IP/port, unique
`node_id` per board).

Expected bindings for the live validation run:

- Node 1: `COM5`
- Node 2: `COM6`
- Both nodes stream ADR-018 CSI to host UDP `5005`.

## Live Validation Checklist

- Dashboard console shows `[UDP] CSI Receiver listening on 0.0.0.0:5005` and periodic
  `[UDP] Received N packets in last 5s`.
- Node 1 streams independently.
- Node 2 streams independently.
- Both fresh nodes produce `fused_two_node` mode.
- Board DSP card shows per-node firmware metrics refreshing ~1 Hz (RuView-lineage
  firmware only; silent boards age out of the card within 5 s).
- Stopping one node returns to degraded single-node mode after the stale timeout.
- A spoofed `nodeId` from a different source is rejected and logged as
  `node_source_mismatch` (rate-limited; the warning notes the duplicate-node_id
  provisioning pitfall).
- If the target/scene freezes for >5 s the client watchdog clears it (no ghost target).
- CSI Hz, midpoint localization, detection, respiration, and heart-rate metrics are
  recorded only after real hardware measurement.
