> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Audit

## Real
- `server/`
  - Active Express auth, audit, HTTP API, WebSocket live pipeline
- `client/`
  - Active React dashboard shell and live WebSocket consumer
- `shared/schema.ts`
  - Current shared runtime contract surface
- `phantom/`
  - Emerging Python milestone runtime package
- `tests/`
  - Active Python regression suite
- `firmware/esp32-csi-node/main/`
  - Active ESP32-S3 firmware baseline

## Legacy
- `server/storage.ts`
  - Compatibility holdover, not the preferred auth/audit home
- `scripts/udp_parser.py`
  - Older parsing helper, not the canonical runtime path
- `scripts/tracking_processor.py`
  - Legacy processing helper outside the shared package plan
- `script/`
  - Suspicious duplicate tooling root; not treated as authoritative

## Placeholder or synthetic
- `server/lib/signal-processing.ts`
  - `DemoDataGenerator` remains valid only for explicit demo mode
- `scripts/ai_inference.py`
  - Optional-only path, not required for truthful milestone-1 sensing
- `ai model and densepose/`
  - Postponed assets, not part of baseline live truth

## Postponed
- `server/lib/udp-server.ts`
  - Keep as compatibility path, but not the milestone-1 Python authority
- `scripts/ruview-dashboard-bridge.py`
  - Transitional bridge, not baseline
- `scripts/reporting/`
  - Useful utilities, but not the canonical live runtime owner
- `firmware/esp32-csi-node/main/display_*`
  - Non-baseline UI/display path
- `firmware/esp32-csi-node/main/ota_*`
  - Postpone if it interferes with raw CSI baseline
- `firmware/esp32-csi-node/main/wasm_*`
  - Postpone from milestone baseline

## Node live path classification
- `server/lib/websocket.ts`: real, temporary truth source, fixed in this pass
- `client/src/hooks/use-websocket.ts`: real, fixed in this pass
- `client/src/components/dashboard/point-cloud-3d.tsx`: real, fixed in this pass
- `client/src/components/dashboard/RadialScene.tsx`: real, fixed in this pass
- `client/src/components/dashboard/HumanMesh.tsx`: real, but now gated by `target_state`
- `client/src/pages/dashboard.tsx`: real, fixed in this pass

## Generated and non-authoritative
- `dist/`
- `build/`
- `node_modules/`
- `.pytest_cache/`

## Immediate removals not yet performed
- No source files were deleted in this pass.
- Placeholder behavior was removed from the default runtime path instead of deleting all demo-capable code.
