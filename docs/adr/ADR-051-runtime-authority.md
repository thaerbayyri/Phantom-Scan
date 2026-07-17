# ADR-051: Milestone-1 Runtime Authority is the Node/TS Server

**Status:** Accepted
**Date:** 2026-07-17
**Closes:** PS-AUDIT-001 (CRITICAL) from `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
**Decision maker:** Operator (remediation WP-1 decision gate, Option B)

## Context

The behavioral audit found runtime ownership of UDP `:5005` inverted relative to the
written Milestone-1 canon. The canon said the Python `phantom/` package solely owns UDP
`:5005` ingest and publishes derived frames on `:8789 /api/sensing/frame`, with the Node
dashboard as a follower. In the shipped code the inverse is true: `server/index.ts` starts
`server/lib/udp-server.ts` as the live `:5005` owner, and every `phantom/` runtime module
is marked `SUPERSEDED`. The documented Python-authority→Node-follower bridge does not
exist in `server/` source. Two options were presented: (A) restore the canon by moving
live ingest back to Python, or (B) bless the shipped reality and update the spec.

## Decision

**Option B.** The Node/TS server is THE AUTHORITY for Milestone-1 live operation:

- `server/lib/udp-server.ts` is the sole live binder of UDP `:5005` (no `reuseAddr`,
  hard `EADDRINUSE` on conflict).
- The authoritative derived-frame publisher is the TS server on `:5000`
  (WebSocket `/ws` broadcasts: `radialTarget`, `targetState`, `vitalSigns`,
  `targetIdentity`, `nodeFeatures`). There is exactly one publisher of derived frames.
- The Python package (`phantom.*`) is **reference, replay, and test tooling only**. Its
  live mode (`python -m phantom.runtime live`) and its `:8789 /api/sensing/frame` API are
  **retired from live operation**; they remain usable for offline replay
  (`python -m phantom.runtime replay`) and pytest targets.
- Any document that states "Python owns :5005" or "the dashboard follows
  `:8789 /api/sensing/frame`" is superseded by this ADR.

## Consequences

- Remediation work packages WP-4 (legacy-parser retirement), WP-5 (node identity),
  WP-7 (replay/out-of-order enforcement), and WP-8 (pinning hardening) land in
  `server/`, the process that actually runs live.
- WP-8 must make the retired Python live mode fail hard rather than silently co-bind
  `:5005` on Windows (`SO_REUSEADDR` removal / explicit live-bind guard), so no
  superseded module can silently claim the authority port.
- `phantom/` DSP geometry/timing fixes (WP-6) are reference-quality fixes, not live-path
  changes, and may alternatively delete the superseded fused path.
