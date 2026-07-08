> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Real-Hardware Detection & Movement Test Report

Trial log for the two-node ESP32-S3 positional-fidelity campaign. One row per
real trial. Synthetic runs never go in this file.

Baseline geometry for all trials unless stated otherwise:

- `NODE_ANCHORS`: N1 = `(-1.5, 0)`, N2 = `(+1.5, 0)`
- `NODE_SEPARATION_M = 3`
- Room-frame origin = baseline midpoint
- Tape marks on the axis at `0.0 / 0.75 / 1.5 / 2.25 / 3.0 m` from N1

Record the exact runtime context per trial:

- `PHANTOM_MOTION_THRESHOLD`
- `PHANTOM_TREND_DEADBAND_MPS`
- firmware build / self-ping status
- per-node fps
- wall cell / thickness
- room geometry id

## P0 — Preflight

Preserve the original hardware sanity gate. Do not trust any later stage if the
ingest rate is broken.

| Date | Node 1 fps | Node 2 fps | self-ping @50Hz seen | fused_two_node available | Motion threshold | Trend deadband | Pass (fps ≥ 20 both) |
|------|-----------|-----------|----------------------|--------------------------|------------------|----------------|----------------------|
|      |           |           |                      |                          |                  |                |                      |

## S1 — Empty-Room Calibration + Soak

Preserve the existing calibration and soak structure verbatim in intent. This
stage establishes the empty-room baseline and confirms the detector stays quiet.

| Date | mean | sigma | max | k chosen | Threshold set | 10-min soak targets emitted (pass = 0) | Artifacts |
|------|------|-------|-----|----------|---------------|----------------------------------------|-----------|
|      |      |       |     |          |               |                                        |           |

## S2 — Negative Controls

Preserve the fan / curtain / AC control rows. These are still required evidence.

| Date | Control (fan/curtain/AC) | Position | Duration | Max motion observed | Targets emitted (pass = 0) | Artifacts |
|------|--------------------------|----------|----------|---------------------|----------------------------|-----------|
|      |                          |          |          |                     |                            |           |

## S3 — Presence and Static Dwells

Still person at known on-axis marks. This is the first stage that should be
fully computable from the enriched CSV without screenshot reconstruction.

| Date | Mark (m from N1) | Duration | Target visible | Displayed x (m) | Ground-truth x (m) | Error (m) | Breathing-only held? | GT source | Artifacts |
|------|------------------|----------|----------------|-----------------|--------------------|-----------|----------------------|-----------|-----------|
|      |                  |          |                |                 |                    |           |                      |           |           |

## S4 — On-Axis Walk Accuracy

Core positional-fidelity stage. Walk N1→N2→N1 at about `0.5 m/s`, three reps.
Use the enriched CSV for error calculations.

| Date | Rep | Mark / segment | Displayed x (m) | Ground-truth x (m) | On-axis error (m) | Displayed dN1 (m) | True dN1 (m) | dN1 error (m) | Balance monotonic on leg? | Artifacts |
|------|-----|----------------|-----------------|--------------------|-------------------|-------------------|--------------|---------------|---------------------------|-----------|
|      |     |                |                 |                    |                   |                   |              |               |                           |           |

Summary:

- mean on-axis error = ___ m
- max on-axis error = ___ m
- mean dN1 error = ___ m

## S5 — Trend / Direction

Validate the mirrored trend signal and turnaround latency.

| Date | Leg | `trend_n1` / `trend_n2` correct while walking | Flip latency at turnaround (s) | Toward approached node shown live | Artifacts |
|------|-----|-----------------------------------------------|--------------------------------|-----------------------------------|-----------|
|      |     |                                               |                                |                                   |           |

## S6 — Off-Axis Projection Mapping

Document the honest failure mode rather than hiding it. The target is still a
1-D baseline estimate, so off-axis subjects project onto the line.

| Date | Path (parallel / perpendicular / diagonal / arc) | True lateral offset (m) | Displayed projected x (m) | Notes on distortion | Artifacts |
|------|--------------------------------------------------|-------------------------|---------------------------|--------------------|-----------|
|      |                                                  |                         |                           |                    |           |

## S7 — Mirror / Symmetry Cases

Useful when two different room positions project to similar on-axis readings.

| Date | Scenario | Position A | Position B | Displayed overlap? | Notes | Artifacts |
|------|----------|------------|------------|--------------------|-------|-----------|
|      |          |            |            |                    |       |           |

## S8 — Robustness / Confounds

Documented behavior, not a blanket pass/fail bucket. Includes node dropout,
single-node fallback, two-person blends, and any operator-side ambiguity.

| Date | Scenario (dropout / single-node fallback / two people / off-axis mover) | Observed behavior | Ghost target? (dropout must be NO) | Caveat shown? | Artifacts |
|------|-------------------------------------------------------------------------|-------------------|------------------------------------|---------------|-----------|
|      |                                                                         |                   |                                    |               |           |

## Analysis Rules

- System-side quantities come from the live CSV alone.
- Ground-truth-joined quantities come from the enriched CSV produced by `scripts/join-groundtruth.ts`.
- `trend_n1` and `trend_n2` are one mirrored derivative signal, not two independent measurements.
- Raw CSV cadence is not the same as independent-sample cadence; decimate by effective node/window rate before confidence-interval work.

## Known Honest Limits

- Position is 1-D on the N1–N2 axis, not free room position.
- Front/back ambiguity remains in fused two-node mode.
- Off-axis subjects project onto the baseline and therefore read a distorted on-axis position.
- Single-node fallback is a different estimator, not a coarse version of fused mode.
- Two people or any competing strong mover blend into one target.
