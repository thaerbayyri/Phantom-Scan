# Milestone 1 Fix Plan

## Completed in this pass
1. Stabilize the current Node truth path before broader migration.
2. Remove fake target retention from the default live dashboard path.
3. Introduce a canonical temporary `target_state` contract.
4. Rewire dashboard rendering to consume `target_state`.
5. Update tests so authenticated endpoints are exercised through the real login/session flow.

## Next incremental steps
1. Mirror the same `target_state` contract in `phantom/` and make Python emit identical semantics.
   If `target_state.target_visible` is false, no target mesh should render.
   If `position_confident` is false, no confidently placed human target should render.
2. Move Node-side recording semantics toward the milestone JSONL schema instead of CSV/session hybrids.
3. Port the live ingest truth path from `server/lib/websocket.ts` into `phantom.runtime` without changing the UI contract.
4. Add explicit stale-timeout, disconnect, and replay-stop UI assertions on the frontend side.
5. Reduce dashboard payload coupling to legacy fields like `radialTarget`, `poseFrame`, and `vitalSigns`.
6. Add two-node health/state semantics to the Python authority path and only then hand off dashboard authority from Node to Python.
7. Ensure switching sessions or replay files resets prior target scene state.

## Deferred on purpose
- No ground-up rewrite of the Node live path
- No mandatory ML path
- No DensePose-first rendering
- No flight stack, GPS, IMU, MAVLink, or drone control additions
