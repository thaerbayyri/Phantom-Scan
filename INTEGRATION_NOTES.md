> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Integration Notes

## Runtime Authority

The Python `phantom/` package remains the Milestone 1 authority for ingest, recording, deterministic DSP, runtime mode, and source-pinning security. The Node dashboard path is kept as a live UI compatibility surface.

Canonical live mode now uses Python as the sole UDP `5005` binder. Node follows `http://127.0.0.1:8789/api/sensing/frame` and relays authority state to the existing React `/ws` client. The Node UDP path remains available only with `PHANTOM_UDP_MODE=dev` and is mutually exclusive with canonical Python ingest.

## Source-IP Pinning

Both runtime paths now bind each observed `nodeId` to the first source address and port seen during the session.

- Python implementation: `phantom.ingest.SourcePinningGuard`
- Node implementation: `server/lib/udp-server.ts` `SourcePinningGuard`
- A mismatched source is rejected before it can update per-node buffers, fusion state, AI forwarding, or dashboard state.
- Python runtime records mismatches as `security_event` JSONL records with `event_type = node_source_mismatch`.

## Deterministic-vs-AI Rule

AI remains advisory in this checkout.

- Allowed AI contributions: pose metadata, confidence hints, vitals hints, adapter status, and debug context.
- Disallowed AI behavior: directly flipping the deterministic human/non-human decision.
- If AI dependencies or weights are unavailable, the runtime reports deterministic-only mode and continues.
- `scripts/ai_inference.py` emits `label: "unknown"` plus advisory metadata, not an authoritative human/mechanical verdict.

## AI Dependency and Boot Contract

The explicit AI dependency manifest is `requirements-live-ai.txt`.

The smoke probe in `phantom.ai_status.probe_ai_stack()` checks:

- `torch` import
- `safetensors` import
- `ai model and densepose/model/csi-embed-v2.safetensors` loading
- 8-feature input producing a 128-dimensional embedding

`model.rvf.jsonl` is inspection-only and is not used as a runtime model input.

## Calibration and Adapters

The runtime reports adapter presence for:

- `ai model and densepose/model/node-1.json`
- `ai model and densepose/model/node-2.json`

Session headers include AI status and active adapter metadata. Runs without adapter files are labelled through AI status as missing/uncalibrated rather than treated as calibrated evidence.

## Dashboard Passivity

The React dashboard can start/stop local host processing, set local data source, and update local processing config. It must not write to ESP32 nodes, serial ports, firmware, or upstream transport.

The normal dashboard surface no longer exposes hardware configuration or system shell controls. The server-side ESP32 configure endpoint is disabled for Phase 1 authority-follow mode.

## Honest Metrics

Live detection rate, respiration accuracy, heart-rate accuracy, CSI Hz, and midpoint localization are `[TO BE MEASURED]` until a real two-node hardware run records them.
