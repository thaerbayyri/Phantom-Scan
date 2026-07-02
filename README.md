# Phantom Scan

<p align="center">
  <img src="client/public/wifi.png" alt="Phantom Scan dashboard and WiFi CSI sensing" width="100%">
</p>

## Through-Wall WiFi CSI Sensing for Two ESP32-S3 Nodes

**Phantom Scan** is a ground-based WiFi CSI sensing system built around:

- two ESP32-S3 CSI nodes
- a laptop host
- deterministic DSP
- JSONL recording and replay
- a live React dashboard
- a Python runtime path that is becoming the Milestone 1 authority

This repo is being stabilized for a **realistic two-node ESP32-S3 deployment**. It does **not** target drones, GPS, IMU, MAVLink, or flight-control systems.

[![Node.js 18+](https://img.shields.io/badge/node-18%2B-green.svg)](https://nodejs.org/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![ESP-IDF](https://img.shields.io/badge/firmware-ESP32--S3-orange.svg)](https://www.espressif.com/)
[![Recording](https://img.shields.io/badge/recording-JSONL-purple.svg)](#recording-and-replay)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

> | Focus | Current Direction |
> |------|-------------------|
> | **Hardware** | Exactly **2 ESP32-S3 nodes** |
> | **Live UI** | Express + WebSocket + React dashboard |
> | **Milestone-1 authority** | Python runtime package in `phantom/` |
> | **Recording** | **JSONL only** |
> | **Fallback behavior** | stay up with one node; fused outputs require both |
> | **Priority** | correctness, observability, replayability, testing |

---

## Current Runtime State

There are two runtime tracks in this repository.

### 1. Live dashboard path (authoritative for live mode)

The active live path is the Node/TS host, and it is the **sole owner of UDP :5005**:

- `server/lib/udp-server.ts` binds UDP :5005, parses ADR-018 CSI + heartbeat frames, and source-pins each node
- `server/lib/websocket.ts` runs the processing pipeline, **two-node balance fusion**, and WebSocket publishing
- Express handles auth and audit; React renders the operator UI
- accepted raw frames are forwarded to the optional AI sidecar on :5006

`server/lib/authority-follower.ts` is intentionally **inert** (compatibility stub); nothing reads the old Python authority API.

### 2. Python runtime path (replay/tooling; gated in dev)

The Python package (`phantom.protocol`, `phantom.ingest`, `phantom.recording`, `phantom.dsp`, `phantom.runtime`, `phantom.api`) remains the replay/recording/DSP toolkit and test target.

Its live mode also binds :5005, so `npm run dev` (`script/dev-full.cjs`) **does not start it by default** — set `PHANTOM_USE_AUTHORITY=1` only if you intentionally want the Python authority to own :5005 instead of the dashboard (never run both; the port clash silently starves the dashboard).

---

## System Design

Phantom Scan is organized around five layers.

### Layer A: Firmware capture and transport

Location:

- `firmware/esp32-csi-node/`

Responsibilities:

- capture CSI on ESP32-S3
- keep callback work minimal
- queue data off the callback path
- stamp CSI with device timestamps
- emit node ID, sequence number, heartbeat/status packets
- send UDP frames to the host
- **self-ping the gateway (ICMP @ ~50 Hz)** so the router's echo replies keep the
  CSI callback fed on quiet networks — without this the CSI engine starves
  (`yield=0pps`) and every downstream layer reads zero (`csi_collector.c`,
  `csi_start_self_ping`)

Important files:

- `firmware/esp32-csi-node/main/main.c`
- `firmware/esp32-csi-node/main/csi_collector.c`
- `firmware/esp32-csi-node/main/stream_sender.c`
- `firmware/esp32-csi-node/main/nvs_config.c`

### Layer B: Host ingest, parser, logger, replay

Current live path:

- `server/lib/udp-server.ts`
- `server/lib/websocket.ts`
- `shared/schema.ts`

Milestone 1 Python path:

- `phantom/protocol.py`
- `phantom/ingest.py`
- `phantom/recording.py`
- `phantom/runtime.py`

Responsibilities:

- receive UDP packets
- validate schema/version/packet shape
- preserve both device and host timestamps
- detect packet loss and out-of-order frames
- maintain per-node state
- write replayable JSONL sessions

### Layer C: Deterministic DSP

Relevant areas:

- `phantom/dsp.py`
- `scripts/csi_filter_pipeline.py`

Required deterministic stages:

- amplitude extraction
- phase unwrap
- static clutter suppression
- Hampel filter
- respiration-band filtering
- motion energy / variance detection
- cross-node correlation

### Layer D: Optional ML / inference

Relevant areas:

- `scripts/ai_inference.py`
- `ai model and densepose/`

Rules:

- optional only
- disabled/isolated by default in the milestone path
- system must continue in DSP-only mode when models are missing or incompatible
- model weights are **not committed**: `ai model and densepose/model` is a git
  submodule pointer plus a small stub; large weights belong in Git LFS or a
  release asset, never a normal commit

### Layer E: API / UI / monitoring

Relevant areas:

- `server/`
- `client/`

Responsibilities:

- operator login
- audit logging
- live dashboard rendering
- history/report/activity views
- dashboard state publishing

---

## Architecture Summary

### Live path

```text
ESP32-S3 node 1 ----\
                     \         UDP ingest       targetState / metrics
ESP32-S3 node 2 -------> Host runtime -------------------------------> React dashboard
                           |         \
                           |          \-> JSONL session recording
                           |
                           \-> deterministic DSP / degraded or fused outputs
```

### Replay path

```text
JSONL session -> parser -> runtime semantics -> deterministic DSP -> dashboard-compatible outputs
```

### Degraded mode rules

- system stays up when one node is missing
- per-node ingest and DSP continue
- fused outputs are withheld unless both nodes are valid and aligned
- dashboard must not invent active targets when truthful state is absent

---

## Repository Structure

Top-level structure:

```text
phantom scan/
├── client/                      React dashboard
├── server/                      Express app, auth, audit, UDP + WS live path
├── phantom/                     Python runtime package
├── firmware/esp32-csi-node/     ESP32-S3 firmware project
├── scripts/                     capture, replay, provisioning, utilities
├── shared/                      shared TypeScript schemas
├── tests/                       Python test suite
├── docs/                        ADRs and supporting docs
├── data/                        sessions, operator seed, runtime state
├── recordings/                  capture artifacts
├── BOOTSTRAP.md                 quick command reference
├── AUDIT.md                     repo disposition
├── SETUP_AUDIT.md               setup/dependency audit
├── MILESTONE1_FIX_PLAN.md       stabilization plan
├── TARGET_RENDER_AUDIT.md       target render audit
├── TARGET_TEST_PLAN.md          regression/test plan
└── TARGET_VERIFICATION_REPORT.md final verification notes
```

### Client

Important areas:

- `client/src/pages/dashboard.tsx`
- `client/src/pages/login.tsx`
- `client/src/pages/activity.tsx`
- `client/src/components/dashboard/`
- `client/src/hooks/use-websocket.ts`
- `client/src/hooks/use-auth.tsx`

Purpose:

- operator-facing dashboard
- target/metric rendering
- report/history/activity routes

### Server

Important areas:

- `server/index.ts`
- `server/routes.ts`
- `server/lib/udp-server.ts`
- `server/lib/websocket.ts`
- `server/lib/target-state.ts`
- `server/auth/`
- `server/audit/`

Purpose:

- Express host
- auth and audit authority
- temporary live truth source for dashboard runtime
- UDP ingest bridge
- WebSocket dashboard publishing

### Python runtime

Files:

- `phantom/__init__.py`
- `phantom/protocol.py`
- `phantom/ingest.py`
- `phantom/recording.py`
- `phantom/dsp.py`
- `phantom/runtime.py`
- `phantom/api.py`

Purpose:

- canonical Milestone 1 runtime shape
- ingest, replay, DSP, recording, API

### Firmware

Important contents:

- `firmware/esp32-csi-node/main/`
- `firmware/esp32-csi-node/provision.py`
- `firmware/esp32-csi-node/nvs_node1.csv`
- `firmware/esp32-csi-node/nvs_node1.bin`
- `firmware/esp32-csi-node/nvs_node2.csv`
- `firmware/esp32-csi-node/nvs_node2.bin`

### Tests

Important tests include:

- `tests/test_udp_ad018.py`
- `tests/test_phantom_runtime.py`
- `tests/test_csi_pipeline.py`
- `tests/test_esp_capture_e2e.py`
- `server/lib/udp-server.test.ts`
- `server/lib/target-state.test.ts`
- `server/lib/node-fusion.test.ts` (balance localization, empty-room gate, trends)
- `server/auth/service.test.ts`

Run the server suite with `npx tsx --test server/**/*.test.ts` (31 tests passing at
the time of writing).

---

## Two-Node ESP32-S3 Baseline

Milestone 1 assumes exactly two nodes.

Required behavior:

- unique `node_id`
- sequence number per frame
- device timestamp carried by firmware
- host receive timestamp preserved by host
- heartbeat/status packets
- packet loss detection
- out-of-order detection
- per-node buffers
- degraded mode with one node
- fused outputs only when both nodes are valid and aligned

---

## Two-Node Live Localization (RuView balance method)

When both nodes are live (`fused_two_node`), the dashboard places the target on the
line between the two boards using the cross-node motion ratio.

### Geometry

Node anchor positions are a single constant shared by server and client
(`NODE_ANCHORS` in `shared/schema.ts`):

```text
N1 = (-1.5, 0)      N2 = (+1.5, 0)      separation = 3 m, origin at the midpoint
```

### Fusion (server/lib/node-fusion.ts)

- per node: a 3-second **time-based** window of **per-subcarrier amplitude frames**
  (≤64 subcarriers per packet, as in RuView's bridge). Motion energy is the temporal
  std of **each subcarrier** averaged across subcarriers → raw `absStd`, plus a
  saturated display `motion = min(1, absStd/mean·4)`. A best-subcarrier scalar
  fallback exists only for legacy senders — its subcarrier index jumps per frame,
  so its std is selection noise and cannot localize
- `balance = r2 / (r1 + r2)` using the **raw, unsaturated** `absStd` values
  (0 → at node 1, 0.5 → midpoint, 1 → at node 2)
- target position: `x = N1.x + (N2.x − N1.x)·balance` — it slides along the N1–N2 axis
- **empty-room gate**: no target is emitted (not a centered ghost) unless
  `max(motion1, motion2)` clears `PHANTOM_MOTION_THRESHOLD` (default 0.12 — a
  placeholder that must be calibrated from an empty-room baseline and validated
  against a fan/curtain negative control)

### Per-node distance and direction

Each broadcast `SensorNode` carries, while a live fused target exists:

- `distanceM` — along-axis distance from the target to that node
  (`sep·balance` for N1, `sep·(1−balance)` for N2)
- `trend` — `approaching` / `receding` / `stable`, from the sign of `d(balance)/dt`
  with a deadband (`PHANTOM_TREND_DEADBAND_MPS`, default 0.05 m/s, also a
  calibration placeholder)

The radar renders two labeled beacons (N1 cyan, N2 pink) with live
`N1 · 1.2 m ▼ approaching`-style labels, the N1–N2 axis line, connector lines from
the target to each node, and a travel arrow pointing toward the node being approached.

### Honest limits (by design)

- **1-D only:** two nodes cannot resolve a true (x, z). The position is along the
  N1–N2 line; a person standing off-axis reads as a wrong on-line distance.
- "Moving away from *both* nodes" (perpendicular escape) is not representable
  without per-node ranging (future work: preserve per-node subcarriers and use
  two-circle intersection, which adds a front/back mirror ambiguity).
- `trend` reflects smoothed balance movement; a still person may read `stable`.

---

## Recording and Replay

Milestone 1 recording format is **JSONL only**.

Expected record types:

- `session_header`
- `csi_frame`
- `heartbeat`
- `derived_frame`
- `session_footer`

Recording expectations:

- preserve authoritative device timestamp when valid
- always preserve host receive timestamp for audit/fallback
- replay through the same parser/runtime semantics used in live mode

---

## Dashboard Behavior

Current dashboard expectations:

- login required
- no placeholder live targets in the default runtime
- target rendering must follow truthful `targetState`
- single-node live mode is degraded, not fake fused localization
- stopping a scan must not auto-download a PDF
- reports/history remain explicit operator actions

Important target-state rules:

- if `target_visible` is false, no target mesh renders
- if `position_confident` is false, no confidently placed human target renders
- degraded visible targets may still render as abstract markers

Radar scene (`client/src/components/dashboard/RadialScene.tsx`):

- renders **both** node beacons at their `NODE_ANCHORS` positions (N1 cyan, N2 pink)
  with live distance + approaching/receding labels, plus the N1–N2 axis line
- in fused mode the target slides along the axis and shows connector lines to each node
- falls back to a single origin beacon when no node data has arrived yet

---

## Setup

## 1. Node dashboard setup

Requirements:

- Node.js 18+
- npm

Install:

```bash
npm install
```

Useful commands:

```bash
npm run check
npm run test:dashboard-auth
npm run build
npm run dev
npm run start
```

Open:

- `http://localhost:5000`

## 2. Python runtime setup

Requirements:

- Python 3.13 recommended in the current repo state

Main commands:

```bash
python -m pytest
python -m phantom.runtime live
python -m phantom.runtime replay --input <session.jsonl>
```

Local note:

- On this machine, an explicit Python 3.13 path was used because the repo-local `.venv` was not reliable.

## 3. Firmware setup

Requirements:

- ESP-IDF shell
- ESP32-S3 hardware
- serial access

Project directory:

- `firmware/esp32-csi-node`

Build:

```bash
idf.py build
```

Flash:

```bash
idf.py -p COM5 flash monitor
```

## 4. Provisioning notes

Provisioning helper:

- `firmware/esp32-csi-node/provision.py`

Current NVS artifacts:

- `nvs_node1.csv`
- `nvs_node1.bin`
- `nvs_node2.csv`
- `nvs_node2.bin`

Managed component cleanup note:

- if `idf.py fullclean` fails because `managed_components/` hashes changed, either move intentional edits into `components/` or delete the affected managed component folders and let ESP-IDF restore them

---

## Run Guide

### Run the current live dashboard path

```bash
npm run dev
```

Then:

1. open `http://localhost:5000`
2. log in with the operator account
3. start the scan
4. ensure the ESP32 nodes are sending UDP traffic to the host

### Run the Python milestone runtime

```bash
python -m phantom.runtime live
```

### Run replay

```bash
python -m phantom.runtime replay --input <session.jsonl>
```

---

## Default Local Login

Current local development seed:

- Username: `thaer`
- Password: `thaer`

This is a local development convenience, not a production credential policy.

---

## Testing

### Node / dashboard checks

```bash
npm run check
npm run test:dashboard-auth
npm run build
```

### Python checks

```bash
python -m pytest
```

### Firmware

Firmware commands are documented here, but actual verification depends on ESP-IDF availability and attached hardware.

---

## Important Notes

- `dist/` and `node_modules/` are generated artifacts, not authoritative source/config
- the old dashboard diagnostic virtual terminal path has been removed
- report download is no longer automatically triggered on scan stop
- the Node/TS host is the authoritative live path and sole owner of UDP :5005
- the Python package is the replay/recording/DSP toolkit; its live authority mode is
  gated behind `PHANTOM_USE_AUTHORITY=1` and must not run alongside the dashboard

---

## Useful Documents

- [BOOTSTRAP.md](./BOOTSTRAP.md)
- [SETUP_AUDIT.md](./SETUP_AUDIT.md)
- [AUDIT.md](./AUDIT.md)
- [MILESTONE1_FIX_PLAN.md](./MILESTONE1_FIX_PLAN.md)
- [TARGET_RENDER_AUDIT.md](./TARGET_RENDER_AUDIT.md)
- [TARGET_TEST_PLAN.md](./TARGET_TEST_PLAN.md)
- [TARGET_VERIFICATION_REPORT.md](./TARGET_VERIFICATION_REPORT.md)

---

## Verification Snapshot

Verified in local development during stabilization work:

- `npm run check`
- `npm run test:dashboard-auth`
- `npm run build`
- `python -m pytest`

Firmware build commands are documented here, but firmware verification depends on ESP-IDF shell access and hardware.

---

## License

MIT
