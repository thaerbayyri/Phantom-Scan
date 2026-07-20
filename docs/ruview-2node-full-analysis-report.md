# RuView Two-Node ESP32 Analysis Report — ARCHIVED

> **⚠ ARCHIVED HISTORICAL BENCH DIAGNOSTIC — NOT THE LIVE RUNTIME.**
> This document originally analyzed `scripts/ruview-dashboard-bridge.py` (a standalone,
> bench-only Python UI) as if it were the live backend for the two-node ESP32-S3 setup.
> It is not. **The Node/TS server (`npm run dev`) is the sole live UDP `:5005` owner and
> canonical live path** (`docs/adr/ADR-051-runtime-authority.md`). The node coordinates,
> packet-parsing ownership, and "live backend" framing originally in this report's body
> are OBSOLETE and were removed in WP-13 (`PS-AUDIT-010`) — do not use them for a real
> deployment. `scripts/ruview-dashboard-bridge.py` still exists in the repo and still
> works standalone on a bench, but must never be run alongside the dashboard (both bind
> `:5005`).

Original date: 2026-07-07. Collapsed to this archived-note form: 2026-07-20.

## What this document was

A code-grounded walkthrough of the two-node RuView bench setup: two ESP32 boards
streaming raw CSI over UDP `:5005` to a Python bridge (`scripts/ruview-dashboard-bridge.py`),
which computed a simple 1-D "balance" estimate between the two nodes and served a
standalone HTTP/WebSocket UI on `:3000`/`:3001`. The full original walkthrough (packet
field lists, bridge internals, UI file inventory, operator command sequence) is preserved
in git history — see `git log -- docs/ruview-2node-full-analysis-report.md` for the
pre-WP-13 version if the bench-only bridge workflow is ever needed again.

## What is canonical now

- **Live runtime authority**: the Node/TS server, not the Python bridge —
  `docs/adr/ADR-051-runtime-authority.md`.
- **Live fusion math**: README.md's "Two-Node Live Localization (RuView balance method)"
  section and `server/lib/node-fusion.ts` (see also
  `docs/adr/ADR-054-fusion-display-vs-authoritative-balance.md`).
- **Geometry**: centered ±1.5 m / 3 m node separation — `shared/schema.ts` NODE_ANCHORS.
  The `[4.0, 0.0, 6.0]` / `[16.0, 0.0, 6.0]` coordinates that appeared throughout the
  original version of this document are obsolete bench-fixture positions, not the
  canonical geometry.

## Historical value preserved

A few ideas from the original bench analysis remain true and useful context for anyone
working on the live TS path:

- **CSI starvation is real and firmware-mitigated.** The ESP32 CSI engine only produces
  CSI when it receives OFDM frames; on a quiet network that can starve. The firmware's
  self-ping loop (`csi_start_self_ping()` in `csi_collector.c`) exists specifically to
  keep OFDM replies — and therefore CSI callbacks — flowing. This is still active in the
  current firmware and still one of the most important implementation details in the
  whole system.
- **The 1-D balance-ratio idea is the ancestor of the current live fusion math.**
  With only two nodes, true 2D/3D localization isn't possible; the original bridge (and
  the current live TS path) instead estimate which node sees more motion perturbation and
  place a target along the line between the two board anchors. The live implementation
  has since diverged (contrast exponent, display bias — see ADR-054) but the underlying
  1-D concept traces back to this bench work.
- **Distinct `node_id` + basic node-health supervision matter.** Duplicate node IDs
  prevent the host from distinguishing sensors; the adaptive controller's periodic
  packet-yield/RSSI/noise-floor/motion/presence sampling (still present in
  `adaptive_controller.c`) is what operators use during bring-up to confirm both boards
  are alive and streaming.

## Honest limits (unchanged in spirit, restated for context)

This bench setup did not do, and the current live system still does not do:

- true 2D room localization
- true 3D reconstruction
- limb-level pose inference
- robust learned multi-person counting

What a two-node RF setup can do well, then and now:

- prove both nodes are alive and CSI is flowing
- estimate gross motion and presence
- estimate breathing and heart rate with caveats
- produce a coarse 1-D moving-target estimate between the two nodes

That remains the correct, honest interpretation of what a two-node CSI setup provides.
