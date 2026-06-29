# Phantom Scan

Phantom Scan is a ground-based WiFi CSI sensing system built for a two-node ESP32-S3 setup plus a laptop host. The project combines ESP32 firmware, a live dashboard, Python ingest/replay/DSP runtime work, JSONL recording, and deterministic sensing pipelines.

This repository is being stabilized around these boundaries:

- exactly two expected ESP32-S3 CSI nodes
- ground-based sensing only
- no drone logic
- no GPS, IMU, MAVLink, or flight-control dependencies
- correctness, observability, replayability, and testing first

## What Exists Today

There are two important runtime tracks in this repo.

### 1. Current live dashboard path

This is the active UI/runtime path used for live dashboard work today.

- Express owns auth and audit
- Express + WebSocket drive the live dashboard
- UDP CSI packets are ingested by the Node host path
- React renders the live dashboard
- target rendering is gated by truthful `targetState`

### 2. Milestone 1 Python authority path

This is the target authoritative runtime shape for Milestone 1.

- `phantom.protocol`
- `phantom.ingest`
- `phantom.recording`
- `phantom.dsp`
- `phantom.runtime`
- `phantom.api`

The Python path is the intended authority for ingest, recording, replay, DSP, and runtime API, but the current Node live path is still the temporary truth source for dashboard/live bug fixing until the migration is complete.

## System Design

Phantom Scan is organized around five layers.

### Layer A: Firmware capture and transport

Location:

- `firmware/esp32-csi-node/`

Responsibilities:

- capture CSI on ESP32-S3
- queue CSI data outside the callback hot path
- stamp frames with device time
- attach `node_id` and sequence numbers
- send CSI frames and heartbeat/status packets over UDP

Important implementation files:

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
- validate packet structure and schema version
- preserve device timestamp and host receive timestamp
- track packet loss and out-of-order frames
- buffer by node
- expose degraded vs fused runtime state
- write and replay JSONL sessions

### Layer C: Deterministic DSP

Current and transitional DSP logic exists across:

- `phantom/dsp.py`
- `scripts/csi_filter_pipeline.py`

Expected deterministic stages:

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

Status:

- optional only
- not authoritative for Milestone 1
- system must continue in DSP-only mode when model files are missing or incompatible

### Layer E: API / UI / monitoring

Current dashboard/API path:

- `server/`
- `client/`

Responsibilities:

- operator login
- audit logging
- live status and health
- history and report views
- live dashboard rendering

## Architecture Summary

High-level live flow:

1. ESP32-S3 nodes capture CSI and emit UDP packets.
2. Host UDP ingest receives CSI and heartbeat frames.
3. Runtime normalizes timestamps, packet metadata, and node state.
4. DSP computes per-node and fused metrics.
5. WebSocket publishes live state to the React dashboard.
6. JSONL recording preserves the same session stream for replay.

High-level replay flow:

1. JSONL session is loaded.
2. The same parser/runtime semantics are applied.
3. Derived outputs are recomputed through the same logic.
4. Replay publishes dashboard-compatible state.

## Repository Structure

Top-level structure:

```text
phantom scan/
├── client/                      React dashboard
├── server/                      Express app, auth, audit, UDP bridge, WS
├── phantom/                     Python runtime package
├── firmware/esp32-csi-node/     ESP32-S3 firmware project
├── scripts/                     Provisioning, replay, capture, utilities
├── shared/                      Shared TypeScript schemas
├── tests/                       Python protocol/runtime tests
├── docs/                        ADRs and supporting docs
├── data/                        operator seed, sessions, runtime data
├── recordings/                  capture artifacts
├── BOOTSTRAP.md                 quick command reference
├── AUDIT.md                     repo disposition
├── SETUP_AUDIT.md               setup/dependency audit
├── MILESTONE1_FIX_PLAN.md       stabilization plan
├── TARGET_RENDER_AUDIT.md       target-state render audit
├── TARGET_TEST_PLAN.md          target regression plan
└── TARGET_VERIFICATION_REPORT.md verification notes
```

### `client/`

Important areas:

- `client/src/pages/dashboard.tsx`
- `client/src/pages/login.tsx`
- `client/src/pages/activity.tsx`
- `client/src/components/dashboard/`
- `client/src/hooks/use-websocket.ts`
- `client/src/hooks/use-auth.tsx`

Purpose:

- operator-facing dashboard
- auth-driven route protection
- live target and metric rendering
- report/history/activity surfaces

### `server/`

Important areas:

- `server/index.ts`
- `server/routes.ts`
- `server/lib/udp-server.ts`
- `server/lib/websocket.ts`
- `server/lib/target-state.ts`
- `server/auth/`
- `server/audit/`

Purpose:

- Express application
- operator auth and session handling
- audit logging
- UDP ingest for live dashboard path
- WebSocket live publishing

### `phantom/`

Files:

- `phantom/__init__.py`
- `phantom/protocol.py`
- `phantom/ingest.py`
- `phantom/recording.py`
- `phantom/dsp.py`
- `phantom/runtime.py`
- `phantom/api.py`

Purpose:

- canonical Python milestone runtime package
- protocol and recording contracts
- replay and deterministic DSP baseline

### `firmware/esp32-csi-node/`

Important contents:

- `main/`
- `provision.py`
- `nvs_node1.csv`
- `nvs_node1.bin`
- `nvs_node2.csv`
- `nvs_node2.bin`
- `sdkconfig`
- `sdkconfig.defaults`

Important firmware source files:

- `main/main.c`
- `main/csi_collector.c`
- `main/stream_sender.c`
- `main/edge_processing.c`
- `main/nvs_config.c`

### `scripts/`

Important utilities include:

- `scripts/record-csi-udp.py`
- `scripts/replay_to_dashboard.py`
- `scripts/csi_capture.py`
- `scripts/csi_filter_pipeline.py`
- `scripts/generate-operator-seed.ts`
- `scripts/synth-csi-udp.py`
- `scripts/csi-udp-relay.py`

### `tests/`

Current Python test set includes:

- `tests/test_udp_ad018.py`
- `tests/test_phantom_runtime.py`
- `tests/test_csi_pipeline.py`
- `tests/test_esp_capture_e2e.py`
- `tests/test_reporting.py`
- `tests/test_occupancy.py`

Node-focused tests currently live under:

- `server/**/*.test.ts`

## Current Runtime Behavior

### Dashboard behavior

Current dashboard expectations:

- login required
- target rendering is state-driven
- no placeholder/demo target rendering in normal live mode
- degraded single-node mode remains visible
- fused outputs require both nodes
- stopping a scan does not auto-download a PDF
- reports/history remain explicit operator actions

### Target-state rules

The dashboard consumes a `targetState` contract with semantics like:

- `none`
- `stale`
- `idle`
- `moving`
- `degraded`

Critical rules:

- if `target_visible` is false, no target mesh should render
- if `position_confident` is false, no confidently placed human target should render
- degraded visible targets may still render as lower-confidence abstract markers

## Two-Node ESP32-S3 Baseline

Milestone 1 assumes exactly two nodes.

Expected node behavior:

- unique `node_id`
- per-frame sequence number
- device timestamp on outbound packets
- heartbeat/status packets
- queue and overflow counters
- reconnect behavior after WiFi loss

Expected host behavior:

- independent per-node state
- packet loss detection
- out-of-order detection
- degraded mode when one node is stale or missing
- fused outputs only when both nodes are valid and aligned

## Recording Format

Milestone 1 recording format is JSONL only.

Expected record types:

- `session_header`
- `csi_frame`
- `heartbeat`
- `derived_frame`
- `session_footer`

Required recording properties:

- device timestamp preserved when valid
- host receive timestamp preserved for audit/fallback
- schema versioning
- replayable through the same runtime semantics as live mode

## Setup

## 1. Node / dashboard setup

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

- Python 3.13 recommended in this repo state

Install environment and run tests/runtime as appropriate for your machine.

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
- serial access to the nodes

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

## 4. Node provisioning

Provisioning helper:

- `firmware/esp32-csi-node/provision.py`

Local NVS artifacts currently present:

- `nvs_node1.csv`
- `nvs_node1.bin`
- `nvs_node2.csv`
- `nvs_node2.bin`

If `idf.py fullclean` fails because `managed_components/` hashes changed:

- move intentional component changes into `components/`, or
- delete the affected managed component folders and let ESP-IDF restore them

## Run Guide

### Run the live dashboard path

```bash
npm run dev
```

Then:

1. open `http://localhost:5000`
2. log in with the local operator account
3. start the scan
4. ensure ESP32 nodes are sending UDP packets to the host

### Run the Python runtime directly

```bash
python -m phantom.runtime live
```

### Run replay

```bash
python -m phantom.runtime replay --input <session.jsonl>
```

## Current Local Login

Current local development seed:

- Username: `thaer`
- Password: `thaer`

This is a local dev convenience and not a production credential policy.

## Testing

### Node checks

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

Firmware commands are documented, but actual verification depends on ESP-IDF availability and attached hardware.

## Important Notes

- `dist/` and `node_modules/` are generated artifacts, not authoritative source/config
- the old dashboard diagnostic virtual terminal path has been removed
- report download is no longer automatically triggered on scan stop
- current live dashboard debugging still uses the Node path as the temporary live truth source
- the Python package remains the Milestone 1 authority target

## Useful Documents

- [BOOTSTRAP.md](./BOOTSTRAP.md)
- [SETUP_AUDIT.md](./SETUP_AUDIT.md)
- [AUDIT.md](./AUDIT.md)
- [MILESTONE1_FIX_PLAN.md](./MILESTONE1_FIX_PLAN.md)
- [TARGET_RENDER_AUDIT.md](./TARGET_RENDER_AUDIT.md)
- [TARGET_TEST_PLAN.md](./TARGET_TEST_PLAN.md)
- [TARGET_VERIFICATION_REPORT.md](./TARGET_VERIFICATION_REPORT.md)

## Verification Snapshot

Verified in local development during stabilization work:

- `npm run check`
- `npm run test:dashboard-auth`
- `npm run build`
- `python -m pytest`

Firmware build commands are documented here, but firmware verification depends on an ESP-IDF shell and hardware access.

## License

MIT
