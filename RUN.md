# Run Guide

This guide targets the current `main` checkout and the authority-owned live path.

## Python Environment

Create and activate a local virtual environment from the explicit Python 3.13 interpreter. Do not rely on the Windows Store `python.exe` alias.

```powershell
& 'C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe' -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Expected Python version after activation:

```text
Python 3.13.9
```

Optional advisory AI install:

```powershell
pip install -r requirements-live-ai.txt
python -c "import json; from phantom.ai_status import probe_ai_stack; print(json.dumps(probe_ai_stack().to_dict(), indent=2))"
```

If the AI probe is not ready, the runtime remains deterministic-only.

## Canonical Ports

- Dashboard/API: `5000`
- Python authority UDP CSI ingest: `5005`
- AI sidecar UDP input: `5006`
- Python authority HTTP API: `8789`

## Canonical Start Sequence

1. Build, flash, and provision the firmware first. Canonical live runs assume both boards are already streaming the current 32-byte ADR-018 CSI frame plus heartbeat contract to host UDP `5005`.

Serial pass signals before moving on:

- WiFi connects to the target SSID
- `self-ping started -> <gw> @50Hz (CSI OFDM source)`
- `CSI filter upgraded to MGMT+DATA`
- CSI callback logs climb
- `medium tick: yield=...` is non-zero on a quiet network

2. Start the Python authority. It is the sole canonical binder of UDP `5005`.

```powershell
python -m phantom.runtime live --host 0.0.0.0 --port 5005 --api-host 127.0.0.1 --api-port 8789 --forward-ai-host 127.0.0.1 --forward-ai-port 5006 --no-synthetic
```

3. Optional: start the advisory AI sidecar after dependencies are installed.

```powershell
python scripts\ai_inference.py
```

Synthetic self-feed is disabled by default. To explicitly run the AI synthetic feed for demo-only work:

```powershell
$env:PHANTOM_AI_SYNTHETIC = "1"
python scripts\ai_inference.py
```

4. Start the Node dashboard. In canonical mode it follows the Python authority and does not bind UDP `5005`.

```powershell
npm run dev
```

The dashboard polls `http://127.0.0.1:8789/api/sensing/frame` and broadcasts authority state to the existing React `/ws` client.

## Dev-Only UDP Mode

The old Node UDP path is still available for parser/dashboard development, but it is mutually exclusive with the Python authority on UDP `5005`.

```powershell
$env:PHANTOM_UDP_MODE = "dev"
npm run dev
```

Do not use this mode for canonical two-node evidence.

## Firmware

From an ESP-IDF shell:

```powershell
cd firmware\esp32-csi-node
idf.py build
idf.py -p COM5 flash monitor
idf.py -p COM6 flash monitor
```

Expected bindings for the live validation run:

- Node 1: `COM5`
- Node 2: `COM6`
- Both nodes stream ADR-018 CSI to host UDP `5005`.

## Live Validation Checklist

- `GET http://127.0.0.1:8789/api/status` returns `authority: true`.
- `GET http://127.0.0.1:8789/api/sensing/frame` returns `source: live` and `synthetic_enabled: false`.
- Node 1 streams independently.
- Node 2 streams independently.
- Both fresh nodes produce `fused_two_node` mode.
- Stopping one node returns to degraded single-node mode after the stale timeout.
- A spoofed `nodeId` from a different source is rejected and logged as `node_source_mismatch`.
- CSI Hz, midpoint localization, detection, respiration, and heart-rate metrics are recorded only after real hardware measurement.
