# Negative-Control Session Checklist (Item 2)

Ready-to-run checklist for the real-hardware fan/curtain/HVAC/empty-room negative
control against the **live TS authority path** — the specific gap flagged
`[UNVERIFIED]` in `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md:439` and tracked as Item 2
of `PhantomScan_Research_Gap_Analysis.md`. This fills in `REAL_TEST_REPORT.md`'s
Stage S2 table, which exists but had no concrete device list/positions/durations.

**What this validates:** whether Item 1's classifier-corroboration gate
(`server/lib/node-fusion.ts` — `evaluateClassifierCorroboration`,
`fuseTwoNodeTarget`, `hasSingleNodePresenceEvidence`) reduces false triggers from
non-human movers on the path that actually drives the live dashboard, as opposed
to the firmware-only mitigation that already existed.

**Prior evidence (real, already recorded, predates Item 1):** three real sessions
already exist in `data/sessions/` from 2026-07-20/23:

| Session | Device | Ticks | target_visible=1 rate |
|---|---|---|---|
| `empty_room_fan_off_20260720_...csv` | fan OFF (true baseline) | 465 | 0.0% |
| `emty_room_with_fan_2026-07-23T12-10...csv` | fan ON | 1,455 | 11.8% |
| `emty_room_with_fan_2026-07-23T12-17...csv` | fan ON | 5,000 | 31.2% |

(Measured directly with `scripts/analyze_negative_control.py` against these real
files — see that script's own output for the exact numbers; do not requote these
from memory in a future report without re-running the script, in case the files
change.) These sessions **predate** Item 1 — they have no `classifier_corroboration`
column, so they prove the false-positive problem is real on the live path, but
cannot show whether Item 1's fix helps. That is what this checklist re-measures.

## Devices required

- [ ] Oscillating fan (the same one used in the 2026-07-23 sessions, if available —
      note make/model/speed setting if not, so results are comparable)
- [ ] Curtain/blind near an air vent or window (something that moves with airflow,
      not manually)
- [ ] HVAC vent actively blowing (or a space heater with a fan) within CSI range of
      at least one node
- [ ] A stopwatch/timer and this repo checked out with the current build running

## Positions

Use the same baseline geometry as `REAL_TEST_REPORT.md`: N1 = (-1.5, 0), N2 =
(+1.5, 0), 3 m separation. Place each device:
- [ ] At the room midpoint (0.0 m from N1 on-axis) — worst case, equidistant
- [ ] Near N1 (0.75 m from N1) — closest-approach worst case
- [ ] Off-axis, ~1.5 m perpendicular from the N1–N2 line — realistic placement

## Session procedure (repeat per device x per position = up to 9 runs)

1. Start the live server: `npm run dev` (per `RUN.md` — confirm `fused_two_node`
   mode is active and both nodes show `fps >= 20`, i.e. P0 preflight passing).
2. Confirm the room is otherwise empty (no humans, pets) for the full duration.
3. Start recording from the dashboard (or the `startRecording` WS message) with a
   session name that encodes device + position, e.g. `fan_midpoint`,
   `curtain_nearN1`, `hvac_offaxis`.
4. Turn the device on; let it run for **at least 5 minutes** (the 2026-07-23
   sessions ran 1,455-5,000 ticks at ~40 Hz aggregate ~= 35-125s — run *longer*
   than that this time so the sample is more statistically stable).
5. Stop recording. The CSV lands in `data/sessions/<name>_<timestamp>.csv`
   automatically (`server/lib/websocket.ts` `serializeToCSV`).
6. Record the exact runtime context in `REAL_TEST_REPORT.md`'s S2 table row for
   this run: date, device, position, duration, max motion observed (from the
   dashboard), targets emitted (should be 0 for a true pass), artifact filename.

## Analysis (after each run, or batch at the end)

```
python scripts/analyze_negative_control.py --device fan data/sessions/fan_midpoint_<timestamp>.csv
python scripts/analyze_negative_control.py --device fan --glob "data/sessions/fan_*.csv"
```

Read the script's output for:
- `target_visible=1` rate — the false-positive rate for this device/position.
- `classifier_corroboration` breakdown on visible ticks — a nonzero
  `contradicted` count here would itself be a bug (Item 1's gate should never let
  a confidently-mechanical tick through); the script flags this automatically as
  `[BUG SUSPECTED]`.
- `classifier_corroboration` breakdown on suppressed ticks — how many ticks the
  classifier actively vetoed vs. how many never cleared the energy gate at all.
  A high `contradicted` count among suppressed ticks is Item 1 directly working.

## Pass/fail

- **Pass (target)**: `target_visible=1` rate for every non-human device/position
  combination is 0%, or is meaningfully lower than the pre-Item-1 baseline above
  (11.8%/31.2% for the fan) with the reduction attributable to `contradicted`
  suppressions in the analysis output.
- **Still open even if this passes**: pets are the literature's documented hard
  case (see `PhantomScan_Research_Gap_Analysis.md` §3(a) citing the "Et Tu Alexa?"
  finding) — this checklist does not cover a pet negative control; add one if a
  pet will be present in the deployment environment.

## Status of this item until run

`[TO BE MEASURED]` — this checklist, the recording harness (Item 1's
`classifier_corroboration` column is now wired into
`server/lib/recording-export.ts`), and the analysis script
(`scripts/analyze_negative_control.py`) are ready. No one has run a *new* session
against the current (post-Item-1) build yet. Until then, do not claim the
false-positive rate has improved — only that the pre-Item-1 baseline is real and
measured, and the tooling to re-measure it post-fix is ready.
