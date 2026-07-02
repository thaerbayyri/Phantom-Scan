# 2-Node ESP32-S3 CSI Sensing — Port & Run Guide

> A portable guide to bring up **two ESP32-S3 boards doing WiFi CSI human sensing** and
> integrate them into another project. Structured to match the target "Phantom Scan"
> architecture (Layers **A**–**E**). Numbers marked *(measured)* were verified on real
> hardware; others are design values.
>
> **Honesty:** WiFi CSI is coarse RF sensing, **not** a camera. With **2 nodes** you get
> presence + motion + **1-D** target position (along the line between the boards), not
> volumetric point clouds or per-limb pose. Firmware is "working" only when a **real boot
> log** shows CSI `yield > 0`.
>
> **Current repo truth:** the supported Phantom Scan runtime is the **Python authority path**
> (`phantom/`) with a **32-byte ADR-018 CSI frame** plus **40-byte heartbeat** packets. The
> Node dashboard is a follower/compatibility consumer in canonical runs and should not be treated
> as the authoritative UDP ingest path.

---

## 0. The hardware/network contract (fix this first)

| Item | Value |
|---|---|
| Nodes | 2x ESP32-S3 (8 MB flash, e.g. N16R8) |
| Aggregator | one host PC on the **same 2.4 GHz SSID** |
| AP | 2.4 GHz, single fixed channel (5 GHz CSI is unreliable on ESP32) |
| Transport | each board -> **UDP -> `HOST_IP:5005`** |
| Identity | **distinct `node_id`** per board (1 and 2) |

Everything else depends on this. The host IP the boards target **must be stable** (static
lease or reserved IP). Node IPs themselves are DHCP and may change — that's fine.

---

## Layer A — Firmware capture & transport

**Target files:** `firmware/esp32-csi-node/main/{main.c, csi_collector.c, stream_sender.c, nvs_config.c}`

### A.1 The one non-obvious failure — CSI starvation
The ESP32 CSI engine **only produces CSI for received OFDM frames**. A station on a quiet
network hears only sparse beacons -> the CSI callback starves -> `yield=0pps` -> your DSP gets
nothing -> presence/motion/target all read **0**. This looks like "the sensor is dead" but the
board is fine and connected.

**The fix (must be in the firmware you flash):**
1. **Self-ping the gateway at ~50 Hz.** The router's ICMP echo-replies are OFDM unicast frames
   to this station and drive the CSI callback regardless of ambient traffic. (Reference here:
   `csi_collector.c` -> `csi_start_self_ping()`, pings `gw` @ `interval_ms=20`.)
2. **Promiscuous filter = MGMT + DATA** (not MGMT-only), so received data frames also generate
   CSI. On display builds the MGMT->MGMT+DATA upgrade must be applied explicitly.
3. **Disable modem sleep:** `esp_wifi_set_ps(WIFI_PS_NONE)` — sleep between DTIM beacons kills yield.

*(measured)* Before fix: `yield=0pps`, 0 fps to host. After fix: **~40 pps**, **41 fps** raw CSI
per node, controller state `8 (DEGRADED)` -> `5 (healthy)`, frames grow `len=128` -> `len=256`.

### A.2 Flash both boards (use the FIXED build, not a stale release)
```bash
# from the firmware build output dir (bootloader/partition/ota/app)
python -m esptool --chip esp32s3 -p COM5 -b 460800 write_flash \
  0x0 bootloader/bootloader.bin 0x8000 partition_table/partition-table.bin \
  0xf000 ota_data_initial.bin 0x20000 <app>.bin
# repeat -p COM6
```
> Pitfall seen this session: a prebuilt "release" binary lacked the self-ping fix and starved,
> even though a same-version `build/` binary had it. **Verify the binary contains the fix**
> (search the .bin for the `self-ping started` log string) before trusting it.

### A.3 Provision NVS (WiFi + host target + identity)
```bash
python provision.py --port COM5 --ssid "<SSID>" --password "<secret>" \
    --target-ip <HOST_IP> --target-port 5005 --node-id 1
python provision.py --port COM6 ... --node-id 2      # distinct node_id!
```
Never echo/commit the password.

### A.4 Accept criteria (serial @115200)
```
wifi:connected with <SSID>, channel <N>
self-ping started -> <gw> @50Hz (CSI OFDM source)
CSI filter upgraded to MGMT+DATA
CSI cb #1 ... #100 ... #200        <- climbing
medium tick: state=5 yield=~40pps  <- yield > 0 is the pass signal
```
If `yield=0` here, **stop** — Layers B–E will all read zero. It's a Layer-A problem.

---

## Layer B — Host ingest, parser, logger, replay

**Target files:** `phantom/{protocol.py, ingest.py, recording.py, runtime.py}`, and the TS live
path `server/lib/{udp-server.ts, websocket.ts}`, `shared/schema.ts`.

### B.1 Wire protocol (the current integration contract)
Two little-endian UDP packet types arrive on `:5005`. The current repo does **not** use the
older 20-byte host contract or `0xC5110006` feature-state packets as the supported path.
Canonical parsing lives in `phantom/protocol.py`; Node-side compatibility parsing lives in
`server/lib/udp-server.ts`.

**`0xC5110001` — ADR-018 raw CSI** (32-byte header, then interleaved `int8` I/Q):
| Off | Field | Type |
|----|-------|------|
| 0..3 | magic `0xC5110001` | u32 LE |
| 4 | schema_version | u8 |
| 5 | node_id | u8 |
| 6 | n_antennas | u8 |
| 7..8 | n_subcarriers | u16 LE |
| 9..12 | freq_mhz | u32 LE |
| 13..16 | seq | u32 LE |
| 17 | rssi_dbm | i8 |
| 18 | noise_dbm | i8 |
| 19 | channel | u8 |
| 20..27 | device_ts_us | u64 LE |
| 28..31 | device_ts_ms | u32 LE |
| 32.. | I/Q pairs | i8,i8 ... |

**`0xC51100A1` — heartbeat** (40 bytes):
`schema_version`, `node_id`, `wifi_connected`, `seq`, `device_ts_ms`,
`callback_drops`, `queue_high_watermark`, `send_failures`, `reconnect_count`,
`firmware_build_id`.

Current acceptance rules:
- drop wrong magic, unsupported schema, truncated headers, and mismatched I/Q payload sizes
- preserve both host receive time and device timestamps when valid
- pin each `node_id` to its first observed source IP/port for the session
- record CSI, heartbeat, and security events to JSONL through the same authority path

### B.2 Ingest responsibilities (`phantom/ingest.py`, `phantom/runtime.py`, `phantom/api.py`)
- **Canonical live binder**: `python -m phantom.runtime live --host 0.0.0.0 --port 5005 --api-port 8789 --no-synthetic`
- **Health contract**:
  - `GET /api/health`
  - `GET /api/status`
  - `GET /api/sensing/frame`
- **Per-node state**: maintain separate CSI/heartbeat buffers and node health for nodes `1` and `2`.
- **Loss/reorder detection**: track CSI and heartbeat sequence gaps per node.
- **Degraded vs fused truth**:
  - one fresh node -> degraded single-node mode
  - two fresh nodes -> fused two-node mode
- **Replay**: JSONL remains the only supported recording/replay format in the authority path.
- **Node dashboard role**: in canonical runs the dashboard follows authority state; it should not bind UDP `5005`.

---

## Layer C — Deterministic DSP

**Target files:** `phantom/dsp.py`, `scripts/csi_filter_pipeline.py`

Recommended deterministic stages (map to your required list):

| Stage | What it does |
|---|---|
| amplitude extraction | `hypot(I,Q)` per subcarrier (already in parser) |
| phase unwrap | `np.unwrap` per subcarrier over the window (for phase-based features) |
| static clutter suppression | subtract per-subcarrier running mean (empty-room baseline) |
| Hampel filter | median + MAD outlier rejection per subcarrier (kills impulsive spikes) |
| respiration band | band-pass 0.1-0.5 Hz on amplitude -> breathing energy |
| **motion energy** | **mean per-subcarrier *temporal* std over the window / mean amplitude** -> 0..1 |
| cross-node correlation | compare the two nodes' motion to localize (below) |

**Motion energy (the core detector), matches this session's bridge:**
```python
# window = list of amp-vectors for one node
import statistics as st
def motion_energy(window):
    k = min(len(a) for a in window)
    sub_std = [st.pstdev([a[j] for a in window]) for j in range(k)]
    base = sum(sum(a)/len(a) for a in window)/len(window) or 1.0
    abs_std = sum(sub_std)/k
    return min(1.0, abs_std/base*4.0)          # 0=still, 1=high motion
# present = motion > 0.12  (or edge presence flag, or variance > 0.8)
```

**1-D target localization (2-node cross-node ratio):**
```python
r1, r2 = abs_std_node1, abs_std_node2            # raw per-node perturbation (un-normalized)
balance = r2/(r1+r2) if (r1+r2) > 1e-6 else 0.5  # 0 -> at node1, 1 -> at node2
tx = p1x + (p2x - p1x)*balance                   # place target on the line between boards
```
*(measured)* still -> `motion~=0.19, balance~=0.51` (center); walking toward node 2 ->
`motion=1.00, balance~=0.86`. The blob **translates**, it doesn't just brighten.

---

## Layer D — Optional ML / inference

**Target files:** `scripts/ai_inference.py`, `densepose/`

- **Disabled by default.** The system must run **DSP-only** when models are missing/incompatible.
- Feed the model the same windowed CSI tensor the DSP uses; gate it behind a config flag.
- **Honest scope:** per-limb pose / DensePose needs **4+ nodes and a trained model**. With 2
  nodes, keep ML off and rely on Layer C. Don't surface a skeleton you can't substantiate.

---

## Layer E — API / UI / monitoring (+ 3D)

**Target files:** `server/`, `client/`

### E.1 Authority-first dashboard publishing
The supported live contract is the authority snapshot exposed by `phantom/api.py`, with the
dashboard following that state. For canonical two-node evidence:
- start Python authority first on `:5005` and `:8789`
- optionally start the AI sidecar after authority is up
- start the Node dashboard as a follower, not as the UDP owner
- use `/api/status` and `/api/sensing/frame` as the truth source when the UI looks wrong

### E.2 3D visualization
- **Reliable path:** a small Three.js page that reads `signal_field.values` (20x20) and renders
  it as a 3D height-field / point cloud, with `target` as a glowing marker on the board line.
  This shows *your* live data with no backend guessing.
- **Richer path:** a gaussian-splat / scene renderer (pattern: a `SensingTab` that inits a splat
  renderer and updates it from `sensing_update`).
- **Honest 3D caveat:** with 2 nodes this is **1-D position + motion intensity displayed in a 3D
  scene** — not a volumetric (x,y,z) reconstruction. Say so in the UI.

---

## Run-from-scratch quickstart

```text
1. Flash both boards with the fixed firmware — Layer A.2
2. Provision distinct `node_id` values and host target `:5005` — Layer A.3
3. Verify serial: WiFi connect, self-ping start, CSI callbacks climbing, non-zero `yield`
4. Start Python authority on UDP `:5005` and API `:8789`
5. Confirm `GET /api/health`, `GET /api/status`, and `GET /api/sensing/frame`
6. Verify one-node degraded mode, then two-node fused mode
7. Start the follower dashboard only after authority is healthy
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| everything 0, `yield=0pps` | firmware lacks self-ping / MGMT+DATA | reflash the FIXED firmware (A.1-A.2) |
| board connects, no UDP at host | wrong `--target-ip`, or nothing on :5005 | set host's real IP; start ingest first |
| `sendto ENOMEM` on serial | no listener on :5005, TX buffer backs up | start Layer-B ingest; it clears |
| target never moves | boards too close / person not between them | 2-4 m apart, walk the line between them |
| both nodes overwrite each other | same `node_id` | re-provision `--node-id 1` / `2` |
| UI blank but data flows | follower dashboard issue, wrong mode, or stale client state | check `GET /api/sensing/frame` first, then verify Node is following authority instead of owning UDP |

## Reference implementations in this repo
| Layer | Look at |
|---|---|
| A firmware/self-ping | `firmware/esp32-csi-node/main/csi_collector.c` |
| A provisioning | `firmware/esp32-csi-node/provision.py` |
| B authority runtime | `phantom/runtime.py`, `phantom/api.py`, `phantom/ingest.py`, `phantom/protocol.py` |
| B raw-CSI recorder (JSONL) | `scripts/record-csi-udp.py` |
| E follower dashboard | `server/lib/authority-follower.ts`, `server/lib/websocket.ts`, `client/src/pages/dashboard.tsx` |

*Numbers labeled (measured) were verified on 2x ESP32-S3 (8 MB) on channel 6 during setup:
41 fps raw CSI/node, 128 subcarriers, motion 0.20->1.00 and balance 0.51->0.86 on movement.*
