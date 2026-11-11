> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Target Test Plan

## Truthfulness regressions
- `no data -> state=none`
- `stale target -> state=stale`
- `single-node live target -> state=degraded`
- `demo target -> source_mode=synthetic`
- `websocket close/error -> cleared target state`
- `empty point cloud -> no fabricated 3D points`
- `unknown target -> no humanoid mesh unless truthful human classification exists`

## Tests added or updated
- Added `server/lib/target-state.test.ts`
  - source-mode mapping
  - empty truthful state
  - degraded single-node live target
  - synthetic demo target
  - stale demotion
- Updated `tests/test_esp_capture_e2e.py`
  - authenticated login/session bootstrap before protected ingestion and status endpoints

## Tests to add next
- Frontend render tests for `targetState.target_visible`
- Replay-stop clearing test
- Stale timeout test from real websocket messages
- Session switch and replay-file switch reset test for prior target scene state
- Python runtime parity tests for `phantom.runtime` emitting the same `target_state` shape
