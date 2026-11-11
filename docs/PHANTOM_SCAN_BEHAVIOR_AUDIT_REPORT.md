# PHANTOM_SCAN Behavior Audit Report

## 1. Executive Summary

This checkout is internally consistent and testable — both suites were re-run for this audit (TS: 99/99 pass; Python: 77 pass, 6 skip) — but its active runtime architecture does not match the stated Milestone-1 canonical design. The live path in this repository is the Node/TypeScript host owning UDP `:5005`, while the Python `phantom/` package is explicitly marked as superseded reference/replay code; the canon requires the inverse (`README.md:45-60`, `server/index.ts:71-75`, `server/lib/udp-server.ts:373-387`, `phantom/runtime.py:1-6`). The ADR-018 32-byte wire format, heartbeat exclusion, and Fix C dispatch ordering are implemented correctly and covered by tests (`firmware/esp32-csi-node/main/csi_collector.c:156-239`, `phantom/protocol.py:149-227`, `server/lib/udp-server.ts:184-345`, `server/lib/udp-server.test.ts:56-100`, `tests/test_udp_ad018.py:75-117`), and replaying two committed live JSONL sessions through `phantom/` ingest produced 16,741 derived frames with zero invariant violations (balance stayed in `[0,1]`, no garbage `z ≈ −3.99e37` positions, no crashes). The largest behavioral defect against canon is verdict authority: the firmware currently sets presence from motion threshold alone instead of requiring a respiratory periodicity gate (`firmware/esp32-csi-node/main/edge_processing.c:876-953`). The active TS fusion path also deviates from the canonical `~3 s` linear `balance = r2/(r1+r2)` model by using a `1500 ms` window, a contrast exponent, and a display bias (`server/lib/websocket.ts:23-31`, `server/lib/node-fusion.ts:57-80`, `server/lib/node-fusion.ts:225-257`). Security posture is weaker than the resolved-items list claims: MEDIUM-1 is NOT fixed — a live home-network SSID and WPA2 password remain committed in git-tracked firmware config files and NVS binaries (`firmware/esp32-csi-node/sdkconfig.defaults:9-10`, `firmware/esp32-csi-node/sdkconfig:604`). The F1 firewall holds for the deterministic verdict variables, but the WebSocket handler accepts `targetIdentity`/`vitalSigns` messages from any authenticated client without checking the AI-client flag, so model-originated `humanProb` can transiently occupy the operator-facing identity channel (`server/lib/websocket.ts:346-357`, `scripts/ai_inference.py:458-487`). Source-IP pinning (the MEDIUM-3 mitigation) exists in both ingest paths but is trust-on-first-use with a 10 s stale-rebind window in the live TS path, and the live ingest performs no replay/sequence validation (`server/lib/udp-server.ts:49`, `server/lib/udp-server.ts:99-108`, `phantom/ingest.py:100-133`). Documentation drift is substantial, including a deliverable that marks uncharacterized accuracy targets (±1/±2 BPM, ≥95% occupancy, ±5° AoA) as "✅ Validated" and stale 5 m-baseline geometry in root reports (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:556-568`, `DETECTION_REPORT.md:32`, `TEST_REPORT.md:89`).

Severity counts:

- `CRITICAL`: 2
- `HIGH`: 5
- `MEDIUM`: 5
- `LOW`: 1
- `DOC`: 5

## 2. Verified-Correct Behaviors

- ADR-018 is implemented as a 32-byte little-endian header with matching field order across firmware serialization, Python unpack, and TS parsing: firmware writes `magic/schema/node_id/n_ant/n_sub/freq/seq/rssi/noise/channel/device_ts_us/device_ts_ms` in `csi_serialize_frame()`, Python unpacks the same `<IBBBHIIbbBQI`, and TS reads the same offsets (`firmware/esp32-csi-node/main/csi_collector.c:156-239`, `phantom/protocol.py:172-227`, `server/lib/udp-server.ts:304-341`). Tests assert the same layout and field values (`server/lib/udp-server.test.ts:19-81`, `tests/test_udp_ad018.py:26-117`, `tests/test_esp_capture_e2e.py:230-312`).
- Heartbeat magic `0xC51100A1` is excluded from CSI conversion in both active TS ingest and Python parsing (`phantom/protocol.py:160-165`, `server/lib/udp-server.ts:296-302`). Regression coverage exists in both stacks (`server/lib/udp-server.test.ts:83-90`, `tests/test_udp_ad018.py:104-117`).
- Fix C dispatch ordering is present at both dispatch sites I found: packet classification reads the full little-endian u32 magic before any legacy interpretation, and the CSI parser attempts ADR-018 before the legacy layout (`phantom/protocol.py:157-169`, `server/lib/udp-server.ts:184-203`, `server/lib/udp-server.ts:291-345`). A TS regression test explicitly exercises the collision case by building a packet whose byte 0 is `0x01` but must route through ADR-018-first logic (`server/lib/udp-server.test.ts:45-54`, `server/lib/udp-server.test.ts:93-100`).
- The dashboard itself is not writing directly to nodes, serial, or firmware. The client hook only sends WebSocket control messages to the local host process (`updateConfig`, `startProcessing`, `stopProcessing`, `setDataSource`, `startRecording`, `stopRecording`, `markSyncEvent`) (`client/src/hooks/use-websocket.ts:426-492`). The explicit ESP32 configure route returns `403`, and the UI invariant test forbids `api/esp32/configure` and `execute-task` controls in the dashboard/top bar (`server/routes.ts:47-52`, `tests/test_invariants.py:39-45`).
- Source-IP pinning is implemented and tested in the active TS ingest: first sender claims a node, same-IP port changes are allowed, different-IP conflicts are rejected until the binding goes stale, and security events are bounded (`server/lib/udp-server.ts:40-160`, `server/lib/udp-server.test.ts:102-162`). The Python reference runtime also rejects spoofed node sources in tests (`tests/test_phantom_runtime.py:98-119`).
- Auth bypass protection is present in the current server code. Production requires `PHANTOM_SESSION_SECRET`, protected routes return `401` without a valid operator session, and login attempts are rate-limited (`server/auth/service.ts:80-92`, `server/auth/service.ts:214-237`, `server/auth/service.ts:319-449`, `server/auth/service.ts:496-515`).
- JSONL logging uses serialized JSON records rather than raw field concatenation in both the audit log and the Python recorder, reducing line-injection risk from crafted frame content (`server/audit/logger.ts:105-117`, `phantom/recording.py:53-55`).
- Shared geometry constants in the active TS/UI path correctly encode a centered 3 m baseline at `(-1.5, 0)` and `(+1.5, 0)` (`shared/schema.ts:248-256`, `README.md:331-336`).
- Firmware self-ping (Option 1, anti-starvation) is IMPLEMENTED. `csi_start_self_ping()` creates an infinite ICMP ping session to the gateway with `interval_ms = 20` and 1-byte payload to keep OFDM traffic (and therefore CSI callbacks) flowing, and it is started from the CSI collector init path (`firmware/esp32-csi-node/main/csi_collector.c:75-132`, `firmware/esp32-csi-node/main/csi_collector.c:328`). It degrades gracefully with logged skips when the station netif, IP info, or gateway is not yet available (`firmware/esp32-csi-node/main/csi_collector.c:83-95`). Note the 20 ms interval is the OFDM *source* rate; measured CSI emit rate remains 3–7 Hz per canon.
- F1 firewall (deterministic verdict authority) holds for the verdict variables. The operator-facing classification originates from the deterministic micro-Doppler classifier (`server/lib/websocket.ts:861`) and is rewritten from that source on every processing tick (`server/lib/websocket.ts:944-945`); the target verdict state machine consumes only fusion confidence, never model output (`server/lib/target-state.ts:122`, `server/lib/target-state.ts:149`). The AI sidecar itself labels its output advisory and sends `label: "unknown"` with a separate `advisoryLabel` field (`scripts/ai_inference.py:441-445`, `scripts/ai_inference.py:465-478`). The AI stack probe correctly falls back to `deterministic_only` when torch/safetensors or model weights are absent — honest-default behavior, an environment/packaging item, not a pipeline bug (`phantom/ai_status.py:40-62`). See PS-AUDIT-014 for the residual display-channel weakness.
- Runtime replay through `phantom/` ingest is clean (Phase 4 executed this session). Replaying the committed session `data/sessions/74b9bc7d51744175959d483941aa8e1a.jsonl` (135 KB) produced 76 derived frames (75 fused / 1 degraded), balance in `[0.356, 0.631]`, zero NaN/Inf/garbage-position violations. Replaying a 50,000-record slice of `data/sessions/ad3b220d21b84250951f12760c7020b6.jsonl` (29 MB live capture) produced 16,665 derived frames (16,663 fused), balance in `[0.198, 0.746]`, zero invariant violations, no crashes. `is_motion` was true for 33,321 of ~33,330 per-node flags with only 3 transitions — plausible for a continuously occupied capture but uninterpretable without an empty-room negative control (see UNVERIFIED register).
- Both test suites pass on this machine as of this audit session: `npm test` → 99/99 pass, 0 fail; `python -m pytest tests -q` (Python 3.13) → 77 passed, 6 skipped.

## 3. Findings

### PS-AUDIT-001
Severity: `CRITICAL`

Problem:
The active runtime ownership of UDP `:5005` is inverted relative to the canonical Milestone-1 architecture.

Analysis:
The repository states that the active live path is the Node/TS host and that it is the sole owner of UDP `:5005` (`README.md:45-60`, `README.md:597-600`). Startup code launches the UDP ingest in-process from the Node server (`server/index.ts:71-75`). The TS UDP server describes itself as the sole ESP32 ingest for the live pipeline and mirrors accepted packets to Python only as an advisory sidecar on `:5006` (`server/lib/udp-server.ts:373-387`, `server/lib/udp-server.ts:465-468`). Meanwhile the Python authority files are explicitly marked `SUPERSEDED` and warn that running alongside the dashboard steals `:5005` (`phantom/dsp.py:1-7`, `phantom/runtime.py:1-6`).

Impact:
This is a first-order architecture mismatch against the canon. Any behavior audit, detector authority claim, or security boundary framed around “Python solely owns `:5005` and Node follows `/api/sensing/frame`” is false for the current checkout. It also changes where replay, source pinning, input validation, and security controls must be evaluated.

Recommended Fix:
Choose one authority and remove the split.
- Preferred canon-aligned design: move live UDP `:5005` ownership back to `phantom/`, emit derived frames over `/api/sensing/frame`, and make `server/` a pure follower.
- If the TS path is intentionally the product direction, update the canonical spec and remove the superseded-but-still-runnable Python live authority mode.
Effort: `L`

Validation:
Run only one ingest owner and prove it with:
- one bind owner on `:5005`
- one derived-frame publisher on `:8789`
- an end-to-end capture showing ESP32 UDP entering the authority process and the dashboard following only derived frames

### PS-AUDIT-002
Severity: `CRITICAL`

Problem:
The firmware presence verdict is motion-threshold driven, not respiratory-gated as required by canon.

Analysis:
Board DSP computes breathing and heart estimates (`firmware/esp32-csi-node/main/edge_processing.c:876-913`), but the actual presence assignment is `s_presence_score = s_motion_energy` followed by `s_presence_detected = (s_presence_score > threshold)` (`firmware/esp32-csi-node/main/edge_processing.c:938-953`). I found no board-side logic that requires 0.1–0.5 Hz respiratory periodicity before asserting human presence. The Python reference DSP does implement a deterministic human gate requiring motion and respiratory periodicity, but that path is marked superseded (`phantom/dsp.py:163-173`).

Impact:
This violates the canonical authority definition for `is_human`. In the current firmware, any motion-like perturbation above threshold can assert presence without respiratory confirmation, increasing false positives from non-human movers and invalidating claims about sovereign respiratory gating.

Recommended Fix:
Redefine board-side verdict authority so `is_human` requires:
- motion present
- respiration periodicity present in the 0.1–0.5 Hz band
- optional cardiac band only as confidence enhancement, never as a gate relaxer
Keep `motion_energy` and `presence_score` as metrics, but separate them from the authoritative verdict bit.
Effort: `M`

Validation:
Add firmware/unit or host-replay coverage proving:
- fan/curtain motion alone does not set `is_human`
- breathing-only human presence does set `is_human`
- heart-band-only energy cannot flip a negative respiratory verdict

### PS-AUDIT-003
Severity: `HIGH`

Problem:
The live TS fusion path does not implement the canonical `~3 s` linear `balance = r2/(r1+r2)` model.

Analysis:
The live pipeline uses a `1500 ms` motion window (`server/lib/websocket.ts:23-31`). Fusion applies a contrast exponent `p` before ratio formation and then a second display bias toward the nearer node (`server/lib/node-fusion.ts:57-80`, `server/lib/node-fusion.ts:225-257`). The canonical model requires a rolling `~3 s` amplitude window and a direct linear ratio `balance = r2/(r1+r2)` without contrast shaping. The README still documents a 3-second linear model (`README.md:355-367`), so the code and repository-level description already disagree.

Impact:
Displayed target position and trend velocity are not canon-faithful. The live dot will move more aggressively toward endpoints and with lower temporal averaging than the specified model, so position behavior, emptiness thresholds, and movement trends cannot be compared directly to the canonical design.

Recommended Fix:
If canon is authoritative:
- change `MOTION_WINDOW_MS` to the validated time window matching the canonical rolling horizon
- remove `BALANCE_CONTRAST_EXPONENT`
- remove `biasBalanceTowardNearestNode()` from the authoritative position path
If the nonlinear behavior is intentional, reclassify it as a display transform and document a separate authoritative linear balance.
Effort: `M`

Validation:
Replay the same two-node capture through:
- current code
- a linear 3 s reference implementation
Compare emitted `balance`, `x`, and trend labels frame-by-frame.

### PS-AUDIT-004
Severity: `HIGH`

Problem:
The active live parser still accepts the superseded 20-byte CSI header in a live code path.

Analysis:
`parseCsiPacket()` explicitly falls back from ADR-018 to a legacy 20-byte header (`server/lib/udp-server.ts:284-370`). The regression test `parseCsiPacket routes legacy packets after ADR-018 check` intentionally preserves that behavior (`server/lib/udp-server.test.ts:93-100`). The canonical spec says the old 20-byte RuView format is superseded and its presence in a live path is itself a finding.

Impact:
A live ingest endpoint can still accept obsolete packets that should have been retired. That increases protocol ambiguity, complicates security review, and preserves a class of silent format drift the canon explicitly forbids.

Recommended Fix:
Gate legacy parsing behind an explicit compatibility flag or remove it from the production live path. Keep legacy parsing only in offline conversion or replay tooling if historical captures still require it.
Effort: `S`

Validation:
Add two tests:
- live mode rejects 20-byte legacy packets
- offline compatibility mode accepts them only when explicitly enabled

### PS-AUDIT-005
Severity: `HIGH`

Problem:
Node identity and geometry in code are keyed to `1` and `2`, not to canonical hardware IDs `29052` and `44260`.

Analysis:
The ADR-018 header stores `node_id` as a single byte in firmware and Python (`firmware/esp32-csi-node/main/csi_collector.c:156-239`, `phantom/protocol.py:177-190`), and the active shared geometry anchors are keyed as `1` and `2` (`shared/schema.ts:252-256`). The Python reference tests also build around node IDs `1` and `2` (`tests/test_phantom_runtime.py:101-118`). I found no active runtime mapping from hardware IDs `29052` and `44260` to the canonical anchors.

Impact:
The current repository cannot represent the canonical hardware IDs directly in the live ADR-018 `node_id` field, and the anchor mapping is therefore not aligned to the specified physical identity contract. That is a hard mismatch if those hardware IDs are meant to be the runtime sensor identities.

Recommended Fix:
Introduce one explicit identity layer:
- either widen the protocol and in-memory types so the canonical hardware IDs are carried directly
- or define and enforce a documented runtime mapping `29052 -> N1`, `44260 -> N2` at the authority ingest boundary
Effort: `M`

Validation:
Capture live frames from both boards and prove that the authority emits stable anchor assignment for the canonical IDs under reboot, port changes, and source-IP rebinds.

### PS-AUDIT-006
Severity: `HIGH`

Problem:
The Python reference authority path still encodes stale 5 m geometry and stale sample-rate assumptions, and the tests still lock those assumptions in.

Analysis:
`dual_node_on_axis_position()` defaults to `baseline_m = 5.0` and returns `x_m = baseline_m * balance` (`phantom/dsp.py:142-159`). `NodeDspPipeline` and the respiration filter both default to `sample_rate_hz = 20.0` (`phantom/dsp.py:82-105`, `phantom/dsp.py:176-190`). `tests/test_invariants.py` still asserts that equal motion yields `x_m = 2.5` for `baseline_m=5.0` (`tests/test_invariants.py:9-13`). This directly conflicts with the canonical centered 3 m baseline and the measured 3–7 Hz CSI rate.

Impact:
Although marked superseded, the in-repo Python “authority” reference code and its tests preserve wrong geometry and wrong timing assumptions. That is dangerous because the same module is used for replay/reference reasoning and will mislead future changes or audits.

Recommended Fix:
If the Python package remains in-repo:
- change its geometry and timing constants to the canonical values
- convert any remaining 20 Hz assumptions to measured-or-derived sample-rate handling
- update tests so they encode `(-1.5 .. +1.5)` rather than `0 .. 5`
Effort: `S`

Validation:
Run Python tests after replacing the stale assumptions and add one invariant asserting midpoint equals `0.0 m` on the centered axis, not `2.5 m`.

### PS-AUDIT-007
Severity: `MEDIUM`

Problem:
The active TS UDP ingest path does not enforce replay or out-of-order rejection, even though sequence and timestamps are parsed.

Analysis:
TS parsing reads `seq`, `deviceTsUs`, and `deviceTsMs` from ADR-018 (`server/lib/udp-server.ts:304-341`), but I found no active validation in `startUDPServer()` or downstream fusion that checks monotonic sequence or timestamp progress before accepting the frame (`server/lib/udp-server.ts:409-468`). By contrast, the Python reference ingest tracks `packet_loss_count`, `out_of_order_count`, and last seen CSI/heartbeat sequence values (`phantom/ingest.py:18-44`).

Impact:
The active live ingest is exposed to replay and out-of-order injection on unauthenticated UDP. Even if spoofed `nodeId` from a different IP is rejected by pinning, a same-source replay or reordered burst can still perturb motion windows and displayed target state.

Recommended Fix:
Add per-node monotonic acceptance rules in the active authority:
- reject or quarantine clearly old sequences
- count gaps and out-of-order arrivals
- define rollover behavior explicitly
- prefer device timestamp when valid and bound host/device skew
Effort: `M`

Validation:
Add active-path tests that feed:
- in-order frames
- same-source replayed frames
- same-source out-of-order frames
- sequence rollover frames
and assert only the accepted set reaches motion fusion.

### PS-AUDIT-008
Severity: `MEDIUM`

Problem:
The optional Python live authority bind configuration is still capable of unsafe port sharing behavior on Windows.

Analysis:
The active TS owner explicitly avoids `reuseAddr` because Windows `SO_REUSEADDR` can silently share `:5005` with nondeterministic delivery (`server/lib/udp-server.ts:381-385`). The Python UDP ingest still sets `SO_REUSEADDR = 1` before binding (`phantom/ingest.py:136-143`). README also acknowledges that running both authorities can silently starve the dashboard (`README.md:60`).

Impact:
If an operator enables the superseded Python authority mode by mistake, Windows may admit a second bind pattern the TS path was deliberately engineered to forbid. That is a robustness and operator-safety defect even if the normal path no longer uses Python live ingest.

Recommended Fix:
Make the Python live mode fail hard on Windows bind conflicts:
- remove `SO_REUSEADDR` from the live authority path
- or forbid live bind entirely unless an explicit offline compatibility flag is set
Effort: `S`

Validation:
On Windows, start the active dashboard, then attempt Python live authority startup and assert deterministic `EADDRINUSE`/startup failure instead of silent shared receive.

### PS-AUDIT-009
Severity: `DOC`

Problem:
Repository documentation still preserves stale protocol and formula statements that contradict the current canon.

Analysis:
The historical preliminary deliverable still describes a “fixed 20-byte header” (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:193`) and contains a PSC correction formula using `2π / λ` (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:524-527`), while canon requires ADR-018 32-byte framing and `4π / λ` for round trip. The same document also retains old UAV/100 Hz content (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:485-500`, `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:604`, `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:699`).

Impact:
These documents can mislead protocol implementers and reviewers into certifying the wrong wire format or wrong phase model.

Recommended Fix:
Mark these sections explicitly as historical, or replace them with a short “superseded” stub that points to the current canonical runtime contract.
Effort: `S`

Validation:
Search docs for `20-byte`, `2π / λ`, `100 Hz`, `UAV`, and confirm remaining hits are either removed or labeled `superseded`.

### PS-AUDIT-010
Severity: `DOC`

Problem:
A historical in-repo report still documents obsolete node geometry and an obsolete Python bridge runtime as if it were the working two-node path.

Analysis:
`docs/ruview-2node-full-analysis-report.md` is now marked historical, but it still contains fixed node positions `[4.0, 0.0, 6.0]` and `[16.0, 0.0, 6.0]` (`docs/ruview-2node-full-analysis-report.md:328-329`) and describes the Python bridge as the live backend (`docs/ruview-2node-full-analysis-report.md:239-253`). Canon requires a centered 3 m baseline and the current repository no longer uses that bridge as the default live runtime (`README.md:45-60`, `shared/schema.ts:248-256`).

Impact:
Even with the historical banner, this document remains a high-friction source of wrong geometry and wrong runtime ownership.

Recommended Fix:
Collapse the file to a short archived-note form or add an early “obsolete geometry/runtime” warning directly above the stale sections.
Effort: `S`

Validation:
Open the document and confirm the first screen explicitly warns that its geometry and runtime sections are non-authoritative.

### PS-AUDIT-011
Severity: `DOC`

Problem:
README’s fusion description is stale relative to the active code.

Analysis:
README documents a 3-second time-based window and direct `balance = r2 / (r1 + r2)` (`README.md:355-367`), but the active code uses a `1500 ms` window plus contrast and display bias (`server/lib/websocket.ts:23-31`, `server/lib/node-fusion.ts:57-80`, `server/lib/node-fusion.ts:225-257`).

Impact:
The main operator/developer document describes different target behavior than the code actually emits.

Recommended Fix:
Either update README to the actual live math, or restore the code to the documented linear 3 s model.
Effort: `S`

Validation:
Re-read README fusion section and compare line-for-line to the authoritative implementation in `server/lib/node-fusion.ts`.

### PS-AUDIT-012
Severity: `MEDIUM`

Problem:
MEDIUM-1 (hardcoded Wi-Fi credentials) is NOT fixed: a live home-network SSID and WPA2 password are committed in git-tracked files.

Analysis:
`CONFIG_CSI_WIFI_SSID="Thaer_2.4Ghz"` and `CONFIG_CSI_WIFI_PASSWORD="Bmt#0987"` appear in `firmware/esp32-csi-node/sdkconfig.defaults:9-10` and `firmware/esp32-csi-node/sdkconfig:604` (read directly and confirmed by `git grep`). The same password also matches inside the tracked NVS provisioning binaries `firmware/esp32-csi-node/nvs_node1.bin` and `nvs_node2.bin`, and in `sdkconfig.old:538`. All five paths are git-tracked (`git ls-files` confirms); `.gitignore` covers none of them except that no entry covers them at all. The canonical spec lists MEDIUM-1 as resolved; this checkout contradicts that.

Impact:
Anyone with repository access (or a clone of its history) obtains the operator's real WPA2 pre-shared key and network name. This is a live secret leak independent of any runtime behavior, and it invalidates the "MEDIUM-1 resolved" claim.

Recommended Fix:
- Rotate the Wi-Fi password immediately (out-of-repo action).
- Replace SSID/password values in `sdkconfig.defaults` with placeholders; stop tracking `sdkconfig`, `sdkconfig.old`, and the `nvs_node*.bin` provisioning binaries (gitignore them; provision NVS locally at flash time).
- Scrub history (`git filter-repo`) if the repository will ever be shared.
Effort: `S` (config cleanup) + `M` (history scrub and rotation logistics)

Validation:
`git grep` for the SSID and password strings across the working tree and history returns nothing; a fresh clone builds with placeholder credentials and boards join only via locally provisioned NVS.

### PS-AUDIT-013
Severity: `MEDIUM`

Problem:
MEDIUM-3 (spoofed `nodeId`) is partially mitigated: source-IP pinning exists in both ingest paths, but the live TS guard is trust-on-first-use with a 10 s stale-rebind window.

Analysis:
The live TS `SourcePinningGuard` pins each `nodeId` to the first source IP that uses it (`server/lib/udp-server.ts:77-83`), accepts same-IP port changes (`server/lib/udp-server.ts:86-92`), and rebinds to a NEW IP after only `STALE_BINDING_MS = 10_000` of silence (`server/lib/udp-server.ts:49`, `server/lib/udp-server.ts:99-108`). Accepted frames flow via `sourceGuard.check(...)` into `signalServer.ingestSample(...)`, where the frame's `nodeId` byte selects which node's buffers and displayed position update. The Python reference guard pins `(ip, port)` permanently for the session with no expiry, and silently skips the check entirely when the packet has no source info (`phantom/ingest.py:100-133`, skip at `phantom/ingest.py:112-113`). Conflicting-IP rejections are logged as bounded security events in the TS path (`server/lib/udp-server.ts:110-135`).

Impact:
An attacker on the LAN who transmits before a legitimate node's first frame (boot race), or during any >10 s node outage (power cycle, Wi-Fi drop), captures that `nodeId` binding and can then skew the displayed position and motion metrics at will from their own IP. Within a healthy steady state, spoofing from a different IP is correctly rejected.

Recommended Fix (design only):
Add optional static pinning: a config map `nodeId -> source IP` that pre-populates the guard's bindings at startup and disables both TOFU claiming and silent stale-rebind for statically pinned nodes (rebind requires an operator-visible action or an explicit security event acknowledgment). Keep TOFU as the default only for unprovisioned setups.
Effort: `S`

Validation:
Unit tests: with static pinning configured, (a) a foreign-IP frame before any legitimate frame is rejected; (b) a foreign-IP frame after 30 s of node silence is rejected and logged; (c) the legitimate IP always re-attaches.

### PS-AUDIT-014
Severity: `HIGH`

Problem:
The WebSocket handler accepts `poseFrame`, `targetIdentity`, and `vitalSigns` messages from ANY authenticated client — the `isAI` registration flag is never checked — so model-originated (or operator-forged) identity data can transiently occupy the operator-facing verdict display channel.

Analysis:
`registerAIClient` sets `client.isAI = true` (`server/lib/websocket.ts:333-337`), but the `poseFrame`/`targetIdentity`/`vitalSigns` cases that follow gate only on `this.status.isProcessing`, not on `client.isAI` (`server/lib/websocket.ts:339-357`). An accepted `targetIdentity` message overwrites `this.currentTargetIdentity` and is broadcast to all dashboards on the SAME message type the deterministic classifier uses (`server/lib/websocket.ts:348-349` vs. the deterministic write at `server/lib/websocket.ts:944-945`). The AI sidecar sends exactly such messages carrying its own model-derived `humanProb` (`scripts/ai_inference.py:458-460`, `scripts/ai_inference.py:469-478`). Newly connecting clients are served whatever is currently stored (`server/lib/websocket.ts:1201-1203`). The deterministic tick rewrites the value each processing frame, so the exposure is a race/flicker window plus the new-client snapshot — the deterministic verdict variables themselves (`classification`, `targetState`) are never written from these messages.

Impact:
This weakens firewall F1 at the presentation boundary: a model-originated `humanProb` is indistinguishable from the deterministic classification on the wire, and any authenticated non-AI client can inject identity/vitals frames that all connected dashboards will display until the next deterministic tick. It is not a flip of the deterministic `is_human` authority, which is why this is HIGH rather than CRITICAL.

Recommended Fix:
- Require `client.isAI === true` for `poseFrame`/`targetIdentity`/`vitalSigns` message handling.
- Move AI identity onto a distinct advisory message type (e.g. `advisoryIdentity`) and never write `currentTargetIdentity`/`currentVitalSigns` from client messages; the deterministic pipeline remains the only writer of the authoritative channels.
Effort: `S`

Validation:
Tests: (a) a non-AI authenticated client sending `targetIdentity` produces no state change and no broadcast; (b) an AI client's output arrives only as the advisory type; (c) the new-client snapshot (`server/lib/websocket.ts:1201-1203`) always serves deterministic values.

### PS-AUDIT-015
Severity: `MEDIUM`

Problem:
First-operator trust-on-first-use bootstrap: on a fresh install with no operator seed, the first `POST /api/auth/login` silently creates and authenticates the operator from whatever credentials are submitted.

Analysis:
When `operatorState.missing` is true, the login handler generates an operator seed from the submitted username/password, writes it, regenerates the session, and returns an authenticated session (`server/auth/service.ts:346-378`). The bootstrap is audit-logged (`server/auth/service.ts:367-373`), but nothing restricts who may trigger it.

Impact:
Anyone who can reach the dashboard port before the legitimate operator's first login becomes the operator. MEDIUM-2 (auth bypass) is otherwise fixed — routes and the WebSocket upgrade are session-guarded — but this residual window undermines it on unprovisioned installs.

Recommended Fix:
Restrict bootstrap to loopback source addresses, or require an explicit provisioning step (CLI command or one-time token in an environment variable) before the first login can create the operator.
Effort: `S`

Validation:
Tests: bootstrap login from a non-loopback address (or without the provisioning token) returns 403 and creates no seed; the provisioned path still succeeds exactly once.

### PS-AUDIT-016
Severity: `LOW`

Problem:
The superseded Python fused path computes balance from raw mean amplitudes (not motion metrics) and its cross-node correlation is structurally always zero.

Analysis:
`_build_derived_frame()` calls `dual_node_on_axis_position(left_metrics["mean_amplitude"], right_metrics["mean_amplitude"], baseline_m=5.0)` — absolute amplitude, not the canonical normalized temporal-std motion metric (`phantom/runtime.py:203-207`). It also calls `cross_node_correlation` with two single-element arrays built from the latest `dynamic_mean` values (`phantom/runtime.py:198-202`); a length-1 array has zero standard deviation, so the guard at `phantom/dsp.py:135-138` returns `0.0` unconditionally. The replayed sessions confirm the fused output is produced without error, but every `cross_node_correlation` value in a derived frame is a constant `0.0` by construction.

Impact:
Reference/replay conclusions drawn from this path are misleading: its "position" tracks static per-node gain (AGC/antenna asymmetry between the two boards), not motion, and its correlation field carries no information. Severity is LOW only because the path is marked superseded; if it is ever used as the comparison baseline for the TS pipeline, the comparison is invalid.

Recommended Fix:
Feed windowed motion-metric histories (not single samples) into the correlation, and use the normalized motion metric for balance — or delete the fused path from the superseded package and keep only per-node metrics.
Effort: `S`

Validation:
Replay any two-node session and assert `cross_node_correlation` varies and correlates with simultaneous per-node motion; assert balance responds to motion asymmetry, not to static amplitude offsets.

### PS-AUDIT-017
Severity: `DOC`

Problem:
Uncharacterized accuracy targets are presented as achieved ("✅ Validated"), laundering targets into measurements.

Analysis:
The deliverable's performance table marks every row "✅ Validated", including respiration ±1 BPM, cardiac ±2 BPM, occupancy ≥95% on a "4-node mesh", AoA ±5°, PDP ±15 cm, and a 20 Hz CSI frame rate (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md:556-568`). This contradicts the repository's own honesty gates, which mark the same quantities `[TO BE MEASURED]` (`DETECTION_REPORT.md:32`, `TEST_REPORT.md:89`, `TEST_REPORT.md:115`). Separately, the AI model README claims "100% accuracy" presence detection (`ai model and densepose/model/README.md:31`, `ai model and densepose/model/README.md:94`, `ai model and densepose/model/README.md:110`, `ai model and densepose/model/README.md:148`) while the same file admits the training loss never moved and "the optimizer was not actually learning" (`ai model and densepose/model/README.md:43`).

Impact:
Any reader citing the deliverable will report fabricated capability levels for a defense-grade system. This is the most consequential documentation defect in the repository.

Recommended Fix:
Change every unmeasured row's status to `Target — [TO BE MEASURED]`; where a measurement exists, link the session artifact and measurement conditions. Reconcile the AI README's headline claims with its own caveat section.
Effort: `S`

Validation:
Grep for "✅ Validated" and "100% accuracy"; every remaining hit must link a committed measurement artifact (session file + analysis) or be rephrased as a target.

### PS-AUDIT-018
Severity: `DOC`

Problem:
Root-level reports still specify the stale 5 m node baseline.

Analysis:
`DETECTION_REPORT.md:32` says midpoint localization "Requires two live nodes on `[0,0]` to `[5,0]` baseline"; `DETECTION_REPORT.md:72` instructs "Run midpoint sanity on the 5 m baseline."; `TEST_REPORT.md:89` and `TEST_REPORT.md:115` both require nodes "on the 5 m (test) baseline". Canon (and the active TS code, `shared/schema.ts:248-256`) is a 3 m baseline centered at the origin, N1 = (−1.5, 0), N2 = (+1.5, 0).

Impact:
Anyone executing these checklists will place hardware on the wrong geometry, and midpoint sanity expectations (x = 2.5 m) will not match the live system (x = 0 m).

Recommended Fix:
Update the four lines to the centered 3 m baseline and midpoint x = 0 m; cross-reference `shared/schema.ts` as the geometry source of truth.
Effort: `S`

Validation:
Grep root reports for "5 m" / "[5,0]" and confirm zero remaining geometry references; midpoint procedures state x = 0 m.

## 4. Prioritized Fix Roadmap

1. Rotate the leaked Wi-Fi password and scrub credentials from tracked files (`PS-AUDIT-012`). Independent of all other work; do it first because it is a live secret, not a code change.
2. Resolve authority ownership of UDP `:5005` and derived-frame publication (`PS-AUDIT-001`). Everything else depends on which process is authoritative.
3. Restore canonical verdict authority on the board or in the chosen authority process (`PS-AUDIT-002`). Do not tune thresholds before the verdict definition is correct.
4. Gate the WebSocket identity/vitals channel on the AI-client flag and split advisory identity onto its own message type (`PS-AUDIT-014`). Small, independent, and closes the F1 presentation gap.
5. Remove or quarantine legacy 20-byte parsing from the active live path (`PS-AUDIT-004`). This reduces protocol ambiguity before adding more validation.
6. Add replay/out-of-order enforcement to the active authority (`PS-AUDIT-007`) and static source pinning (`PS-AUDIT-013`). Both must land in the true authority process (blocked by item 2).
7. Close the first-operator bootstrap window (`PS-AUDIT-015`).
8. Align identity and geometry contracts to canonical hardware IDs and the 3 m centered baseline (`PS-AUDIT-005`, `PS-AUDIT-006`), and fix or delete the superseded Python fused path (`PS-AUDIT-016`).
9. Reconcile live fusion math with the canonical linear model, or explicitly split “authoritative balance” from “display transform” (`PS-AUDIT-003`).
10. Hard-fail superseded Python live bind conflicts on Windows (`PS-AUDIT-008`).
11. Clean stale docs after code/runtime authority is settled (`PS-AUDIT-009` to `PS-AUDIT-011`, `PS-AUDIT-017`, `PS-AUDIT-018`). `PS-AUDIT-017` (accuracy laundering) should not wait for the code items — correct the "✅ Validated" table immediately.

Dependencies and blockers:

- Ground-truth accuracy claims remain blocked until a canonical authority path is chosen and instrumented.
- Hardware-ID validation is blocked by the current `u8` `node_id` contract unless a mapping layer is formally defined.
- Replay hardening must land in the true authority process; otherwise it becomes dead code.

## 5. UNVERIFIED Register

- `UNVERIFIED — live hardware behavior on July 17, 2026`. Needed: two active ESP32-S3 boards on the current firmware, serial logs, and a live `:5005` capture while walking/empty-room controls are performed.
- `UNVERIFIED — whether canonical hardware IDs 29052 and 44260 exist anywhere outside this repo or are expected to map onto runtime node IDs 1 and 2`. Needed: provisioning artifact or hardware manifest defining the mapping.
- `UNVERIFIED — Windows firewall/runtime bind behavior for the superseded Python live authority on this machine`. Needed: a controlled dual-start attempt with both authorities launched on Windows and the resulting socket behavior recorded.
- `UNVERIFIED — active TS-path empty-room false-positive rate under non-human movers`. Needed: recorded negative-control captures (fan, curtain, HVAC, empty room) replayed through the actual authority path. Relevant observation: in the replayed 29 MB live session, per-node `is_motion` was true for 33,321 of ~33,330 flags with only 3 transitions; without an empty-room capture it is impossible to distinguish "continuously occupied session" from "motion gate effectively always-on".
- `UNVERIFIED — whether NVS provisioning fully removes the sdkconfig credential dependency at runtime` (i.e., whether a board flashed with placeholder sdkconfig values and real NVS credentials joins Wi-Fi correctly). Needed: one build/flash cycle with sanitized sdkconfig and NVS-only credentials on real hardware.
- `UNVERIFIED — whether any external consumer still depends on the legacy 20-byte parser`. Needed: packet capture or deployment inventory showing live senders and their exact frame formats.
- `UNVERIFIED — whether any hidden or external code path parses superseded 28-byte/DataView framing`. Needed: full deployment inventory beyond this repository; I did not find such a parser in the checked-in code.

## 6. Appendix

### Commands Executed With Outputs (trimmed)

```powershell
Get-ChildItem -Force
```

Output:

```text
.git
.github
.venv
.vscode
client
data
docs
firmware
phantom
recordings
scripts
server
shared
tests
...
```

```powershell
rg --files
```

Output:

```text
Enumerated repository files for audit targeting.
```

```powershell
npm test   # re-run in the final audit session
```

Output (trimmed):

```text
✔ parseCsiPacket routes legacy packets after ADR-018 check
✔ SourcePinningGuard rejects same node id from a foreign source
✔ classifyPacketMagic distinguishes every known packet type
ℹ tests 99
ℹ pass 99
ℹ fail 0
ℹ duration_ms 7485.1494
```

```powershell
python -m pytest tests -q
```

Output:

```text
Python was resolved to the Windows Store shim and did not start successfully.
```

```powershell
& 'C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe' -m pytest tests -q   # re-run in the final audit session
```

Output:

```text
77 passed, 6 skipped in 40.15s
```

```powershell
git ls-files firmware/esp32-csi-node/sdkconfig firmware/esp32-csi-node/sdkconfig.defaults `
  firmware/esp32-csi-node/nvs_node1.bin firmware/esp32-csi-node/nvs_node2.bin firmware/esp32-csi-node/sdkconfig.old
git grep -n "Bmt#0987" -- ':!node_modules'
```

Output (trimmed; all five files tracked):

```text
firmware/esp32-csi-node/sdkconfig
firmware/esp32-csi-node/sdkconfig.defaults
firmware/esp32-csi-node/nvs_node1.bin
firmware/esp32-csi-node/nvs_node2.bin
firmware/esp32-csi-node/sdkconfig.old
Binary file firmware/esp32-csi-node/nvs_node1.bin matches
Binary file firmware/esp32-csi-node/nvs_node2.bin matches
firmware/esp32-csi-node/sdkconfig:604:CONFIG_CSI_WIFI_PASSWORD="..."
firmware/esp32-csi-node/sdkconfig.defaults:10:CONFIG_CSI_WIFI_PASSWORD="..."
firmware/esp32-csi-node/sdkconfig.old:538:CONFIG_CSI_WIFI_PASSWORD="..."
```

```powershell
python replay_audit.py "data\sessions\74b9bc7d51744175959d483941aa8e1a.jsonl"
```

Output:

```json
{
  "derived_frames": 76,
  "modes": { "degraded": 1, "fused": 75 },
  "balance_min": 0.35608159822697705,
  "balance_max": 0.630564091413417,
  "x_m_min": 1.7804079911348851,
  "x_m_max": 3.152820457067085,
  "is_motion_true": 147,
  "is_motion_transitions": 3,
  "invariant_violations": [],
  "violation_count": 0
}
```

```powershell
python replay_audit.py "data\sessions\ad3b220d21b84250951f12760c7020b6.jsonl" 50000
```

Output:

```json
{
  "derived_frames": 16665,
  "modes": { "degraded": 2, "fused": 16663 },
  "balance_min": 0.1981503854339553,
  "balance_max": 0.7457307964010479,
  "x_m_min": 0.9907519271697764,
  "x_m_max": 3.7286539820052393,
  "is_motion_true": 33321,
  "is_motion_transitions": 3,
  "invariant_violations": [],
  "violation_count": 0
}
```

Note: `x_m` spans `0.99–3.73` on a `0..5` axis — this replay confirms the superseded Python path still maps positions onto the stale 5 m node-1-origin axis (`PS-AUDIT-006`), while satisfying the balance/NaN/garbage-position invariants.

Representative search commands used during the audit:

```powershell
rg -n "5005|5006|8789|0xC5110001|0xC51100A1|SO_REUSEADDR|baseline_m: float = 5.0|BALANCE_CONTRAST_EXPONENT|s_presence_score = s_motion_energy" README.md server phantom firmware docs tests shared
```

```powershell
rg -n "api/esp32/configure|execute-task|wsRef\.current\.send" client/src/hooks/use-websocket.ts server/routes.ts tests/test_invariants.py
```

### Files Read

- `README.md`
- `package.json`
- `shared/schema.ts`
- `server/index.ts`
- `server/routes.ts`
- `server/lib/udp-server.ts`
- `server/lib/udp-server.test.ts`
- `server/lib/websocket.ts`
- `server/lib/node-fusion.ts`
- `server/auth/service.ts`
- `server/auth/service.test.ts`
- `server/audit/logger.ts`
- `phantom/protocol.py`
- `phantom/dsp.py`
- `phantom/ingest.py`
- `phantom/runtime.py`
- `phantom/api.py`
- `phantom/recording.py`
- `firmware/esp32-csi-node/main/csi_collector.h`
- `firmware/esp32-csi-node/main/csi_collector.c`
- `firmware/esp32-csi-node/main/stream_sender.c`
- `firmware/esp32-csi-node/main/edge_processing.h`
- `firmware/esp32-csi-node/main/edge_processing.c`
- `firmware/esp32-csi-node/main/main.c`
- `tests/test_udp_ad018.py`
- `tests/test_phantom_runtime.py`
- `tests/test_esp_capture_e2e.py`
- `tests/test_invariants.py`
- `tests/test_authority_api.py`
- `docs/WINDOWS_ESP32_SETUP.md`
- `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`
- `docs/ruview-2node-full-analysis-report.md`
- `firmware/esp32-csi-node/sdkconfig.defaults`
- `phantom/ai_status.py`
- `scripts/ai_inference.py` (WS emit path, fusion/advisory sections)
- `server/lib/target-state.ts` (verdict inputs)
- `DETECTION_REPORT.md` / `TEST_REPORT.md` (geometry claims)
- `ai model and densepose/model/README.md` (accuracy claims)
- `data/sessions/*.jsonl` (session headers and record format)

### Analysis Scripts Created

One read-only replay/invariant script, created OUTSIDE the repository (session scratchpad, not `audit_tmp/`, to keep the working tree untouched):

- `replay_audit.py` — loads `phantom.runtime.PhantomRuntime`, replays a JSONL session via `replay_file()` with recorder output redirected to a temp directory, and reports: derived-frame count, mode distribution, balance min/max, `x_m` min/max, NaN/Inf checks on `motion_energy`/`dynamic_mean`/`mean_amplitude`, `|x| > 1e6` garbage-position checks, and `is_motion` transition counts. Its two outputs are reproduced verbatim above. No repository file was modified by this audit other than this report.
