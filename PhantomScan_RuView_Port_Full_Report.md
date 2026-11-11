# Phantom Scan 4-Node — RuView Port, Fixes and Live Validation: Full Report

Branch `feat/two-node-radar-live-detection` · commits `f121ce3` … `22f69d5` (14 commits, 71 files) · 17–18 Oct 2026

---

## 1. Summary

**Request.** Read the RuView project, find what is new, and update Phantom Scan's 4-node `fused_room` mode so it captures a human moving in the room; study how RuView uses AI for human detection; then run, flash and test everything, fix the bugs found, and explain how the detected position should be shown.

**Outcome in one paragraph.** All ten planned phases are built, tested and committed (TypeScript 334/334 tests, Python 141 passed / 5 skipped, type-check clean). The new firmware is flashed on all four boards and the whole system was run live. That live testing found and fixed 8 more real bugs (sidecar could never log in; AI said "walking, human 100 %" in any room; position snapped to anchor corners; track left the room; report timing; and others). **The decisive finding is negative:** in the scripted scan, the per-node perturbation signal **does not separate an empty room from an occupied one** in this setup. Presence and position therefore cannot yet be trusted as human detection. The next step is a labelled dataset recording, not more threshold tuning.

| Area | State |
|---|---|
| Code, unit/integration tests | Done, green |
| Firmware | Built with ESP-IDF 5.5.2 (E:\Espressif), flashed to nodes 1–4, verified on serial |
| Live system run (4 real nodes) | Done: ingest, fusion, recorder, AI sidecar, dashboard login |
| Human detection quality | **Not achieved** — signal does not discriminate (see §7) |
| Per-room ML models | Training pipeline done; **no models yet** (needs labelled recordings) |

---

## 2. What RuView contributes (research findings)

Surveyed `ruvnet/RuView` (main @ `a1ca023`, firmware v0.8.14, 2026-10-13).

**Useful ideas ported**
- CSI must come from one transmitter, and that filter must run **before** the 50 Hz rate gate (ADR-345/060).
- Per-node adaptive baseline with time constants derived from the measured frame rate (`smooth_and_classify_node`), room-level debounce.
- Amplitude-only fusion across nodes (cross-node phase is not calibratable — ADR-345).
- Per-node AGC-normalised link motion metric; placement check (`geometric_diversity`).

**How RuView actually uses AI** — almost none of its live detection is ML:
- Presence, motion, vitals and falls are deterministic DSP (thresholds, baselines, debounce) on the ESP32 and in the server.
- The only ML in its live server path is a per-room 15-feature logistic regression (ADR-048) that, when loaded, *overrides* presence (we deliberately did not copy that).
- Models trained on real ESP32 data are weak by its own metrics: people-count CNN 62.3 % (trained only for 0 vs ≥1; confidence uncorrelated with correctness), pose 3 % PCK@20. The headline "92.9 % PCK@20" claim was retracted; strong numbers (83 % pose) come from the public MM-Fi dataset (3 antennas × 114 subcarriers) and do not transfer to 1-antenna ESP32-S3.
- Its own conclusion: per-room calibration with ~50–200 labelled samples is what works.
- Defects in its count cog that we avoided: normalisation applied in training but not at runtime; window layout read transposed.

---

## 3. Starting state of Phantom Scan (verified before changing anything)

Root causes that hurt tracking a moving person:
1. Firmware forwarded CSI from **any** transmitter (promiscuous MGMT+DATA, no source-MAC filter) — each node's "motion" mixed unrelated links.
2. `fused_room` gate was `max(motion) ≥ 0.6`, tuned on the old 2-node rig; saturated on ~half of 4-node ticks.
3. Centroid weighted by raw perturbation → empty-room floor common to all nodes pulled the target to the centre.
4. Kalman filter defects: process noise not scaled with time, started at (0,0), wrong covariance update, could lock out after a fast move, not reset when a node dropped.
5. `isMoving` hard-coded `true` in fused modes → "idle" unreachable; a still person vanished after 5 s.
6. Ingest: first 64 raw CSI entries (including DC/guard nulls); I/Q read real-first (ESP-IDF stores imaginary first); room geometry hard-coded 4 × 6 m.
7. AI sidecar: every frame ingested twice (real UDP + a synthetic noisy vector), one global 5 Hz limit for all nodes, fake 14 rpm / 72 bpm vitals shown as real, hard-coded `person_count=1`, a tautological F1 test, UDP parser reading v1 packets with the legacy header layout.

---

## 4. What was built (by phase)

### Phase 1 — Framework fixes (`f121ce3`)
- Fused localisation no longer depends on the ISAR toggle (MUSIC/point-cloud/DBSCAN extracted into `runMusicTracking`).
- Micro-Doppler classifier now fed the clutter-removed residual (was fed the background *mean*).
- One `BackgroundSubtractor` per node (was shared across interleaved nodes).
- Hardware queue bounded per node (8) so a 4-node burst cannot pin the global cap.
- `targetDebug` covers all anchored nodes; node live/stale transitions logged once; fused Kalman reset when the active node set changes.
- `positionBasis` gains `fused_room_centroid`.

### Phase 2 — Configurable room geometry (`148db4d`)
- `server/lib/room-geometry.ts`: loads `PHANTOM_ROOM_CONFIG` or `config/room.json` (template `config/room.example.json`); zod-validated (finite dims ≤ 50 m, node ids 1–4, anchors inside the room, no collinear layouts); RuView-style `geometricDiversity` check.
- Also fixed a latent bug: the signal-field grid used the *width* cell size for depth.
- Not hard-coded any more. **You must still enter your real node positions** (default = old 4 × 6 m corners).

### Phase 3 — Kalman correctness (`20c7a13`)
First-measurement initialisation; process noise scales with gap length; correct velocity-covariance update; per-axis re-init after 5 consecutive rejected fixes (no lock-out); rejected-count exposed; also fixed a bug that wiped the fused target every tick when ISAR was off.

### Phase 4 — Ingest (`2498816`)
`csi-subcarriers.ts`: LLTF block only, 51 data subcarriers (DC, guards and the ESP32-S3 invalid first word dropped), constant length across frame types, **imaginary-first** byte order (confirmed in ESP-IDF docs).

### Phase 5 — Adaptive baseline presence (`41fb6d2`, later revised)
`node-baseline.ts` per-node tracker, `RoomPresence` debounce, AGC-normalised perturbation, `computeRadialTrends`, still-person hold (`idle`), Kalman-based velocity. Revised twice after live testing (see §6).

### Phase 6 — Firmware MAC filter (`8ea592b`, fixed in `5db93a9`)
`csi_filter_pure.{c,h}` (host-testable), filter applied first in the CSI callback, NVS blob `filter_mac` (absent = auto AP BSSID, FF:… = off), `esp-flash.py --filter-mac`, refreshed on GOT_IP **and** STA_CONNECTED (roam fix).

### Phase 7 — AI sidecar & advisory path (`f6ec7fe`, `74ee2c3`)
Correct v1 parser (`phantom/protocol.py` + `phantom/subcarriers.py`), no double-ingest, per-node 5 Hz throttle, vitals `null` when unreliable, pose/presence-head/LoRA opt-in, schema-validated advisory messages, AI panel redesigned, a **real** F1 invariant test (extreme AI advisories leave every deterministic broadcast identical), sidecar login (`PHANTOM_AI_USERNAME/PASSWORD`, env only).

### Phase 8 — Dataset capture (`4096bdd`)
`dataset-recorder.ts` (per-node 51-subcarrier amplitudes, rotating JSONL, validated ids), WS `startDatasetRecording/stopDatasetRecording`, dashboard "Training Data Capture" panel with 10 s countdown, `docs/DATASET_PROTOCOL.md`.

### Phase 9 — Per-room activity classifier (`698f6aa`)
15 shared window features, leave-one-recording/day-out logistic regression vs a majority baseline, a motion-heuristic tree and a 50-run shuffled-label null; **exports only if it beats all three**; numpy-only runtime.

### Phase 10 — Per-room people-count CNN (`a927dac`)
RuView `CountNet` re-implemented with its two bugs fixed (single shared normalisation; asserted channel-major layout); temperature-scaled confidence (ECE reported); grouped cross-validation; same export gates; classes 0 / 1 / 2+.

---

## 5. Live hardware work

- **Toolchain.** The old `C:\Espressif` was gone. Used your `E:\Espressif` (ESP-IDF v5.5.2); repointed its Python venv (`pyvenv.cfg`) from `C:` to `E:`. A partial C: download I started remains (delete blocked) — safe to remove.
- **Build.** First-try clean build, 0xccf00 bytes (60 % of the app partition free), into `firmware/esp32-csi-node/build_filter/` (gitignored). Your old `build/` untouched.
- **Flash.** COM8 = node 4, COM9 = node 2, COM5 = node 1, COM6 = node 3. App/bootloader/partition table/otadata only — **NVS preserved** (node ids, Wi-Fi, target IP). All hashes verified.
- **Serial verification.** Node ids held; each board pinned the filter to the router BSSID `78:8c:b5:fc:da:ba`; `mac_skip` > 0 (~⅓ of frames correctly dropped).
- **Network.** Boards target 192.168.1.155; the PC was initially on 172.16.0.x (sends failed). After joining `Thaer_2.4Ghz` all four streamed.

---

## 6. Live testing — what it found and what was fixed

### 6.1 Functional run (isolated test instance, temporary operator account)
Verified: login, WebSocket auth; 4 nodes active in `fused_room`; `fused_room_centroid` basis; custom room geometry reached nodes and signal field; dataset recorder wrote 270 frames (~67 per node) and refused `../evil`; AI isolation (AI said human 100 % while the real classifier said 0.36 and was unaffected).

**Bugs found and fixed:** (1) sidecar got HTTP 401 on every connection (login added to the server after the sidecar was written) → it now logs in; (2) the heuristic activity said "walking, human 100 %" in any room because absolute thresholds (0.02/0.005) are far below real amplitude scale (mean ≈ 13, 10–20 % fluctuation at rest) → now unit-free, judged against each node's **calibrated empty-room level**, `unknown` until "Calibrate Empty Room" is pressed (verified: unknown/0.5 before, stationary/0.52 after).

### 6.2 Code review of the first ten phases (read-only subagent) → `5db93a9`
Recorder I/O error could escape into the UDP handler; `stop()` could stick; stale baseline when a node returned; firmware filter not refreshed on roam. All fixed with tests. Left as a design trade-off: a perfectly still person is absorbed into the baseline after ~2 min (bounded on purpose).

### 6.3 Scan `test_2` and `test_3` analysis → `7651659`
| Finding | Evidence | Fix |
|---|---|---|
| Position stuck on corner anchors | 39 % of visible rows within 8 cm of a corner; node 2's corner held 40+ s | Weights were relative **rise**, so a quiet-baseline node won; now absolute **excess**, exponent 1.0 |
| Track outside the room, 8 m/s | z = −3.66 in a ±3 m room | `FusedPositionKalman.constrain()` clamps to the anchor box, caps speed at 4 m/s |
| "Calibrate Empty Room" ignored by the real detector | only reached the AI | Also restarts node baselines, room presence, held target |
| Recordings could not be judged | trend only for N1/N2, no tier | New columns: `room_tier`, `excess_n1..4`, `trend_n3/n4`, `position_uncertainty_m` |
| Session report nonsense (2 s, 57,516 m) | ms timestamps treated as s | Normalised; data clock defines start/end; dropout steps capped |

### 6.4 Scripted scan `scan4` (285 s, your ground-truth phases) → `22f69d5`
Fix results: corner snapping 39 % → 0–7 %; positions inside x ±2 / z ±3; speed ≤ 4 m/s; trends now vary on all four nodes; report now correct (288 s, 214 m, 117 events).

Then a further bug: the baseline ignored every sample above the smoothed level, which parks it on the lower edge of the noise. Replaced by a mean-tracking baseline plus per-node scatter; tiers use z = excess / scatter (provisional 4 / 7 / 14). Correct on synthetic noise (tests), **but see §7**.

### 6.5 Position display
The estimate is a coarse perturbation centroid. It is now drawn as a translucent disc + ring around the marker sized by `positionUncertaintyM` (heuristic: ≈ 35 % of the short room side, shrinking with evidence, growing +50 % when one node dominates) and labelled "room-centroid estimate ~ within X m" (≈ 1.3–1.7 m in the scan). It is a drawing aid, **not** a measured error. Not yet viewed in a browser.

---

## 7. The key negative result — human detection quality

Per-phase mean raw perturbation (nodes 1–4) from the recorded scan:

| Phase (ground truth) | N1 | N2 | N3 | N4 |
|---|---|---|---|---|
| empty_1 | 0.187 | 0.144 | 0.192 | 0.188 |
| centre, still | 0.159 | 0.160 | 0.169 | 0.185 |
| walking | 0.158 | 0.172 | 0.190 | 0.163 |
| empty_2 | 0.179 | 0.160 | 0.222 | 0.244 |

- Empty-room values equal or exceed occupied values; the signal also drifts 0.11 → 0.27 within a minute with nobody present.
- Replaying the series through the fixed tracker gives 91–100 % "moving or active" in **every** phase, empty included (both empty phases showed 88 %/100 % visible targets live).
- Standing next to nodes 1, 2, 3 and 4 produced nearly the same location (≈ x −1, z +2.4): the position does not follow where a person stands.
- Caveat: I could not verify the empty phases were truly empty (nobody next to the boards, nothing else moving).

**Conclusion.** The 1.5 s per-node amplitude-perturbation metric carries no usable human signal in this installation at ~10–20 frames/s per node. Retuning cannot fix this; the metric must be replaced or supplemented, using features evaluated offline on labelled data (the CSV does not store per-subcarrier amplitudes, which is why the dataset recorder exists).

---

## 8. Known issues and open items

1. **Detection quality** (§7) — record the labelled dataset (`docs/DATASET_PROTOCOL.md`: empty, empty+fan, still, walking, 2 people; ≥3 sessions, ≥2 subjects), then evaluate better features / train the activity and count models.
2. **Frame rate** — 10–20 fps per node (peaks 55), below the ~20 the window assumes; cause (router vs. four boards sharing the channel) not isolated.
3. **Presence thresholds** (4/7/14 z) are provisional; the 5-minute empty-room run (`npx tsx scripts/calibrate-threshold.ts --seconds 300`) has not been done.
4. **`config/room.json`** holds no real measurements yet.
5. **AI panel** needs `PHANTOM_AI_USERNAME` / `PHANTOM_AI_PASSWORD` for the sidecar; the AI heuristic reads `unknown` until "Calibrate Empty Room".
6. **Untested:** node drop-out/return live, a still person's `idle` hold live, the trained models (none exist), the display in a browser.
7. A perfectly still person is absorbed into the baseline after ~2 min (deliberate, bounded); one classifier-veto tick resets a held target.
8. Pre-existing, left alone: `npm run dev` also starts the old Python authority that collides on UDP 5005 — use `npm run dev:dashboard`.

---

## 9. Verification status

| Check | Result |
|---|---|
| `npm test` | 334 / 334 |
| `python -m pytest tests` | 141 passed, 5 skipped (the 4 live-server tests fail only while another dashboard holds ports 5000/5005) |
| `tsc --noEmit` | clean |
| Firmware build | clean; gcc host test file written (`test_csi_filter_pure.c`) but **not compiled** — no gcc on this machine |
| Live run on 4 real boards | functional paths verified; detection quality not achieved |

---

## 10. Commits

| Commit | Content |
|---|---|
| `f121ce3` | Phase 1 framework fixes (**also contains your 12 staged root `.jsonl` deletions — see §11**) |
| `148db4d` | Phase 2 configurable geometry |
| `20c7a13` | Phase 3 Kalman fixes |
| `2498816` | Phase 4 LLTF subcarriers, I/Q order |
| `f6ec7fe` | Phase 7 AI sidecar fixes |
| `8ea592b` | Phase 6 firmware MAC filter |
| `41fb6d2` | Phase 5 adaptive baseline, hold, trends |
| `4096bdd` | Phase 8 dataset recorder + panel |
| `698f6aa` | Phase 9 activity classifier |
| `a927dac` | Phase 10 count CNN |
| `5db93a9` | Review fixes |
| `74ee2c3` | Sidecar login + relative heuristic |
| `7651659` | test_3 fixes, recording columns, uncertainty display, report timing |
| `22f69d5` | Noise-aware z-score tiers |

New files: 29 (see `git diff --name-status f121ce3^..HEAD`), including `room-geometry`, `csi-subcarriers`, `node-baseline`, `dataset-recorder` (+ tests), `csi_filter_pure.{c,h}`, `phantom/{features,dataset,activity_model,activity_train,count_model,count_train,sidecar,subcarriers}.py`, `scripts/train/*`, `docs/DATASET_PROTOCOL.md`, `config/room.example.json`, the dataset panel.

---

## 11. Disclosures (things that were not part of the request)

- **Deleted files committed.** `f121ce3` included 12 root-level `*.jsonl` deletions that were already **staged** in your working tree at the start (−5,869 lines). They are recoverable from git history (`git show f121ce3^:<file>`); `.gitignore` already treats root `.jsonl` as stray output.
- **Unreviewed edits committed.** `7651659` staged all of `server/lib` and so also committed your earlier uncommitted guards in `signal-processing.ts`, `tracking.ts`, `vitals.ts` (NaN/empty-input hardening; tests pass).
- **System changes.** Installed `safetensors==0.5.3` into Python 3.11 (already pinned in `requirements.txt`); edited `E:\Espressif\python_env\idf5.5_py3.11_env\pyvenv.cfg`; partial ESP-IDF download left in `C:\Espressif`.
- **Login lockout (429)** was caused by my test dashboard on port 5000; fixed by stopping it and starting the real one. Your operator account/password were not modified or stored; I used the password once to verify login.
- Test data written under `data/sessions/` (scans `test_2`, `test_3`, `scan4`) and the temporary test operator file live in the scratchpad only; the `e2etest` dataset was deleted.
