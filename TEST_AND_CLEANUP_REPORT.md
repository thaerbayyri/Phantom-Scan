# Test & Cleanup Report — 2026-07-08

All numbers below come from commands executed on this machine on 2026-07-08 against the
uncommitted working tree on branch `feat/two-node-radar-live-detection`.

## Scope

This session's feature work, which this pass validates:

- **Fusion tuning**: motion window 3 s → 1.5 s (`MOTION_WINDOW_MS`, env `PHANTOM_MOTION_WINDOW_MS`);
  balance contrast exponent `r2^p/(r1^p+r2^p)` with p=2 (`PHANTOM_BALANCE_CONTRAST`); client lerp/snap tightened.
- **Coordinate conventions**: `shared/bearing.ts` single source of truth (compass `theta`, travel `angle`);
  motion-arrow/heading decode unified; N/S grid labels corrected; bearing text de-mirrored.
- **Firmware feature-state ingest**: `0xC5110006` parsed in `udp-server.ts`, broadcast as `nodeFeatures`,
  rendered in the Board DSP card; per-node source guard extended with `packet_kind`.
- **UI cleanup**: fabricated demo plots removed (honest NO LIVE STREAM states); info de-duplicated
  (bearing once, caveat once); plots moved to the left column at full width; single scroll context;
  TopBar single-row; ControlPanel sidebar chrome removed; keyboard footer folded into Settings.
- **Docs pass**: RUN.md and both setup guides rewritten to the dashboard-owns-:5005 runtime;
  historical records bannered; `provision.py` → `esp-flash.py` references fixed.
- **Firmware**: early node_id capture (`csi_collector_set_node_id` before WiFi init) added to
  `firmware/esp32-csi-node` (needs reflash to take effect; current boards already run a lineage with it).

## Clean-code actions (this pass)

| Action | Item | Justification |
|---|---|---|
| Deleted | `client/src/components/dashboard/system-control-panel.tsx` | 0 importers (verified by grep before deletion) |
| Deleted | `client/src/components/dashboard/signal-traces.tsx` | 0 importers |
| Deleted | `server/lib/passive-scanner.ts` | 0 TS importers; the live scanner is Python `server/passive_scanner.py` |
| Removed | `computeNodeMotion` + `pstdev` in `server/lib/node-fusion.ts` | Test-only; production uses `computeNodeMotionFromMatrix`. Tests ported to the matrix API (scale/zero-motion assertions preserved) |
| Removed | `trackedTarget` state slice in `client/src/hooks/use-websocket.ts` | Set from WS but never read by any component; server broadcast untouched |
| Untracked | `scripts/__pycache__/*.pyc`, `tests/__pycache__/*.pyc` | Build artifacts committed before the ignore rule; `git rm --cached` |
| Untracked | `.claude/settings.local.json`, `firmware/esp32-csi-node/.claude/settings.json` | Machine-local agent settings; `.claude/` + `**/.claude/` added to `.gitignore` |
| Added | `npm test` and `npm run test:py` scripts | `npm test` previously failed (no script); pytest was unrunnable from package.json |

Deliberately NOT touched: the gated `poseFrame`/HumanMesh volumetric chain (off by design via
`canPresentVolumetricTarget() === false`); bench scripts in `scripts/` (see Known debt).

## Test matrix

| Step | Command | Result |
|---|---|---|
| Typecheck | `npm run check` (tsc) | **clean** — 0 errors |
| TS unit suites | `npm test` (10 files: bearing, node-fusion, target-state, target-spatial, target-presentation, udp-server, recording-export, pose-anchor, join-groundtruth, auth service) | **91 passed, 0 failed, 0 skipped** (8.2 s) |
| Python suites | `npm run test:py` (pytest, 9 test files) | **82 passed, 1 skipped, 0 failed** (119 s; skip = hardware/recording-conditional in test_esp_capture_e2e) |
| Production build | `npm run build` | **clean** — client bundle built in 31.7 s, server `dist/index.cjs` 1.1 MB |
| Post-cleanup regression | `npm test` re-run after all deletions | same 91/91 (one test adapted from the removed scalar API to the matrix API; assertions preserved) |

## Live hardware verification

Environment: two ESP32-S3 boards, operator's 2.4 GHz network (SSID redacted, PS-AUDIT-012), host 192.168.1.155, dashboard `npm run dev` on :5000.

- **Node identity confirmed from boot banners** (serial DTR/RTS reset): **COM5 = node_id 1**
  (IP 192.168.1.133), **COM6 = node_id 2** (IP 192.168.1.238). Boot log shows
  `node_id cached pre-WiFi: 1` — the pre-WiFi capture defense is active on-device.
- **Ingest**: `[UDP] CSI Receiver listening on 0.0.0.0:5005`; steady **~200 packets / 5 s**
  (~40 pkt/s aggregate), RSSI −23…−38 dBm; firmware serial `medium tick: yield=41-43pps` per board.
- **Spoof drill (source-pinning guard)**: a local sender spoofing node_ids 1 and 2 from 127.0.0.1
  for 8 s (~640 packets) was fully rejected against the pinned board sources; console showed only
  **4 rate-limited `[UDP][SEC]` lines** (≤1 per node per 5 s) including the duplicate-node_id
  provisioning hint; the real stream continued uninterrupted (413→416 packets/5 s during the attack).
- **Board DSP card**: shows the honest "no feature-state packets" empty state — correct, because the
  currently-flashed firmware runs edge_tier=0 (raw CSI + heartbeat only; no 0xC5110006 emitter).
  The ingest path itself is covered by unit tests (parse fixture + guard tagging).
- **UI spot-checks** (current build): plots render in the left column at full width; no fabricated
  data anywhere (AoA spectrum/heatmap/doppler show NO LIVE STREAM when their streams are absent);
  bearing appears only on the Distance Meter; the on-axis caveat only on Target Identity;
  one scroll context; TopBar single row.

## Known debt (honest)

1. **Gated volumetric chain**: `poseFrame` plumbing (server broadcast → client → HumanMesh AI branch)
   is unreachable while `canPresentVolumetricTarget()` is hardcoded false. Kept by design; delete or
   enable when a validated pose model exists.
2. **Orphan bench scripts** (no doc/code references — candidates for a future decision, not deleted):
   `scripts/csi-udp-relay.py`, `replay_to_dashboard.py`, `synth-csi-udp.py`, `start_live_capture.py`,
   `test_esp_csi.py`, `c6-presence-watcher.py`.
3. **Conditionally-skipped Python e2e**: `test_esp_capture_e2e.py` skips without live recordings/dev
   server; unlock by running with the dashboard up and recorded sessions present.
4. **`bearing_deg` semantics changed** this session to compass convention (0=N, 90=E). Wire-only —
   nothing persisted the old values — but note it when comparing against pre-change screenshots.
5. **Feature-state live path unverified on hardware**: needs boards flashed with a 0xC5110006-emitting
   firmware (RuView lineage / edge tier with adaptive controller). Unit-tested only.
6. **Everything is uncommitted**: ~35 modified + new files on `feat/two-node-radar-live-detection`,
   including the earlier interrupted push request. Commit + push is the next outstanding action.

## Bottom line

Typecheck, 91 TS tests, 82 Python tests, and the production build are all green after removing
three orphan modules, a dead export, a dead state slice, and four tracked artifacts. Live two-node
ingest, source-pinning security, and the cleaned UI were verified against real hardware.
