> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Target Render Audit

## Live data flow
1. `server/lib/websocket.ts`
2. shared WebSocket messages from `shared/schema.ts`
3. `client/src/hooks/use-websocket.ts`
4. `client/src/pages/dashboard.tsx`
5. `client/src/components/dashboard/point-cloud-3d.tsx`
6. `client/src/components/dashboard/RadialScene.tsx`
7. `client/src/components/dashboard/HumanMesh.tsx` or `DirectionalNode.tsx`

## Fake or misleading target paths found
- Server empty-queue fallback generated demo samples when the selected source was `esp32` or `hardware`.
- Server motion-gate idle path emitted a fallback `radialTarget` specifically to keep the avatar visible.
- Client 3D view generated demo point-cloud geometry whenever the live point array was empty.
- `RadialScene` rendered a human mesh for `unknown` targets, which made stale or weak detections look like active humans.
- Disconnect and stale conditions did not clear all target-facing client state.

## Fixes applied
- Added canonical `targetState` contract to `shared/schema.ts`.
- Added `server/lib/target-state.ts` to build explicit truthful state.
- Removed default empty-queue demo fallback from the live `esp32` and `hardware` path.
- Removed server-side idle-avatar fallback target emission.
- Removed client-side fabricated point cloud generation.
- Gated all target-object rendering on `targetState.target_visible`.
- Demoted unknown visible targets to `DirectionalNode` instead of a humanoid mesh.
- Cleared point cloud, target, pose, vitals, and identity state on stop, source change, stale/no-data, close, and error conditions.

## Canonical temporary contract
- `state`: `none | stale | idle | moving | degraded`
- `source_mode`: `live | replay | synthetic`
- `node_mode`: `single_node | fused_two_node`
- `target_visible`
- `position_confident`
- `position`
- `bearing_deg`
- `range_m`
- `motion_score`
- `confidence`
- `last_update_ms`
- `data_age_ms`
- `stale`
- `reason`

## Current semantic choice
- The current Node live path is treated as single-node for truthful live sensing.
- Therefore a valid live target from the current Node path emits `state=degraded` and `node_mode=single_node`.
- Explicit demo mode still emits `source_mode=synthetic`.
