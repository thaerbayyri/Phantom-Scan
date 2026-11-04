<p align="center">
  <img src="client/public/wifi.png" alt="Phantom Scan dashboard rendering a live 4-node WiFi CSI scan" width="100%">
</p>

<h1 align="center">Phantom Scan</h1>
<p align="center"><strong>Through-wall human presence sensing from $7 ESP32-S3 radios — no cameras, no wearables.</strong></p>

<p align="center">
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-18%2B-green.svg" alt="Node.js 18+"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.13-blue.svg" alt="Python 3.13"></a>
  <a href="https://www.espressif.com/"><img src="https://img.shields.io/badge/firmware-ESP32--S3%20%2F%20ESP--IDF%20v5.2-orange.svg" alt="ESP-IDF v5.2 / ESP32-S3"></a>
  <a href="#recording--replay"><img src="https://img.shields.io/badge/recording-CSV%20%2B%20JSON%20index-purple.svg" alt="CSV recording + JSON session index"></a>
  <a href="#testing"><img src="https://img.shields.io/badge/tests-256%20TS%20%2B%2091%20Python-brightgreen.svg" alt="256 TypeScript + 91 Python tests"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

Phantom Scan turns Wi-Fi Channel State Information (CSI) from up to four ESP32-S3 nodes into a live radar-style view of a room: a moving-target position, distance and approach/recede trend for each node, and board-side vital signs (breathing, heart rate) — rendered in a React dashboard fed by an Express/WebSocket host in real time.

**This is not** a drone, GPS/IMU, or MAVLink flight-control project. It targets a fixed, ground-based, multi-node deployment, and it says so honestly where its physics run out (see [Honest Limitations](#honest-limitations)).

> | Focus | Current State |
> |---|---|
> | **Hardware** | 1–4 ESP32-S3 nodes; **primary live deployment is 4**, one per room corner |
> | **Fusion modes** | `single_node` (1 live) → `fused_two_node` (exactly 2, 1-D on-axis) → `fused_room` (3–4, 2-D centroid) |
> | **Live path** | Express + WebSocket + React, in one Node/TS process |
> | **Runtime authority** | `server/` (Node/TS) — see [ADR-051](docs/adr/ADR-051-runtime-authority.md) |
> | **Recording format** | Per-session CSV (frame-by-frame) + JSON session index (`data/sessions/_index.json`) |
> | **Position smoothing** | 2-D constant-velocity Kalman filter (`FusedPositionKalman`) on the fused track, both fusion modes |
> | **Degraded behavior** | stays up with any subset of nodes missing; fused output withheld until the mode's minimum node count is valid |
> | **Localization** | 1-D on-axis with exactly 2 nodes; perturbation-weighted 2-D centroid with 3–4 — never RF multilateration, no false precision claimed |
> | **Priority order** | correctness → observability → replayability → testing |
> | **Known open issue** | 4-node empty-room false-positive presence detection under active investigation — see [Honest Limitations](#honest-limitations) |

---

## Table of Contents

- [Quick Start](#quick-start)
- [Runtime Authority](#runtime-authority)
- [System Design](#system-design)
- [Phantom Balance Fusion](#phantom-balance-fusion)
- [Fused Position Kalman Filter](#fused-position-kalman-filter)
- [Wire Protocol](#wire-protocol)
- [Environment Variables](#environment-variables)
- [Setup](#setup)
- [Usage](#usage)
- [Testing](#testing)
- [Recording & Replay](#recording--replay)
- [Project Structure](#project-structure)
- [Documentation Index](#documentation-index)
- [Honest Limitations](#honest-limitations)
- [License](#license)

---

## Quick Start

Pick the path that matches what you're doing right now.

### 1. Full stack (dashboard + Python reference runtime side by side)

```bash
npm install
npm run dev
```

### 2. Dashboard only (Node/TS live path — this is what talks to real hardware)

```bash
npm install
npm run dev:dashboard
```

Open [http://localhost:5000](http://localhost:5000) and log in ([default local credentials](#usage)). Point each ESP32-S3 node's UDP stream at this host on port `5005`; the host auto-detects how many nodes are live (1–4) and picks the fusion mode accordingly — no config flag to flip between "2-node" and "4-node" builds.

### 3. Firmware — build, flash, provision

```bash
# Build — native idf.py (with export.ps1 activated) or Docker, either works;
# Docker is the more reproducible option, especially on Windows.
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd)/firmware/esp32-csi-node:/project" -w /project \
  espressif/idf:v5.2 bash -c \
  "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"

# Flash each node individually (repeat per COM port — one flash per physical node)
python -m esptool --chip esp32s3 --port COM6 --baud 460800 \
  write_flash --flash_mode dio --flash_size 8MB \
  0x0 firmware/esp32-csi-node/build/bootloader/bootloader.bin \
  0x8000 firmware/esp32-csi-node/build/partition_table/partition-table.bin \
  0x10000 firmware/esp32-csi-node/build/esp32-csi-node.bin

# Provision Wi-Fi + a unique node ID per board, without reflashing app code
python esp-flash.py --port COM7 --ssid "YourSSID" --password "YourPass" --target-ip 192.168.1.155
```

All nodes join the same Wi-Fi AP and self-ping their gateway at ~50 Hz to keep the CSI engine fed (this is a per-node RF stimulus trick, **not** inter-node coordination — nodes never talk to each other). Every node needs a distinct `node_id` (1–4) provisioned via `esp-flash.py`; the host maps that ID straight to a fixed room-corner anchor (see [Phantom Balance Fusion](#phantom-balance-fusion)).

See [firmware/esp32-csi-node/README.md](firmware/esp32-csi-node/README.md) for the full firmware architecture and Windows/Ubuntu setup notes in [docs/WINDOWS_ESP32_SETUP.md](docs/WINDOWS_ESP32_SETUP.md) / [docs/UBUNTU_ESP32_SETUP.md](docs/UBUNTU_ESP32_SETUP.md).

### 4. Python reference path (replay, offline DSP, tests only — not live)

```bash
python -m pytest tests/ -q
python -m phantom.runtime replay --input <session.jsonl>
```

---

## Runtime Authority

There are two runtime tracks in this repository, and only one of them is allowed to be live at a time.

> **The Node/TS server (`server/`) is the sole live authority.** It is the only process that may bind UDP `:5005`, and the only publisher of derived frames (WebSocket `/ws` on `:5000`). See [ADR-051](docs/adr/ADR-051-runtime-authority.md).

**Live dashboard path (`server/`)**
- `server/lib/udp-server.ts` binds UDP `:5005`, parses CSI + heartbeat + feature-state frames, and source-pins each of up to 4 nodes.
- `server/lib/node-fusion.ts` computes the fused position — `fuseTwoNodeTarget` (2 nodes, 1-D) or `fuseNodeTargets` (3–4 nodes, 2-D centroid) — and `server/lib/fused-position-kalman.ts` smooths it into a stable track.
- `server/lib/websocket.ts` runs the DSP/fusion pipeline and publishes `radialTarget`, `targetState`, node beacon markers, and firmware metrics over `/ws`.
- Firmware DSP metrics (presence, motion, respiration, heart rate at 1 Hz/node) render in the **Board DSP** card, kept strictly separate from host-side fusion for cross-checking.
- Express handles auth/audit; accepted raw frames are optionally forwarded to an AI sidecar on `:5006`.

**Python reference path (`phantom/`)**
- `phantom.protocol`, `phantom.ingest`, `phantom.recording`, `phantom.dsp`, `phantom.runtime`, `phantom.api` remain the replay/recording/reference-DSP toolkit and the target for the Python test suite.
- Its live mode is retired: `python -m phantom.runtime live` refuses to bind by default, and will only start under the explicit compatibility override `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1` — which must never be set while the dashboard is running (both would fight over UDP `:5005`).

| Port | Owner | Purpose |
|---|---|---|
| `5000` (falls back to `5001`–`5019` if busy) | `server/` | Dashboard UI + API |
| `5005` | `server/` (sole owner) | ESP32 → host CSI/vitals/heartbeat ingest (UDP), all nodes share this one port |
| `5006` | `server/` → AI sidecar | Forwarded raw frames for optional ML inference |

---

## System Design

Phantom Scan is organized in five layers, firmware to browser:

```text
ESP32-S3 node 1 ----\
ESP32-S3 node 2 -----\        UDP :5005 ingest        targetState / metrics
ESP32-S3 node 3 -------> Node/TS host runtime ------------------------------> React dashboard
ESP32-S3 node 4 -----/      |          \
  (1-4 live; mode      |           \-> per-session CSV + JSON index (data/sessions/)
   auto-selected)      |
                        \-> deterministic DSP -> node-fusion -> Kalman smoothing -> WebSocket /ws
```

**Replay path:**
```text
Recorded session (CSV / JSONL) -> parser -> runtime semantics -> deterministic DSP -> dashboard-compatible outputs
```

| Layer | Responsibility | Key files |
|---|---|---|
| **A — Firmware capture** | Capture CSI on-device, timestamp, self-ping the gateway (ICMP @ ~50 Hz) so the CSI engine doesn't starve on a quiet network, stream UDP frames | `firmware/esp32-csi-node/main/{main.c, csi_collector.c, stream_sender.c, nvs_config.c}` |
| **B — Host ingest** | Receive UDP, validate schema/version, preserve device + host timestamps, detect loss/reorder, maintain per-node state (up to 4), write session CSV + index | `server/lib/{udp-server.ts, websocket.ts, session-store.ts}`, `shared/schema.ts`; Python: `phantom/{protocol,ingest,recording,runtime}.py` |
| **C — Deterministic DSP** | Amplitude extraction, phase unwrap, static-clutter suppression, Hampel filter, respiration-band filtering, motion energy, cross-node correlation | `phantom/dsp.py`, `scripts/csi_filter_pipeline.py` |
| **D — Node fusion + smoothing** | Per-node motion energy → 1-D or 2-D fused position (`node-fusion.ts`) → 2-D Kalman smoothing of the fused track (`fused-position-kalman.ts`) | `server/lib/{node-fusion.ts, fused-position-kalman.ts}` |
| **E — Optional ML** | Disabled/isolated by default; system must keep running in DSP-only mode if models are absent | `scripts/ai_inference.py`, `ai model and densepose/` (model weights are a git submodule pointer, never committed directly) |
| **F — API / UI** | Operator login, audit logging, live dashboard rendering, history/report/activity views | `server/`, `client/` |

**Degraded-mode rules:** the system stays up with any subset of nodes missing; per-node ingest and DSP keep running regardless of how many other nodes are live; fused output is withheld unless the active mode's minimum node count is met and time-aligned (2 for `fused_two_node`, 3+ for `fused_room`); the dashboard must never invent an active target when truthful state says there isn't one.

---

## Phantom Balance Fusion

Phantom Scan places the target using each node's **cross-node motion ratio** as a proximity proxy — a deliberately honest model, not fabricated RF ranging. The math scales from 2 to 4 nodes without changing that honesty contract.

### Geometry

Node anchors are a single shared constant (`NODE_ANCHORS` in `shared/schema.ts`) — one node per corner of a `ROOM_WIDTH_M` × `ROOM_DEPTH_M` (4 m × 6 m) rectangle, origin at the room center, listed in perimeter order 1→2→3→4→1 so the client can draw a clean room-boundary polygon:

```text
N1 = (-2, -3)   N2 = (+2, -3)   N3 = (+2, +3)   N4 = (-2, +3)
```

With exactly nodes 1+2 live, the target slides along the N1–N2 line (`NODE_SEPARATION_M` = 4 m, same axis the original 2-node rig used). With 3 or 4 nodes live, the target is a weighted centroid over all active anchors.

Coordinate conventions live in one place, `shared/bearing.ts` — never inline the trig elsewhere:
- **`theta`** — compass bearing, `atan2(x, z)`, 0° = north, clockwise-positive.
- **`angle`** — direction of travel, math convention, `atan2(vz, vx)`, 0° = east.

### How the fusion works (`server/lib/node-fusion.ts`)

1. Each node keeps a **`PHANTOM_MOTION_WINDOW_MS`** window (default **1500 ms**) of per-subcarrier amplitude frames (up to 64 subcarriers/packet). Motion energy is the temporal standard deviation of each subcarrier, averaged across subcarriers, giving a raw unsaturated perturbation `absStd` per node. The **display** `motion` value clamps that into 0–1 via `MOTION_SATURATION_SCALE` (default **4**): `motion = min(1.0, (absStd/mean) * 4)`.
2. **2-node mode** (`fuseTwoNodeTarget`) — `balance = r2^p / (r1^p + r2^p)` over the raw perturbations (`p` = `PHANTOM_BALANCE_CONTRAST`, default **2.0**, widens balance toward whichever node sees clearly more perturbation). Target position: `x = N1.x + (N2.x − N1.x) · (biased balance)`, sliding along the N1–N2 axis; the on-screen `x` further applies a nearest-node display bias, `PHANTOM_BALANCE_BIAS_EXPONENT` (default **0.72**). The plain, undecorated `balanceLinear = r2/(r1+r2)` is the authoritative cross-check an analytics consumer should read — it never drives what's drawn. See [ADR-054](docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md).
3. **3–4-node mode** (`fuseNodeTargets`) — the direct N-node generalization: `pos = Σ(anchor_i · r_i^p) / Σ(r_i^p)`, a contrast-weighted centroid across every active anchor. Same honesty contract as the 2-node case — this is a perturbation-weighted centroid, not RF multilateration; there is no `biasBalanceTowardNearestNode` display squeeze here, since that step only makes sense projected onto a single axis (the contrast exponent alone does the equivalent "pull toward the dominant node" work in 2-D).
4. **Empty-room gate (THE detector, identical in both modes):** no target is emitted (never a centered ghost) unless `max(motion_1..N) >= PHANTOM_MOTION_THRESHOLD` (default **0.6**, see the calibration caveat below) **and** the sum of raw perturbations exceeds a numerical floor. A deterministic micro-Doppler classifier (`server/lib/signal-processing.ts`) can additionally *suppress* — never assert — a presence claim when it confidently labels the signal mechanical (fan/HVAC), mirroring the firmware's own `edge_evaluate_human_presence` pattern.

Each broadcast node also carries `distanceM` (on-axis distance in 2-node mode, true straight-line distance to the anchor in 3–4-node mode) and `trend` (`approaching` / `receding` / `stable`, from the sign of `d(balance)/dt` with a `PHANTOM_TREND_DEADBAND_MPS` deadband, default 0.05 m/s). The radar renders each active node's beacon, connector lines to the target, and a travel arrow toward the node being approached.

> **Calibration caveat (active investigation):** `PHANTOM_MOTION_THRESHOLD` (0.6) was set on 2026-07-20 from a single 60 s empty-room recording on a 2-node rig (296 samples: mean 0.49, σ 0.027, max 0.58) and is **provisional**. Repeated real 4-node empty-room recordings in September 2026 show persistent false-positive presence detection, with the `motion_nX` metric pinned at its 1.0 saturation ceiling on roughly half of all ticks — meaning the recorded data is **censored** (clamped) and cannot honestly support re-deriving the threshold as-is. `raw_perturbation_n1..n4` (see [Recording & Replay](#recording--replay)) now exports the unclamped ratio specifically to unblock this diagnosis. Do not change `MOTION_SATURATION_SCALE` or `DEFAULT_MOTION_THRESHOLD` independently — the code comment on `MOTION_SATURATION_SCALE` is explicit that they must be re-derived together, from real uncensored data, never guessed. A mean + k·σ rule over a window that short is not supported: recordings of the same empty room separate from each other (symmetric AUC upper bounds 0.68–0.91 against a 0.65 limit, `reports/fix-2026-11/13-PS-FIX-11.md`). Real recalibration needs a live empty-room soak of at least 60 minutes with an entry log, plus a negative control with a fan or vibration source in the same link state, evaluated with `scripts/calibrate-threshold.ts --evaluate`; the resulting false-alarm and detection rates are `[TO BE MEASURED]`.

---

## Fused Position Kalman Filter

Both fusion modes' raw output is recomputed from scratch every ~50 ms tick with zero history — that alone produces a visibly jittery on-screen marker. `server/lib/fused-position-kalman.ts` (`FusedPositionKalman`) smooths it:

- **Natively 2-D.** Two independent 1-D constant-velocity Kalman filters (state `[pos, vel]` per axis, scalar 2×2 P/Q/R math). There is no fake `y=0` measurement anywhere — unlike the repo's other Kalman filter (`tracking.ts`'s 6-state 3-D `KalmanFilter`, used only by the separate single-node DBSCAN spatial path and left untouched by this one).
- **`predict(nowMs)`** clamps `dt` between `MIN_DT_S` (0.001s) and `MAX_DT_S` (0.3s) — the ceiling stops one large stale-drop gap from producing one outsized position jump; 0.3s sits below the real 0.4–0.83s max inter-tick gaps observed in live 4-node sessions, and well under the pipeline's separate 1500ms full-staleness reset.
- **`update([x, z])`** gates the innovation against `GATE_SIGMA_MULT` (3.0) sigmas per axis — a single wild-tick outlier is skipped rather than yanking the marker, without ever loosening R for every other tick.
- **Q/R are derived from real captured 4-node `fused_room` session data**, not placeholders: `R_X = 0.0044 m²`, `R_Z = 0.0011 m²` (from the best available near-still segment), `Q_POS_X`/`Q_POS_Z` at ~2.5× the respective R, `Q_VEL = 0.5 (m/s²)²` (pedestrian acceleration process noise). See the class docstring for the exact source sessions and the honest caveat that these are initial, data-grounded starting values pending a dedicated stationary-target soak — same confidence level as this project's other session-derived constants.
- Wired into **both** fusion branches in `websocket.ts`: `predict()`/`update()` run every tick before velocity/trend math, and the filtered `x`/`z` — not the raw fused position — feed the broadcast `radialTarget`, `fusedSnapshot`, and `roomFusedSnapshot`. `clearFusedSnapshot()` resets the filter alongside the other fusion state so a node-mode flip (e.g. 2 nodes → 4 nodes mid-session) never leaks stale velocity/covariance into the new mode.

Validated in `server/lib/fused-position-kalman.test.ts` against real recorded `x_disp_m`/`z_disp_m` and real inter-tick timestamps (not synthetic data): filtering reduces mean tick-to-tick jitter on both axes, and the filtered track stays within ~0.002m median / ~0.02m p95 of the raw recorded track — proving the smoothing isn't laggy enough to misrepresent real motion.

---

## Wire Protocol

All packets travel over UDP to the host on `:5005`. A 4-byte little-endian magic number identifies the frame type. All nodes (1–4) share this one port; the host source-pins each by IP/node ID.

| Magic | Frame | Rate | Notes |
|---|---|---|---|
| `0xC5110001` | CSI frame | ~41-43 pps/node measured (50 Hz firmware send-rate cap, not a guaranteed rate — see `csi_collector.c` `CSI_MIN_SEND_INTERVAL_US`) | 32-byte header (ADR-018); legacy 20-byte header accepted only under `PHANTOM_ALLOW_LEGACY_CSI` |
| `0xC5110002` | Vitals | 1 Hz/node | Board-side presence/motion/vitals, shown alongside — never fused into — the host-DSP target math |
| `0xC5110004` | WASM module output | event-driven | Output from optional programmable sensing modules |
| `0xC5110006` | Feature-state | 1 Hz/node | Board-computed motion/presence/respiration/heart-rate metrics for the **Board DSP** card |
| `0xC51100A1` | Heartbeat | periodic | Per-node liveness signal |

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `NODE_ENV` | — | `development` / `production` |
| `PORT` / `HOST` | `5000` / all interfaces | Dashboard HTTP/WebSocket bind |
| `UDP_PORT` | `5005` | CSI ingest bind port (shared by all 1–4 nodes) |
| `PHANTOM_MOTION_WINDOW_MS` | `1500` | Fusion motion-energy time window |
| `PHANTOM_MOTION_THRESHOLD` | `0.6` | Empty-room detection gate — provisional: set from one 60 s empty recording on a 2-node rig; see the calibration caveat under [Phantom Balance Fusion](#phantom-balance-fusion) |
| `PHANTOM_BALANCE_CONTRAST` | `2.0` | Contrast exponent (both 2-node balance and N-node centroid weighting) |
| `PHANTOM_BALANCE_BIAS_EXPONENT` | `0.72` | Nearest-node display bias exponent (2-node mode only) |
| `PHANTOM_TREND_DEADBAND_MPS` | `0.05` | Approach/recede trend deadband |
| `PHANTOM_MECHANICAL_REJECT_MAX` | — | Max `humanProb` at which the micro-Doppler classifier may suppress a presence claim |
| `PHANTOM_STATIC_NODE_SOURCES` | — | JSON mapping to pin node IDs (1–4) to fixed source IPs |
| `PHANTOM_ROOM_GEOMETRY_ID` / `PHANTOM_WALL_CELL` / `PHANTOM_WALL_THICKNESS_M` | — | Room/wall geometry context for display |
| `PHANTOM_AUDIT_DIR` | — | Audit log output directory |
| `PHANTOM_FIRMWARE_BUILD_ID` / `PHANTOM_SELF_PING_STATUS` | — | Firmware build/status metadata surfaced in the UI |
| `PHANTOM_OPERATOR_SEED_PATH` | `data/operator.json` | Operator credential store |
| `PHANTOM_SESSION_SECRET` | — | Session signing secret |
| `PHANTOM_BOOTSTRAP_TOKEN` | — | Required for first-operator bootstrap from a non-loopback address |
| `PHANTOM_ALLOW_LEGACY_CSI` | unset (off) | Compatibility opt-in for legacy 20-byte CSI frames |
| `PHANTOM_ALLOW_RETIRED_LIVE_AUTH` | unset (off) | Required to start the retired Python live mode |
| `PHANTOM_AUTHORITY_HOST` / `PHANTOM_AUTHORITY_PORT` / `PHANTOM_AUTHORITY_URL` | `127.0.0.1` / `8789` | Address of the Python reference runtime when run alongside `npm run dev` |
| `DATABASE_URL` | — | Postgres connection string (`drizzle-kit push`, session store) |
| `PHANTOM_PYTHON` / `PYTHON` | — | Explicit Python interpreter path override |

---

## Setup

### 1. Node dashboard

Requirements: Node.js 18+, npm.

```bash
npm install
npm run check              # type-check
npm run dev:dashboard      # dashboard only
npm run dev                # dashboard + Python reference runtime together
npm run build && npm run start   # production
```

### 2. Python reference runtime

Requirements: Python 3.13.

```bash
python -m pytest tests/ -q
python -m phantom.runtime replay --input <session.jsonl>
```

### 3. Firmware

Requirements: ESP-IDF v5.2 toolchain (native `idf.py` via `export.ps1`, or Docker — see [Quick Start §3](#quick-start)), ESP32-S3 hardware (1–4 boards), serial access per board.

See [firmware/esp32-csi-node/README.md](firmware/esp32-csi-node/README.md) for the full architecture. On Windows, allow the UDP port through the firewall:

```bash
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```

Platform-specific walkthroughs: [docs/WINDOWS_ESP32_SETUP.md](docs/WINDOWS_ESP32_SETUP.md), [docs/UBUNTU_ESP32_SETUP.md](docs/UBUNTU_ESP32_SETUP.md), [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md).

---

## Usage

1. Start the dashboard: `npm run dev:dashboard` (or `npm run dev` for the full stack).
2. Open [http://localhost:5000](http://localhost:5000).
3. Log in — current local development seed is username `thaer` / password `thaer` (a dev convenience, not a production credential policy).
4. Start a scan and confirm each connected ESP32-S3 node is streaming UDP traffic to the host. The dashboard shows `single_node` / `fused_two_node` / `fused_room` based on how many are currently live — no manual mode switch.

Dashboard surfaces:

| Component | What it shows |
|---|---|
| Radar / point cloud (`RadialScene.tsx`, `point-cloud-3d.tsx`) | Live Kalman-smoothed target position, node beacons (up to 4), distance/trend labels |
| Signal Signature heatmap & spectrum | Temporal MUSIC signature per node (not spatial angle — see aoa-spectrum.tsx honesty note) |
| Vitals monitor | Breathing/heart-rate estimates |
| Node Features / Board DSP card | Firmware-computed metrics per node, shown independently for cross-checking |
| AI Advisory panel | Optional AI-sidecar output, clearly marked non-authoritative |
| Metrics / control panel | Live signal metrics and scan controls |
| History / Activity / Report pages | Past sessions, audit activity, generated reports |

---

## Testing

```bash
npm test                     # TypeScript: server/**/*.test.ts + client/src/lib/**/*.test.ts + tests/behavioral/**/*.test.ts + scripts/accuracy/__tests__/**/*.test.ts
npm run test:dashboard-auth  # TypeScript: server tests only
npm run test:py              # Python: pytest tests/
```

Current verified state (this session, 2026-09-09):

- **TypeScript:** `256 pass, 0 fail`
- **Python:** `91 passed, 1 skipped` (skip is environmental, not a regression)
- **Firmware:** `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c` is host-compiled independently (`gcc -std=c99 -O2 -I. test/test_edge_dsp_pure.c edge_dsp_pure.c -lm -o test/test_edge_dsp_pure.exe`, verified this session via WSL); all assertions pass. Not part of `npm test` or `pytest`.

---

## Recording & Replay

Each session writes two artifacts, both under `data/sessions/`:

- **Per-session CSV** (`server/lib/recording-export.ts`) — one row per processed frame, header starts with a `# phantom_session_meta` comment line (session name, node anchors, thresholds, fps at start) followed by typed columns: `session_ts_ms`, `x_disp_m`/`z_disp_m` (displayed position, suppressed atomically when the gate is closed), `distance_n1_m..n4_m`, `trend_n1..n4`, `motion_n1..n4` (saturated 0–1 display value), **`raw_perturbation_n1..n4`** (the same ratio, unclamped — added this session specifically so a value pinned at `motion_nX=1.0` can still be told apart from a mildly-elevated one; see the calibration caveat under [Phantom Balance Fusion](#phantom-balance-fusion)), `node1_fps..node4_fps`, `target_visible`, `node_mode`, and ground-truth columns (`gt_x_m`, etc.) when tagged.
- **JSON session index** (`server/lib/session-store.ts`) — a fast-lookup summary per session (id, name, start/end time, duration, frame count, target classification + confidence, average distance/speed, data source) appended to `data/sessions/_index.json`, plus one standalone `<id>.json` record per session for the History page.

Separately, a small number of raw `.jsonl` CSI-frame captures (`data/sessions/*.jsonl`) remain as fixtures for wire-protocol round-trip tests (e.g. `parseCsiPacket`) — these are not the primary per-session recording format.

- Both device and host receive timestamps are preserved (device timestamp is authoritative when valid; host timestamp is the audit/fallback).
- Replay runs through the exact same parser/runtime semantics as live mode.

---

## Project Structure

```text
phantom scan/
├── client/                      React + Vite dashboard (Vite root: client/)
│   └── src/
│       ├── pages/                dashboard, login, activity, history, report
│       ├── components/dashboard/ radar scene, AoA views, vitals, AI advisory, node features
│       └── hooks/                use-websocket.ts, use-auth.tsx
├── server/                      Express host — the live runtime authority
│   ├── index.ts                  entrypoint: auth, websocket, routes, UDP server
│   ├── lib/                      udp-server.ts, websocket.ts, node-fusion.ts,
│   │                             fused-position-kalman.ts, recording-export.ts,
│   │                             session-store.ts, target-state.ts, ...
│   └── auth/                     session/auth service
├── shared/                      Zod schemas shared by client + server (schema.ts, bearing.ts, ...)
├── phantom/                      Python reference runtime (replay, DSP, tests — not live)
├── firmware/esp32-csi-node/      ESP-IDF firmware project (own README, own build)
├── scripts/                      capture, replay, calibration, reporting utilities
├── script/                       dev orchestration (dev-full.cjs, build.ts)
├── tests/                        Python pytest suite + tests/behavioral/ (tsx --test)
├── data/                         sessions/ (per-session CSV + JSON index + a few legacy JSONL fixtures), operator store, audit/
└── docs/                         ADRs, deployment guides, technical reports
```

---

## Documentation Index

**Current / binding**

| Document | What it covers |
|---|---|
| [PHANTOM_SCAN_REMEDIATION_REPORT.md](PHANTOM_SCAN_REMEDIATION_REPORT.md) | Most up-to-date record of what's fixed, deferred, and still an open operator action (predates the 4-node work below — treat as historical context, not current status) |
| [ADR-051](docs/adr/ADR-051-runtime-authority.md) | Why the Node/TS server, not Python, owns live runtime |
| [ADR-054](docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md) | Why `balance` (display) and `balanceLinear` (authoritative) intentionally differ |
| [RUN.md](RUN.md) | Canonical start sequence and port map |
| [docs/research/csi-phase-in-wifi-sensing.md](docs/research/csi-phase-in-wifi-sensing.md) | How CSI phase is used for AoA, ranging, and vital signs, and why raw phase needs SFO/PDD sanitization first |
| [BOOTSTRAP.md](BOOTSTRAP.md) | One-page command cheat sheet |
| [SETUP_AUDIT.md](SETUP_AUDIT.md) / [AUDIT.md](AUDIT.md) | Setup and repository disposition audits |

**Historical / archived** — kept for context, not descriptions of the current system:

| Document | Why it's historical |
|---|---|
| [docs/ruview-2node-full-analysis-report.md](docs/ruview-2node-full-analysis-report.md) | Explicitly archived; superseded by ADR-051, the 4-node `fused_room` work, and this README |
| [docs/adr/README.md](docs/adr/README.md) (ADR catalog) | Documents a broader, more ambitious multistatic-mesh / pose-estimation vision than what's actually shipped here — many entries are `Proposed` or `Superseded` |
| [TARGET_RENDER_AUDIT.md](TARGET_RENDER_AUDIT.md) | Marked superseded at the top; point-in-time record of fixed rendering bugs |
| [MILESTONE1_FIX_PLAN.md](MILESTONE1_FIX_PLAN.md), [TARGET_TEST_PLAN.md](TARGET_TEST_PLAN.md), [TARGET_VERIFICATION_REPORT.md](TARGET_VERIFICATION_REPORT.md) | Point-in-time stabilization/test records, from the original 2-node system |

The repository root also holds a number of dated audit and test reports (`PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`, `PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md`, `TEST_REPORT.md`, etc.) — these are point-in-time verification snapshots, not living documentation.

---

## Honest Limitations

> Phantom Scan tells the truth about what its physics physically can't do, rather than faking a cleaner result.

- **Not RF multilateration.** Even with 4 nodes, `fuseNodeTargets` is a perturbation-weighted centroid of node anchors, not true ranging or angle-of-arrival localization. With exactly 2 nodes the target is further restricted to the on-axis line between them — a person standing off-axis reads as a wrong on-line distance, not a wrong plane.
- **`trend` reflects smoothed balance movement** — a still person may still read `stable` even during small in-place motion.
- **Active investigation: 4-node empty-room false positives.** Multiple real empty-room recordings on the live 4-node rig (September 2026, several physical layouts, before and after a firmware reflash) show a persistent phantom "moving" target. A full code audit found no fusion/motion-computation bug and no single consistently-bad node (the effect shifts with physical repositioning, not with which board). The `motion_nX` metric is saturated (clamped at 1.0) on roughly half of all ticks in these recordings, which makes the existing data too "censored" to responsibly re-derive `DEFAULT_MOTION_THRESHOLD`/`MOTION_SATURATION_SCALE` — a correctly-calibrated threshold cannot be computed from clamped inputs. `raw_perturbation_n1..n4` (unclamped) now ships in every recording specifically to unblock this; leading unconfirmed hypothesis is RF self-interference among same-channel, same-AP nodes each self-pinging at 50 Hz, as an alternative to a genuinely-elevated real noise floor. See [Phantom Balance Fusion](#phantom-balance-fusion) for the calibration caveat and do not retune the threshold/scale constants independently of each other or without fresh uncensored data.
- **Calibration placeholders, not fully validated thresholds.** `PHANTOM_TREND_DEADBAND_MPS` (0.05), the firmware's `EDGE_RESP_PERIOD_CV_MIN` (0.002), and the `FusedPositionKalman` Q/R constants (see [Fused Position Kalman Filter](#fused-position-kalman-filter)) are derived from real captured session data but not from a dedicated stationary-target calibration soak; `PHANTOM_MOTION_THRESHOLD` carries the more serious open issue described above.
- **Firmware calibration bootstrap hardening.** The firmware's per-node calibration window now rejects and retries a calibration sample whose max deviates more than `EDGE_CALIB_REJECT_SIGMA_MULT` (8σ) from its own running mean, closing a class of bug where one contaminated boot-time sample could poison a node's baseline for the rest of the session — fixed and covered by `test_edge_dsp_pure.c` this session, independent of the 4-node false-positive investigation above.

---

## License

MIT
