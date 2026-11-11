> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Run Log

Generated: 2026-07-01T04:01:07+03:00

## Scope

This log records the staged run/test validation requested for the current `main` checkout. It records measured facts only. Live target-detection metrics remain `[TO BE MEASURED]` because no real CSI packets arrived during the canonical authority dry run and firmware flashing/tooling was blocked in this shell.

## Pre-flight

| Check | Result | Evidence |
|---|---:|---|
| `.venv` exists | PASS | `.venv\Scripts\Activate.ps1` exists. |
| Venv Python | PASS | `.venv\Scripts\python.exe --version` -> `Python 3.13.9`. |
| Explicit Python | PASS | `C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe --version` -> `Python 3.13.9`. |
| Bare `python` | FAIL | Resolves to `C:\Users\thaer\AppData\Local\Microsoft\WindowsApps\python.exe` and fails with `ResourceUnavailable`. Use the venv or explicit interpreter. |
| Live CLI flags | PASS | `python -m phantom.runtime live --help` exposes `--api-host`, `--api-port`, `--forward-ai-host`, `--forward-ai-port`, `--synthetic`, and `--no-synthetic`. |
| TCP ports before run | PASS | No listener found on `5000` or `8789` during pre-flight check. |
| UDP ports before run | PASS | No endpoint output for `5005` or `5006` during pre-flight check. |
| Serial ports | PARTIAL | `.NET SerialPort.GetPortNames()` returned `COM4`, `COM3`, `COM6`, `COM5`; WMI `Win32_SerialPort` enumeration failed with `Access denied`. |
| ESP-IDF | BLOCKED | `idf.py --version` failed: `idf.py` is not recognized in this shell. |

## AI Probe

Command:

```powershell
.\.venv\Scripts\python.exe -c "import json; from phantom.ai_status import probe_ai_stack; print(json.dumps(probe_ai_stack().to_dict(), indent=2))"
```

Observed:

```json
{
  "mode": "advisory",
  "ready": true,
  "reason": "ok",
  "model_dir": "ai model and densepose\\model",
  "embedding_shape": [
    2,
    128
  ],
  "adapters": {
    "node_1": "active",
    "node_2": "active"
  }
}
```

Interpretation: AI dependencies and the safetensors-backed embedding path are available in the current venv. Under F1, this is advisory only; `phantom.dsp` remains sovereign for the human verdict.

## Software Gate

| Command | Result | Output |
|---|---:|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | PASS | `75 passed, 5 skipped, 6 warnings in 63.13s`. |
| `npm run check` | PASS | `tsc` exited 0. |
| `npm run test:dashboard-auth` | PASS | `19 pass, 0 fail`. |
| `npm run build` | PASS | Built client and server; Vite emitted the existing large chunk warning. |

Additional replay CLI check:

1. Initial attempt to create a replay fixture under `C:\tmp\phantom-replay-check` failed with `PermissionError: [WinError 5] Access is denied`.
2. Fixture generation succeeded under `C:\Users\thaer\AppData\Local\Temp\phantom-replay-check`.
3. `.\.venv\Scripts\python.exe -m phantom.runtime replay --input C:\Users\thaer\AppData\Local\Temp\phantom-replay-check\4604549b20e84395b399269c10c62f7a.jsonl` exited 0.

## Canonical Authority Dry Run

Command:

```powershell
.\.venv\Scripts\python.exe -m phantom.runtime live --host 0.0.0.0 --port 5005 --api-host 127.0.0.1 --api-port 8789 --forward-ai-host 127.0.0.1 --forward-ai-port 5006 --no-synthetic --duration 20
```

The command exited 0. No CSI or heartbeat packet was observed during the run.

`GET http://127.0.0.1:8789/api/status` during the run:

```json
{
  "status": "ok",
  "runtime_mode": "live_degraded_single_node",
  "started": false,
  "authority": true,
  "source": "live",
  "synthetic_enabled": false,
  "source_pinning": {},
  "source_pinning_rejections": 0,
  "nodes": {
    "1": {
      "stale": true,
      "last_csi_rx_ns": null,
      "last_heartbeat_rx_ns": null,
      "buffered_csi_frames": 0,
      "buffered_heartbeats": 0
    },
    "2": {
      "stale": true,
      "last_csi_rx_ns": null,
      "last_heartbeat_rx_ns": null,
      "buffered_csi_frames": 0,
      "buffered_heartbeats": 0
    }
  },
  "last_derived": null
}
```

`GET http://127.0.0.1:8789/api/sensing/frame` during the run:

```json
{
  "status": "ok",
  "runtime_mode": "live_degraded_single_node",
  "authority": true,
  "source": "live",
  "synthetic_enabled": false,
  "node_mode": "single_node",
  "source_pinning": {},
  "source_pinning_rejections": 0,
  "ml_status": {
    "mode": "advisory",
    "ready": true,
    "reason": "ok",
    "embedding_shape": [
      2,
      128
    ],
    "adapters": {
      "node_1": "active",
      "node_2": "active"
    }
  },
  "derived": null
}
```

## Dashboard Follow-mode Smoke

| Check | Result | Evidence |
|---|---:|---|
| Production start script on Windows | FAIL | `npm start` fails because `NODE_ENV=production` is not valid Windows shell syntax. |
| Dev dashboard start | PASS | `npm run dev` started, initialized WebSocket server, and served HTTP 200 on `http://127.0.0.1:5000`. |
| Canonical Node UDP behavior | PASS | Startup logged `authority-follow mode enabled; Node will not bind UDP 5005`; `Get-NetUDPEndpoint -LocalPort 5005` produced no endpoint output. |
| Python authority absent during dashboard-only smoke | EXPECTED | Dashboard logged `Waiting for Python authority at http://127.0.0.1:8789: TypeError: fetch failed`. |

The dashboard process spawned during this smoke was stopped after validation.

## Hardware Gate Status

| Stage | Result | Evidence |
|---|---:|---|
| Stage B single-node bring-up | BLOCKED | COM5 is visible, but ESP-IDF is unavailable and no packets arrived on canonical UDP `5005`. |
| Stage C dual-node bring-up | BLOCKED | COM6 is visible, but dual-node firmware provisioning/streaming could not be validated without ESP-IDF or live packets. |
| Stage D detection characterization | [TO BE MEASURED] | Requires Stage C green plus repeated live trials. |

## Honesty Statement

Measured: Python/Node software gates, replay CLI, authority API contract, no-synthetic dry-run state, AI advisory readiness, COM port names, missing ESP-IDF command, and dashboard authority-follow behavior.

Not measured: single-node live CSI Hz, two-node fused mode, live midpoint localization, live UI target presentation, through-wall detection rate, false-positive rate, respiration MAE, and heart-rate MAE.

No synthetic, replay-only, no-packet, or single-node result was promoted to a live detection metric.
