> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Current State

Generated for the current checkout in `D:\WIFI csi\phanotm\phantom scan`.

## Inventory

- Branch: `main`
- Tracked Python/JavaScript/TypeScript/TSX files: 307
- Node runtime: `v24.13.0`
- Default `python --version`: failed because `python.exe` resolves to the Windows Store alias.
- Verified Python interpreter for this machine: `C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe`, version `Python 3.13.9`

Top-level tracked layout:

```text
.agents
.gitignore
.vscode
ai model and densepose
AUDIT.md
BOOTSTRAP.md
build_and_flash.ps1
client
components.json
data
design_guidelines.md
docs
drizzle.config.ts
dual_target_analysis.png
firmware
MILESTONE1_FIX_PLAN.md
new-implementation_plan.md
package-lock.json
package.json
phantom
postcss.config.js
pyproject.toml
pytest.ini
README.md
recordings
script
scripts
server
SETUP_AUDIT.md
shared
tailwind.config.ts
TARGET_RENDER_AUDIT.md
TARGET_TEST_PLAN.md
TARGET_VERIFICATION_REPORT.md
tests
tsconfig.json
vite.config.ts
```

## Active Entry Points

- Node live dashboard path: `server/index.ts`, `server/lib/udp-server.ts`, `server/lib/websocket.ts`
- Python Milestone 1 authority path: `phantom/protocol.py`, `phantom/ingest.py`, `phantom/dsp.py`, `phantom/runtime.py`, `phantom/api.py`
- AI sidecar path: `scripts/ai_inference.py`
- Firmware path: `firmware/esp32-csi-node`
- Dashboard path: `client/src`

## Protocol Truth

- Python ADR-018 parser uses `CSI_HEADER_SIZE = 32` and unpacks `<IBBBHIIbbBQI`.
- Node ADR-018 parser checks the 4-byte magic first, then schema version 1, then uses a 32-byte header.
- Node legacy parsing is still present as a fallback after the ADR-018 check.
- Heartbeats use magic `0xC51100A1` and are excluded from Node CSI sample conversion.
- The attached prompt's `28-byte: uint32 seq + 6xfloat32` / `DataView` claim does not match this checkout and is rejected for this implementation.

## Scope Guard

`rg "MAVLink|mavlink|drone|UAV|PSC"` finds references in documentation, research notes, one network validation script, and firmware SPSC comments. The active Phase 1 runtime paths inspected here do not require flight control, MAVLink, UAV, drone, GPS, or IMU behavior.

## Current Stabilization Deltas

- Python runtime now enforces per-session node source pinning for CSI and heartbeat packets.
- Node UDP compatibility path now mirrors source pinning before forwarding to AI or dashboard ingestion.
- Node dashboard ingestion now accepts both node IDs instead of silently dropping node 2.
- Runtime status now exposes AI availability and source-pinning state.
- AI dependency smoke probing fails closed to deterministic-only mode when dependencies or model files are unavailable.
- Python authority can expose `/api/status` and `/api/sensing/frame` on port `8789`.
- Canonical Node startup follows Python authority and does not bind UDP `5005`; Node UDP ingest is dev-only with `PHANTOM_UDP_MODE=dev`.
- Synthetic AI self-feed is opt-in through `PHANTOM_AI_SYNTHETIC`; canonical live runs report `synthetic_enabled: false`.
