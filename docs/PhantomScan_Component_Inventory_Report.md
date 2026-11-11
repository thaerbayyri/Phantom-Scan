# Phantom Scan — Component Inventory Report

**Date:** 2026-08-21
**Branch:** `feat/two-node-radar-live-detection`
**Purpose:** A single, accurate map of every component in the repository — what it is, what it owns, and how it connects to the rest of the system. Compiled by reading the live source tree (`server/`, `client/`, `phantom/`, `firmware/`, `scripts/`, `shared/`, `docs/adr/`, `tests/`), not from prior documentation alone; cross-checked against [README.md](README.md) and [ADR-051](docs/adr/ADR-051-runtime-authority.md).

---

## 1. System at a glance

Phantom Scan turns Wi-Fi CSI from two ESP32-S3 nodes into a live 1-D radar view of a room (target position/distance/trend along the node-to-node axis) plus board-side vitals (breathing, heart rate) — rendered in a React dashboard fed by an Express/WebSocket host.

```text
ESP32-S3 node 1 ----\
                     \  UDP :5005 (ADR-018 frames)      targetState / metrics
ESP32-S3 node 2 -------> Node/TS host runtime (server/) ------------------------> React dashboard (client/)
                            |          \
                            |           \-> JSONL session recording (data/sessions/)
                            |           \-> forwarded raw frames -> AI sidecar :5006 (scripts/ai_inference.py, advisory only)
                            \-> deterministic DSP -> Phantom Balance Fusion -> WebSocket /ws
```

There are **two runtime tracks**, and only one is allowed to be live at a time: the Node/TS server (`server/`) is the sole live authority (binds UDP `:5005`, publishes `/ws`); the Python stack (`phantom/`) is a **replay/reference/test** toolkit whose live mode is retired and refuses to bind unless explicitly overridden. See [ADR-051](docs/adr/ADR-051-runtime-authority.md).

---

## 2. Firmware — `firmware/esp32-csi-node/` (ESP-IDF v5.2, ESP32-S3)

The on-device C firmware that runs on the two physical nodes. Own README, own build (Docker-based `idf.py`), own host-compiled test binary.

| File | Role |
|---|---|
| `main.c` | Entry point / task orchestration |
| `csi_collector.c` | Captures CSI from the Wi-Fi driver, rate-caps sends (`CSI_MIN_SEND_INTERVAL_US`) |
| `edge_processing.c` | On-device signal conditioning / ring-buffer state (recently reworked for 2-node hardware reality — see git log) |
| `edge_dsp_pure.c` | Pure-C DSP core, host-testable independent of ESP-IDF (`test/test_edge_dsp_pure.c`) |
| `rv_feature_state.c` | Computes the board-side feature-state frame (presence/motion/respiration/heart-rate) |
| `stream_sender.c` | Packs and sends UDP frames (CSI, vitals, feature-state, heartbeat) |
| `nvs_config.c` | Non-volatile config storage (Wi-Fi creds, target IP, node ID) |
| `rvf_parser.c`, `wasm_runtime.c`, `wasm_upload.c` | Optional programmable-sensing (WASM module) support — frame `0xC5110004` |
| `display_hal.c`, `display_task.c`, `display_ui.c` | On-board display (LVGL-based, `managed_components/lvgl__lvgl/`) |
| `ota_update.c`, `power_mgmt.c` | OTA firmware update, power management |

**Wire protocol emitted (all UDP → host `:5005`, 4-byte LE magic):**

| Magic | Frame | Rate | Notes |
|---|---|---|---|
| `0xC5110001` | CSI | ~41–43 pps/node | 32-byte header (ADR-018); legacy 20-byte accepted only under `PHANTOM_ALLOW_LEGACY_CSI` |
| `0xC5110002` | Vitals | 1 Hz/node | Board presence/motion/vitals — shown, never fused into host DSP |
| `0xC5110004` | WASM module output | event-driven | Optional programmable sensing |
| `0xC5110006` | Feature-state | 1 Hz/node | Board-computed motion/presence/respiration/HR for the **Board DSP** UI card |
| `0xC51100A1` | Heartbeat | periodic | Per-node liveness |

This is the project's **own** firmware — tuned last session for the actual 2-node hardware (ghost-target fix, MUSIC/AoA false-precision fix, node-gain bias fix). It is not literally upstream RuView firmware, though it speaks a compatible ADR-018-style wire format.

---

## 3. Host runtime — `server/` (Node.js + Express + TypeScript) — **the live authority**

| File | Role |
|---|---|
| `index.ts` | Entrypoint: wires auth, WebSocket, HTTP routes, UDP server |
| `routes.ts` | HTTP API routes |
| `storage.ts` | Persistence (sessions, operator store) |
| `static.ts` / `vite.ts` | Static asset / Vite dev-middleware serving |
| `auth/service.ts`, `auth/ws-auth.ts` | Operator auth (Passport local), WebSocket auth |
| `lib/udp-server.ts` | **Sole ESP32 ingest.** Hard-binds UDP `:5005` (no `reuseAddr` — a second listener fails loud rather than silently stealing packets), validates magic/schema, source-pins nodes, mirrors accepted raw frames to the AI sidecar on `:5006` |
| `lib/websocket.ts` | Runs the DSP/fusion pipeline, publishes `radialTarget`, `targetState`, node beacons, firmware metrics over `/ws` |
| `lib/node-fusion.ts` | **Phantom Balance Fusion** — the 1-D two-node localization math (see §7) |
| `lib/signal-processing.ts` | Deterministic DSP: amplitude extraction, MUSIC-based temporal signature, motion energy |
| `lib/target-state.ts` | Target lifecycle / state machine |
| `lib/tracking.ts` | Target tracking over time |
| `lib/vitals.ts` | Host-side vitals cross-check |
| `lib/complex.ts` | Complex-number helpers for CSI math |
| `lib/recording-export.ts` | Exports recorded sessions |
| `lib/session-store.ts` | Session persistence |
| `lib/runtime-settings.ts` | Runtime-tunable settings (thresholds, env-driven) |
| `lib/phase-test-logger.ts` | CSI phase diagnostic logging (added last session) |
| `*.test.ts` (12 files) | Unit tests for the above — part of the 132-test TS suite |

**Ports owned:** `5000` (dashboard UI/API, falls back 5001–5019), `5005` (sole ESP32 ingest), forwards to `5006` (AI sidecar, advisory only).

---

## 4. Shared contracts — `shared/`

| File | Role |
|---|---|
| `schema.ts` | Zod schemas shared by client + server; `NODE_ANCHORS` (N1/N2 geometry constant) |
| `bearing.ts` | Single source of truth for angle conventions (`theta` compass bearing vs. `angle` direction-of-travel) — "never inline the trig elsewhere" |
| `target-spatial.ts` | Spatial target types |
| `target-presentation.ts` | Presentation-layer target formatting (has its own test file in `server/lib/`) |

---

## 5. Dashboard — `client/` (React + Vite + Radix UI + Tailwind + Three.js)

| Area | Files |
|---|---|
| **Pages** | `dashboard.tsx`, `login.tsx`, `history.tsx`, `activity.tsx`, `report.tsx`, `not-found.tsx` |
| **Hooks** | `use-websocket.ts` (live `/ws` client), `use-auth.tsx`, `use-mobile.tsx`, `use-toast.ts` |
| **3D scene** | `RadialScene.tsx`, `point-cloud-3d.tsx`, `DirectionalNode.tsx`, `HumanMesh.tsx`, `MachineStatic.tsx` |
| **Signal views** | `aoa-heatmap.tsx`, `aoa-spectrum.tsx` (explicitly documented as *temporal* MUSIC signature, not spatial angle), `doppler-spectrogram.tsx` |
| **Vitals / identity** | `vitals-monitor.tsx`, `target-identity-card.tsx`, `ai-advisory-panel.tsx` (marked non-authoritative in the UI) |
| **Controls / metrics** | `control-panel.tsx`, `scan-controller.tsx`, `metrics-panel.tsx`, `node-features-card.tsx`, `distance-meter.tsx`, `top-bar.tsx` |

Talks to `server/` only — never binds UDP, never talks to the Python stack directly.

---

## 6. Python reference stack — `phantom/` (replay / offline DSP / tests — **not live**)

| File | Role |
|---|---|
| `protocol.py` | Wire-format parsing (mirrors the TS parser, used for replay/tests) |
| `ingest.py` | Frame ingestion logic |
| `dsp.py` | Deterministic DSP: phase unwrap, static-clutter suppression, Hampel filter, respiration filtering, motion energy, cross-node correlation |
| `recording.py` | JSONL session read/write |
| `runtime.py` | `python -m phantom.runtime replay|live` — `live` is retired, refuses to bind without `PHANTOM_ALLOW_RETIRED_LIVE_AUTH=1` |
| `api.py` | Reference HTTP API surface |
| `ai_status.py` | AI-sidecar status reporting |

Target of the 81-test (`6 skipped`) Python pytest suite in `tests/`.

---

## 7. AI sidecar (advisory only) — `scripts/ai_inference.py`

Listens on **UDP `:5006`** (and optionally a `rawSample` WebSocket feed) for frames forwarded by `server/lib/udp-server.ts`. Loads real extracted model weights from `ai model and densepose/model/` (see §8) and emits pose/identity/vitals back over WebSocket to the dashboard, **explicitly advisory** — code comments state it "can never originate or flip the dashboard's target presence."

Model stack actually loaded:
- `Enc` — contrastive CSI encoder (8→64→128), from `csi-embed-v2.safetensors`
- `PoseNet` — Conv1d pose regressor (56→64→128→128, fc→256→34) matching `pose_v1.safetensors` exactly
- `PresenceHead` — logistic head from `presence-head.json`, applied to the un-normalized embedding
- `LoRAAdapter` — per-node rank-4 room adapters (`node-1.json`, `node-2.json`)

Related/legacy Python UDP tools in `scripts/`:
- `udp_parser.py` — standalone ADR-018 + vitals parser (diagnostic/reference)
- `ruview-dashboard-bridge.py` — **explicitly marked LEGACY/REFERENCE**; a former dependency-free stand-in for a Rust backend that can't be built here; its motion math has since been ported natively into `server/lib/node-fusion.ts`. Its own docstring warns not to run it alongside the dashboard (both bind `:5005`).
- `csi-udp-relay.py`, `csi_capture.py`, `record-csi-udp.py`, `replay_to_dashboard.py`, `synth-csi-udp.py`, `serial_phase_logger.py`, `c6-presence-watcher.py`, `node_health_diagnostic.py`, `config_node.py`, `test_esp_csi.py`, `calibrate-threshold.ts` — capture, replay, calibration, and diagnostic utilities
- `csi_filter_pipeline.py` — DSP filter pipeline (mirrors `phantom/dsp.py`)
- `inspect_pose_weights.py` — verifies loaded weights against the safetensors files
- `build_academic_reports.py`, `build_detailed_final_report.py`, `build_how_project_detact_the_humen.py`, `edit_existing_phantomscan_doc.py` — documentation/report generation helpers

Python deps ([requirements-live-ai.txt](requirements-live-ai.txt)): `numpy`, `scipy`, `torch`, `safetensors`, `websocket-client`, `pyserial`.

---

## 8. Model weights — `ai model and densepose/`

A **separate git repository** (nested `.git/`, Git LFS objects) — i.e. effectively a submodule-style pointer, not first-party source, per the README's note that model weights are "never committed directly."

| File | Role |
|---|---|
| `model/csi-embed-v2.safetensors`, `model/model.safetensors`, `model/pose_v1.safetensors` | Trained weights (encoder, base model, pose head) |
| `model/csi-embed-v2-int4.bin`, `model/model-q2/q4/q8.bin` | Quantized variants |
| `model/presence-head.json`, `model/node-1.json`, `model/node-2.json` | Logistic presence head + per-node LoRA adapters |
| `model/training-metrics.json`, `model/csi-embed-v2-metrics.json` | Training/eval metrics |
| `model/config.json`, `model/model.rvf.jsonl` | Model config / RVF format dump |
| `wifi_densepose/__init__.py` | Python package wrapper |

This is the real, already-integrated counterpart of the upstream `ruvnet/wifi-densepose-pretrained` Hugging Face release (confirmed to exist: contrastive CSI encoder + presence head, LoRA per-node adapters, ~8 KB 4-bit-quantized) — already SISO-shaped, so no MIMO-simulation adapter is needed.

---

## 9. Tests

| Location | Covers |
|---|---|
| `server/lib/*.test.ts`, `server/auth/service.test.ts` (12 files) | TS unit tests — part of `npm test` (132 pass) |
| `tests/behavioral/**/*.test.ts` | Behavioral TS tests |
| `tests/*.py` (11 files: `test_csi_pipeline`, `test_occupancy`, `test_reporting`, `test_ai_smoke`, `test_authority_api`, `test_esp_capture_e2e`, `test_invariants`, `test_phantom_runtime`, `test_udp_ad018`, `test_node_health_diagnostic`, `test_phantom_cross_node_correlation`, `network_link_validation`) | Python pytest suite — 81 passed / 6 skipped (missing `torch` or needs a running dev server) |
| `firmware/esp32-csi-node/main/test/test_edge_dsp_pure.c` | Host-compiled (`gcc`) DSP-core test — independent of both `npm test` and `pytest` |

---

## 10. Documentation — `docs/`

- **`docs/adr/`** — 58 Architecture Decision Records. Only a handful are "current/binding" (ADR-051 runtime authority, ADR-054 fusion display-vs-authoritative, ADR-018 ESP32 wire format, ADR-057 single-node presence gate, ADR-056 gain-normalized balance, ADR-055 velocity boost, ADR-058 firmware SFO/PDD scope). The other ~50 describe a much more ambitious, largely unbuilt multistatic-mesh / distributed-consensus / post-quantum / mobile-app vision (`Proposed`/`Superseded` status) — **not** a description of the current two-node system.
- **`docs/research/`** — CSI phase/AoA research notes, RF graph-theory / topological-sensing series, CNN-LSTM deep-learning notes.
- Platform setup guides: `WINDOWS_ESP32_SETUP.md`, `UBUNTU_ESP32_SETUP.md`, `LOCAL_DEPLOYMENT.md`, `SPATIAL_CALIBRATION.md`.
- **Repo-root reports** (~35 files: `PHANTOM_SCAN_REMEDIATION_REPORT.md`, the `PhantomScan_*_Report.md`/`*_Fix.md`/`*_Analysis.md` series, `TEST_REPORT.md`, `AUDIT.md`, etc.) — point-in-time session/audit/fix records, not living documentation. `PHANTOM_SCAN_REMEDIATION_REPORT.md` is the authoritative "current state" summary; `README.md` is the authoritative architecture reference.

---

## 11. Build / dev orchestration

| File | Role |
|---|---|
| `package.json` | npm scripts (`dev`, `dev:dashboard`, `build`, `test`, `test:py`, `auth:seed`, `db:push`) and full JS dependency list (Express, React 18, Radix UI, Three.js/`@react-three/fiber`, Drizzle ORM, Zod, Vite 7, esbuild, tsx) |
| `script/dev-full.cjs` | Orchestrates dashboard + Python reference runtime together (`npm run dev`) |
| `script/build.ts` | Production build |
| `drizzle.config.ts` | Postgres/Drizzle ORM config (`DATABASE_URL`) |
| `vite.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `components.json` | Frontend build/style tooling |
| `pyproject.toml`, `pytest.ini`, `requirements-live-ai.txt` | Python project/test config |
| `build_and_flash.ps1` | Windows firmware build+flash helper |

---

## 12. Data / runtime artifacts

- `data/sessions/` — JSONL recordings (`session_header → csi_frame/heartbeat → derived_frame → session_footer`) + `_index.json`
- `data/` also holds the operator credential store (`PHANTOM_OPERATOR_SEED_PATH`) and audit log dir
- `recordings/`, loose `*.jsonl` files at repo root, `csi_recording_*.csv`, `test_capture.csv` — ad hoc capture dumps from prior sessions
- `dist/`, `build/` — build outputs
- `generated_reports/` — outputs of the `build_*_reports.py` scripts

---

## 13. Key environment variables (full table in [README.md](README.md#environment-variables))

Most load-bearing: `UDP_PORT` (5005), `PHANTOM_MOTION_THRESHOLD` (0.12, empty-room gate), `PHANTOM_BALANCE_CONTRAST` (2.0), `PHANTOM_STATIC_NODE_SOURCES` (source-pinning), `PHANTOM_ALLOW_LEGACY_CSI`, `PHANTOM_ALLOW_RETIRED_LIVE_AUTH` (must never be set alongside the dashboard), `PHANTOM_AUTHORITY_HOST/PORT/URL` (Python reference runtime address when run via `npm run dev`).

---

## 14. Architectural invariants worth knowing before changing any of the above

1. **`server/` is the sole live authority** — only it may bind UDP `:5005` or publish `/ws`. (ADR-051)
2. **AI sidecar output is advisory-only** — it is displayed, never allowed to originate or override the deterministic target/presence decision.
3. **Display balance ≠ authoritative balance** — `node-fusion.ts` deliberately emits two different numbers (`balance` for rendering, `balanceLinear` for ground truth) — don't collapse them. (ADR-054)
4. **1-D localization is intentional, not a limitation to "fix" with fake 2-D math** — two nodes cannot resolve `(x, z)`; the README calls out "no false 2-D claims" as a design principle.
5. **`ruview-dashboard-bridge.py` and the Python live-mode path are legacy** — don't run either alongside the dashboard; both would fight over `:5005`.
