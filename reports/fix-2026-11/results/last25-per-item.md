# Last 25 raw lines of each suite, per item (2026-11-04)

Full unabridged output is in `90-test-report.md`; the final Wave 3 report repeats it in full.

## Wave 3 baseline (before Item A)

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (23.7413ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (542.3068ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (189.446ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (24.6447ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3243ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (15.4711ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (40.3397ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (2.2538ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.6644ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.5844ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.4484ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.4507ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.223ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.4303ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.6054ms)
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 11131.3061
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.5857ms)
✔ fused_room: present_still without a prior target never creates one (0.3663ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.7586ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.5925ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (14.8733ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.7695ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.407ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.7803ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.6876ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (7.6494ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.7955ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3239ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7438ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5744ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (8.5661ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (9.6066ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.3075ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1290.9559
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.7855ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3358ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.341ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.0582ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4391ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3362ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3954ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (11.7759ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.1709ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.1561ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.246ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 952.8199
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.17s =======================
```

### Python, scratch venv

```text
........................................................................ [ 20%]
.....................sssss.............................................. [ 41%]
........................................................................ [ 62%]
........................................................................ [ 82%]
...........................................................              [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
342 passed, 5 skipped, 7551 warnings in 189.42s (0:03:09)
```

## after Item A

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (22.8962ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (476.8203ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (145.1606ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (22.7306ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3143ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (15.7291ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (8.7421ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.3961ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.2301ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.2754ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.1303ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.1538ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.1161ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.2819ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.1973ms)
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8954.7086
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.4537ms)
✔ fused_room: present_still without a prior target never creates one (0.312ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.6749ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.4312ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (10.5272ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.561ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.1334ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.5569ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.5055ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (6.3435ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.812ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3697ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.8276ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5242ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (7.6391ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (6.7057ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2689ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 984.2496
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.6173ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3209ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3212ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.0868ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4183ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3171ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3575ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (12.2837ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (0.9956ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.1214ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2364ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 938.2999
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.15s =======================
```

### Python, scratch venv

```text
........................................................................ [ 19%]
.........................................sssss.......................... [ 39%]
........................................................................ [ 58%]
........................................................................ [ 78%]
........................................................................ [ 98%]
.......                                                                  [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
362 passed, 5 skipped, 7551 warnings in 163.95s (0:02:43)
```

## after Item B

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (22.8853ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (477.1238ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (112.7615ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (13.3825ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.2608ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (12.303ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (3.8821ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.4149ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.3172ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.4156ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2335ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2675ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.19ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.3693ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.4492ms)
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8667.1908
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.6496ms)
✔ fused_room: present_still without a prior target never creates one (0.4089ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.7872ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.4867ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (12.6525ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.5684ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.176ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.5608ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.4612ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (6.6094ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.8653ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3841ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7263ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.4988ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (6.8179ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (6.304ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2136ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1035.6857
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.7521ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3602ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3063ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.0948ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4258ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3376ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.4671ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (13.0004ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.1839ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2001ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.233ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1264.6115
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.16s =======================
```

### Python, scratch venv

```text
........................................................................ [ 17%]
.........................................sssss.......................... [ 35%]
........................................................................ [ 53%]
........................................................................ [ 71%]
........................................................................ [ 89%]
.........................................                                [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
396 passed, 5 skipped, 7551 warnings in 168.39s (0:02:48)
```

## after Item A2

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (21.6394ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (519.7112ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (135.5429ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (18.8516ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3226ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (12.4148ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (5.2214ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (2.6544ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.6251ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.5008ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2271ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2763ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2261ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.4183ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.3138ms)
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9158.9186
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.5204ms)
✔ fused_room: present_still without a prior target never creates one (0.3563ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.6695ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.3825ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (11.3607ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.5608ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.2161ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.6043ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.4985ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (6.3811ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.7197ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2844ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7351ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5721ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (7.729ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (5.9462ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.1789ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1015.335
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.658ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.2799ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3228ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.0525ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4181ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3023ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3509ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (11.8479ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.1447ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2199ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2197ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 959.4452
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.17s =======================
```

### Python, scratch venv

```text
........................................................................ [ 17%]
.........................................................sssss.......... [ 34%]
........................................................................ [ 51%]
........................................................................ [ 69%]
........................................................................ [ 86%]
.........................................................                [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
412 passed, 5 skipped, 7551 warnings in 165.44s (0:02:45)
```

## after Item C

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (19.6846ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (410.4508ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (203.2781ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (24.5203ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.2805ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (12.6941ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (11.8583ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.7994ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.4727ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.4847ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2508ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.3455ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2553ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.4815ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.4518ms)
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 13420.1192
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.4401ms)
✔ fused_room: present_still without a prior target never creates one (0.2937ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.6339ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.5523ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (10.5093ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.5367ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.1864ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.6189ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.5233ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (7.4097ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.3301ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3578ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7251ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5066ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (8.2183ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (7.552ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2361ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1018.1965
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] handleMessage from ai: vitalSigns
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.8013ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3323ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3056ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.0998ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4131ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3146ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.309ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (13.501ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.2149ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2291ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2348ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1025.8512
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.19s =======================
```

### Python, scratch venv

```text
........................................................................ [ 15%]
.........................................................sssss.......... [ 31%]
........................................................................ [ 47%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 94%]
..........................                                               [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
453 passed, 5 skipped, 7551 warnings in 169.53s (0:02:49)
```

## after Item D

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (25.5292ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (468.9819ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (144.987ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (14.9572ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.2626ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (13.4543ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (4.5018ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.6093ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.4072ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.4714ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2281ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2402ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2018ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.3793ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.2912ms)
ℹ tests 450
ℹ suites 0
ℹ pass 450
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9790.6234
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.622ms)
✔ fused_room: present_still without a prior target never creates one (0.3855ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.7707ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.5401ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (16.9612ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.6961ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.5324ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.6901ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.6101ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (9.5238ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.8047ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2771ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7873ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5956ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (7.4631ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (6.3118ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2132ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1079.6385
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.8099ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3118ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3468ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.4104ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4561ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3175ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3212ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (13.3746ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.5015ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2461ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2298ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 971.5656
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.16s =======================
```

### Python, scratch venv

```text
........................................................................ [ 15%]
.........................................................sssss.......... [ 31%]
........................................................................ [ 47%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 94%]
..........................                                               [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
453 passed, 5 skipped, 7551 warnings in 167.97s (0:02:47)
```

## after Item H

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (39.0597ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (537.2797ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (195.7408ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (26.9607ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3219ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (11.1055ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (7.193ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (2.2814ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.3514ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.5088ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.3165ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2546ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2128ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.3719ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.2099ms)
ℹ tests 450
ℹ suites 0
ℹ pass 450
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9962.0913
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.5608ms)
✔ fused_room: present_still without a prior target never creates one (0.4814ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.7192ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.508ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (17.9262ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (1.1159ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (2.3099ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (1.2159ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (1.1589ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (11.5293ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2506ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.4856ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (1.3341ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (1.2444ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (10.15ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (8.3126ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2652ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1270.496
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (2.122ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.4005ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.4106ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.2594ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4861ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3758ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.4105ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (15.7321ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.5993ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.6332ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3077ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1634.9681
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.20s =======================
```

### Python, scratch venv

```text
........................................................................ [ 15%]
.........................................................sssss.......... [ 31%]
........................................................................ [ 47%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 94%]
..........................                                               [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
453 passed, 5 skipped, 7551 warnings in 181.05s (0:03:01)
```

## after Item I

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (30.2922ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (514.8577ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (115.3504ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (14.6469ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.3333ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (12.6046ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (5.5279ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.1486ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.2591ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.357ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.223ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.2353ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.1429ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.2621ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.2469ms)
ℹ tests 450
ℹ suites 0
ℹ pass 450
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9193.8204
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.4157ms)
✔ fused_room: present_still without a prior target never creates one (0.2889ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.6159ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.3939ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (10.4899ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.5083ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.1596ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.5441ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.4545ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (6.3795ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.7944ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2831ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.697ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5572ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (7.0688ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (6.0076ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2241ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1012.5857
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[WS] handleMessage from ai: vitalSigns
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.9721ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.3998ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3315ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.1004ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4429ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3287ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3546ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (13.1685ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.2519ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.3088ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.2512ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 929.6396
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.16s =======================
```

### Python, scratch venv

```text
........................................................................ [ 14%]
........................................................................ [ 28%]
............................sssss....................................... [ 43%]
........................................................................ [ 57%]
........................................................................ [ 71%]
........................................................................ [ 86%]
.....................................................................    [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
496 passed, 5 skipped, 7551 warnings in 176.11s (0:02:56)
```

## after section 4

### TS `npm test`

```text
✔ protected route returns 401 with a garbage/forged cookie (23.4614ms)
✔ login is rate-limited (429) after repeated failed attempts against a real operator (506.2675ms)
✔ POST /api/esp32/configure always returns 403, even for an authenticated operator with an arbitrary body (137.5308ms)
✔ POST /api/esp32/configure returns 401 (not 403-then-write) without authentication — the firewall is not reachable pre-auth either (16.6803ms)
✔ [HISTORICAL — fixed upstream, see PS-BEHTEST-004/ADR-056] fuseTwoNodeTarget's balance drifts under a static multiplicative gain asymmetry IF fed raw absStd directly (pr
✔ FIXED (PS-BEHTEST-004/ADR-056): the real production composition (computeNodeMotionFromMatrix -> computeGainNormalizedPerturbation -> fuseTwoNodeTarget) is gain-invarian
✔ fuseTwoNodeTarget hits the r1^p+r2^p<=EPS fallback (balance=0.5) when present via the linear r1+r2 gate but the contrast-exponentiated sum underflows (0.2785ms)
✔ AuditLogger: adversarial username/details content cannot break JSONL record structure (10.8963ms)
✔ real captured CSI frames (data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl) round-trip through parseCsiPacket with exact field fidelity (5.7197ms)
✔ parseCsiPacket rejects a truncated frame (shorter than the 32-byte ADR-018 header) in live mode (1.3777ms)
✔ parseCsiPacket rejects a 32-byte header that declares more IQ bytes than it carries (0.283ms)
✔ parseCsiPacket accepts an oversized frame without crashing (IQ payload is not length-capped) (0.4455ms)
✔ parseCsiPacket with a non-1 schema version at ADR-018 length falls through and is rejected in live mode (0.2429ms)
✔ parseCsiPacket with a non-1 schema version, replayed through compat mode, is safely rejected (not silently misparsed as legacy garbage) (0.289ms)
✔ parseCsiPacket rejects a garbage/unknown magic directly (0.2188ms)
✔ parseFeatureStatePacket structurally parses NaN/Infinity float fields without crashing (no float sanity check in the parser) (0.3337ms)
✔ parseEdgeVitalsPacket structurally parses NaN/Infinity motion/presence float fields without crashing (0.1954ms)
ℹ tests 450
ℹ suites 0
ℹ pass 450
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9082.9486
```

### `npx tsc --noEmit` (empty = 0 errors)

```text
(no output: 0 errors)
```

### AI-firewall, whole file

```text
✔ fused_room: a person who stops moving is held at the last position (stationary hold) (0.4003ms)
✔ fused_room: present_still without a prior target never creates one (0.3198ms)
✔ fused_room: a stationary hold broadcasts isMoving=false and the idle target state (0.7048ms)
✔ fused_room: node trend arrows follow the filtered 2-D velocity (0.4117ms)
✔ dataset recording: start/stop messages validate input and record live amplitude vectors (10.115ms)
✔ a dataset recorder I/O failure auto-stops the recording and never throws out of ingestSample (0.5566ms)
✔ a node that went silent and returns re-warms its baseline instead of reusing stale state (1.1682ms)
✔ fused_room: a quiet-baseline node with a large RELATIVE rise does not win the position (0.541ms)
✔ fused_room: position weights fall off gently (no winner-take-all snap to the strongest corner) (0.4524ms)
✔ filtered fused position is clamped to the room and reported speed is physically capped (6.3229ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (0.794ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.3357ms)
✔ fused_room radialTarget carries a bounded position uncertainty radius (0.7529ms)
✔ recording rows get the room tier, excess and four-node trends while fused_room is live (0.5066ms)
✔ dataset recording: the panel gets live frame counts while recording (not only at start/stop) (7.4119ms)
✔ dataset recording: a client that connects mid-recording is told it is recording (5.7669ms)
✔ dataset recording: nothing is sent to a new client when no recording is running (0.2263ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1042.1624
```

### AI-firewall, filtered `F1|AI|advisory|firewall`

```text
[WS] AI client ai sent malformed targetIdentity — dropped: Number must be less than or equal to 2
[WS] handleMessage from ai: vitalSigns
[WS] AI client ai sent malformed vitalSigns — dropped: Expected number, received string
[ESP32] Queue: 1 | h1=(1.00, 1.00) h2=(1.00, 1.00) rssi=-45
[WS] handleMessage from dashboard: calibrateBaseline
[WS] handleMessage from dashboard: calibrateBaseline
✔ non-AI client's targetIdentity produces no state change and no broadcast (1.6287ms)
✔ non-AI client's vitalSigns produces no state change and no broadcast (0.2992ms)
✔ non-AI client's poseFrame produces no state change and no broadcast (0.3349ms)
✔ AI client's targetIdentity is relayed as advisoryIdentity and never writes currentTargetIdentity (1.1165ms)
✔ AI client's vitalSigns is relayed as advisoryVitalSigns and never writes currentVitalSigns (0.4095ms)
✔ AI client's poseFrame still writes currentPoseFrame and broadcasts poseFrame (no deterministic source exists) (0.3315ms)
✔ registerAIClient sets isAI, unblocking the gated message types (0.3806ms)
✔ F1: extreme AI advisories leave every deterministic broadcast byte-identical (12.7038ms)
✔ malformed AI advisory payloads are dropped at the WS boundary, not relayed (1.0568ms)
✔ Calibrate Empty Room re-warms the real detector's baselines, not only the AI sidecar (1.2446ms)
✔ Calibrate Empty Room is acknowledged by the server itself, so it works with no AI sidecar (0.221ms)
ℹ tests 11
ℹ suites 0
ℹ pass 11
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 904.9096
```

### F1/F2

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0 -- D:\WIFI csi\phanotm\_scratch_venv_fulltest\Scripts\python.exe
rootdir: D:\WIFI csi\phanotm\phantom scan
configfile: pytest.ini
collecting ... collected 6 items / 3 deselected / 3 selected

tests/test_invariants.py::test_f1_ai_sidecar_only_sends_advisory_message_types PASSED [ 33%]
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED [ 66%]
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED [100%]

======================= 3 passed, 3 deselected in 0.14s =======================
```

### Python, scratch venv

```text
........................................................................ [ 13%]
........................................................................ [ 26%]
.....................................................sssss.............. [ 40%]
........................................................................ [ 53%]
........................................................................ [ 66%]
........................................................................ [ 80%]
........................................................................ [ 93%]
...................................                                      [100%]
============================== warnings summary ===============================
tests/test_csi_pipeline.py: 307 warnings
tests/test_esp_capture_e2e.py: 7244 warnings
  D:\WIFI csi\phanotm\_scratch_venv_fulltest\Lib\site-packages\pywt\_multilevel.py:43: UserWarning: Level value of 3 is too high: all coefficients will experience boundar
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
534 passed, 5 skipped, 7551 warnings in 219.57s (0:03:39)
```
