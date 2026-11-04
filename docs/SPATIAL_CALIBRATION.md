# Spatial/DBSCAN Energy-Threshold Calibration (Item 4)

**Status: `[TO BE MEASURED]` — calibration logic and tooling are implemented and
unit-tested; the actual calibrated constant does not exist yet because no
calibrated empty-room capture has been run on real hardware.** Until that run
happens, the live threshold is unchanged from its historical hardcoded value.

## What this is

ADR-057 flagged that the spatial/tracking presence path has no calibrated
absolute noise floor:

- `TrackingProcessor`'s cluster gate was a hardcoded `maxEnergy > 10`
  (`server/lib/tracking.ts`) with no documented derivation.
- The MUSIC point-cloud cut (`pThreshold = maxPower - 10`,
  `server/lib/websocket.ts`) is relative-only — an empty room still has a max.

This mainly exposes **stationary-person detection** via spatial clustering; the
temporal `MotionGate` (auto-calibrated, `server/lib/signal-processing.ts`)
already covers moving targets.

## What changed (this session)

1. `server/lib/tracking.ts` — new pure `calibrateEnergyThreshold(samples, k)`
   (mean + k·σ over whatever samples it is given — a **provisional**,
   descriptive helper: it is not drift- or pooling-checked, and since PS-FIX-11
   `scripts/calibrate-threshold.ts` no longer derives the motion gate this way), plus `DEFAULT_SPATIAL_ENERGY_THRESHOLD`
   (env `PHANTOM_SPATIAL_ENERGY_THRESHOLD`, default **10 — identical to the old
   hardcoded literal**, so behavior is unchanged until an operator applies a
   real calibration). `TrackingProcessor` now accepts the threshold as a
   constructor parameter instead of a buried literal.
2. `scripts/calibrate-threshold.ts` — new `--spatial` flag: alongside the
   motion-gate calibration it samples per-packet total amplitude energy and
   prints a **provisional**, descriptive `PHANTOM_SPATIAL_ENERGY_THRESHOLD`
   suggestion (mean+3σ / mean+4σ over that one run). It is not drift- or
   pooling-checked: do not apply it from a single run.
3. `server/lib/tracking.test.ts` — unit tests for the calibration math
   (synthetic samples, clearly labeled) and regression tests pinning the
   default threshold to the historical value.

## What has NOT changed

- The live threshold value: still effectively `10` until someone runs the
  procedure below. No live behavior was altered using unvalidated data.
- The MUSIC point-cloud `pThreshold = maxPower - 10` relative cut is untouched —
  calibrating it requires the same real capture, and the point-cloud stage's
  angle output is synthetic-only on single-antenna hardware anyway (see
  `DETECTION_REPORT.md` single-antenna caveat), so the energy gate downstream
  of it (this calibration) is where an absolute floor helps presence evidence.

## Known limitation of the `--spatial` proxy

`--spatial` samples **per-packet total amplitude energy**, which is the closest
live-capturable proxy for the cluster energies the tracking gate sums, but it is
not identical to in-pipeline cluster energy (which depends on the MUSIC point
cloud and DBSCAN membership). Treat its suggestion as a starting point, then
validate behaviorally.

## Procedure (hardware session: hours, not minutes)

A 5-minute run cannot support a threshold. The committed 0.6 motion gate came from a
single 60 s empty recording, and recordings of the same empty room separate from each
other (symmetric AUC upper bounds 0.68–0.91 against a 0.65 limit, `reports/fix-2026-11/13-PS-FIX-11.md`).
The procedure below is **provisional** until it has been run; the resulting false-alarm
and detection figures stay `[TO BE MEASURED]`.

1. Stop the dashboard (the calibration tool must own UDP :5005).
2. Empty the room completely and keep an entry log (time, who, door). Collect an
   **empty soak of at least 60 minutes**, nodes not moved (add `--spatial` to also
   sample spatial energy):
   `npx tsx scripts/calibrate-threshold.ts --label empty --seconds 3600 --out .tmp/cal/empty1.json`
   Then, in the **same link state**, a **fan negative control of at least 5 minutes**
   (fan or other vibration source, no person):
   `npx tsx scripts/calibrate-threshold.ts --label fan --seconds 300 --out .tmp/cal/fan.json`
3. Evaluate offline (no socket):
   `npx tsx scripts/calibrate-threshold.ts --evaluate --empty .tmp/cal/empty1.json --fan .tmp/cal/fan.json`
   The tool refuses to print a candidate when the soak is too short, the negative
   control is missing, the runs span a link-state change, or the empty-vs-empty control
   shows drift. A refusal is a valid outcome. The spatial-energy figure is descriptive only.
4. Restart the dashboard with the candidate value:
   `PHANTOM_SPATIAL_ENERGY_THRESHOLD=<suggested> npm run dev`
5. Validate per ADR-057's own recommendation: leave the room empty >5 s in
   single-node mode and confirm the target clears; re-enter and confirm a real
   target still shows — **including surviving a few seconds of standing still**
   (the stationary-person case is the whole point of this calibration).
6. Run a fan negative control (docs/NEGATIVE_CONTROL_CHECKLIST.md) and confirm
   the fan does not produce sustained tracked clusters above the new floor.
7. Record the chosen value, date, and session artifacts here and in
   `REAL_TEST_REPORT.md` S1.

## Result log

| Date | Room/geometry | Samples | mean | sigma | k | Chosen threshold | Validated (empty-clear + still-person + fan)? | Artifacts |
|------|---------------|---------|------|-------|---|------------------|-----------------------------------------------|-----------|
|      |               |         |      |       |   | `[TO BE MEASURED]` |                                             |           |
