# Phantom Scan — Real Live Failure Analysis (2026-08-07)

Covers two tasks: (1) analyzing a real live target-marker failure on Thaer's actual two-node
ESP32 hardware, (2) tracing an unexplained UDP :5005 traffic pattern observed in this sandbox
during an earlier investigation. Both are reported here even though Task 1's evidence chain has
a real gap — see "Confidence and gaps" below before acting on the fix recommendation.

---

## Task 1 — Live target-marker failure

### What data was available

Thaer was asked (Step 1A) to capture a deliberate reproduction: start a case recording, keep
DevTools Console/Network open, reproduce the symptom, then send the session file, a console
export, a screenshot, and the exact time window. **That deliberate capture was not provided** —
no console log export, no screenshot, and no explicit confirmation of which session is the
repro.

However, a real ESP32 hardware session appeared in `data/sessions/` timestamped within this same
session window:

- `data/sessions/000000116 - 2026-08-07.json` / `000000115 - 2026-08-07.json` — the dashboard's
  own case export. `dataSource: "esp32"`, session `dsgdfsg`, 1292.5 s (~21.5 min), 22,585 frames,
  809 timeline events, classification 89.7% confidence `human`.
- `data/sessions/dsgdfsg_2026-08-07T17-27-22-007Z.csv/json/pdf` — a second export of the same
  session (same `session_name`/`recording_start_ms`) from a different reporting tool
  (`scripts/reporting/session_reporter.py`). The `.csv` is the valuable one: it has **per-tick
  `target_visible`, `target_state`, `motion_n1`, `motion_n2`** columns — 5,000 rows covering the
  first ~276 s of the real session (`session_ts_ms` runs 0 → 276,099).

Because this session is real ESP32 data, arrived at the right time, and its granular data shows
exactly the reported symptom (below), it is being treated as strong corroborating evidence — but
**it was not confirmed by Thaer as the deliberate repro**, so treat the root cause below as
well-evidenced but not hardware-confirmed. See "Confidence and gaps."

### What the data shows

From the 5,000-row CSV (`node_mode` is `fused_two_node` for all rows):

| `target_state` | rows | % | `target_visible` |
|---|---|---|---|
| `none` | 3,681 | 73.6% | false |
| `stale` | 1,143 | 22.9% | false |
| `moving` | 176 | 3.5% | true |

The on-screen target marker was only eligible to render **3.5% of the time**, across a session
the dashboard's own event timeline (`000000116 - 2026-08-07.json`) shows as continuous human
presence throughout — "Target started moving" at t=0.9s, "First classification: human" at t=3s,
and a steady stream of "Entered Close/Mid range" and "Position update" events every few seconds
for the full 21 minutes, with classification oscillating `human`/`mechanical` but never
disappearing from that log. That's the mismatch: the server's own summary shows a target was
tracked essentially the whole time, but the fine-grained `target_visible` flag — the thing that
actually gates the on-screen marker — was almost always false.

### Root cause (traced to the exact gate)

`target_visible` is set by [server/lib/target-state.ts:90](server/lib/target-state.ts#L90) /
[:146](server/lib/target-state.ts#L146) — true only when a `radialTarget` exists, i.e. only when
the presence/motion gate in `fuseTwoNodeTarget` fires. That gate is one line:
[server/lib/node-fusion.ts:346](server/lib/node-fusion.ts#L346):

```ts
return Math.max(input.motion1, input.motion2) >= threshold && r1 + r2 > EPS;
```

`threshold` defaults to `DEFAULT_MOTION_THRESHOLD = 0.6`
([node-fusion.ts:43](server/lib/node-fusion.ts#L43)), documented at
[node-fusion.ts:34-36](server/lib/node-fusion.ts#L34-L36) as calibrated 2026-07-20 against an
**empty-room baseline**: `max(motion1, motion2)` over 296 samples — mean 0.49, sigma 0.027, max
0.58. 0.6 was chosen as "just above that noise ceiling."

Measuring the same `motion1`/`motion2` quantity (`computeNodeMotionFromMatrix`'s `.motion` field,
already gain-normalized as `absStd/mean * 4`, clamped to 1 —
[node-fusion.ts:236](server/lib/node-fusion.ts#L236)) from this real session's CSV:

| `target_state` | motion_n1 avg | motion_n1 max | motion_n2 avg | motion_n2 max |
|---|---|---|---|---|
| `none` (gate never fired) | 0.403 | 0.595 | 0.314 | 0.398 |
| `stale` (gate fired once, then aged out) | 0.463 | 0.595 | 0.312 | 0.376 |
| `moving` (gate fired) | 0.581 | 0.735 | 0.298 | 0.338 |

Two things stand out:

1. **Even during confirmed motion, node1's signal barely clears the gate.** Average `motion1`
   during `moving` ticks is 0.581 — *below* the 0.6 threshold on average, only crossing it in
   43.2% of those ticks (the rest still render no marker despite the room-level event log saying
   a target was present and moving). During `none`/`stale`, `motion1` maxes out at 0.595 — a
   hair under the gate, essentially every tick.
2. **`motion2` never meaningfully contributes.** Its ceiling across the entire 5,000-row sample
   is 0.398, well under both the 0.6 threshold and even the empty-room noise ceiling (0.58) the
   threshold was calibrated against. In this room/hardware placement, node 2 is functionally
   inert for the presence gate; `max(motion1, motion2)` is really just `motion1` throughout.

**Conclusion:** this isn't a logic bug in the gate (`Math.max(...) >= threshold` is doing exactly
what it says) or a regression from the recent MUSIC/PS-BEHTEST-004 fixes (`motion1`/`motion2`
already use the same normalized-ratio form as the gain-normalized `r1`/`r2` balance inputs — no
missing normalization there, that hypothesis was checked and ruled out). It's a **calibration/
dynamic-range problem**: in this specific room and hardware placement, real human-motion signal
on node 1 sits in almost the same band (0.40–0.735) as the empty-room noise ceiling the 0.6
threshold was tuned against (max 0.58), so the gate only fires on the upper tail of real motion
instead of reliably. Node 2 is essentially not contributing at all here, so there's no fallback
node keeping the target visible when node 1 dips under threshold.

### Fix status: not applied

I'm not shipping a threshold change from this analysis alone, for two reasons specific to this
project:

- `DEFAULT_MOTION_THRESHOLD` is a **safety-calibrated constant** — the same comment block
  documents it was tuned specifically so a fan/curtain (the project's known false-positive risk,
  see `docs/NEGATIVE_CONTROL_CHECKLIST.md`) stays rejected. Lowering it blindly from a single
  session's data, without re-running the negative control, risks reopening that false-positive
  gap — exactly the kind of guess the F1/F2 invariants this project holds are meant to prevent.
- The proper re-calibration path already exists and is documented in the file itself:
  `scripts/calibrate-threshold.ts`. It must be run **against the real rig**, dashboard stopped
  (single owner of :5005) — an empty-room soak, then a fan-on-axis negative-control soak — and
  I have no hardware access in this sandbox to run it.

**Recommended next step for Thaer:** run
`npx tsx scripts/calibrate-threshold.ts --seconds 120` empty-room, then again with a fan on-axis,
per the script's own header instructions, and compare the suggested threshold against this
session's real motion distribution above. If the fan's max still stays safely below wherever the
new threshold lands, lower `PHANTOM_MOTION_THRESHOLD` (or the "Fused Target Presence Threshold"
UI slider) to that value. Separately, node 2's near-total non-contribution in this room is worth
a quick physical check (antenna orientation/placement relative to the sensing area) — even a
correctly-calibrated threshold won't help if node 2 structurally never sees usable motion here.

No regression test was added, since the fix itself (a recalibrated threshold, or a hardware
placement change) isn't something I can determine or validate from this sandbox — a test against
a specific threshold value would just encode a guess.

### Confidence and gaps

- **Not hardware-confirmed as the repro Thaer described.** The session data is consistent with
  "target marker mostly doesn't appear despite continuous real presence," but Thaer never
  explicitly said "yes, this is the run where I saw it fail" or gave a timestamp to anchor to.
- The `dsgdfsg_2026-08-07T17-27-22-007Z.json` summary (the `session_reporter.py` export) has an
  unrelated, separate bug worth flagging on its own: it reports `duration_s: 5.44` for the same
  5,000 rows that actually span 276.1 s of `session_ts_ms`, and every `event_timeline` entry has
  a garbled `elapsed_formatted` value (e.g. `"29738941202:19"`) and a nonsensical
  `total_distance_m: 1760.982` against `avg_speed_ms: 0.0064`. This looks like a units/field bug
  in `scripts/reporting/session_reporter.py` or `models.py`. It's cosmetic to this
  investigation (the CSV's raw per-tick data is unaffected and is what the analysis above used),
  but it's a real bug in its own right — not investigated further per staying focused on the
  marker issue; flagging for a separate pass if wanted.
- No raw UDP capture exists for this session, so end-to-end verification against wire packets
  wasn't possible — the analysis is entirely from the CSV's already-parsed `motion_n1`/
  `motion_n2`/`target_state` columns, one processing stage downstream of the raw radio data.

**MUSIC fix status: untouched, and not implicated.** Nothing in this trace touches
`computeMUSICSpectrum`/`powerIterationEigen` or the AoA/temporal-signature path — the failure is
fully explained by the presence/motion gate upstream of it.

---

## Task 2 — Ambient UDP :5005 traffic in this sandbox

Investigated separately (lower urgency, not blocking Task 1). Findings:

- **No rogue listener.** Exactly one process is bound to :5005 right now: the real dev server
  (`node ... server/index.ts`, reached via the normal `npm run dev` → `dev-full.cjs` chain). The
  server's own design makes a second listener impossible to add silently — it deliberately omits
  `SO_REUSEADDR` ([udp-server.ts:535-538](server/lib/udp-server.ts#L535-L538)) specifically so a
  conflicting bind fails loudly instead of stealing packets.
- **No stray Python ingest authority.** The only `python.exe` processes running are VS Code's
  `isort` language server — not a `phantom.runtime live` authority.
- **No synthetic-traffic generator currently running.** The only other relevant node processes
  are `chrome-devtools-mcp` instances left from an earlier browser-automation test session — not
  traffic generators. The large UDP replay from that earlier test has already exited.
- **The `/tmp/phantom-*` directories are a red herring**, fully explained:
  `phantom-bootstrap-*`, `phantom-behtest-*`, `phantom-audit-*`, and `phantom-seed-noise-*` are
  all tempdir fixtures created by `server/auth/service.test.ts` and `tests/behavioral/*.test.ts`
  — unrelated to CSI/UDP traffic.
- **Could not get a definitive packet-level capture.** `pktmon` (Windows' built-in capture tool)
  requires admin rights, which this sandbox denies. The one indirect signal gathered — a
  system-wide UDP receive-rate sample of ~103 datagrams/sec over 4 s — is not port-attributed
  (includes DNS/mDNS/telemetry/etc.) and isn't strong evidence either way.

**Leading hypothesis, not confirmed:** since no generator process exists now and the port design
rules out a silent second listener, the ~85 pkt/s traffic seen during the earlier staleness
investigation was most likely leftover buffered packets from that same session's 62,344-frame
real-time UDP replay (sent minutes earlier), still draining from the OS socket receive queue when
the fresh dev server's log was checked — not an independent, still-running source.

**Standing caveat for future sandbox "live" tests:** treat a few seconds of apparent "ambient"
traffic right after a large UDP replay in this sandbox as queue drain-off, not a new source,
unless it persists well past a reasonable drain window.
