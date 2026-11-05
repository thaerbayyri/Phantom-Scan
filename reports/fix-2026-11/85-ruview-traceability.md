# 85 — RuView traceability (state at Gate 1, after Wave 1)

**Source quality.** The RuView references below come from the **task's digest of an outside research report** (secondary: PR/issue text and release notes). **I did not read any RuView source (GitHub/Hugging Face) in this session**: no web access was used, so every source column is `[UNVERIFIED — from the digest, not read at source]`. Per the rules, I port **methods and invariants, never numbers**, and cite by PR/issue/ADR *filename or number as given*, noting that ADR numbers collide. The single RuView artifact I did read is the one in the repo (`ai model and densepose/model/`), whose numbers I measured myself (presence head: ‖w‖ = 3.668, bias = 8.188).

## Adopt list

| # | idea (digest) | RuView source `[UNVERIFIED]` | our file(s) | test(s) | result / status |
|--|--|--|--|--|--|
| 1 | Drift-controlled evaluation: occupied-sensitivity control so an always-"absent" model cannot pass; false alarms and misses reported separately; abstentions counted as misses; `null`, never a fabricated zero | issues #1440, #1952; PR #2424, #2256 | `scripts/presence_eval/twonode.py`, `stats.py`, `jsonutil.py`; `scripts/eval-presence-on-datasets.ts`, `scripts/accuracy/auc-bootstrap.ts` (PS-FIX-04) | `tests/test_presence_eval_controls.py` (11), `scripts/accuracy/__tests__/auc-bootstrap.test.ts` (6) | **done for the harness.** On our data: the always-absent control is rejected; empty-vs-empty gate C4 (upper bound ≤ 0.65) fails for **all 15** candidates. *Not done:* "interleaved empty/occupied blocks within the same hour" is a **recording** protocol (Wave 4, `07-next-recording-protocol.md`). |
| 2 | PHY/identity guards: never mix subcarrier count, sig_mode/bandwidth, transmitter; key CSI per (receiver, transmitter); audit RSSI byte offsets | issues #1440, #1348; PR #1828, #2286/#2309 | prerequisite only: header `capture{channel,bandwidthMHz,bssid,…}`, `geometryHash`, `recorder` (PS-FIX-03) | `server/lib/dataset-recorder.test.ts`, `tests/test_record_dataset.py` | **UPDATE after Wave 2 — PS-FIX-08 done in shadow mode** (`11-PS-FIX-08.md`): RSSI byte offset audited against the firmware serializer with one hand-built frame pinned in both test suites (`tests/test_csi_header_offsets.py`, `server/lib/phy-guard.test.ts`; no offset error); `server/lib/phy-guard.ts` locks (subcarriers, channel, freq) per node and only counts/logs (a test proves it never drops a frame). Bandwidth/sig_mode/transmitter are not in our header (PS-FIX-36). Original status text follows: **not started** (PS-FIX-08, Wave 2). Per-frame PHY is still not recorded; those fields are operator-stated only. |
| 3 | Rate-truthful timing: measure rate from timestamps; windows in seconds; room-level hysteresis | ADR-347 / PR #1762, #1793 | docs corrected to the measured rate (PS-FIX-05); inventory tool measures rate per node | `tests/test_presence_eval_inventory.py` | **partly**: the documentation truth is fixed; **PS-FIX-07 measured the real arrival process** (`12-PS-FIX-07.md`: ~65 fps/node ≈ 2 frames per ping interval, irregular, no duplicates); code changes (rate-scaled timing, hysteresis) are PS-FIX-12 (Wave 3, not started). |
| 4 | Fail-closed outputs: `presence=false ⇒ people=0`, vitals abstain with reason, no frozen-snapshot re-broadcast, explicit freshness | PR #1762, #1914, #2379, issue #1950 | — | — | **not started** (PS-FIX-15, -16, Wave 3, approval required). |
| 5 | Firmware robustness: bounded calibration, CSI-stall watchdog, bounded ping timeout, 802.11b self-ping trap | PR #2246, #2198; v0.8.13-esp32; issue #2287, PR #2309 | — | — | **not started** (PS-FIX-14, Wave 3, host-tested only, not flashed). Note from reading our firmware: the ping timeout is already bounded (20 ms) and the interval is 30 ms (`csi_ping_pure.h`). |

## Experiment-before-trusting list

| idea | RuView source `[UNVERIFIED]` | status |
|--|--|--|
| Empty-room prior with negative-only authority | ADR-355, PR #1826/#1840/#2407 | **skipped by Thaer's instruction** (PS-FIX-10); not built |
| Fan/periodicity rejector (RuView has none) | RuView firmware README (per digest) | **done offline, negative result** (PS-FIX-09, `14-PS-FIX-09.md`): the spectral feature does not identify a fan (AUC 0.39–0.60, CIs include 0.5), empties separate from each other, a veto cuts walking AUC 0.74 → 0.37; also found that a 50 Hz resampling aliases the 33.3 Hz ping cadence to 16.7 Hz |
| Breathing channel | issue #1422 | Wave 4 (needs a reference belt) |
| Link-based fusion; scalar energy weighting failed on ESP32 (ADR-345) | ADR-345 | our energy-balance indicator stays labelled "relative energy balance, not a location" (Wave 3 display item) |

## Ignore / never repeat list

| item | what we did |
|--|--|
| Published presence head (bias 8.19 > ‖w‖ 3.67 ⇒ p ≥ 0.989 for any input; issue #1521) | **measured the head shipped in our repo: ‖w‖ = 3.668, bias = 8.188, p_min = 0.989; the sidecar now refuses it** (`phantom/presence_guard.py`, `tests/test_presence_guard.py`, PS-FIX-06) |
| MM-Fi-derived weights are CC BY-NC 4.0; on-device pose ≈ 3 % PCK@20 | `06-licences.md`: MM-Fi licence is stated in our own `docs/adr/ADR-015…:62`; `pose_v1.safetensors` has unverified provenance; flagged, not deleted |
| Pose/DensePose/WiFlow, slot-count counting, RSSI skeletons | no code adopted; status notes added to docs (PS-FIX-05) |
| Headline figures (82.3 % presence, 92.9 % PCK, 54K fps, "through-wall 5 m", "<30 mm jitter", breathing/HR ranges) | swept (`results/doc-claims-audit.txt`); living docs labelled "[TO BE MEASURED]", upstream README bannered; dated records left unchanged |
