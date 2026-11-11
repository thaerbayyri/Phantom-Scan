# Fused Room: Scaling Phantom Scan from 2 to 4 Nodes

**Project:** Phantom Scan — WiFi-CSI human sensing radar
**Branch:** `feat/two-node-radar-live-detection`
**Date:** 2026-08-24
**Status:** Verified live on real ESP32-S3 hardware — 243 tests passing, 0 type errors

---

## 01 — Why

A prior session deliberately aligned the whole stack to a "2-node hardware reality." Two new ESP32-S3 boards arriving on COM8/COM9 meant that ceiling — baked into the hardware-ID map, the fusion math, and the renderer — had to come out everywhere at once, without breaking the 2-node path the existing tests already depended on.

| Before | After |
|---|---|
| Node IDs 1–2 only; 3rd/4th packets silently dropped at ingest | Node IDs 1–4 mapped and ingested |
| Target placed by 1-D interpolation on a single N1–N2 line | Target placed by a weighted centroid across all active nodes |
| Dashboard drew one axis line between two beacons | Dashboard draws the full room boundary + a live signal-intensity floor |
| `node_mode`: `single_node` / `fused_two_node` | `node_mode` adds `fused_room` (3–4 nodes live) |

---

## 02 — Geometry

Anchors moved from a centered 3m N1–N2 line to the four corners of a 4m × 6m room, walked in perimeter order — the order the boundary renderer depends on to draw a clean quad instead of a crossed shape.

| Node | Port | Position (x, z) |
|---|---|---|
| N1 | COM5 | (-2, -3) |
| N2 | COM6 | (2, -3) |
| N3 | COM8 (new) | (2, 3) |
| N4 | COM9 (new) | (-2, 3) |

`shared/schema.ts` — `NODE_ANCHORS`, `ROOM_WIDTH_M = 4`, `ROOM_DEPTH_M = 6`.

---

## 03 — Algorithm

The existing 2-node "balance" placement turned out to be a weighted centroid in disguise. Expanding it revealed the exact generalization needed for N nodes — no new localization concept, just widening what was already there:

```
balance·n2 + (1−balance)·n1  ≡  Σ(wᵢ·anchorᵢ) / Σ(wᵢ)   where wᵢ = rᵢ^p
```

`r` = per-node gain-normalized CSI perturbation, `p` = contrast exponent. At N=2 this is exactly `fuseTwoNodeTarget`'s existing math; at N=3–4 it's the new `fuseNodeTargets` in `server/lib/node-fusion.ts`.

**Honesty preserved, not upgraded.** This is still a perturbation-proxy estimate, not RF ranging or multilateration — the same caveat culture the codebase already enforces. The dashboard's caveat text was updated to say exactly that: *"room-centroid estimate — not RF-ranged position."*

**What stayed untouched.** `fuseTwoNodeTarget` is byte-for-byte unchanged; the 2-node path (and its full existing test suite) runs exactly as before. `fuseNodeTargets` is a new, additive function used only when 3+ nodes are live.

---

## 04 — Verification

COM8 and COM9 were flashed with the existing firmware build (no firmware source changes needed — `CSI_NODE_ID` already supported the full 0–255 range) and provisioned as node 3 and node 4. The dev server was started, the scan launched from the browser, and the live feed was watched end-to-end.

- **4/4** node IDs accepted
- **2,960** live samples captured during the session
- **243** tests passing
- **2** follow-up UI bugs found live and fixed

Confirmed:
- All four node IDs ingested without the old "unmapped runtime node_id" rejection (`server/lib/udp-server.ts` — hardware-ID map extended, no other ingest logic changed).
- Target visibly tracked through the room — "Near N2" → "Near N3" → "Near N4" — with per-node distances updating live (e.g. N1 4.6m · N2 5.3m · N3 3.3m · N4 1.9m, changing frame to frame).
- Room boundary and signal-intensity floor grid rendered correctly around all four live beacons (`client/src/components/dashboard/RadialScene.tsx`).
- "FUSED ROOM" badge and "ROOM-CENTROID ESTIMATE" caveat confirmed correct after two follow-up fixes — both mode labels initially fell through to stale 2-node/single-node wording (`target-identity-card.tsx`, `shared/target-presentation.ts`).

---

## 05 — Reference check: RuView

Before building the fusion math, the sibling `RuView` project's own 4-node implementation was read for reference (`F:\RuView-0.8.2-esp32`), at the user's pointer. Its algorithm turned out to be the same 2-node limitation under a 4-node label — `compute_update()` only ever fuses the two lowest-numbered active nodes, matching this project's own `fuseTwoNodeTarget` exactly. Nothing to copy there.

Its renderer was the useful part: a Three.js floor-plane point grid colored by a spatial intensity array, plus dynamic per-node markers. That pattern was ported — not copied verbatim — into the new `SignalFieldGrid` react-three-fiber component.

---

## 06 — Files touched, by phase

| Phase | File | Change |
|---|---|---|
| firmware | `firmware/esp32-csi-node/` | No source change — existing build flashed to COM8/COM9, provisioned node-id 3/4 |
| schema | `shared/schema.ts` | 4-node hardware-ID map, room-corner anchors, `fused_room` mode, new `signalField` broadcast type |
| algorithm | `server/lib/node-fusion.ts` | New `fuseNodeTargets` — N-node weighted-centroid fusion |
| server | `server/lib/websocket.ts` | Ingest gate, mode resolution, room velocity tracking, signal-field grid computation |
| server | `server/lib/recording-export.ts` | CSV export generalized to 4 nodes (motion/distance/fps columns) |
| frontend | `client/.../RadialScene.tsx` | 4-color node map, `RoomBoundary`, `SignalFieldGrid` (adapted from RuView) |
| frontend | `shared/target-spatial.ts`, `target-presentation.ts` | `fused_room` presentation branch + honest caveat text |
| frontend | `use-websocket.ts`, `dashboard.tsx`, `point-cloud-3d.tsx` | `signalField` plumbed from socket to renderer |
| tests | `node-fusion.test.ts`, `recording-export.test.ts` | 4 new room-fusion tests; one anchor-geometry assertion updated |

---

## 07 — Open items

**Per-node trend arrows are inert in room mode.** Approaching/receding labels stay "stable" for all four nodes under `fused_room` — the 2-node axis-velocity hysteresis doesn't generalize cleanly to 2-D, and it wasn't the core ask. Position and speed are fully live; only the directional arrow-toward-a-specific-node label is deferred.

**Node 2 dropped out mid-verification.** The live window sampled during testing showed nodes 1, 3, 4 active but not 2 at that moment — worth a power/WiFi check on that board if all four need to be live simultaneously.

**Docs not yet updated.** `docs/WINDOWS_ESP32_SETUP.md` still describes the 2-board procedure only; the COM8/COM9 steps used in this session should be folded in.
