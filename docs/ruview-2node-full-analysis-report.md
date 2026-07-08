# RuView Two-Node ESP32 Analysis Report

> **⚠ HISTORICAL BENCH DIAGNOSTIC (superseded as a runtime).** This report analyzes
> `scripts/ruview-dashboard-bridge.py` as a live backend. In the current repo the
> **TS dashboard (`npm run dev`) is the canonical live path and sole owner of UDP
> `:5005`** — it also parses the `0xC5110006` feature-state packets described here.
> **Never run the bridge and the dashboard together** (both bind `:5005`); use the
> bridge only standalone on a bench. The provisioning script formerly named
> `provision.py` is now `esp-flash.py` (references below updated).

Date: 2026-07-07

## Purpose

This report explains how the two-node RuView setup works in this repository, what code paths are actually required to run it, how the moving target is derived and presented, and what the real limits are.

This is a code-grounded report based on the current checkout and the live hardware path that was rerun successfully on this machine.

## Executive Summary

The working two-node path in this checkout is:

1. Two ESP32 boards run `firmware/esp32-csi-node`.
2. Each board joins the same 2.4 GHz Wi-Fi network and streams UDP to the host on port `5005`.
3. The host runs `scripts/ruview-dashboard-bridge.py`.
4. The bridge parses raw CSI packets and compact feature-state packets, computes a simple two-node motion and localization model, then serves:
   - HTTP UI on `:3000`
   - WebSocket sensing stream on `:3001`
5. The browser UI reads `/api/v1/status`, `/health/*`, and `/ws/sensing` and renders the result.

The key point is that the moving target shown in the two-node setup is not true 2D or 3D localization. It is a 1D estimate along the line between the two nodes. The bridge computes which node sees the larger raw motion perturbation, converts that ratio into a `balance` value from `0..1`, and places a target blob on the line between the two board positions.

## What Is Actually Running

For the live two-node path, the important components are:

- Firmware:
  - `firmware/esp32-csi-node/main/main.c`
  - `firmware/esp32-csi-node/main/csi_collector.c`
  - `firmware/esp32-csi-node/main/stream_sender.c`
  - `firmware/esp32-csi-node/main/edge_processing.c`
  - `firmware/esp32-csi-node/main/adaptive_controller.c`
  - `firmware/esp32-csi-node/main/nvs_config.c`
- Provisioning:
  - `firmware/esp32-csi-node/esp-flash.py`
- Host bridge:
  - `scripts/ruview-dashboard-bridge.py`
- UI consumers:
  - `ui/components/SensingTab.js`
  - `ui/services/sensing.service.js`
  - `ui/services/websocket-client.js`
  - `ui/utils/backend-detector.js`
  - `ui/config/api.config.js`

The large Rust workspace exists, but for this machine and this run, the Python bridge is the practical live backend for the two-node setup.

## Physical and Network Contract

The two-node system depends on a few non-negotiable facts:

- Both ESP32 boards must be on the same 2.4 GHz Wi-Fi network.
- Both boards must target the host IP and UDP port `5005`.
- Each board must have a distinct `node_id`.
- The host must actually own the provisioned target IP at runtime.

In this repo, those values are stored by `esp-flash.py` into NVS under the `csi_cfg` namespace and loaded at boot by `nvs_config_load()` in `nvs_config.c`.

Important stored values:

- `ssid`
- `password`
- `target_ip`
- `target_port`
- `node_id`
- `tdm_slot`
- `tdm_nodes`
- optional `csi_channel`

Without correct provisioning, the rest of the stack can look healthy while receiving no live data.

## Firmware Boot and Bring-Up Sequence

The firmware startup order in `main.c` matters:

1. Initialize NVS.
2. Load runtime config with `nvs_config_load(&g_nvs_config)`.
3. Capture `node_id` early with `csi_collector_set_node_id(g_nvs_config.node_id)`.
4. Connect to Wi-Fi with `wifi_init_sta()`.
5. Initialize UDP sender with `stream_sender_init_with(g_nvs_config.target_ip, g_nvs_config.target_port)`.
6. Start CSI collection with `csi_collector_init()`.
7. Start edge processing with `edge_processing_init(&edge_cfg)`.
8. Start the adaptive controller with `adaptive_controller_init(NULL)`.
9. Optionally enable `MGMT+DATA` capture after display probing with `csi_collector_enable_data_capture()`.

The early `node_id` capture exists because Wi-Fi init has historically clobbered the config struct. The code explicitly defends against that in `csi_collector.c`.

## Why Two Nodes Work at All

### 1. CSI generation

The ESP32 CSI engine only produces CSI when it receives OFDM Wi-Fi frames. On a quiet network, that can starve.

`csi_collector.c` addresses this in three important ways:

- It disables modem sleep with `esp_wifi_set_ps(WIFI_PS_NONE)`.
- It enables promiscuous mode.
- It starts a self-ping loop with `csi_start_self_ping()`.

`csi_start_self_ping()` pings the gateway every 20 ms, which creates roughly 50 Hz of received OFDM replies. Those replies force the CSI callback to keep firing even when ambient traffic is low.

This is one of the most important implementation details in the whole system. Without it, the node can be connected to Wi-Fi and still produce effectively no useful CSI.

### 2. Multi-node coexistence

The two-node setup relies on distinct identities and a basic TDM-style configuration:

- `node_id`
- `tdm_slot`
- `tdm_nodes`

These are provisioned through `esp-flash.py` and loaded through `nvs_config.c`.

The host-side bridge does not implement TDM itself. It simply receives packets from both nodes and keeps per-node rolling buffers. The TDM discipline is a firmware-side concern.

### 3. Continuous health supervision

The adaptive controller in `adaptive_controller.c` periodically samples:

- packet yield
- RSSI
- noise floor
- motion score
- presence score

It logs the medium tick state with the values operators actually use during bring-up:

- state
- yield in packets per second
- motion
- presence
- RSSI

It also emits a compact `rv_feature_state` packet at 1 Hz using magic `0xC5110006`.

## On-Wire Data Contracts

### Raw CSI packet

The raw packet is serialized in `csi_serialize_frame()` in `csi_collector.c`.

Important fields:

- magic: `0xC5110001`
- `node_id`
- number of antennas
- number of subcarriers
- frequency in MHz
- sequence number
- RSSI
- noise floor
- PPDU flags
- interleaved I/Q bytes

For the current live path, the bridge only needs enough of this to derive:

- node identity
- RSSI
- channel
- amplitude vectors from I/Q

### Feature-state packet

The compact feature-state format is defined in `rv_feature_state.h` and finalized in `rv_feature_state.c`.

Important fields:

- magic: `0xC5110006`
- `node_id`
- capture profile `mode`
- sequence
- timestamp
- `motion_score`
- `presence_score`
- `respiration_bpm`
- `respiration_conf`
- `heartbeat_bpm`
- `heartbeat_conf`
- `anomaly_score`
- `node_coherence`
- quality flags
- CRC32

The bridge only extracts the fields it needs for presentation:

- motion
- presence
- respiration BPM and confidence
- heartbeat BPM and confidence

## What the Edge DSP on the Boards Does

The edge DSP task lives in `edge_processing.c`.

The important pipeline is:

1. read CSI I/Q samples from the ring buffer
2. extract phase
3. unwrap phase
4. update Welford variance per subcarrier
5. select top-K subcarriers
6. bandpass filter for breathing and heart rate
7. estimate periodicity
8. compute motion energy
9. compute presence score
10. detect falls
11. estimate multi-person slot count
12. send vitals and feature packets

Important output variables:

- `s_motion_energy`
- `s_presence_score`
- `s_breathing_bpm`
- `s_heartrate_bpm`
- `s_latest_pkt.n_persons`

Important honesty point:

The firmware README is explicit that the person count in tier 2 is a heuristic over grouped top-K subcarriers. It is not a learned occupancy counter.

## What the Python Bridge Actually Does

The Python bridge in `scripts/ruview-dashboard-bridge.py` is the most important host-side file for the two-node setup.

### 1. It is the live backend

It binds:

- UDP `:5005`
- HTTP `:3000`
- WS `:3001`

It serves:

- `/`
- `/live`
- `/api/v1/status`
- `/health/*`
- `/ws/sensing`
- `/api/v1/stream/pose`
- `/api/v1/stream/events`

This is why the browser UI can work without the full Rust backend.

### 2. It keeps per-node rolling state

It stores per-node CSI windows in:

- `state.csi[node_id] -> deque(maxlen=120)`

Each entry contains:

- host receive time
- RSSI
- mean amplitude
- amplitude vector

This means the host-side model uses about three seconds of recent CSI history per node.

### 3. It parses exactly two packet types

- `parse_csi()` handles `0xC5110001`
- `parse_feat()` handles `0xC5110006`

Everything else is ignored.

### 4. It computes the host-side live model

`compute_update(state)` derives:

- node list
- node RSSI summaries
- `mean_rssi`
- `variance`
- `std`
- `motion_band_power`
- `breathing_band_power`
- `respiration_bpm`
- `heartbeat_bpm`
- classification
- signal field
- target

This function is the actual explanation for what the UI shows.

## How the Moving Target Is Computed

This is the central question in the two-node system.

The bridge computes:

1. for each node, per-subcarrier temporal standard deviation over the recent window
2. average of those standard deviations as `abs_std`
3. normalized motion as:

`motion = min(1.0, abs_std / base * 4.0)`

where `base` is mean amplitude over the same recent window

This produces:

- `motion_per_node[node_id]`
- `motion_raw_per_node[node_id]`

The target localization uses the raw motion, not the saturated normalized motion:

- `r1 = motion_raw_per_node[node1]`
- `r2 = motion_raw_per_node[node2]`
- `balance = r2 / (r1 + r2)` if possible, else `0.5`

Then the target is placed on the line between the two fixed node positions:

- `tx = p1.x + (p2.x - p1.x) * balance`
- `tz = p1.z + (p2.z - p1.z) * balance`

The fixed node positions are:

- node 1: `[4.0, 0.0, 6.0]`
- node 2: `[16.0, 0.0, 6.0]`

So the target is always somewhere on that line.

### What this means in practice

- If node 1 sees the stronger perturbation, the target moves toward node 1.
- If node 2 sees the stronger perturbation, the target moves toward node 2.
- If both nodes see similar perturbation, the target sits near the center.

This is why the target appears to move between the nodes even though the system is not doing true room-scale 2D localization.

## How the Signal Field Is Generated

The bridge also emits a `signal_field` with:

- `grid_size = [20, 1, 20]`
- `values = 400 floats`

This is not reconstructed volumetric sensing.

It is a synthetic visualization layer built from:

- a faint baseline value
- a Gaussian-like bump centered on the current target estimate
- bump strength scaled by `motion_band_power`

So the field is best understood as a live visualization surface for the target estimate and motion intensity, not as literal spatial tomography.

## How the UI Presents the Data

### `SensingTab.js`

This is the primary 3D-style sensing panel.

It:

- starts `sensingService`
- listens for sensing updates
- updates the 3D Gaussian-splat renderer
- updates HUD metrics
- updates per-node cards

It also contains an explicit honesty note:

- with `0` or few nodes you get presence, breathing, and gross motion
- `3-4+` nodes are needed for spatial resolution and limb-level tracking

### `sensing.service.js`

This service builds the sensing WebSocket URL from the current page origin:

- `3000 -> 3001`
- `8080 -> 8765`

It connects to `/ws/sensing`, tracks connection state, and falls back to client-side simulation only after repeated failures.

It also calls `/api/v1/status` after connection to determine whether the server source is:

- live hardware
- server-side simulated

### `websocket-client.js`

This supports the live demo style pages using same-origin `/ws/sensing` or derived equivalents.

### `backend-detector.js`

This checks `/health/live` and decides whether the backend is available.

Because the Python bridge implements the required health routes, the normal UI can remain in live mode when the bridge is running.

### `/live`

The bridge ships its own minimal debug page at `/live`.

This page is the clearest representation of the two-node result because it does not pretend to be full pose or room reconstruction. It shows:

- two board markers
- a target blob on the line between them
- a motion bar
- presence
- respiration
- RSSI

For debugging the two-node setup, `/live` is the most honest view.

## What the Project Needs in Order to Run the Two-Node Path

### Mandatory runtime pieces

1. Two flashed ESP32 boards running the current `esp32-csi-node` firmware.
2. Provisioned NVS values:
   - SSID
   - password
   - target IP
   - target port
   - unique node IDs
3. Host reachable at the exact provisioned `target_ip`.
4. Python runtime with `aiohttp`.
5. `scripts/ruview-dashboard-bridge.py` running.
6. Browser opening either:
   - `http://localhost:3000/live`
   - `http://localhost:3000/`

### Recommended runtime conditions

- 2.4 GHz AP
- fixed channel
- host and boards on same subnet
- boards separated by roughly 2-4 meters
- user walking along the line between nodes

### Optional pieces

- Rust sensing server
- WASM modules
- mmWave sensor
- swarm bridge

These are not required for the core two-node moving target demo.

## What Can Fail

The main failure modes are visible directly in the code.

### 1. CSI starvation

If self-ping or data-frame capture is missing, CSI yield can collapse to zero.

Symptoms:

- no useful callbacks
- low yield
- motion and presence stay near zero

Relevant code:

- `csi_start_self_ping()` in `csi_collector.c`
- `csi_collector_enable_data_capture()` in `csi_collector.c`

### 2. Wrong host IP

If the provisioned `target_ip` does not belong to the current host network, the boards will keep trying to send but the bridge will receive nothing.

Symptoms:

- bridge `nodes=[]`
- `packets=0`
- board serial logs show `sendto ENOMEM` or repeated send failures

Relevant code:

- `stream_sender_init_with()` in `main.c`
- `stream_sender_send()` in `stream_sender.c`
- `esp-flash.py`

### 3. Duplicate node IDs

If both boards use the same `node_id`, the host cannot treat them as distinct sensors.

### 4. Wrong page or wrong backend expectation

The sensing UI works because the bridge exposes the expected routes. If the wrong page or a backend that does not serve the same health and WebSocket routes is used, the UI can look offline even while the boards are alive.

## Honest Limits of the Two-Node Setup

This setup does not do:

- true 2D room localization
- true 3D reconstruction
- limb-level pose inference
- robust learned multi-person counting

What it really does well:

- prove both nodes are alive
- prove CSI is flowing
- estimate gross motion
- estimate presence
- estimate breathing and heart rate with caveats
- produce a coarse 1D moving target between the two nodes

That is the correct interpretation of the code and the runtime.

## Current Proven Working Path on This Machine

The live rerun on this machine succeeded through the Python bridge.

Verified results:

- source: `esp32`
- nodes: `[1, 2]`
- channel: `6`
- packet count increasing over time

That is the real pass condition for this checkout.

## Recommended Operator Workflow

1. Confirm host IP matches the provisioned `target_ip`.
2. Confirm both boards are visible on serial.
3. Confirm board logs show:
   - Wi-Fi connected
   - self-ping started
   - CSI callback logs increasing
   - medium tick yield non-zero
4. Start the bridge:

```powershell
& 'C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe' scripts\ruview-dashboard-bridge.py --udp-port 5005 --http-port 3000 --ws-port 3001
```

5. Confirm:

- `http://127.0.0.1:3000/api/v1/status`
- `http://127.0.0.1:3000/health`

6. Open:

- `http://localhost:3000/live`

7. Walk between the boards and watch the target slide along the line.

## Bottom Line

The two-node implementation in this repo is internally coherent and works as a live coarse RF motion/presence system.

Its real architecture is:

- firmware creates CSI and compact node features
- bridge converts those into a host-side rolling two-node model
- UI renders a 1D target estimate and signal field

Its real limitation is also clear:

the moving target is a differential two-node line estimate, not full spatial tracking.

That is exactly what the current code supports, and it is the right way to describe the system to avoid overstating it.
