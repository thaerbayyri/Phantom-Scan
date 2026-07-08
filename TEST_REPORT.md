> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Test Report

Generated: 2026-07-01T04:01:07+03:00

This report covers the current `main` checkout after the authority-owned live path changes and the staged run/test validation pass.

## Software Verification

| Check | Result | Observed output |
|---|---:|---|
| Full Python suite | PASS | `75 passed, 5 skipped, 6 warnings in 63.13s`. |
| Node dashboard/server tests | PASS | `19 pass, 0 fail`; includes ADR-018 parser, heartbeat exclusion, source-pinning, target-state, and auth tests. |
| TypeScript check | PASS | `npm run check` completed with `tsc` exit code 0. |
| Production build | PASS | `npm run build` completed; Vite reported the existing large chunk warning. |
| Replay CLI | PASS | Temporary JSONL replay file ran through `python -m phantom.runtime replay --input ...` with exit code 0. |

## Stage A - Software-only Gate

| A# | Check | Result | Evidence |
|---|---|---:|---|
| A1 | Deterministic replay | PASS | Public replay CLI exited 0 against a generated JSONL session in the user temp directory. |
| A2 | Protocol parity | PASS | Python and Node tests parse the committed 32-byte ADR-018 fixture field-by-field. |
| A3 | Heartbeat exclusion | PASS | Python parses heartbeat as `HeartbeatV1`; Node excludes heartbeat fixtures from CSI conversion. |
| A4 | Source-pin + log | PASS | Python rejects spoofed source; Node logs `security_event` / `node_source_mismatch`. |
| A5 | Fusion midpoint | PASS | Synthetic equal-balance test returns `x_m = 2.5` and `dimensionality = 1D-on-axis`. |
| A6 | Firewall F1 | PASS | Perturbed AI/advisory outputs do not change deterministic `is_human`; AI sidecar emits `label = "unknown"` / advisory metadata. |
| A7 | Synthetic lockout | PASS | Canonical dry run reported `synthetic_enabled:false`, `source:"live"`, and `derived:null` with no input. |
| A8 | Scope guard | PASS | Active runtime files checked by tests do not import MAVLink/UAV/drone/GPS/IMU/PSC modules. |

Stage A gate result: PASS.

## AI Probe

Result: advisory AI available, deterministic authority preserved.

Observed `probe_ai_stack()` result:

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

F1 interpretation: AI can provide advisory confidence/metadata only. `phantom.dsp` remains the authority for the human verdict.

## Pre-flight / Authority Contract

| Check | Result | Evidence |
|---|---:|---|
| Venv Python | PASS | `.venv\Scripts\python.exe --version` -> `Python 3.13.9`. |
| Bare Python | FAIL | `python --version` hit the Windows Store alias and failed; use `.venv\Scripts\python.exe` or the explicit Python 3.13 path. |
| Live flags | PASS | `--api-host`, `--api-port`, `--forward-ai-host`, `--forward-ai-port`, `--synthetic`, and `--no-synthetic` are present. |
| `/api/status` | PASS | Returned `authority:true`, `source:"live"`, `synthetic_enabled:false`, node freshness, AI status, and source-pinning fields. |
| `/api/sensing/frame` | PASS | Returned `authority:true`, `node_mode:"single_node"`, `source:"live"`, `synthetic_enabled:false`, empty source pinning, AI status, and `derived:null`. |

## Stage B - Single-node Live Gate

| B# | Check | Result | Evidence |
|---|---|---:|---|
| B1 | Node 1 appears in source pinning | [TO BE MEASURED] | COM5 is visible, but no packet arrived on UDP `5005`. |
| B2 | Live, not synthetic | PASS | Authority dry run reported `source:"live"` and `synthetic_enabled:false`. |
| B3 | CSI Hz over 60 seconds | [TO BE MEASURED] | No live CSI packets arrived, so Hz cannot be computed. |
| B4 | No-synthetic under drop | PASS | With no input, `derived:null`; no target was generated. |
| B5 | Deterministic gate sanity | [TO BE MEASURED] | Requires live node stream and operator-controlled present/empty trials. |

Stage B gate result: BLOCKED by missing live packet stream and unavailable ESP-IDF tooling.

## Stage C - Dual-node Live Gate

| C# | Check | Result | Evidence |
|---|---|---:|---|
| C1 | Both nodes fresh | [TO BE MEASURED] | Requires live packets from node 1 and node 2. |
| C2 | Independent streams | [TO BE MEASURED] | COM5 and COM6 are visible, but no live source-pinned streams were observed. |
| C3 | Degraded transition | PASS (software) / [TO BE MEASURED] (live) | Runtime tests cover stale/recovered transitions; live hardware transition remains unmeasured. |
| C4 | Live spoof rejection | PASS (software) / [TO BE MEASURED] (live) | Source-pinning tests pass; live foreign-source injection was not run. |
| C5 | Dual-node balance sanity | [TO BE MEASURED] | Requires two fresh live nodes on the 5 m baseline. |
| C6 | AoA labelling | [TO BE MEASURED] | Requires live UI target presentation; no target was present. |

Stage C gate result: BLOCKED because Stage B did not produce a live node stream.

## Dashboard Follow-mode

| Check | Result | Evidence |
|---|---:|---|
| Default Node UDP behavior | PASS | `npm run dev` logged `authority-follow mode enabled; Node will not bind UDP 5005`. |
| Dashboard HTTP smoke | PASS | `GET http://127.0.0.1:5000` returned HTTP 200. |
| UDP 5005 ownership | PASS | `Get-NetUDPEndpoint -LocalPort 5005` produced no endpoint output during Node follow-mode smoke. |
| Production `npm start` on Windows | FAIL | Script uses Unix-style `NODE_ENV=production node dist/index.cjs`, which is not valid in Windows `cmd`. |

## Live Hardware Validation

| Item | Result | Observed output |
|---|---:|---|
| Serial ports visible | PARTIAL | `.NET SerialPort.GetPortNames()` returned `COM4`, `COM3`, `COM6`, `COM5`; WMI enumeration was access-denied. |
| Firmware toolchain | BLOCKED | `idf.py --version` failed because `idf.py` is not recognized in this shell. |
| Python authority bind/API | PASS | Authority served `/api/status` and `/api/sensing/frame` on `8789` during the dry run. |
| Node dashboard follow mode | PASS | Node dashboard did not bind UDP `5005` in canonical mode. |
| Node 1 live stream | [TO BE MEASURED] | Requires firmware/tooling or active node stream. |
| Node 2 live stream | [TO BE MEASURED] | Requires firmware/tooling or active node stream. |
| Fused two-node live target | [TO BE MEASURED] | Requires actual CSI packets from both nodes. |
| CSI Hz over 60 seconds | [TO BE MEASURED] | No packets arrived during the canonical dry run. |
| Midpoint sanity check | [TO BE MEASURED] | Requires two active nodes on the 5 m test baseline. |
| UI live target presentation | [TO BE MEASURED] | Requires live packets; synthetic fallback is not valid evidence. |

## Honesty Statement

Measured in this pass: software tests, replay CLI, parser parity, source-pinning parity, authority API availability, AI advisory readiness, synthetic lockout/no-target behavior, dashboard follow-mode behavior, COM port names, and missing ESP-IDF tooling.

Not measured: live detection rate, false-positive rate, respiration accuracy, heart-rate accuracy, live CSI Hz, live midpoint localization, live spoof injection, and live UI target presentation.

No synthetic, replay-only, no-packet, or single-node result was promoted to a live detection metric.
